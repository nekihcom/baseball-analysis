import csv
from datetime import datetime, timedelta, timezone

from ama_baseball.collectors import BASE_URL
from ama_baseball.definitions import DEFINITIONS, Table
from ama_baseball.runner import run
from fakes import FakeFetcher, FakeStore

STARTED_AT = datetime(2026, 10, 26, 12, 0, 0, tzinfo=timezone(timedelta(hours=9)))
SCHEDULE = next(d for d in DEFINITIONS if d.key == "schedule")


def _orcas_pages(load_fixture) -> dict[str, str]:
    query = (
        "search_result%5Bgame_date%5D={}&search_result%5Bgame_type%5D=&search_result%5Bopponent_team_name%5D="
        "&search_result%5Btournament_name%5D=&search_result%5Bis_walk_game%5D=&search_result%5Bunreached%5D="
        "&search_result%5Bunreached%5D=true"
    )
    team_url = f"{BASE_URL}/orcas"
    pages = {
        f"{team_url}/plan": load_fixture("plan.html"),
        f"{team_url}/stats": load_fixture("stats.html"),
        f"{team_url}/stats/batters_table": load_fixture("batters_default.html"),
        f"{team_url}/game?page=1": load_fixture("game_page1.html"),
        f"{team_url}/game?page=2": load_fixture("game_page2.html").replace('rel="next"', ""),
    }
    for year in range(2022, 2027):
        pages[f"{team_url}/stats/batters_table?{query.format(year)}"] = load_fixture("batters_2025.html")
        pages[f"{team_url}/stats/pitchers_table?{query.format(year)}"] = load_fixture("pitchers_2025.html")
    return pages


def test_初回実行でシートとCSVを作成しバックアップは作らない(tmp_path, load_fixture):
    store = FakeStore()

    code = run(["orcas"], False, store, FakeFetcher(_orcas_pages(load_fixture)), tmp_path, STARTED_AT)

    assert set(store.sheets) == {d.sheet_name for d in DEFINITIONS}
    schedule = store.sheets["スケジュール"]
    assert schedule.columns == ["チーム", "収集日時", "日時", "種別", "タイトル", "予定詳細ID"]
    assert schedule.rows[0] == {
        "チーム": "orcas",
        "収集日時": "2026-10-26T12:00:00+09:00",
        "日時": "2026-11-08",
        "種別": "練習試合",
        "タイトル": "活動日",
        "予定詳細ID": "388787",
    }
    assert {r["年度"] for r in store.sheets["打者年度別成績"].rows} == {"2022", "2023", "2024", "2025", "2026"}
    with (tmp_path / "schedule.csv").open(encoding="utf-8", newline="") as f:
        assert list(csv.reader(f))[1] == ["orcas", "2026-10-26T12:00:00+09:00", "2026-11-08", "練習試合", "活動日", "388787"]
    assert list((tmp_path / "bks").iterdir()) == []
    assert code == 0


def test_既存シートをバックアップし失敗したデータは既存行を維持する(tmp_path, load_fixture):
    existing = Table(
        columns=list(SCHEDULE.columns),
        rows=[
            {"チーム": "orcas", "収集日時": "old", "日時": "2026-01-01", "種別": "", "タイトル": "旧", "予定詳細ID": "1"},
            {"チーム": "other", "収集日時": "old", "日時": "2026-01-02", "種別": "", "タイトル": "他", "予定詳細ID": "2"},
        ],
    )
    store = FakeStore({"スケジュール": existing})
    pages = _orcas_pages(load_fixture)
    del pages[f"{BASE_URL}/orcas/plan"]

    code = run(["orcas"], False, store, FakeFetcher(pages), tmp_path, STARTED_AT)

    assert code == 1
    assert store.sheets["スケジュール（バックアップ）"].rows == existing.rows
    assert (tmp_path / "bks" / "schedule.bk.csv").exists()
    assert [r["タイトル"] for r in store.sheets["スケジュール"].rows] == ["旧", "他"]
    assert "試合結果（バックアップ）" not in store.sheets


def test_1チームの失敗で他チームの処理を止めない(tmp_path, load_fixture):
    store = FakeStore()
    pages = _orcas_pages(load_fixture)

    run(["missing", "orcas"], False, store, FakeFetcher(pages), tmp_path, STARTED_AT)

    assert {r["チーム"] for r in store.sheets["スケジュール"].rows} == {"orcas"}


def test_バックアップの書き込みに失敗したら収集せず中止する(tmp_path, load_fixture):
    store = FakeStore({"スケジュール": Table(columns=list(SCHEDULE.columns))}, fail_on_replace={"スケジュール（バックアップ）"})
    fetcher = FakeFetcher(_orcas_pages(load_fixture))

    code = run(["orcas"], False, store, fetcher, tmp_path, STARTED_AT)

    assert code == 1
    assert fetcher.requested == []
    assert not (tmp_path / "schedule.csv").exists()

