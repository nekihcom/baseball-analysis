import logging
import re

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


class ParseError(Exception):
    pass


def make_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def require(root: BeautifulSoup | Tag, selector: str) -> Tag:
    element = root.select_one(selector)
    if element is None:
        raise ParseError(f"要素が見つかりません: {selector}")
    return element


def normalize_header(text: str) -> str:
    return re.sub(r"\s+", "", text)


def cell_text(element: Tag | None) -> str:
    if element is None:
        return ""
    return element.get_text(strip=True)


def own_text(element: Tag | None) -> str:
    if element is None:
        return ""
    return "".join(s for s in element.find_all(string=True, recursive=False)).strip()


def parse_table(table: Tag, expected_headers: tuple[str, ...]) -> tuple[list[str], list[list[Tag]]]:
    head_row = table.select_one("thead tr")
    if head_row is None:
        raise ParseError("表のヘッダ行が見つかりません")
    headers = [normalize_header(th.get_text()) for th in head_row.find_all("th")]
    check_headers(headers, expected_headers)

    rows = []
    for tr in table.select("tbody > tr"):
        cells = tr.find_all("td", recursive=False)
        if len(cells) != len(headers):
            raise ParseError(f"列数がヘッダと一致しません: ヘッダ {len(headers)} 列、行 {len(cells)} 列")
        rows.append(cells)
    return headers, rows


def check_headers(headers: list[str], expected: tuple[str, ...]) -> None:
    unexpected = [h for h in headers if h not in expected]
    missing = [h for h in expected if h not in headers]
    if unexpected:
        logger.warning("想定外の列があります: %s", ", ".join(unexpected))
    if missing:
        logger.warning("想定列がありません: %s", ", ".join(missing))


def to_iso_date(year: int | str, month: int | str, day: int | str) -> str:
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
