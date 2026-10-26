import logging

from ama_baseball import parsers
from ama_baseball.fetcher import Fetcher

logger = logging.getLogger(__name__)

BASE_URL = "https://teams.one/teams"
MAX_GAME_PAGES = 100
_YEAR_QUERY = (
    "search_result%5Bgame_date%5D={year}&search_result%5Bgame_type%5D=&search_result%5Bopponent_team_name%5D="
    "&search_result%5Btournament_name%5D=&search_result%5Bis_walk_game%5D=&search_result%5Bunreached%5D="
    "&search_result%5Bunreached%5D=true"
)


class CollectError(Exception):
    pass


def decide_target_years(available: list[int], has_existing_rows: bool, all_years: bool, current_year: int) -> list[int]:
    if all_years or not has_existing_rows:
        return sorted(available)
    return [current_year] if current_year in available else []


class TeamCollector:
    def __init__(self, fetcher: Fetcher, team: str):
        self._fetcher = fetcher
        self._team = team
        self._available_years: list[int] | None = None
        self._available_years_error: Exception | None = None

    def schedule(self) -> list[dict[str, str]]:
        return parsers.parse_schedule(self._fetcher.get(f"{BASE_URL}/{self._team}/plan"))

    def game_results(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        total = None
        for page_number in range(1, MAX_GAME_PAGES + 1):
            page = parsers.parse_game_results(self._fetcher.get(f"{BASE_URL}/{self._team}/game?page={page_number}"))
            rows.extend(page.rows)
            total = page.total if page.total is not None else total
            if not page.has_next:
                break
        else:
            raise CollectError(f"試合結果のページ数が上限（{MAX_GAME_PAGES}）を超えました")

        if total is not None and total != len(rows):
            logger.warning("試合結果の件数が件数表示と一致しません: 表示 %d 件、取得 %d 件", total, len(rows))
        return rows

    def team_stats(self) -> list[dict[str, str]]:
        return parsers.parse_team_stats(self._fetcher.get(f"{BASE_URL}/{self._team}/stats"))

    def available_years(self) -> list[int]:
        if self._available_years_error is not None:
            raise self._available_years_error
        if self._available_years is None:
            try:
                html = self._fetcher.get(f"{BASE_URL}/{self._team}/stats/batters_table")
                self._available_years = parsers.parse_available_years(html)
            except Exception as e:
                self._available_years_error = e
                raise
        return self._available_years

    def batter_year_stats(self, years: list[int]) -> list[dict[str, str]]:
        return self._year_stats("batters_table", parsers.parse_batter_stats, years)

    def pitcher_year_stats(self, years: list[int]) -> list[dict[str, str]]:
        return self._year_stats("pitchers_table", parsers.parse_pitcher_stats, years)

    def _year_stats(self, page: str, parse, years: list[int]) -> list[dict[str, str]]:
        rows = []
        for year in years:
            html = self._fetcher.get(f"{BASE_URL}/{self._team}/stats/{page}?{_YEAR_QUERY.format(year=year)}")
            rows.extend({"年度": str(year), **row} for row in parse(html))
        return rows
