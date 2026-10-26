import csv
from pathlib import Path

from ama_baseball.definitions import Table


def write_csv(path: Path, table: Table) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(table.columns)
        writer.writerows([row.get(c, "") for c in table.columns] for row in table.rows)
