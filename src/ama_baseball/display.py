from dataclasses import dataclass, field
from pathlib import Path

from ama_baseball.csv_io import read_csv
from ama_baseball.definitions import NUMBER, PLAYER_NAME, TEAM, Row, Table

TEAM_MASTER_CSV = "team_mst.csv"
PLAYER_MASTER_CSV = "player_mst.csv"


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
    rows = []
    for row in table.rows:
        converted = dict(row)
        if TEAM in row:
            converted[TEAM] = masters.team_labels.get(row[TEAM], "")
        if PLAYER_NAME in row:
            converted[PLAYER_NAME] = _player_name(row, masters)
        rows.append(converted)
    return Table(columns=list(table.columns), rows=rows)


def _player_name(row: Row, masters: Masters) -> str:
    return masters.player_names.get((row.get(TEAM, ""), row.get(NUMBER, "")), "")
