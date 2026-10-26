import re
from dataclasses import dataclass

from ama_baseball.parsers.common import ParseError, cell_text, make_soup, own_text, require, to_iso_date

_DATE = re.compile(r"(\d{4})/(\d{1,2})/(\d{1,2})")
_TOTAL = re.compile(r"全\s*(\d+)\s*件")


@dataclass
class GamePage:
    rows: list[dict[str, str]]
    has_next: bool
    total: int | None


def parse_game_results(html: str) -> GamePage:
    soup = make_soup(html)
    game_list = require(soup, ".gameListContainer ul.contentList")

    rows = []
    for link in game_list.select("li > a.toDetailLink"):
        date_text = own_text(link.select_one("p.date"))
        date = _DATE.search(date_text)
        if date is None:
            raise ParseError(f"試合日を読み取れません: {date_text!r}")
        opponent = link.select_one("p.opponent")
        score = cell_text(link.select_one("p.score"))
        walk_off = score.endswith("x")
        rows.append(
            {
                "日時": to_iso_date(*date.groups()),
                "試合属性": cell_text(opponent.select_one("span.label") if opponent else None),
                "対戦チーム": own_text(opponent),
                "スコア": score.removesuffix("x"),
                "サヨナラ": "TRUE" if walk_off else "FALSE",
                "勝敗": cell_text(link.select_one("p.result")),
            }
        )

    pagination = soup.select_one(".paginationContainer")
    has_next = pagination is not None and pagination.select_one('a[rel="next"]') is not None
    total = None
    if pagination is not None:
        match = _TOTAL.search(pagination.get_text())
        if match:
            total = int(match.group(1))
    return GamePage(rows=rows, has_next=has_next, total=total)
