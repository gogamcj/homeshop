"""CSV로 편성표를 가져온다. 제휴로 받은 편성 데이터나 수기 정리본을 넣을 때 쓴다.

필수 열: channel_code, start_at, title
선택 열: end_at, product_name, brand, category, price, product_url, external_id
날짜 형식: 2026-10-31 20:40 또는 2026-10-31T20:40
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from .channels import BY_CODE
from .models import Broadcast

REQUIRED = ("channel_code", "start_at", "title")


class ImportError_(ValueError):
    pass


def _dt(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    return datetime.fromisoformat(value.replace(" ", "T", 1))


def _price(value: str) -> int | None:
    value = (value or "").replace(",", "").replace("원", "").strip()
    return int(value) if value else None


def read_csv(path: str | Path) -> list[Broadcast]:
    items: list[Broadcast] = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
        if missing:
            raise ImportError_(f"필수 열이 없습니다: {', '.join(missing)}")
        for line_no, row in enumerate(reader, start=2):
            code = row["channel_code"].strip()
            if code not in BY_CODE:
                raise ImportError_(f"{line_no}행: 알 수 없는 채널 코드 '{code}'")
            try:
                start = _dt(row["start_at"])
                end = _dt(row.get("end_at", ""))
                price = _price(row.get("price", ""))
            except ValueError as e:
                raise ImportError_(f"{line_no}행: {e}") from e
            if start is None:
                raise ImportError_(f"{line_no}행: start_at이 비어 있습니다")
            items.append(
                Broadcast(
                    channel_code=code,
                    start_at=start,
                    end_at=end,
                    title=row["title"].strip(),
                    product_name=(row.get("product_name") or "").strip(),
                    brand=(row.get("brand") or "").strip(),
                    category=(row.get("category") or "").strip(),
                    price=price,
                    product_url=(row.get("product_url") or "").strip(),
                    external_id=(row.get("external_id") or "").strip(),
                )
            )
    return items
