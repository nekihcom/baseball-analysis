import logging

import pytest

from ama_baseball.parsers import (
    ParseError,
    parse_available_years,
    parse_batter_stats,
    parse_game_results,
    parse_pitcher_stats,
    parse_schedule,
    parse_team_stats,
)


class TestSchedule:
    def test_予定を年月見出しと日から日付にして取り出す(self, load_fixture):
        rows = parse_schedule(load_fixture("plan.html"))

        assert len(rows) == 3
        assert rows[0] == {"日時": "2026-11-08", "種別": "練習試合", "タイトル": "活動日", "予定詳細ID": "388787"}
        assert rows[2] == {"日時": "2026-12-13", "種別": "練習試合", "タイトル": "仮・活動日", "予定詳細ID": "388789"}

    def test_予定が無いページは0件(self):
        assert parse_schedule('<div id="future_plans"><div class="planLists"></div></div>') == []

    def test_コンテナ要素が無いページは解析失敗(self):
        with pytest.raises(ParseError):
            parse_schedule("<html><body><p>メンテナンス中</p></body></html>")

    def test_見出しより前の予定は解析失敗(self):
        html = '<div id="future_plans"><ul class="schedule-list"><li><a href="/teams/x/plan/1"><p class="week-text">1</p></a></li></ul></div>'
        with pytest.raises(ParseError):
            parse_schedule(html)


class TestGameResults:
    def test_試合を取り出しサヨナラを分離する(self, load_fixture):
        page = parse_game_results(load_fixture("game_page1.html"))

        assert len(page.rows) == 20
        assert page.rows[0] == {
            "日時": "2026-10-11",
            "試合属性": "練習試合",
            "対戦チーム": "Keriers/ケリアーズ",
            "スコア": "6-9",
            "サヨナラ": "TRUE",
            "勝敗": "勝ち",
        }
        assert page.rows[-1]["日時"] == "2024-09-29"
        assert page.rows[-1]["サヨナラ"] == "FALSE"

    def test_次ページの有無と件数表示を読み取る(self, load_fixture):
        page = parse_game_results(load_fixture("game_page2.html"))

        assert page.has_next is True
        assert page.total == 47

    def test_ページ送りが無ければ次ページなし(self):
        page = parse_game_results('<div class="gameListContainer"><ul class="contentList"></ul></div>')

        assert page.rows == []
        assert page.has_next is False
        assert page.total is None

    def test_一覧が無いページは解析失敗(self):
        with pytest.raises(ParseError):
            parse_game_results("<html></html>")


class TestTeamStats:
    def test_年度行と通算行を取り出す(self, load_fixture):
        rows = parse_team_stats(load_fixture("stats.html"))

        assert [r["年"] for r in rows] == ["2026", "2025", "2024", "2023", "2022", "通算"]
        assert rows[0]["勝率"] == ".500"
        assert rows[0]["打率"] == ".338"

    def test_年度行の防御率をhidden値から計算する(self, load_fixture):
        rows = parse_team_stats(load_fixture("stats.html"))

        assert rows[0]["防御率"] == "0.88"

    def test_通算行の空欄をhidden値の合計から計算する(self, load_fixture):
        total = parse_team_stats(load_fixture("stats.html"))[-1]

        assert total["試合"] == "47"
        assert total["打率"] == ".250"
        assert total["本塁打"] == "16"
        assert total["盗塁"] == "80"
        assert total["防御率"] == "3.50"

    def test_投球回が0なら防御率はー(self):
        html = """
        <div class="teamStatsDetailContainer"><table class="stats_batting"><thead><tr><th>年</th><th>防御率
        <input type="hidden" name="team_era_inning" value="7"></th></tr></thead><tbody>
        <tr><td>2026</td><td><input type="hidden" name="earned_run_2026" value="0">
        <input type="hidden" name="inning_2026" value="0"><input type="hidden" name="part_of_inning_2026" value="0"></td></tr>
        </tbody></table></div>"""

        assert parse_team_stats(html)[0]["防御率"] == "ー"

    def test_表が無いページは解析失敗(self):
        with pytest.raises(ParseError):
            parse_team_stats("<html></html>")


class TestPlayerStats:
    def test_打者の背番号と選手名を分割する(self, load_fixture):
        rows = parse_batter_stats(load_fixture("batters_2025.html"))

        assert len(rows) == 15
        assert rows[0]["背番号"] == "3"
        assert rows[0]["選手名"] == "大ちゃん"
        assert rows[0]["打率"] == ".294"
        assert rows[0]["OPS"] == ".898"

    def test_投手成績を取り出す(self, load_fixture):
        rows = parse_pitcher_stats(load_fixture("pitchers_2025.html"))

        assert len(rows) == 6
        assert rows[1] == {
            "背番号": "17", "選手名": "関端(B…", "試合数": "3", "勝": "2", "ホールド": "0", "セーブ": "0",
            "敗": "0", "勝率": "1.000", "防御率": "0.00", "投球回": "8回0/3", "投球数": "102", "失点": "1",
            "自責点": "0", "完投": "0", "完封": "0", "被安打": "4", "被本塁打": "0", "奪三振": "12",
            "与四球": "2", "与死球": "0", "ボーク": "0", "暴投": "1",
        }  # fmt: skip

    def test_背番号が無い選手は背番号を空欄にする(self):
        html = _player_table(["背番号", "試合数"], [["もっちー", "3"]])

        assert parse_batter_stats(html) == [{"背番号": "", "選手名": "もっちー", "試合数": "3"}]

    def test_列の増減を警告し想定外の列も取り込む(self, caplog):
        html = _player_table(["背番号", "試合数", "新指標"], [["13 もっちー", "3", "1.5"]])

        with caplog.at_level(logging.WARNING):
            rows = parse_batter_stats(html)

        assert rows[0]["新指標"] == "1.5"
        assert "想定外の列があります: 新指標" in caplog.text
        assert "想定列がありません: 打率" in caplog.text

    def test_表が無いページは解析失敗(self):
        with pytest.raises(ParseError):
            parse_batter_stats('<div class="battingStatsDetailContainer"></div>')

    def test_年度選択肢から4桁の年だけを集める(self, load_fixture):
        assert parse_available_years(load_fixture("batters_default.html")) == [2022, 2023, 2024, 2025, 2026]


def _player_table(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th><p>{h}</p></th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f'<div class="battingStatsDetailContainer"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'
