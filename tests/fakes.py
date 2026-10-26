from ama_baseball.definitions import Table
from ama_baseball.fetcher import FetchError


class FakeFetcher:
    def __init__(self, pages: dict[str, str]):
        self.pages = pages
        self.requested: list[str] = []

    def load_robots(self) -> None:
        pass

    def get(self, url: str) -> str:
        self.requested.append(url)
        if url not in self.pages:
            raise FetchError(f"HTTP 404: {url}")
        return self.pages[url]


class FakeStore:
    def __init__(self, sheets: dict[str, Table] | None = None, fail_on_replace: set[str] | None = None):
        self.sheets = dict(sheets or {})
        self.fail_on_replace = fail_on_replace or set()

    def read(self, sheet_name: str) -> Table | None:
        return self.sheets.get(sheet_name)

    def replace(self, sheet_name: str, table: Table) -> None:
        if sheet_name in self.fail_on_replace:
            raise RuntimeError(f"書き込み失敗: {sheet_name}")
        self.sheets[sheet_name] = Table(columns=list(table.columns), rows=[dict(r) for r in table.rows])
