import csv
from pathlib import Path

from ama_baseball.definitions import Table


def read_csv(path: Path) -> Table | None:
    if not path.is_file():
        return None
    with path.open(encoding="utf-8", newline="") as f:
        values = list(csv.reader(f))
    if not values:
        return Table()
    header, *body = values
    rows = [dict(zip(header, line + [""] * (len(header) - len(line)))) for line in body]
    return Table(columns=header, rows=rows)


def write_csv(path: Path, table: Table) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(table.columns)
        writer.writerows([row.get(c, "") for c in table.columns] for row in table.rows)
