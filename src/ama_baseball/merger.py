from ama_baseball.definitions import TEAM, YEAR, DataDefinition, Row, Table


def merge(current: Table, collected: list[Row], team: str, years: list[int] | None, definition: DataDefinition) -> Table:
    target_years = None if years is None else {str(y) for y in years}

    def in_scope(row: Row) -> bool:
        if row.get(TEAM) != team:
            return False
        return target_years is None or row.get(YEAR) in target_years

    kept = [row for row in current.rows if not in_scope(row)]
    columns = _merge_columns(definition.columns, current.columns, collected)
    rows = [{c: row.get(c, "") for c in columns} for row in kept + collected]
    return Table(columns=columns, rows=definition.sort_rows(rows))


def _merge_columns(expected: tuple[str, ...], current: list[str], collected: list[Row]) -> list[str]:
    columns = list(expected)
    for column in [*current, *(c for row in collected for c in row)]:
        if column not in columns:
            columns.append(column)
    return columns
