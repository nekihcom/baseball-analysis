import re

from bs4 import Tag

from ama_baseball.parsers.common import ParseError, cell_text, make_soup, parse_table, require

TEAM_STATS_HEADERS = ("年", "試合", "勝ち", "負け", "引分", "勝率", "得点", "失点", "打率", "本塁打", "盗塁", "防御率")

_HIDDEN = re.compile(r"^(hit|at_bats|home_run|steal|earned_run|inning|part_of_inning)_\d{4}$")
_TOTAL_LABEL = "通算"
_NO_VALUE = "ー"


def parse_team_stats(html: str) -> list[dict[str, str]]:
    soup = make_soup(html)
    table = require(soup, ".teamStatsDetailContainer table.stats_batting")
    headers, rows = parse_table(table, TEAM_STATS_HEADERS)
    era_inning = _era_inning(soup)

    records = []
    totals: dict[str, int] = {}
    for cells in rows:
        record = {h: cell_text(c) for h, c in zip(headers, cells)}
        hidden = _hidden_values(cells)
        for name, value in hidden.items():
            totals[name] = totals.get(name, 0) + value

        if record.get("年") == _TOTAL_LABEL:
            _fill_totals(record, totals, era_inning)
        elif "防御率" in record and not record["防御率"] and "earned_run" in hidden:
            record["防御率"] = _era(hidden["earned_run"], hidden.get("inning", 0), hidden.get("part_of_inning", 0), era_inning)
        records.append(record)
    return records


# サイトは以下の値を HTML に含めず、hidden input から JS で計算して表示する。
# 空欄で保存すると分析に使えないため、サイトの JS と同じ式で補う。
def _fill_totals(record: dict[str, str], totals: dict[str, int], era_inning: int) -> None:
    if "打率" in record and not record["打率"]:
        record["打率"] = _batting_average(totals.get("hit", 0), totals.get("at_bats", 0))
    if "本塁打" in record and not record["本塁打"]:
        record["本塁打"] = str(totals.get("home_run", 0))
    if "盗塁" in record and not record["盗塁"]:
        record["盗塁"] = str(totals.get("steal", 0))
    if "防御率" in record and not record["防御率"]:
        record["防御率"] = _era(totals.get("earned_run", 0), totals.get("inning", 0), totals.get("part_of_inning", 0), era_inning)


def _era_inning(soup) -> int:
    element = soup.select_one('input[name="team_era_inning"]')
    if element is None:
        raise ParseError("防御率の計算に使うイニング数（team_era_inning）が見つかりません")
    return int(element.get("value", "0"))


def _hidden_values(cells: list[Tag]) -> dict[str, int]:
    values = {}
    for cell in cells:
        for element in cell.select('input[type="hidden"]'):
            match = _HIDDEN.match(element.get("name", ""))
            if match:
                values[match.group(1)] = int(element.get("value") or 0)
    return values


def _era(earned_run: int, inning: int, part_of_inning: int, era_inning: int) -> str:
    outs = 3 * inning + part_of_inning
    if outs == 0:
        return _NO_VALUE
    return f"{earned_run * era_inning * 3 / outs:.2f}"


def _batting_average(hit: int, at_bats: int) -> str:
    if hit == 0 or at_bats == 0:
        return ".000"
    return f"{hit / at_bats:.3f}".removeprefix("0")
