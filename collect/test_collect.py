"""파싱/병합 로직 단위 테스트. 응답 샘플은 문서화된 형식을 따라 만든 것이며
실제 서버 응답과의 일치는 Actions 첫 실행으로 확인해야 합니다.
실행: python -m unittest discover -s collect"""
import json
import unittest
from unittest import mock

import apt
import market

INTEGRATION = {"totalInfos": [
    {"code": "per", "value": "13.21배"}, {"code": "eps", "value": "5,400원"},
    {"code": "cnsPer", "value": "9.40배"}, {"code": "cnsEps", "value": "7,590원"},
    {"code": "pbr", "value": "1.12배"}, {"code": "bps", "value": "63,700원"}]}
ANNUAL = {"financeInfo": {
    "trTitleList": [{"key": "202412", "isConsensus": "N"}, {"key": "202612", "isConsensus": "Y"}, {"key": "202712", "isConsensus": "Y"}],
    "rowList": [{"title": "BPS", "columns": {"202412": {"value": "52,000"}, "202612": {"value": "68,000"}, "202712": {"value": "74,000"}}}]}}
BASIC = {"closePrice": "71,300", "localTradedAt": "2026-10-13T16:10:00+09:00"}

XML_OK = """<?xml version="1.0" encoding="UTF-8"?><response><header><resultCode>000</resultCode><resultMsg>OK</resultMsg></header>
<body><items>
<item><aptNm> 마포래미안푸르지오 </aptNm><umdNm>아현동</umdNm><dealAmount> 125,000</dealAmount><dealYear>2026</dealYear><dealMonth>9</dealMonth><dealDay>12</dealDay><excluUseAr>84.97</excluUseAr><floor>12</floor><cdealType></cdealType></item>
<item><aptNm>마포래미안푸르지오</aptNm><umdNm>아현동</umdNm><dealAmount>120,000</dealAmount><dealYear>2026</dealYear><dealMonth>9</dealMonth><dealDay>20</dealDay><excluUseAr>59.9</excluUseAr><floor>3</floor></item>
<item><aptNm>마포래미안푸르지오</aptNm><umdNm>아현동</umdNm><dealAmount>124,000</dealAmount><dealYear>2026</dealYear><dealMonth>9</dealMonth><dealDay>25</dealDay><excluUseAr>84.97</excluUseAr><floor>7</floor><cdealType>O</cdealType></item>
<item><aptNm>다른아파트</aptNm><umdNm>아현동</umdNm><dealAmount>99,000</dealAmount><dealYear>2026</dealYear><dealMonth>9</dealMonth><dealDay>1</dealDay><excluUseAr>84.9</excluUseAr><floor>2</floor></item>
</items><numOfRows>1000</numOfRows><pageNo>1</pageNo><totalCount>4</totalCount></body></response>"""
XML_ERR = """<OpenAPI_ServiceResponse><cmmMsgHeader><errMsg>SERVICE ERROR</errMsg><returnAuthMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</returnAuthMsg><returnReasonCode>30</returnReasonCode></cmmMsgHeader></OpenAPI_ServiceResponse>"""


class MarketTests(unittest.TestCase):
    def test_num(self):
        self.assertEqual(market.num("1,234.5배"), 1234.5)
        self.assertEqual(market.num("71,200원"), 71200)
        self.assertIsNone(market.num("N/A"))
        self.assertIsNone(market.num(None))

    def test_snapshot(self):
        base = market.BASE.format(code="005930")
        resp = {base + "/integration": INTEGRATION, base + "/basic": BASIC, base + "/finance/annual": ANNUAL}
        with mock.patch.object(market, "get_json", side_effect=lambda u, **k: resp[u]):
            r = market.snapshot("005930")
        self.assertEqual(r["d"], "2026-10-13")
        self.assertEqual((r["per"], r["fper"], r["pbr"]), (13.21, 9.4, 1.12))
        self.assertAlmostEqual(r["fpbr"], 71300 / 68000, places=6)   # 첫 추정연도 BPS

    def test_snapshot_fallbacks(self):
        base = market.BASE.format(code="x")
        info = {"totalInfos": [{"code": "cnsEps", "value": "7,130원"}, {"code": "bps", "value": "71,300원"}]}
        resp = {base + "/integration": info, base + "/basic": BASIC, base + "/finance/annual": {}}
        with mock.patch.object(market, "get_json", side_effect=lambda u, **k: resp[u]):
            r = market.snapshot("x")
        self.assertAlmostEqual(r["fper"], 10.0)      # 추정PER 없으면 현재가/추정EPS
        self.assertAlmostEqual(r["pbr"], 1.0)        # PBR 없으면 현재가/BPS
        self.assertIsNone(r["fpbr"])                 # 추정 BPS 못 구하면 None (0으로 채우지 않음)

    def test_sane_rejects_garbage(self):
        self.assertIsNone(market.sane(-3.0)); self.assertIsNone(market.sane(0)); self.assertIsNone(market.sane(9999))


class AptTests(unittest.TestCase):
    CFG = {"aptNm": "마포 래미안 푸르지오", "dong": "아현동", "area": 84, "areaTol": 1.5}

    def test_parse_and_filter(self):
        total, items = apt.parse_page(XML_OK)
        self.assertEqual(total, 4)
        hits = [apt.to_trade(i) for i in items if apt.matches(i, self.CFG)]
        self.assertEqual(hits, [{"d": "2026-09-12", "p": 125000, "f": 12}])   # 면적 다름·해제·타단지 제외

    def test_api_error_is_loud(self):
        with self.assertRaises(RuntimeError) as cm:
            apt.parse_page(XML_ERR)
        self.assertIn("SERVICE_KEY_IS_NOT_REGISTERED_ERROR", str(cm.exception))

    def test_months_back_crosses_year(self):
        with mock.patch.object(apt, "kst_today", return_value=__import__("datetime").date(2026, 2, 5)):
            self.assertEqual(list(apt.months_back(4)), ["202602", "202601", "202512", "202511"])


if __name__ == "__main__":
    unittest.main()
