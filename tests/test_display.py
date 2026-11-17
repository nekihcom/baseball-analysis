from ama_baseball.csv_io import write_csv
from ama_baseball.definitions import Table
from ama_baseball.display import Masters, drop_unidentified, load_masters, to_sheet

MASTERS = Masters(team_labels={"orcas": "ORCAS"}, player_names={("orcas", "1"): "田中"})


def _batter(team: str, number: str, name: str) -> dict[str, str]:
    return {"チーム": team, "年度": "2026", "背番号": number, "選手名": name}


def test_チーム列をラベルに変換する():
    table = Table(columns=["チーム", "日時"], rows=[{"チーム": "orcas", "日時": "2026-11-08"}])

    converted = to_sheet(table, MASTERS)

    assert converted.columns == ["チーム", "日時"]
    assert converted.rows == [{"チーム": "ORCAS", "日時": "2026-11-08"}]


def test_選手名列を変換前のチームと背番号で引き当てる():
    table = Table(columns=["チーム", "年度", "背番号", "選手名"], rows=[_batter("orcas", "1", "たなか")])

    converted = to_sheet(table, MASTERS)

    assert converted.rows == [_batter("ORCAS", "1", "田中")]


def test_マスタに無いチームと選手は空欄にする():
    table = Table(
        columns=["チーム", "年度", "背番号", "選手名"],
        rows=[_batter("other", "1", "たなか"), _batter("orcas", "99", "だれか")],
    )

    converted = to_sheet(table, MASTERS)

    assert converted.rows == [_batter("", "1", ""), _batter("ORCAS", "99", "")]


def test_変換元のテーブルを変更しない():
    table = Table(columns=["チーム", "年度", "背番号", "選手名"], rows=[_batter("orcas", "1", "たなか")])

    to_sheet(table, MASTERS)

    assert table.rows == [_batter("orcas", "1", "たなか")]


def test_マスタCSVを読み込む(tmp_path):
    write_csv(tmp_path / "team_mst.csv", Table(columns=["チーム", "ラベル"], rows=[{"チーム": "orcas", "ラベル": "ORCAS"}]))
    write_csv(
        tmp_path / "player_mst.csv",
        Table(columns=["チーム", "背番号", "名前"], rows=[{"チーム": "orcas", "背番号": "1", "名前": "田中"}]),
    )

    masters, missing = load_masters(tmp_path)

    assert masters == MASTERS
    assert missing == []


def test_マスタCSVが無ければ空のマスタとして扱う(tmp_path):
    masters, missing = load_masters(tmp_path)

    assert masters == Masters()
    assert missing == ["team_mst.csv", "player_mst.csv"]


def test_背番号が空欄でマスタの選手名も引けない行を除外する():
    table = Table(
        columns=["チーム", "年度", "背番号", "選手名"],
        rows=[_batter("orcas", "1", "たなか"), _batter("orcas", "", "ぎり"), _batter("orcas", "99", "だれか")],
    )

    kept = drop_unidentified(table, MASTERS)

    assert kept.rows == [_batter("orcas", "1", "たなか"), _batter("orcas", "99", "だれか")]


def test_背番号が空欄でもマスタで選手名を引ければ残す():
    masters = Masters(player_names={("orcas", ""): "背番号なし"})
    table = Table(columns=["チーム", "年度", "背番号", "選手名"], rows=[_batter("orcas", "", "ぎり")])

    assert drop_unidentified(table, masters).rows == table.rows


def test_選手名列を持たないテーブルは除外しない():
    table = Table(columns=["チーム", "背番号"], rows=[{"チーム": "orcas", "背番号": ""}])

    assert drop_unidentified(table, MASTERS).rows == table.rows
