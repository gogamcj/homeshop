"""공영쇼핑 TV 편성표.

편성표 화면(/tvshopping/tvSchedule.do)은 날짜를 고르면
POST /tvshopping/selectScheduleSub.do (brcStdDate=YYYYMMDD) 로 JSON을 받아 그린다.
robots.txt는 /tvshopping/ 경로를 막지 않는다 (/api/, /goods/ 등은 막음).

응답의 prdList는 방송 1건에 상품이 여럿이면 상품마다 1행이고, brcPgmSchdgId(편성 ID)로 묶인다.
"""
from __future__ import annotations

import json
from datetime import date, datetime

from ..models import Broadcast
from . import register
from .base import ChannelAdapter

BASE = "https://www.gongyoungshop.kr"


def _dtm(s: str) -> datetime:
    return datetime.strptime(s, "%Y%m%d%H%M")


def _int(v) -> int | None:
    try:
        n = int(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return n


@register
class GongyoungAdapter(ChannelAdapter):
    channel_code = "gongyoung"

    def schedule_url(self, day: date) -> str:
        return f"{BASE}/tvshopping/selectScheduleSub.do"

    def fetch_schedule(self, day: date) -> list[Broadcast]:
        resp = self.fetcher.post(
            self.schedule_url(day),
            data={"brcStdDate": f"{day:%Y%m%d}"},
            headers={"Accept": "application/json"},
        )
        return self.parse(resp.text, day)

    def parse(self, body: str, day: date) -> list[Broadcast]:
        rows = json.loads(body).get("prdList") or []
        out: list[Broadcast] = []
        seen: set[tuple[str, str]] = set()
        first_of_pgm: set[str] = set()
        for r in rows:
            pgm_id = str(r.get("brcPgmSchdgId") or "")
            prd_id = str(r.get("prdId") or "")
            if not r.get("brcBgnDtm") or (pgm_id, prd_id) in seen:
                continue
            seen.add((pgm_id, prd_id))
            is_main = pgm_id not in first_of_pgm
            first_of_pgm.add(pgm_id)

            list_price = _int(r.get("prdPrc"))
            sale_price = _int(r.get("cnmerUprc"))
            price = sale_price if sale_price else list_price
            name = (r.get("prdNm") or "").strip()
            out.append(
                Broadcast(
                    channel_code=self.channel_code,
                    start_at=_dtm(r["brcBgnDtm"]),
                    end_at=_dtm(r["brcEndDtm"]) if r.get("brcEndDtm") else None,
                    title=(r.get("brcPgmNm") or name).strip(),
                    product_name=name,
                    brand=(r.get("brndNm") or "").strip(),
                    category=(r.get("prdLclsNm") or "").strip(),
                    price=price,
                    product_url=f"{BASE}/goods/selectGoodsDetail.do?prdId={prd_id}" if prd_id else "",
                    external_id=f"{pgm_id}:{prd_id}",
                    extra={
                        "main": is_main,
                        "list_price": list_price,
                        # 상품 페이지에 공개된 누적 구매 수. 2단계 판매량 추정에서 증가량으로 쓴다.
                        "order_count": _int(r.get("ordQty")),
                        "sold_out": r.get("stkSoldYn") == "Y",
                        "counsel_only": r.get("goodsSpCd") == "300",  # 상담접수 상품
                    },
                )
            )
        return out
