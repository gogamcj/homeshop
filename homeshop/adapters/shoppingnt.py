"""쇼핑엔티 TV 편성표.

편성표 화면(/broadcast/tvBroadcastMain)은 날짜 탭을 누르면
GET /broadcast/tvBroadcastList?fromDate=YYYYMMDD 로 HTML 조각을 받아 끼운다.
robots.txt가 없어(사이트가 일반 페이지를 돌려줌) 전체 허용으로 본다.

HTML 구조: ul.time-list > li 하나가 방송 1건.
  - .tit-time: "HH:MM ~ HH:MM" (방송 중인 건은 시간 대신 남은 시간 타이머만 있음)
  - .prd-unit-wrap.typeA .goods: 대표 상품
  - .rel-prd-area li .goods: 연관 상품
"""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta

from bs4 import BeautifulSoup, Tag

from ..models import Broadcast
from . import register
from .base import ChannelAdapter

BASE = "https://www.shoppingntmall.com"
_TIME = re.compile(r"(\d{1,2}):(\d{2})\s*~\s*(\d{1,2}):(\d{2})")
_GOODS = re.compile(r"/display/goods/(\d+)")


def _money(el: Tag | None) -> int | None:
    if el is None:
        return None
    digits = re.sub(r"[^\d]", "", el.get_text())
    return int(digits) if digits else None


def _goods(el: Tag) -> dict | None:
    a = el.find("a", href=_GOODS)
    name = el.select_one(".name")
    if a is None or name is None:
        return None
    btn = el.find(attrs={"data-braze_product_category": True})
    return {
        "id": _GOODS.search(a["href"]).group(1),
        "name": name.get_text(strip=True),
        "price": _money(el.select_one(".purchase .price em")),
        "list_price": _money(el.select_one(".purchase .del em")),
        "category": btn["data-braze_product_category"].strip() if btn else "",
    }


@register
class ShoppingNtAdapter(ChannelAdapter):
    channel_code = "shopnt"

    def schedule_url(self, day: date) -> str:
        return f"{BASE}/broadcast/tvBroadcastList?fromDate={day:%Y%m%d}"

    def parse(self, body: str, day: date) -> list[Broadcast]:
        soup = BeautifulSoup(body, "html.parser")
        ul = soup.select_one("ul.time-list")
        if ul is None:
            return []

        # 1) 방송별 시간과 상품 모으기
        slots: list[dict] = []
        for li in ul.find_all("li", recursive=False):
            tit = li.select_one(".tit-time")
            m = _TIME.search(tit.get_text(" ", strip=True)) if tit else None
            main_el = li.select_one(".prd-unit-wrap.typeA .goods")
            main = _goods(main_el) if main_el else None
            if main is None:
                continue
            related = [g for g in (_goods(x) for x in li.select(".rel-prd-area li .goods")) if g]
            slots.append(
                {
                    "hm": (int(m[1]), int(m[2]), int(m[3]), int(m[4])) if m else None,
                    "onair": "onair" in (li.get("class") or []),
                    "main": main,
                    "related": related,
                }
            )

        # 2) 시:분을 날짜시각으로 바꾼다. 시작 시각이 앞 방송보다 이르면 다음 날로 넘어간 것.
        cur_day = day
        prev: datetime | None = None
        for s in slots:
            if s["hm"] is None:
                s["start"] = s["end"] = None
                continue
            sh, sm, eh, em = s["hm"]
            start = datetime.combine(cur_day, time(sh, sm))
            if prev is not None and start < prev:
                cur_day += timedelta(days=1)
                start += timedelta(days=1)
            end = datetime.combine(cur_day, time(eh, em))
            if end <= start:
                end += timedelta(days=1)
            s["start"], s["end"] = start, end
            prev = start

        # 3) 방송 중인 건은 앞 방송 종료 ~ 다음 방송 시작으로 채운다.
        for i, s in enumerate(slots):
            if s["start"] is None:
                before = next((x["end"] for x in reversed(slots[:i]) if x.get("end")), None)
                after = next((x["start"] for x in slots[i + 1 :] if x.get("start")), None)
                s["start"], s["end"] = before, after

        out: list[Broadcast] = []
        for s in slots:
            if s["start"] is None:
                continue  # 시각을 알 수 없는 건은 버린다
            title = s["main"]["name"]
            for g, is_main in [(s["main"], True)] + [(g, False) for g in s["related"]]:
                out.append(
                    Broadcast(
                        channel_code=self.channel_code,
                        start_at=s["start"],
                        end_at=s["end"],
                        title=title,
                        product_name=g["name"],
                        category=g["category"],
                        price=g["price"],
                        product_url=f"{BASE}/display/goods/{g['id']}",
                        external_id=g["id"],
                        extra={"main": is_main, "list_price": g["list_price"]},
                    )
                )
        return out
