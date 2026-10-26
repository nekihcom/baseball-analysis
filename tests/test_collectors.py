import pytest

from ama_baseball.collectors import BASE_URL, MAX_GAME_PAGES, CollectError, TeamCollector, decide_target_years
from ama_baseball.fetcher import FetchError
from fakes import FakeFetcher

GAME_URL = f"{BASE_URL}/orcas/game?page={{}}"


def _game_page(dates: list[str], has_next: bool, total: int | None = None) -> str:
    items = "".join(
        f'<li><a class="toDetailLink" href="/g"><p class="date">{d}</p><p class="opponent">A</p><p class="score">1-0</p></a></li>'
        for d in dates
    )
    pagination = ""
    if has_next or total is not None:
        next_link = '<a rel="next" href="/next">2</a>' if has_next else ""
        pagination = f'<div class="paginationContainer"><p>（全{total}件）</p>{next_link}</div>'
    return f'<div class="gameListContainer"><ul class="contentList">{items}</ul></div>{pagination}'


class TestDecideTargetYears:
    @pytest.mark.parametrize(
        ("has_rows", "all_years", "current_year", "expected"),
        [
            (True, True, 2026, [2024, 2025, 2026]),
            (False, False, 2026, [2024, 2025, 2026]),
            (True, False, 2026, [2026]),
            (True, False, 2027, []),
        ],
        ids=["全年度再取得の引数あり", "初回", "2回目以降", "当年度が取得可能年度に無い"],
    )
    def test_対象年度を決める(self, has_rows, all_years, current_year, expected):
        assert decide_target_years([2025, 2024, 2026], has_rows, all_years, current_year) == expected


class TestGameResults:
    def test_次ページがある間ページ送りする(self):
        fetcher = FakeFetcher(
            {
                GAME_URL.format(1): _game_page(["2026/1/1"], has_next=True, total=2),
                GAME_URL.format(2): _game_page(["2025/1/1"], has_next=False, total=2),
            }
        )

        rows = TeamCollector(fetcher, "orcas").game_results()

        assert [r["日時"] for r in rows] == ["2026-01-01", "2025-01-01"]
        assert fetcher.requested == [GAME_URL.format(1), GAME_URL.format(2)]

    def test_件数表示と一致しなければ警告する(self, caplog):
        fetcher = FakeFetcher({GAME_URL.format(1): _game_page(["2026/1/1"], has_next=False, total=5)})

        TeamCollector(fetcher, "orcas").game_results()

        assert "件数表示と一致しません" in caplog.text

    def test_ページ数が上限を超えたら失敗(self):
        pages = {GAME_URL.format(n): _game_page(["2026/1/1"], has_next=True) for n in range(1, MAX_GAME_PAGES + 2)}

        with pytest.raises(CollectError):
            TeamCollector(FakeFetcher(pages), "orcas").game_results()

    def test_途中のページで失敗したら全体を失敗にする(self):
        fetcher = FakeFetcher({GAME_URL.format(1): _game_page(["2026/1/1"], has_next=True)})

        with pytest.raises(FetchError):
            TeamCollector(fetcher, "orcas").game_results()


class TestYearStats:
    def test_年度ごとにURLを組み立て年度列を付与する(self, load_fixture):
        html = load_fixture("batters_2025.html")
        fetcher = FakeFetcher({})
        fetcher.get = lambda url: (fetcher.requested.append(url), html)[1]

        rows = TeamCollector(fetcher, "orcas").batter_year_stats([2024, 2025])

        assert fetcher.requested == [
            f"{BASE_URL}/orcas/stats/batters_table?search_result%5Bgame_date%5D={y}&search_result%5Bgame_type%5D="
            "&search_result%5Bopponent_team_name%5D=&search_result%5Btournament_name%5D="
            "&search_result%5Bis_walk_game%5D=&search_result%5Bunreached%5D=&search_result%5Bunreached%5D=true"
            for y in (2024, 2025)
        ]
        assert len(rows) == 30
        assert list(rows[0])[:3] == ["年度", "背番号", "選手名"]
        assert {r["年度"] for r in rows} == {"2024", "2025"}

    def test_取得可能年度はチームごとに1回だけ取得する(self, load_fixture):
        url = f"{BASE_URL}/orcas/stats/batters_table"
        fetcher = FakeFetcher({url: load_fixture("batters_default.html")})
        collector = TeamCollector(fetcher, "orcas")

        collector.available_years()
        collector.available_years()

        assert fetcher.requested == [url]

    def test_取得可能年度の取得失敗は再取得せず同じ失敗を返す(self):
        fetcher = FakeFetcher({})
        collector = TeamCollector(fetcher, "orcas")

        for _ in range(2):
            with pytest.raises(FetchError):
                collector.available_years()
        assert len(fetcher.requested) == 1
