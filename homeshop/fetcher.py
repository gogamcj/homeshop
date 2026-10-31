"""예의 바른 HTTP 수집기.

- 요청 전에 robots.txt를 확인하고, 금지된 경로는 요청하지 않는다.
- 호스트마다 최소 요청 간격을 지킨다.
- 로그인 우회나 차단 회피는 하지 않는다.
"""
from __future__ import annotations

import time
import urllib.robotparser
from urllib.parse import urlsplit

import httpx

DEFAULT_UA = "homeshop-collector/0.1 (+https://github.com/gogamcj/homeshop)"


class RobotsDisallowed(Exception):
    pass


class PoliteFetcher:
    def __init__(
        self,
        user_agent: str = DEFAULT_UA,
        min_interval: float = 3.0,
        timeout: float = 20.0,
        client: httpx.Client | None = None,
        sleep=time.sleep,
        clock=time.monotonic,
    ):
        self.user_agent = user_agent
        self.min_interval = min_interval
        self.client = client or httpx.Client(
            timeout=timeout, headers={"User-Agent": user_agent}, follow_redirects=True
        )
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._last: dict[str, float] = {}
        self._sleep = sleep
        self._clock = clock

    def _robots_for(self, url: str) -> urllib.robotparser.RobotFileParser:
        parts = urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        if base not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                resp = self._request(base + "/robots.txt", check_robots=False)
                if resp.status_code >= 400:
                    # robots.txt가 없으면(4xx) 전체 허용으로 본다. 5xx는 아래에서 처리.
                    rp.parse([] if resp.status_code < 500 else ["User-agent: *", "Disallow: /"])
                else:
                    rp.parse(resp.text.splitlines())
            except httpx.HTTPError:
                # 확인할 수 없으면 보수적으로 금지
                rp.parse(["User-agent: *", "Disallow: /"])
            self._robots[base] = rp
        return self._robots[base]

    def allowed(self, url: str) -> bool:
        return self._robots_for(url).can_fetch(self.user_agent, url)

    def _throttle(self, host: str) -> None:
        last = self._last.get(host)
        if last is not None:
            wait = self.min_interval - (self._clock() - last)
            if wait > 0:
                self._sleep(wait)
        self._last[host] = self._clock()

    def _request(self, url: str, check_robots: bool = True, **kw) -> httpx.Response:
        if check_robots and not self.allowed(url):
            raise RobotsDisallowed(url)
        self._throttle(urlsplit(url).netloc)
        return self.client.get(url, **kw)

    def get(self, url: str, **kw) -> httpx.Response:
        resp = self._request(url, **kw)
        resp.raise_for_status()
        return resp
