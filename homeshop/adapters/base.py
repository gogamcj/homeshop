from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from ..fetcher import PoliteFetcher
from ..models import Broadcast


class ChannelAdapter(ABC):
    """채널 1개의 편성표를 가져와 Broadcast 목록으로 바꾼다."""

    channel_code: str = ""

    def __init__(self, fetcher: PoliteFetcher):
        self.fetcher = fetcher

    @abstractmethod
    def schedule_url(self, day: date) -> str:
        """해당 날짜 편성표 URL."""

    @abstractmethod
    def parse(self, body: str, day: date) -> list[Broadcast]:
        """응답 본문을 방송 목록으로 바꾼다. 네트워크를 쓰지 않는 순수 함수여야 한다."""

    def fetch_schedule(self, day: date) -> list[Broadcast]:
        resp = self.fetcher.get(self.schedule_url(day))
        return self.parse(resp.text, day)
