"""도메인 모델."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Channel:
    code: str
    name: str
    kind: str  # "HS"(TV홈쇼핑), "TC"(T커머스), "LIVE"(라이브커머스)
    homepage: str = ""


@dataclass
class Broadcast:
    """편성표의 방송 1건 (한 방송에 상품이 여럿이면 상품별로 1건)."""

    channel_code: str
    start_at: datetime
    end_at: datetime | None
    title: str
    product_name: str = ""
    brand: str = ""
    category: str = ""
    price: int | None = None  # 원
    product_url: str = ""
    external_id: str = ""  # 채널이 부여한 상품/방송 ID
    extra: dict = field(default_factory=dict)

    @property
    def duration_min(self) -> int | None:
        if self.end_at is None:
            return None
        return int((self.end_at - self.start_at).total_seconds() // 60)
