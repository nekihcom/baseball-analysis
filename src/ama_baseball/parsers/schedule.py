import re

from ama_baseball.parsers.common import ParseError, cell_text, make_soup, own_text, require, to_iso_date

SCHEDULE_COLUMNS = ("日時", "種別", "タイトル", "予定詳細ID")

_PLAN_ID = re.compile(r"/plan/(\d+)/?$")


def parse_schedule(html: str) -> list[dict[str, str]]:
    container = require(make_soup(html), "#future_plans")

    rows = []
    year = month = None
    for element in container.select("p.schedule-title, ul.schedule-list > li > a"):
        if element.name == "p":
            year = cell_text(element.select_one("span.year"))
            month = cell_text(element.select_one("span.month"))
            if not (year.isdigit() and month.isdigit()):
                raise ParseError(f"年月の見出しを読み取れません: {element.get_text(' ', strip=True)}")
            continue

        if year is None:
            raise ParseError("年月の見出しより前に予定があります")
        day = own_text(element.select_one("p.week-text"))
        if not day.isdigit():
            raise ParseError(f"予定の日を読み取れません: {day!r}")
        plan_id = _PLAN_ID.search(element.get("href", ""))
        if plan_id is None:
            raise ParseError(f"予定詳細IDを読み取れません: {element.get('href')!r}")
        rows.append(
            {
                "日時": to_iso_date(year, month, day),
                "種別": cell_text(element.select_one("p.category")),
                "タイトル": cell_text(element.select_one("p.schedule-text")),
                "予定詳細ID": plan_id.group(1),
            }
        )
    return rows
