"""채널 어댑터 파서 테스트. 픽스처는 2026-10-31 실제 응답에서 일부만 잘라 저장한 것."""
from datetime import date, datetime
from pathlib import Path

import httpx

from homeshop import adapters, collector, db
from homeshop.adapters.gongyoung import GongyoungAdapter
from homeshop.adapters.shoppingnt import ShoppingNtAdapter
from homeshop.fetcher import PoliteFetcher

FIX = Path(__file__).parent / "fixtures"
DAY = date(2026, 10, 31)


def test_registered_channels_exist_in_channel_list():
    from homeshop.channels import BY_CODE

    assert {"gongyoung", "shopnt"} <= set(adapters.registered_codes())
    assert set(adapters.registered_codes()) <= set(BY_CODE)


# --- 공영쇼핑 ---------------------------------------------------------------

def _gongyoung():
    return GongyoungAdapter(None).parse((FIX / "gongyoung_20261031.json").read_text(encoding="utf-8"), DAY)


def test_gongyoung_parses_program_and_products():
    items = _gongyoung()
    first = items[0]
    assert first.title == "재방_의류"
    assert first.start_at == datetime(2026, 10, 31, 1, 0)
    assert first.duration_min == 60
    assert first.price == 49900 and first.category == "의류"
    assert first.extra["order_count"] == 6796 and first.extra["main"] is True
    assert first.product_url.endswith("prdId=11953867")
    assert first.external_id == "10113542:11953867"


def test_gongyoung_dedupes_and_marks_main_product():
    items = _gongyoung()
    assert len({(b.external_id) for b in items}) == len(items)  # 중복 행 제거
    gold = [b for b in items if b.title == "재방_보석"]
    assert len(gold) > 1 and [b.extra["main"] for b in gold].count(True) == 1


def test_gongyoung_last_broadcast_crosses_midnight():
    last = _gongyoung()[-1]
    assert last.start_at.date() == DAY and last.end_at.date() == date(2026, 11, 1)


def test_gongyoung_fetch_posts_date():
    seen = {}

    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /api/\n")
        seen["method"], seen["body"] = req.method, req.content.decode()
        return httpx.Response(200, json={"prdList": []})

    f = PoliteFetcher(client=httpx.Client(transport=httpx.MockTransport(handler)), min_interval=0)
    assert GongyoungAdapter(f).fetch_schedule(DAY) == []
    assert seen == {"method": "POST", "body": "brcStdDate=20261031"}


# --- 쇼핑엔티 ---------------------------------------------------------------

def _shopnt():
    return ShoppingNtAdapter(None).parse((FIX / "shoppingnt_20261031.html").read_text(encoding="utf-8"), DAY)


def test_shoppingnt_parses_main_and_related_products():
    items = _shopnt()
    mains = [b for b in items if b.extra["main"]]
    assert len(mains) == 6
    first = mains[0]
    assert first.start_at == datetime(2026, 10, 31, 0, 32)
    assert first.end_at == datetime(2026, 10, 31, 1, 32)
    assert first.price == 88000 and first.extra["list_price"] == 89000
    assert first.category == "다이어트/건강기능"
    assert first.product_url.endswith("/display/goods/11732261")

    related = [b for b in items if not b.extra["main"]]
    assert related and related[0].external_id == "24503436"
    assert related[0].title.startswith("[기획가] 르까프")  # 대표 상품 방송에 묶임


def test_shoppingnt_fills_on_air_slot_from_neighbours():
    mains = [b for b in _shopnt() if b.extra["main"]]
    onair = next(b for b in mains if "천저우" in b.product_name)
    assert onair.start_at == datetime(2026, 10, 31, 22, 33)
    assert onair.end_at == datetime(2026, 10, 31, 23, 33)


def test_shoppingnt_midnight_crossover():
    last = [b for b in _shopnt() if b.extra["main"]][-1]
    assert last.start_at == datetime(2026, 10, 31, 23, 33)
    assert last.end_at == datetime(2026, 11, 1, 0, 32)


def test_shoppingnt_empty_page():
    assert ShoppingNtAdapter(None).parse("<div>편성 없음</div>", DAY) == []


def test_collect_with_real_adapters(monkeypatch):
    conn = db.connect(":memory:")
    db.init_db(conn)
    bodies = {
        "www.gongyoungshop.kr": (FIX / "gongyoung_20261031.json").read_text(encoding="utf-8"),
        "www.shoppingntmall.com": (FIX / "shoppingnt_20261031.html").read_text(encoding="utf-8"),
    }

    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, text=bodies[req.url.host])

    f = PoliteFetcher(client=httpx.Client(transport=httpx.MockTransport(handler)), min_interval=0)
    res = collector.collect(conn, DAY, ["gongyoung", "shopnt"], fetcher=f)
    assert res.skipped == {}
    assert res.saved["gongyoung"] == len(_gongyoung())
    assert db.search_broadcasts(conn, channel="shopnt")[0] == len(_shopnt())
