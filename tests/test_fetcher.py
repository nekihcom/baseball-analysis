import pytest
import requests

from ama_baseball.fetcher import USER_AGENT, FetchError, Fetcher


class FakeResponse:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text
        self.encoding = "utf-8"


class FakeSession:
    def __init__(self, results: list):
        self.results = list(results)
        self.headers: dict[str, str] = {}
        self.calls: list[tuple[str, float]] = []

    def get(self, url: str, timeout: float):
        self.calls.append((url, timeout))
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def __call__(self) -> float:
        return self.now


def _fetcher(results: list) -> tuple[Fetcher, FakeSession, FakeClock]:
    session = FakeSession(results)
    clock = FakeClock()
    return Fetcher(session=session, sleep=clock.sleep, clock=clock), session, clock


def test_User_Agentとタイムアウトを設定して取得する():
    fetcher, session, _ = _fetcher([FakeResponse(200, "ok")])

    assert fetcher.get("https://teams.one/a") == "ok"
    assert session.headers["User-Agent"] == USER_AGENT
    assert session.calls == [("https://teams.one/a", 30)]


def test_前回の完了から1秒以上空けて次を送る():
    fetcher, _, clock = _fetcher([FakeResponse(200), FakeResponse(200)])

    fetcher.get("https://teams.one/a")
    clock.now += 0.3
    fetcher.get("https://teams.one/b")

    assert clock.sleeps == [pytest.approx(0.7)]


@pytest.mark.parametrize(
    "error",
    [requests.Timeout("t"), requests.ConnectionError("c"), FakeResponse(503)],
    ids=["タイムアウト", "接続エラー", "HTTP 5xx"],
)
def test_一時的なエラーは5_10_20秒待って最大3回再試行する(error):
    fetcher, session, clock = _fetcher([error, error, error, FakeResponse(200, "ok")])

    assert fetcher.get("https://teams.one/a") == "ok"
    assert len(session.calls) == 4
    assert clock.sleeps == [5, 10, 20]


def test_再試行しても失敗すれば失敗にする():
    fetcher, session, _ = _fetcher([FakeResponse(500)] * 4)

    with pytest.raises(FetchError, match="HTTP 500"):
        fetcher.get("https://teams.one/a")
    assert len(session.calls) == 4


def test_HTTP_4xxは再試行せず失敗にする():
    fetcher, session, clock = _fetcher([FakeResponse(404)])

    with pytest.raises(FetchError, match="HTTP 404"):
        fetcher.get("https://teams.one/a")
    assert len(session.calls) == 1
    assert clock.sleeps == []


def test_robots_txtで禁止されたURLは取得しない():
    fetcher, session, _ = _fetcher([FakeResponse(200, "User-agent: *\nDisallow: /secret\n")])
    fetcher.load_robots()

    with pytest.raises(FetchError, match="robots.txt"):
        fetcher.get("https://teams.one/secret/a")
    assert len(session.calls) == 1


def test_robots_txtを取得できなければ警告して続行する(caplog):
    fetcher, _, _ = _fetcher([FakeResponse(404), FakeResponse(200, "ok")])

    fetcher.load_robots()

    assert "robots.txt を取得できない" in caplog.text
    assert fetcher.get("https://teams.one/a") == "ok"
