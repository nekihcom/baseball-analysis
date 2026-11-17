import csv
from datetime import datetime, timedelta, timezone

from ama_baseball.collectors import BASE_URL
from ama_baseball.csv_io import read_csv, write_csv
from ama_baseball.definitions import DEFINITIONS, Table
from ama_baseball.runner import run
from fakes import FakeFetcher, FakeStore

STARTED_AT = datetime(2026, 10, 26, 12, 0, 0, tzinfo=timezone(timedelta(hours=9)))
SCHEDULE = next(d for d in DEFINITIONS if d.key == "schedule")
BATTER = next(d for d in DEFINITIONS if d.key == "batter_year_stats")


def _write_masters(data_dir) -> None:
    write_csv(data_dir / "team_mst.csv", Table(columns=["チーム", "ラベル"], rows=[{"チーム": "orcas", "ラベル": "ORCAS"}]))
    write_csv(
        data_dir / "player_mst.csv",
        Table(columns=["チーム", "背番号", "名前"], rows=[{"チーム": "orcas", "背番号": "1", "名前": "マスタ名"}]),
    )


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


def test_初回実行でシートとCSVを作成する(tmp_path, load_fixture):
    _write_masters(tmp_path)
    store = FakeStore()

    code = run(["orcas"], False, store, FakeFetcher(_orcas_pages(load_fixture)), tmp_path, STARTED_AT)

    assert set(store.sheets) == {d.sheet_name for d in DEFINITIONS}
    schedule = store.sheets["スケジュール"]
    assert schedule.columns == ["チーム", "日時", "種別", "タイトル", "収集日時"]
    assert schedule.rows[0] == {
        "チーム": "ORCAS",
        "収集日時": "2026-10-26T12:00:00+09:00",
        "日時": "2026-11-08",
        "種別": "練習試合",
        "タイトル": "活動日",
    }
    assert {r["年度"] for r in store.sheets["打者年度別成績"].rows} == {"2022", "2023", "2024", "2025", "2026"}
    with (tmp_path / "schedule.csv").open(encoding="utf-8", newline="") as f:
        assert list(csv.reader(f))[:2] == [
            ["チーム", "日時", "種別", "タイトル", "収集日時"],
            ["orcas", "2026-11-08", "練習試合", "活動日", "2026-10-26T12:00:00+09:00"],
        ]
    assert code == 0


def test_失敗したデータは既存行を維持する(tmp_path, load_fixture):
    existing = Table(
        columns=list(SCHEDULE.columns),
        rows=[
            {"チーム": "orcas", "収集日時": "old", "日時": "2026-01-01", "種別": "", "タイトル": "旧"},
            {"チーム": "other", "収集日時": "old", "日時": "2026-01-02", "種別": "", "タイトル": "他"},
        ],
    )
    write_csv(tmp_path / "schedule.csv", existing)
    _write_masters(tmp_path)
    store = FakeStore()
    pages = _orcas_pages(load_fixture)
    del pages[f"{BASE_URL}/orcas/plan"]

    code = run(["orcas"], False, store, FakeFetcher(pages), tmp_path, STARTED_AT)

    assert code == 1
    assert [(r["チーム"], r["タイトル"]) for r in read_csv(tmp_path / "schedule.csv").rows] == [("orcas", "旧"), ("other", "他")]
    assert [r["タイトル"] for r in store.sheets["スケジュール"].rows] == ["旧", "他"]
    assert set(store.sheets) == {d.sheet_name for d in DEFINITIONS}
    assert not (tmp_path / "bks").exists()


def test_1チームの失敗で他チームの処理を止めない(tmp_path, load_fixture):
    store = FakeStore()
    pages = _orcas_pages(load_fixture)

    run(["missing", "orcas"], False, store, FakeFetcher(pages), tmp_path, STARTED_AT)

    assert {r["チーム"] for r in read_csv(tmp_path / "schedule.csv").rows} == {"orcas"}


def test_シートにはマスタで変換した値を出しCSVには元の値を残す(tmp_path, load_fixture):
    _write_masters(tmp_path)
    store = FakeStore()

    run(["orcas"], False, store, FakeFetcher(_orcas_pages(load_fixture)), tmp_path, STARTED_AT)

    csv_rows = read_csv(tmp_path / "batter_year_stats.csv").rows
    sheet_rows = store.sheets["打者年度別成績"].rows
    assert {r["チーム"] for r in csv_rows} == {"orcas"}
    assert {r["チーム"] for r in sheet_rows} == {"ORCAS"}
    pairs = {(c["背番号"], c["選手名"], s["選手名"]) for c, s in zip(csv_rows, sheet_rows)}
    assert all(sheet == ("マスタ名" if number == "1" else "") for number, _, sheet in pairs)
    assert all(original != "" for _, original, _ in pairs)


def test_2回目の実行は前回のCSVを現行データとして当年度のみ置き換える(tmp_path, load_fixture):
    _write_masters(tmp_path)
    pages = _orcas_pages(load_fixture)
    run(["orcas"], False, FakeStore(), FakeFetcher(pages), tmp_path, STARTED_AT)
    fetcher = FakeFetcher(pages)

    run(["orcas"], False, FakeStore(), fetcher, tmp_path, STARTED_AT)

    batter_requests = [u for u in fetcher.requested if "batters_table?" in u]
    assert len(batter_requests) == 1
    assert "game_date%5D=2026" in batter_requests[0]
    assert {r["年度"] for r in read_csv(tmp_path / "batter_year_stats.csv").rows} == {"2022", "2023", "2024", "2025", "2026"}


def test_背番号と選手名が空欄の行はCSVにもシートにも出力しない(tmp_path, load_fixture):
    _write_masters(tmp_path)
    existing = Table(
        columns=list(BATTER.columns),
        rows=[
            {"チーム": "other", "年度": "2025", "背番号": "", "選手名": "ぎり"},
            {"チーム": "other", "年度": "2025", "背番号": "8", "選手名": "はやと"},
        ],
    )
    write_csv(tmp_path / "batter_year_stats.csv", existing)
    store = FakeStore()

    run(["orcas"], False, store, FakeFetcher(_orcas_pages(load_fixture)), tmp_path, STARTED_AT)

    csv_others = [r for r in read_csv(tmp_path / "batter_year_stats.csv").rows if r["チーム"] == "other"]
    assert [r["選手名"] for r in csv_others] == ["はやと"]
    assert all(r["背番号"] != "" for r in store.sheets["打者年度別成績"].rows)
    assert len(store.sheets["打者年度別成績"].rows) == len(read_csv(tmp_path / "batter_year_stats.csv").rows)
