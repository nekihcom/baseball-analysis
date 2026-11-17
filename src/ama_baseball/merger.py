from ama_baseball.definitions import COLLECTED_AT, TEAM, YEAR, DataDefinition, Row, Table


def merge(current: Table, collected: list[Row], team: str, years: list[int] | None, definition: DataDefinition) -> Table:
    target_years = None if years is None else {str(y) for y in years}

    def in_scope(row: Row) -> bool:
        if row.get(TEAM) != team:
            return False
        return target_years is None or row.get(YEAR) in target_years

    kept = [row for row in current.rows if not in_scope(row)]
    columns = _merge_columns(definition, current.columns, collected)
    rows = [{c: row.get(c, "") for c in columns} for row in kept + collected]
    return Table(columns=columns, rows=definition.sort_rows(rows))


def _merge_columns(definition: DataDefinition, current: list[str], collected: list[Row]) -> list[str]:
    columns = [c for c in definition.columns if c != COLLECTED_AT]
    excluded = {COLLECTED_AT, *definition.obsolete_columns}
    for column in [*current, *(c for row in collected for c in row)]:
        if column not in columns and column not in excluded:
            columns.append(column)
    return columns + [COLLECTED_AT]
