import logging
import time
from collections.abc import Callable
from urllib.robotparser import RobotFileParser

import requests

from ama_baseball import __version__

logger = logging.getLogger(__name__)

REPOSITORY_URL = "https://github.com/nekihcom/baseball-analysis"
USER_AGENT = f"ama-baseball-collector/{__version__} (+{REPOSITORY_URL})"
ROBOTS_URL = "https://teams.one/robots.txt"


class FetchError(Exception):
    pass


class Fetcher:
    def __init__(
        self,
        session: requests.Session | None = None,
        interval: float = 1.0,
        retry_waits: tuple[float, ...] = (5, 10, 20),
        timeout: float = 30,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._session = session or requests.Session()
        self._session.headers["User-Agent"] = USER_AGENT
        self._interval = interval
        self._retry_waits = retry_waits
        self._timeout = timeout
        self._sleep = sleep
        self._clock = clock
        self._last_finished: float | None = None
        self._robots: RobotFileParser | None = None

    def load_robots(self) -> None:
        try:
            text = self._request(ROBOTS_URL)
        except FetchError as e:
            logger.warning("robots.txt を取得できないため、確認せずに続行します: %s", e)
            return
        robots = RobotFileParser()
        robots.parse(text.splitlines())
        self._robots = robots

    def get(self, url: str) -> str:
        if self._robots is not None and not self._robots.can_fetch(USER_AGENT, url):
            raise FetchError(f"robots.txt で禁止されています: {url}")
        return self._request(url)

    def _request(self, url: str) -> str:
        attempts = len(self._retry_waits) + 1
        for attempt in range(attempts):
            self._wait_interval()
            try:
                response = self._session.get(url, timeout=self._timeout)
            except (requests.Timeout, requests.ConnectionError) as e:
                error = f"{type(e).__name__}: {e}"
                logger.info("GET %s -> %s", url, type(e).__name__)
            else:
                logger.info("GET %s -> %s", url, response.status_code)
                if response.status_code < 400:
                    response.encoding = response.encoding or "utf-8"
                    return response.text
                if response.status_code < 500:
                    raise FetchError(f"HTTP {response.status_code}: {url}")
                error = f"HTTP {response.status_code}"
            finally:
                self._last_finished = self._clock()

            if attempt < attempts - 1:
                wait = self._retry_waits[attempt]
                logger.warning("再試行します（%d/%d 回目、%s 秒後）: %s %s", attempt + 1, len(self._retry_waits), wait, url, error)
                self._sleep(wait)
        raise FetchError(f"{error}: {url}")

    def _wait_interval(self) -> None:
        if self._last_finished is None:
            return
        remaining = self._last_finished + self._interval - self._clock()
        if remaining > 0:
            self._sleep(remaining)
