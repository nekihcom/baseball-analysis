from ama_baseball.definitions import DEFINITIONS, Table
from ama_baseball.merger import merge

DEFS = {d.key: d for d in DEFINITIONS}


def _batter(team: str, year: str, number: str, games: str = "1") -> dict[str, str]:
    return {"チーム": team, "収集日時": "t", "年度": year, "背番号": number, "選手名": "x", "試合数": games}


class TestReplaceScope:
    def test_年度別成績は当該チームの対象年度の行だけを置き換える(self):
        d = DEFS["batter_year_stats"]
        current = Table(
            columns=list(d.columns),
            rows=[_batter("orcas", "2025", "1"), _batter("orcas", "2026", "1"), _batter("other", "2026", "1")],
        )

        merged = merge(current, [_batter("orcas", "2026", "1", games="9")], "orcas", [2026], d)

        values = {(r["チーム"], r["年度"], r["試合数"]) for r in merged.rows}
        assert values == {("orcas", "2025", "1"), ("orcas", "2026", "9"), ("other", "2026", "1")}

    def test_年度別成績で対象年度が無ければ既存行を変えない(self):
        d = DEFS["batter_year_stats"]
        current = Table(columns=list(d.columns), rows=[_batter("orcas", "2025", "1")])

        merged = merge(current, [], "orcas", [], d)

        assert [r["年度"] for r in merged.rows] == ["2025"]

    def test_年度別でないデータは当該チームの全行を置き換える(self):
        d = DEFS["schedule"]
        current = Table(
            columns=list(d.columns),
            rows=[
                {"チーム": "orcas", "日時": "2026-01-01", "予定詳細ID": "1"},
                {"チーム": "orcas", "日時": "2026-02-01", "予定詳細ID": "2"},
                {"チーム": "other", "日時": "2026-01-01", "予定詳細ID": "3"},
            ],
        )

        merged = merge(current, [{"チーム": "orcas", "日時": "2026-03-01", "予定詳細ID": "4"}], "orcas", None, d)

        assert sorted(r["予定詳細ID"] for r in merged.rows) == ["3", "4"]


class TestColumns:
    def test_列の和集合を想定列を先にして並べ空欄を埋める(self):
        d = DEFS["schedule"]
        current = Table(columns=[*d.columns, "旧列"], rows=[{"チーム": "other", "日時": "2026-01-01", "旧列": "a"}])

        merged = merge(current, [{"チーム": "orcas", "日時": "2026-01-02", "新列": "b"}], "orcas", None, d)

        assert merged.columns == [*d.columns, "旧列", "新列"]
        assert merged.rows[0]["新列"] == ""
        assert merged.rows[1]["旧列"] == ""


class TestSort:
    def test_スケジュールは日時昇順_チーム降順(self):
        d = DEFS["schedule"]
        rows = [
            {"チーム": "a", "日時": "2026-01-02"},
            {"チーム": "a", "日時": "2026-01-01"},
            {"チーム": "b", "日時": "2026-01-01"},
        ]

        merged = merge(Table(columns=list(d.columns)), rows, "x", None, d)

        assert [(r["日時"], r["チーム"]) for r in merged.rows] == [
            ("2026-01-01", "b"),
            ("2026-01-01", "a"),
            ("2026-01-02", "a"),
        ]

    def test_チーム成績はチーム昇順_年降順_通算は末尾(self):
        d = DEFS["team_stats"]
        rows = [{"チーム": t, "年": y} for t, y in [("b", "2025"), ("a", "通算"), ("a", "2025"), ("a", "2026")]]

        merged = merge(Table(columns=list(d.columns)), rows, "x", None, d)

        assert [(r["チーム"], r["年"]) for r in merged.rows] == [("a", "2026"), ("a", "2025"), ("a", "通算"), ("b", "2025")]

    def test_年度別成績はチーム昇順_年度降順_背番号を数値で昇順(self):
        d = DEFS["pitcher_year_stats"]
        rows = [_batter("a", "2025", "2"), _batter("a", "2026", "10"), _batter("a", "2026", "9"), _batter("a", "2026", "")]

        merged = merge(Table(columns=list(d.columns)), rows, "x", [], d)

        assert [(r["年度"], r["背番号"]) for r in merged.rows] == [("2026", "9"), ("2026", "10"), ("2026", ""), ("2025", "2")]
