from datetime import date, datetime
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from homeshop import adapters, collector, db, importer
from homeshop.adapters.base import ChannelAdapter
from homeshop.api import create_app
from homeshop.fetcher import PoliteFetcher, RobotsDisallowed
from homeshop.models import Broadcast

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    db.init_db(c)
    return c


# --- CSV 가져오기 -----------------------------------------------------------

def test_read_csv_parses_prices_and_dates():
    items = importer.read_csv(FIX / "sample_schedule.csv")
    assert len(items) == 3
    assert items[0].price == 89000
    assert items[1].price == 39900
    assert items[0].duration_min == 60
    assert items[2].end_at is None and items[2].price is None


def test_read_csv_rejects_unknown_channel(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("channel_code,start_at,title\nnope,2026-10-31 10:00,x\n", encoding="utf-8")
    with pytest.raises(importer.ImportError_, match="알 수 없는 채널"):
        importer.read_csv(p)


def test_read_csv_requires_columns(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("channel_code,title\ngs,x\n", encoding="utf-8")
    with pytest.raises(importer.ImportError_, match="start_at"):
        importer.read_csv(p)


# --- DB --------------------------------------------------------------------

def test_upsert_is_idempotent_and_updates(conn):
    items = importer.read_csv(FIX / "sample_schedule.csv")
    db.upsert_broadcasts(conn, items)
    items[0].price = 79000
    db.upsert_broadcasts(conn, items)
    total, rows = db.search_broadcasts(conn, q="상품 A")
    assert total == 1 and rows[0]["price"] == 79000


def test_search_filters(conn):
    db.upsert_broadcasts(conn, importer.read_csv(FIX / "sample_schedule.csv"))
    assert db.search_broadcasts(conn, channel="cj")[0] == 1
    assert db.search_broadcasts(conn, category="뷰티")[0] == 1
    assert db.search_broadcasts(conn, q="브랜드B")[0] == 1
    assert db.search_broadcasts(conn, date_from="2026-10-31", date_to="2026-10-31")[0] == 2
    assert db.search_broadcasts(conn, date_from="2026-11-01")[0] == 1
    assert db.list_categories(conn) == ["뷰티", "식품", "패션의류"]


# --- 수집기 -----------------------------------------------------------------

def _fetcher(handler, **kw):
    slept = []
    t = [0.0]
    f = PoliteFetcher(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=lambda s: (slept.append(s), t.__setitem__(0, t[0] + s)),
        clock=lambda: t[0],
        **kw,
    )
    return f, slept


def test_fetcher_respects_robots():
    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private\n")
        return httpx.Response(200, text="ok")

    f, _ = _fetcher(handler)
    assert f.get("https://shop.test/schedule").text == "ok"
    with pytest.raises(RobotsDisallowed):
        f.get("https://shop.test/private/x")


def test_fetcher_missing_robots_allows_but_5xx_blocks():
    f, _ = _fetcher(lambda req: httpx.Response(404 if req.url.host == "a.test" else 503))
    assert f.allowed("https://a.test/x")
    assert not f.allowed("https://b.test/x")


def test_fetcher_throttles_per_host():
    f, slept = _fetcher(lambda req: httpx.Response(200, text=""), min_interval=3.0)
    f.get("https://shop.test/a")
    f.get("https://shop.test/b")
    assert slept and abs(slept[-1] - 3.0) < 1e-9


class _FakeAdapter(ChannelAdapter):
    channel_code = "gs"

    def schedule_url(self, day):
        return f"https://shop.test/schedule?d={day:%Y%m%d}"

    def parse(self, body, day):
        return [
            Broadcast("gs", datetime(day.year, day.month, day.day, h), None, f"방송 {h}시")
            for h in map(int, body.split(","))
        ]


def test_collect_saves_and_reports(conn, monkeypatch):
    monkeypatch.setitem(adapters._REGISTRY, "gs", _FakeAdapter)

    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, text="9,20")

    f, _ = _fetcher(handler, min_interval=0)
    res = collector.collect(conn, date(2026, 10, 31), ["gs", "cj"], fetcher=f)
    assert res.saved == {"gs": 2}
    assert res.skipped == {"cj": "어댑터 없음"}
    assert db.search_broadcasts(conn, channel="gs")[0] == 2


# --- API -------------------------------------------------------------------

def test_api_search(tmp_path):
    path = str(tmp_path / "t.db")
    c = db.connect(path)
    db.init_db(c)
    db.upsert_broadcasts(c, importer.read_csv(FIX / "sample_schedule.csv"))
    client = TestClient(create_app(path))

    r = client.get("/api/broadcasts", params={"q": "상품"})
    assert r.status_code == 200 and r.json()["total"] == 2
    assert r.json()["items"][0]["channel_name"] in {"GS샵", "CJ온스타일"}

    assert client.get("/api/broadcasts", params={"date_from": "bad"}).status_code == 422
    chs = client.get("/api/channels").json()
    assert len(chs) == 17 and chs[0]["broadcasts"] == 1
    assert client.get("/").status_code == 200
