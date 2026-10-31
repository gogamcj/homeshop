"""등록된 어댑터로 편성표를 모아 DB에 저장한다."""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import date

from . import adapters as adapter_registry
from . import db
from .fetcher import PoliteFetcher, RobotsDisallowed

log = logging.getLogger(__name__)


@dataclass
class CollectResult:
    saved: dict[str, int] = field(default_factory=dict)
    skipped: dict[str, str] = field(default_factory=dict)


def collect(
    conn: sqlite3.Connection,
    day: date,
    codes: list[str] | None = None,
    fetcher: PoliteFetcher | None = None,
) -> CollectResult:
    fetcher = fetcher or PoliteFetcher()
    result = CollectResult()
    for code in codes or adapter_registry.registered_codes():
        cls = adapter_registry.get_adapter(code)
        if cls is None:
            result.skipped[code] = "어댑터 없음"
            continue
        try:
            items = cls(fetcher).fetch_schedule(day)
        except RobotsDisallowed as e:
            result.skipped[code] = f"robots.txt 금지: {e}"
            continue
        except Exception as e:  # 한 채널 실패가 전체를 멈추지 않도록
            log.exception("수집 실패: %s", code)
            result.skipped[code] = f"오류: {e}"
            continue
        result.saved[code] = db.upsert_broadcasts(conn, items)
    return result
