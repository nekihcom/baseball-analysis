from collections.abc import Callable
from dataclasses import dataclass, field

from ama_baseball import parsers
from ama_baseball.collectors import TeamCollector

TEAM = "チーム"
COLLECTED_AT = "収集日時"
YEAR = "年度"
COMMON_COLUMNS = (TEAM, COLLECTED_AT)

Row = dict[str, str]


@dataclass
class Table:
    columns: list[str] = field(default_factory=list)
    rows: list[Row] = field(default_factory=list)


@dataclass(frozen=True)
class DataDefinition:
    key: str
    sheet_name: str
    columns: tuple[str, ...]
    yearly: bool
    collect: Callable[[TeamCollector, list[int] | None], list[Row]]
    sort_rows: Callable[[list[Row]], list[Row]]

    @property
    def csv_name(self) -> str:
        return f"{self.key}.csv"

    @property
    def backup_csv_name(self) -> str:
        return f"{self.key}.bk.csv"

    @property
    def backup_sheet_name(self) -> str:
        return f"{self.sheet_name}（バックアップ）"


def _number_or_none(value: str) -> int | None:
    return int(value) if value.isdigit() else None


def _sort_by_date(rows: list[Row]) -> list[Row]:
    rows = sorted(rows, key=lambda r: r.get(TEAM, ""), reverse=True)
    return sorted(rows, key=lambda r: r.get("日時", ""))


def _sort_team_stats(rows: list[Row]) -> list[Row]:
    def key(row: Row):
        year = _number_or_none(row.get("年", ""))
        return (row.get(TEAM, ""), year is None, -(year or 0))

    return sorted(rows, key=key)


def _sort_year_stats(rows: list[Row]) -> list[Row]:
    def key(row: Row):
        year = _number_or_none(row.get(YEAR, ""))
        number = _number_or_none(row.get("背番号", ""))
        return (row.get(TEAM, ""), -(year or 0), number is None, number or 0)

    return sorted(rows, key=key)


DEFINITIONS: tuple[DataDefinition, ...] = (
    DataDefinition(
        key="schedule",
        sheet_name="スケジュール",
        columns=COMMON_COLUMNS + parsers.SCHEDULE_COLUMNS,
        yearly=False,
        collect=lambda tc, _: tc.schedule(),
        sort_rows=_sort_by_date,
    ),
    DataDefinition(
        key="game_results",
        sheet_name="試合結果",
        columns=COMMON_COLUMNS + parsers.GAME_RESULTS_COLUMNS,
        yearly=False,
        collect=lambda tc, _: tc.game_results(),
        sort_rows=_sort_by_date,
    ),
    DataDefinition(
        key="team_stats",
        sheet_name="チーム成績",
        columns=COMMON_COLUMNS + parsers.TEAM_STATS_HEADERS,
        yearly=False,
        collect=lambda tc, _: tc.team_stats(),
        sort_rows=_sort_team_stats,
    ),
    DataDefinition(
        key="batter_year_stats",
        sheet_name="打者年度別成績",
        columns=COMMON_COLUMNS + (YEAR, "背番号", "選手名") + parsers.BATTER_HEADERS[1:],
        yearly=True,
        collect=lambda tc, years: tc.batter_year_stats(years),
        sort_rows=_sort_year_stats,
    ),
    DataDefinition(
        key="pitcher_year_stats",
        sheet_name="投手年度別成績",
        columns=COMMON_COLUMNS + (YEAR, "背番号", "選手名") + parsers.PITCHER_HEADERS[1:],
        yearly=True,
        collect=lambda tc, years: tc.pitcher_year_stats(years),
        sort_rows=_sort_year_stats,
    ),
)
