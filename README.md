# homeshop

홈쇼핑·T커머스·라이브커머스 방송 편성을 모으고, 방송별 판매수량·판매금액을 추정해 보여 주는 분석 사이트입니다.

> 판매수량·금액은 홈쇼핑사가 공개하지 않으므로 이 서비스의 수치는 **추정치**입니다.

## 단계

1. **편성표 수집과 검색** (현재) — 채널 목록, DB, 수집 프레임워크, CSV 가져오기, 검색 API·웹 화면
2. 상품 페이지 스냅샷(리뷰 수·구매 수·품절)으로 판매량 추정, 카테고리·시간대 랭킹
3. 라이브커머스 추가, 실데이터로 추정 보정, 유료 플랜

## 실행

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

python -m homeshop init-db
python -m homeshop import-csv tests/fixtures/sample_schedule.csv   # 예시 데이터
python -m homeshop serve                                            # http://127.0.0.1:8000
pytest
```

## 구조

| 경로 | 역할 |
|---|---|
| `homeshop/channels.py` | 수집 대상 17개 채널 (TV홈쇼핑 7, T커머스 10) |
| `homeshop/db.py` | SQLite 스키마, 저장(upsert), 검색, 채널 통계 |
| `homeshop/fetcher.py` | robots.txt 확인, 호스트별 요청 간격 제한 |
| `homeshop/adapters/` | 채널별 편성표 어댑터 (`ChannelAdapter` 상속 후 `register`) |
| `homeshop/collector.py` | 등록된 어댑터를 돌려 DB에 저장 |
| `homeshop/importer.py` | CSV 편성표 가져오기 |
| `homeshop/api.py`, `static/index.html` | 검색 API와 웹 화면 |

## 채널 어댑터 추가하기

```python
from homeshop.adapters import register
from homeshop.adapters.base import ChannelAdapter

@register
class GsAdapter(ChannelAdapter):
    channel_code = "gs"
    def schedule_url(self, day): ...
    def parse(self, body, day): ...   # 네트워크 없이 HTML/JSON → list[Broadcast]
```

`parse()`는 순수 함수로 두고, 실제 응답을 `tests/fixtures/`에 저장해 테스트합니다.

## CSV 형식

필수 열: `channel_code, start_at, title`
선택 열: `end_at, product_name, brand, category, price, product_url, external_id`

## 수집 원칙

- 원천(각 홈쇼핑사·플랫폼)의 공개 페이지에서만 수집합니다. 다른 분석 서비스의 데이터는 가져오지 않습니다.
- robots.txt를 지키고, 호스트마다 요청 간격(기본 3초)을 둡니다.
- 로그인 우회나 차단 회피를 하지 않고, 개인정보(리뷰 작성자 등)는 저장하지 않습니다.
- 상용 출시 전 각 채널 이용약관과 법률 검토를 거칩니다.
