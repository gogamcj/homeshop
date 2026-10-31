"""채널별 편성표 어댑터.

새 채널을 추가하려면 ChannelAdapter를 상속한 클래스를 만들고 register()로 등록한다.
어댑터는 parse()를 순수 함수로 두어, 저장해 둔 HTML/JSON 픽스처로 테스트할 수 있게 한다.
"""
from __future__ import annotations

from .base import ChannelAdapter

_REGISTRY: dict[str, type[ChannelAdapter]] = {}


def register(cls: type[ChannelAdapter]) -> type[ChannelAdapter]:
    _REGISTRY[cls.channel_code] = cls
    return cls


def get_adapter(code: str) -> type[ChannelAdapter] | None:
    return _REGISTRY.get(code)


def registered_codes() -> list[str]:
    return sorted(_REGISTRY)
