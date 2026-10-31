"""수집 대상 채널 목록.

homepage는 참고용이며, 실제 편성표 URL과 파싱 방식은 채널별 어댑터(homeshop/adapters)에서 정한다.
"""
from .models import Channel

CHANNELS: list[Channel] = [
    # TV 홈쇼핑
    Channel("gs", "GS샵", "HS", "https://www.gsshop.com"),
    Channel("cj", "CJ온스타일", "HS", "https://display.cjonstyle.com"),
    Channel("hmall", "현대홈쇼핑", "HS", "https://www.hmall.com"),
    Channel("lotte", "롯데홈쇼핑", "HS", "https://www.lotteimall.com"),
    Channel("ns", "NS홈쇼핑", "HS", "https://www.nsmall.com"),
    Channel("hns", "홈앤쇼핑", "HS", "https://www.hnsmall.com"),
    Channel("gongyoung", "공영쇼핑", "HS", "https://www.gongyoungshop.kr"),
    # T커머스 / 데이터홈쇼핑
    Channel("gsmyshop", "GS마이샵", "TC", "https://www.gsshop.com"),
    Channel("cjplus", "CJ온스타일플러스", "TC", "https://display.cjonstyle.com"),
    Channel("hmallplus", "현대홈쇼핑플러스샵", "TC", "https://www.hmall.com"),
    Channel("lotteone", "롯데OneTV", "TC", "https://www.lotteimall.com"),
    Channel("shopnt", "쇼핑엔티", "TC", "https://www.shoppingntmall.com"),
    Channel("kshop", "KT알파쇼핑", "TC", "https://www.kshop.co.kr"),
    Channel("sk", "SK스토아", "TC", "https://www.skstoa.com"),
    Channel("wshop", "W쇼핑", "TC", "https://www.wshop.co.kr"),
    Channel("shinsegae", "신세계라이브쇼핑", "TC", "https://www.shinsegaetvshopping.com"),
    Channel("nsplus", "NS Shop+", "TC", "https://www.nsmall.com"),
]

BY_CODE = {c.code: c for c in CHANNELS}
