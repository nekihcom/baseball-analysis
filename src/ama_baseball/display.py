import re
from dataclasses import dataclass, field
from pathlib import Path

from ama_baseball.csv_io import read_csv
from ama_baseball.definitions import NUMBER, PLAYER_NAME, TEAM, Row, Table

TEAM_MASTER_CSV = "team_mst.csv"
PLAYER_MASTER_CSV = "player_mst.csv"

STRIKEOUT_RATE = "奪三振率"
WHIP = "WHIP"
# 一般的な 9 イニング換算ではなく、利用者の指定により 7 イニング換算とする
STRIKEOUT_RATE_INNINGS = 7
_INNINGS = re.compile(r"^(\d+)回([0-2])/3$")
_NO_VALUE = "ー"


@dataclass
class Masters:
    team_labels: dict[str, str] = field(default_factory=dict)
    player_names: dict[tuple[str, str], str] = field(default_factory=dict)


def load_masters(data_dir: Path) -> tuple[Masters, list[str]]:
    masters = Masters()
    missing = []
    teams = read_csv(data_dir / TEAM_MASTER_CSV)
    if teams is None:
        missing.append(TEAM_MASTER_CSV)
    else:
        masters.team_labels = {row[TEAM]: row["ラベル"] for row in teams.rows}
    players = read_csv(data_dir / PLAYER_MASTER_CSV)
    if players is None:
        missing.append(PLAYER_MASTER_CSV)
    else:
        masters.player_names = {(row[TEAM], row[NUMBER]): row["名前"] for row in players.rows}
    return masters, missing


def drop_unidentified(table: Table, masters: Masters) -> Table:
    if PLAYER_NAME not in table.columns:
        return table
    rows = [row for row in table.rows if row.get(NUMBER, "") or _player_name(row, masters)]
    return Table(columns=list(table.columns), rows=rows)


def to_sheet(table: Table, masters: Masters) -> Table:
    columns = list(table.columns)
    pitching = {"投球回", "奪三振", "被安打", "与四球", "与死球"} <= set(columns)
    if pitching:
        columns.insert(columns.index("奪三振") + 1, STRIKEOUT_RATE)
        columns.insert(columns.index("与死球") + 1, WHIP)

    rows = []
    for row in table.rows:
        converted = dict(row)
        if TEAM in row:
            converted[TEAM] = masters.team_labels.get(row[TEAM], "")
        if PLAYER_NAME in row:
            converted[PLAYER_NAME] = _player_name(row, masters)
        if pitching:
            converted[STRIKEOUT_RATE] = _per_inning(row, ("奪三振",), STRIKEOUT_RATE_INNINGS, 2)
            converted[WHIP] = _per_inning(row, ("被安打", "与四球"), 1, 3)
        rows.append(converted)
    return Table(columns=columns, rows=rows)


def _per_inning(row: Row, counts: tuple[str, ...], innings: int, digits: int) -> str:
    match = _INNINGS.match(row.get("投球回", ""))
    values = [row.get(c, "") for c in counts]
    if match is None or not all(v.isdigit() for v in values):
        return ""
    outs = 3 * int(match.group(1)) + int(match.group(2))
    if outs == 0:
        return _NO_VALUE
    return f"{sum(int(v) for v in values) * innings * 3 / outs:.{digits}f}"


def _player_name(row: Row, masters: Masters) -> str:
    return masters.player_names.get((row.get(TEAM, ""), row.get(NUMBER, "")), "")
