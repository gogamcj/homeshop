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
pytest          # pyproject.toml에 경로 설정이 있어 저장소 루트에서 바로 실행
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

## 채널별 수집 현황 (2026-10-31 확인)

수집기는 `homeshop-collector` User-Agent를 그대로 밝히고 robots.txt를 따릅니다.
그래서 일반 수집기(`User-agent: *`)를 막은 채널은 자동 수집하지 않고, CSV 가져오기나 제휴로 채웁니다.

| 채널 | 상태 | 근거 |
|---|---|---|
| 공영쇼핑 `gongyoung` | ✅ 어댑터 있음 | `/tvshopping/` 허용. 편성·가격·누적 구매 수(`extra.order_count`) |
| 쇼핑엔티 `shopnt` | ✅ 어댑터 있음 | robots.txt 없음. 편성·가격·연관 상품 |
| CJ온스타일 `cj`, `cjplus` | ⛔ robots 금지 | `User-agent: *` → `Disallow: /` |
| 롯데홈쇼핑 `lotte`, `lotteone` | ⛔ robots 금지 | `User-agent: *` → `Disallow: /` |
| 현대홈쇼핑 `hmall`, `hmallplus` | ⛔ robots 금지 | `User-agent: *` → `Disallow: /` |
| 홈앤쇼핑 `hns` | ⛔ robots 금지 | `User-agent: *` → `Disallow: /` |
| NS홈쇼핑 `ns`, `nsplus` | ⛔ robots 금지 | 웹은 허용이나 편성 데이터를 주는 `mapi.nsmall.com`이 전체 금지 |
| GS샵 `gs`, `gsmyshop` | ⛔ 접속 차단 | 수집기 UA에 오류 페이지 응답 |
| KT알파쇼핑 `kshop` | ⛔ 접속 차단 | 403 차단 안내 |
| 신세계라이브쇼핑 `shinsegae` | ⛔ 접속 차단 | 417 응답 |
| SK스토아 `sk` | 🔍 조사 필요 | 접속 가능, 편성표 데이터 경로 미확인 |
| W쇼핑 `wshop` | 🔍 조사 필요 | 연결 실패 |

막힌 채널은 브라우저 UA 위장 등 우회를 하지 않습니다. 각 사에 데이터 제휴를 요청하거나, 허용된 경로(검색엔진 등)가 생기면 다시 확인합니다.

## CSV 형식

필수 열: `channel_code, start_at, title`
선택 열: `end_at, product_name, brand, category, price, product_url, external_id`

## 수집 원칙

- 원천(각 홈쇼핑사·플랫폼)의 공개 페이지에서만 수집합니다. 다른 분석 서비스의 데이터는 가져오지 않습니다.
- robots.txt를 지키고, 호스트마다 요청 간격(기본 3초)을 둡니다.
- 로그인 우회나 차단 회피를 하지 않고, 개인정보(리뷰 작성자 등)는 저장하지 않습니다.
- 상용 출시 전 각 채널 이용약관과 법률 검토를 거칩니다.
