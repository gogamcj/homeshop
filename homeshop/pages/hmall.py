"""현대홈쇼핑(현대Hmall) 편성표 저장 페이지.

현대홈쇼핑은 robots.txt가 일반 수집기를 막고 있어, 사용자가 브라우저로 저장한 페이지만 읽는다.
CSS 클래스 이름은 빌드마다 바뀌므로 data-* 속성과 aria-label만 사용한다.

  - 상단 시간표: button[data-timeline-id="etv-{편성번호}-{YYYYMMDDHHMMSS}"], aria-label="HH:MM 브랜드"
    → 그날 전체 방송의 시작 시각·브랜드·대표 상품코드(썸네일 파일명)
  - 방송 상세: section[data-schedule-id=...] 안의 .compound-product-item[data-slitm-cd]
    → 상품명·가격. 화면에 그려진 방송만 들어 있다(스크롤한 구간).
"""
from __future__ import annotations

import re
from datetime import datetime

from bs4 import BeautifulSoup, Tag

from ..models import Broadcast
from . import register_page

ITEM_URL = "https://www.hmall.com/md/pda/itemPtc?slitmCd={}"
CHANNELS = {"etv": "hmall", "dtv": "hmallplus"}  # TV쇼핑 / 플러스샵
_ID = re.compile(r"^(?P<ch>[a-z]+)-(?P<pgm>\d+)-(?P<dtm>\d{14})$")
_SLITM = re.compile(r"(\d{10})(?:_\d+)?\.(?:jpe?g|png|gif|webp)", re.I)


def _money(el: Tag | None) -> int | None:
    if el is None:
        return None
    d = re.sub(r"[^\d]", "", el.get_text())
    return int(d) if d else None


def _product(el: Tag) -> dict:
    title = el.select_one(".compound-title")
    brand_el = title.find("span") if title else None
    img = el.find("img", alt=True)
    name = img["alt"].strip() if img else (title.get_text(" ", strip=True) if title else "")
    sale = el.select_one('[aria-label="할인가"]')
    regular = el.select_one('[aria-label="정상가"]')
    alarm = el.select_one("a[data-slitm-cd] em")
    return {
        "id": el["data-slitm-cd"],
        "name": name,
        "brand": brand_el.get_text(strip=True) if brand_el else "",
        "price": _money(sale) or _money(regular),
        "list_price": _money(regular),
        "alarm_count": _money(alarm),
    }


@register_page("hmall", ["www.hmall.com", "hmall.com", "m.hmall.com"])
def parse(html: str) -> list[Broadcast]:
    soup = BeautifulSoup(html, "html.parser")

    # 1) 상단 시간표: 그날 전체 방송
    slots: dict[str, dict] = {}
    for b in soup.select("button[data-timeline-id]"):
        m = _ID.match(b["data-timeline-id"])
        if not m or m["ch"] not in CHANNELS:
            continue
        label = (b.get("aria-label") or "").split(" ", 1)
        img = b.find("img")
        sm = _SLITM.search(img.get("src", "")) if img else None
        slots[b["data-timeline-id"]] = {
            "channel": CHANNELS[m["ch"]],
            "start": datetime.strptime(m["dtm"], "%Y%m%d%H%M%S"),
            "brand": label[1].strip() if len(label) > 1 else "",
            "products": [{"id": sm.group(1), "name": "", "brand": "", "price": None,
                          "list_price": None, "alarm_count": None}] if sm else [],
        }

    # 2) 화면에 그려진 방송 상세로 상품 정보 채우기
    for sec in soup.select("section[data-schedule-id]"):
        sid = sec["data-schedule-id"]
        m = _ID.match(sid)
        if not m or m["ch"] not in CHANNELS:
            continue
        products = [_product(p) for p in sec.select(".compound-product-item[data-slitm-cd]")]
        slot = slots.setdefault(
            sid,
            {"channel": CHANNELS[m["ch"]], "start": datetime.strptime(m["dtm"], "%Y%m%d%H%M%S"),
             "brand": "", "products": []},
        )
        if products:
            slot["products"] = products
            slot["brand"] = slot["brand"] or products[0]["brand"]

    # 3) 종료 시각 = 같은 채널 다음 방송 시작
    out: list[Broadcast] = []
    by_channel: dict[str, list[dict]] = {}
    for s in slots.values():
        by_channel.setdefault(s["channel"], []).append(s)
    for ch, lst in by_channel.items():
        lst.sort(key=lambda s: s["start"])
        for i, s in enumerate(lst):
            end = lst[i + 1]["start"] if i + 1 < len(lst) else None
            title = s["brand"] or (s["products"][0]["name"] if s["products"] else "")
            prods = s["products"] or [{"id": "", "name": "", "brand": s["brand"], "price": None,
                                       "list_price": None, "alarm_count": None}]
            for j, p in enumerate(prods):
                out.append(
                    Broadcast(
                        channel_code=ch,
                        start_at=s["start"],
                        end_at=end,
                        title=title,
                        product_name=p["name"],
                        brand=p["brand"] or s["brand"],
                        price=p["price"],
                        product_url=ITEM_URL.format(p["id"]) if p["id"] else "",
                        external_id=p["id"],
                        extra={
                            "main": j == 0,
                            "list_price": p["list_price"],
                            "alarm_count": p["alarm_count"],  # 방송 알림 신청 수
                            "source": "saved_page",
                        },
                    )
                )
    return out
