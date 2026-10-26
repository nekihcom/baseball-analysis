import gspread
from google.oauth2.service_account import Credentials
from gspread.utils import ValueInputOption

from ama_baseball.definitions import Table

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetStore:
    def __init__(self, spreadsheet_id: str, credentials_path: str):
        credentials = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
        self._book = gspread.authorize(credentials).open_by_key(spreadsheet_id)

    def read(self, sheet_name: str) -> Table | None:
        try:
            worksheet = self._book.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            return None
        values = worksheet.get_all_values()
        if not values:
            return Table()
        header, *body = values
        rows = [dict(zip(header, line + [""] * (len(header) - len(line)))) for line in body]
        return Table(columns=header, rows=rows)

    def replace(self, sheet_name: str, table: Table) -> None:
        values = [table.columns] + [[row.get(c, "") for c in table.columns] for row in table.rows]
        row_count = max(len(values), 1)
        col_count = max(len(table.columns), 1)
        try:
            worksheet = self._book.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            worksheet = self._book.add_worksheet(title=sheet_name, rows=row_count, cols=col_count)
        worksheet.clear()
        worksheet.resize(rows=row_count, cols=col_count)
        # USER_ENTERED だと ".500" が数値、"2026-10-11" が日付に変換され、次回読み込み時に CSV と一致しなくなる
        worksheet.update(values=values, range_name="A1", value_input_option=ValueInputOption.raw)
