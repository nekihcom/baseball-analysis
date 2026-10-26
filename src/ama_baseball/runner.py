import logging
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from ama_baseball.collectors import TeamCollector, decide_target_years
from ama_baseball.csv_io import write_csv
from ama_baseball.definitions import COLLECTED_AT, DEFINITIONS, TEAM, YEAR, DataDefinition, Row, Table
from ama_baseball.fetcher import Fetcher
from ama_baseball.merger import merge

logger = logging.getLogger(__name__)


class Store(Protocol):
    def read(self, sheet_name: str) -> Table | None: ...

    def replace(self, sheet_name: str, table: Table) -> None: ...


@dataclass
class Outcome:
    ok: bool
    detail: str

    def __str__(self) -> str:
        return f"{'OK' if self.ok else 'NG'}({self.detail})"


def run(
    teams: list[str],
    all_years: bool,
    store: Store,
    fetcher: Fetcher,
    data_dir: Path,
    started_at: datetime,
    definitions: tuple[DataDefinition, ...] = DEFINITIONS,
) -> int:
    collected_at = started_at.isoformat(timespec="seconds")
    logger.info("処理を開始します: チーム=%s 全年度=%s 収集日時=%s", ",".join(teams), all_years, collected_at)

    try:
        sheets = {d.key: store.read(d.sheet_name) for d in definitions}
    except Exception as e:
        logger.error("現行シートの読み込みに失敗したため中止します: %s: %s", type(e).__name__, e)
        return 1
    for d in definitions:
        logger.info("現行シート %s: %s", d.sheet_name, "なし" if sheets[d.key] is None else f"{len(sheets[d.key].rows)} 件")

    try:
        _backup(sheets, store, data_dir, definitions)
    except Exception as e:
        logger.error("バックアップに失敗したため中止します: %s: %s", type(e).__name__, e)
        return 1

    tables = {d.key: sheets[d.key] or Table(columns=list(d.columns)) for d in definitions}
    fetcher.load_robots()

    outcomes: dict[str, dict[str, Outcome]] = {}
    for team in teams:
        outcomes[team] = _collect_team(team, all_years, started_at.year, collected_at, fetcher, tables, definitions)

    write_failures = _write_all(tables, store, data_dir, definitions)

    for team, team_outcomes in outcomes.items():
        logger.info("[summary] %-10s %s", team, " ".join(f"{k}={o}" for k, o in team_outcomes.items()))
    for key, error in write_failures.items():
        logger.info("[summary] write      %s=NG(%s)", key, error)

    failed = write_failures or any(not o.ok for team_outcomes in outcomes.values() for o in team_outcomes.values())
    logger.info("処理を終了します: %s", "失敗あり" if failed else "すべて成功")
    return 1 if failed else 0


def _backup(sheets: dict[str, Table | None], store: Store, data_dir: Path, definitions) -> None:
    backup_dir = data_dir / "bks"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for d in definitions:
        table = sheets[d.key]
        if table is None:
            logger.info("現行シートが無いため %s のバックアップを作成しません", d.sheet_name)
            continue
        write_csv(backup_dir / d.backup_csv_name, table)
        store.replace(d.backup_sheet_name, table)
        logger.info("バックアップを作成しました: %s %d 件", d.backup_sheet_name, len(table.rows))


def _collect_team(team, all_years, current_year, collected_at, fetcher, tables, definitions) -> dict[str, Outcome]:
    logger.info("チーム %s の収集を開始します", team)
    outcomes: dict[str, Outcome] = {}
    try:
        collector = TeamCollector(fetcher, team)
        for d in definitions:
            try:
                outcomes[d.key] = _collect_data(team, all_years, current_year, collected_at, collector, tables, d)
            except Exception as e:
                logger.error("%s %s の収集に失敗しました: %s: %s", team, d.key, type(e).__name__, e)
                outcomes[d.key] = Outcome(False, _error_text(e))
    except Exception as e:
        logger.error("チーム %s の処理中に想定外のエラーが発生しました: %s: %s", team, type(e).__name__, e)
        for d in definitions:
            outcomes.setdefault(d.key, Outcome(False, _error_text(e)))
    return outcomes


def _collect_data(team, all_years, current_year, collected_at, collector, tables, d: DataDefinition) -> Outcome:
    years = None
    if d.yearly:
        has_rows = any(row.get(TEAM) == team for row in tables[d.key].rows)
        years = decide_target_years(collector.available_years(), has_rows, all_years, current_year)
        logger.info("%s %s の対象年度: %s", team, d.key, ", ".join(map(str, years)) or "なし")

    collected: list[Row] = [{TEAM: team, COLLECTED_AT: collected_at, **row} for row in d.collect(collector, years)]
    before = len(tables[d.key].rows)
    tables[d.key] = merge(tables[d.key], collected, team, years, d)
    logger.info("%s %s: 取得 %d 件、マージ前 %d 件 → マージ後 %d 件", team, d.key, len(collected), before, len(tables[d.key].rows))

    if years is None:
        return Outcome(True, str(len(collected)))
    counts = Counter(row[YEAR] for row in collected)
    return Outcome(True, ",".join(f"{y}:{counts.get(str(y), 0)}" for y in sorted(years, reverse=True)) or "-")


def _write_all(tables: dict[str, Table], store: Store, data_dir: Path, definitions) -> dict[str, str]:
    failures = {}
    for d in definitions:
        table = tables[d.key]
        try:
            write_csv(data_dir / d.csv_name, table)
            store.replace(d.sheet_name, table)
            logger.info("書き込みました: %s %d 件", d.sheet_name, len(table.rows))
        except Exception as e:
            logger.error("%s の書き込みに失敗しました: %s: %s", d.sheet_name, type(e).__name__, e)
            failures[d.key] = _error_text(e)
    return failures


def _error_text(error: Exception) -> str:
    return str(error) or type(error).__name__
