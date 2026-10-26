import re

from ama_baseball.parsers.common import ParseError, cell_text, make_soup, parse_table, require

BATTER_HEADERS = (
    "背番号", "試合数", "打率", "打席", "打数", "安打", "本塁打", "打点", "得点", "盗塁", "出塁率", "長打率",
    "得点圏打率", "OPS", "二塁打", "三塁打", "塁打数", "三振", "四球", "死球", "犠打", "犠飛", "併殺打",
    "敵失", "失策", "盗塁死", "盗塁阻止",
)  # fmt: skip
PITCHER_HEADERS = (
    "背番号", "試合数", "勝", "ホールド", "セーブ", "敗", "勝率", "防御率", "投球回", "投球数", "失点",
    "自責点", "完投", "完封", "被安打", "被本塁打", "奪三振", "与四球", "与死球", "ボーク", "暴投",
)  # fmt: skip

_PLAYER = re.compile(r"^(\d+)\s*(.*)$")
_PLAYER_HEADER = "背番号"
_YEAR = re.compile(r"^\d{4}$")


def parse_batter_stats(html: str) -> list[dict[str, str]]:
    return _parse_player_stats(html, ".battingStatsDetailContainer table", BATTER_HEADERS)


def parse_pitcher_stats(html: str) -> list[dict[str, str]]:
    return _parse_player_stats(html, ".pitchingStatsDetailContainer table", PITCHER_HEADERS)


def parse_available_years(html: str) -> list[int]:
    select = require(make_soup(html), 'select[name="search_result[game_date]"]')
    return sorted({int(o.get("value")) for o in select.find_all("option") if _YEAR.match(o.get("value", ""))})


def _parse_player_stats(html: str, selector: str, expected: tuple[str, ...]) -> list[dict[str, str]]:
    table = require(make_soup(html), selector)
    headers, rows = parse_table(table, expected)
    if not headers or headers[0] != _PLAYER_HEADER:
        raise ParseError(f"先頭列が「{_PLAYER_HEADER}」ではありません: {headers[:1]}")

    records = []
    for cells in rows:
        player = cell_text(cells[0])
        match = _PLAYER.match(player)
        number, name = match.groups() if match else ("", player)
        record = {"背番号": number, "選手名": name.strip()}
        record.update({h: cell_text(c) for h, c in zip(headers[1:], cells[1:])})
        records.append(record)
    return records
