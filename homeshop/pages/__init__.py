"""브라우저로 직접 저장한 편성표 페이지(.html) 가져오기.

자동 수집이 막힌 채널(robots.txt 금지, 수집기 차단)은 사용자가 평소처럼 브라우저로
편성표를 열고 "웹페이지, 전체"로 저장한 파일을 읽어 DB에 넣는다. 네트워크 요청은 하지 않는다.

새 채널을 추가하려면 parse(html) -> list[Broadcast] 함수를 만들고 register_page()로 등록한다.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from ..models import Broadcast

PageParser = Callable[[str], list[Broadcast]]

_PARSERS: dict[str, PageParser] = {}
_HOSTS: dict[str, str] = {}  # 저장된 페이지 주소의 호스트 → 파서 이름


class PageImportError(Exception):
    pass


def register_page(name: str, hosts: list[str]):
    def deco(fn: PageParser) -> PageParser:
        _PARSERS[name] = fn
        for h in hosts:
            _HOSTS[h] = name
        return fn

    return deco


def supported() -> list[str]:
    return sorted(_PARSERS)


def detect(html: str) -> str | None:
    """브라우저가 남긴 'saved from url=' 주석이나 og:url로 어느 사이트 페이지인지 알아낸다."""
    m = re.search(r"saved from url=\(\d+\)(\S+)", html[:5000]) or re.search(
        r'og:url"\s+content="([^"]+)"', html
    )
    if not m:
        return None
    return _HOSTS.get(urlsplit(m.group(1)).netloc.lower())


def read_page(path: str | Path, name: str | None = None) -> list[Broadcast]:
    html = Path(path).read_text(encoding="utf-8", errors="replace")
    name = name or detect(html)
    if name is None:
        raise PageImportError(
            "어느 채널 페이지인지 알 수 없습니다. --site 로 지정하세요: " + ", ".join(supported())
        )
    if name not in _PARSERS:
        raise PageImportError(f"지원하지 않는 페이지: {name} (지원: {', '.join(supported())})")
    items = _PARSERS[name](html)
    if not items:
        raise PageImportError(
            "편성표를 찾지 못했습니다. 편성표 화면을 연 상태에서 '웹페이지, 전체'로 저장했는지 확인하세요."
        )
    return items


from . import hmall  # noqa: E402,F401
