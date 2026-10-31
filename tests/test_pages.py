"""저장한 편성표 페이지 가져오기 테스트. 픽스처는 2026-10-31 브라우저로 저장한 현대Hmall 편성표를 줄인 것."""
from datetime import datetime
from pathlib import Path

import pytest

from homeshop import db, pages

FIX = Path(__file__).parent / "fixtures"
HMALL = FIX / "hmall_saved_20261101.html"


def test_detects_site_from_saved_url():
    assert pages.detect(HMALL.read_text(encoding="utf-8")) == "hmall"


def test_hmall_timeline_covers_whole_day():
    items = pages.read_page(HMALL)
    starts = sorted({b.start_at for b in items})
    assert len(starts) == 24
    assert starts[0] == datetime(2026, 11, 1, 0, 30)
    first = next(b for b in items if b.start_at == starts[0])
    assert first.channel_code == "hmall" and first.title == "금호고속"
    assert first.end_at == datetime(2026, 11, 1, 1, 30)
    assert first.external_id == "2256898350" and first.product_name == ""


def test_hmall_rendered_sections_have_product_details():
    items = pages.read_page(HMALL)
    robo = [b for b in items if b.title == "로보락"]
    assert len(robo) == 2 and [b.extra["main"] for b in robo] == [True, False]
    assert robo[0].price == 1590000 and robo[0].extra["list_price"] == 1890000
    assert robo[0].extra["alarm_count"] == 39
    assert robo[0].product_url.endswith("slitmCd=2256796243")
    assert robo[0].product_name.startswith("[NEW 스팀] 로보락")
    insurance = next(b for b in items if b.title == "흥국생명")
    assert insurance.price is None  # 상담 상품


def test_unknown_page_needs_site(tmp_path):
    p = tmp_path / "x.html"
    p.write_text("<html></html>", encoding="utf-8")
    with pytest.raises(pages.PageImportError, match="--site"):
        pages.read_page(p)
    with pytest.raises(pages.PageImportError, match="찾지 못했습니다"):
        pages.read_page(p, "hmall")


def test_merge_keeps_details_when_later_save_has_only_timeline():
    conn = db.connect(":memory:")
    db.init_db(conn)
    items = pages.read_page(HMALL)
    db.merge_page_broadcasts(conn, items)
    assert db.search_broadcasts(conn, q="로보락")[0] == 2

    # 다시 저장했는데 그 구간이 화면 밖이라 시간표만 있는 경우
    timeline_only = [b for b in items if b.extra["main"]]
    for b in timeline_only:
        b.product_name, b.price = "", None
    db.merge_page_broadcasts(conn, timeline_only)
    total, rows = db.search_broadcasts(conn, q="S10 MaxV")
    assert total == 2 and rows[0]["price"]

    # 같은 파일을 두 번 넣어도 늘어나지 않는다
    db.merge_page_broadcasts(conn, pages.read_page(HMALL))
    assert db.search_broadcasts(conn, channel="hmall")[0] == len(items)
