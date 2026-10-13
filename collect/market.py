#!/usr/bin/env python3
"""종목별 후행/선행 PER·PBR 스냅샷을 data/market.json 에 하루 한 줄씩 누적한다.

- 후행 PER/PBR : 네이버 금융이 보여주는 PER, PBR (최근 실적 기준)
- 선행 PER     : 네이버 금융의 추정PER (컨센서스 EPS 기준)
- 선행 PBR     : 현재가 / 컨센서스 BPS(추정 첫 해)  -- 직접 계산
선행 값은 과거 시계열을 무료로 받을 수 없어서, 이 스크립트를 돌린 날부터 쌓입니다.
"""
import re
import sys

from util import ROOT, get_json, kst_today, load_json, save_json

BASE = "https://m.stock.naver.com/api/stock/{code}"
OUT = ROOT / "data" / "market.json"
CONFIG = ROOT / "config" / "watch.json"


def num(s):
    """'1,234.5배' / '71,200' / 'N/A' -> float | None"""
    if s is None:
        return None
    m = re.search(r"-?\d[\d,]*\.?\d*", str(s))
    return float(m.group().replace(",", "")) if m else None


def sane(v, hi=500):
    return v if v is not None and 0 < v < hi else None


def parse_integration(j):
    return {it.get("code"): it.get("value") for it in j.get("totalInfos", []) if it.get("code")}


def est_bps(j):
    """annual 재무 표에서 컨센서스(추정) 첫 해의 BPS."""
    fi = j.get("financeInfo", {})
    cons = [t.get("key") for t in fi.get("trTitleList", []) if t.get("isConsensus") == "Y"]
    for row in fi.get("rowList", []):
        if row.get("title") == "BPS":
            for k in cons:
                v = num((row.get("columns", {}).get(k) or {}).get("value"))
                if v:
                    return v
    return None


def snapshot(code):
    base = BASE.format(code=code)
    info_json = get_json(base + "/integration")
    info = parse_integration(info_json)
    try:
        basic = get_json(base + "/basic")
    except RuntimeError as e:
        print(f"  경고: basic 조회 실패 ({e})")
        basic = {}
    try:
        bps_e = est_bps(get_json(base + "/finance/annual"))
    except RuntimeError as e:
        print(f"  경고: 추정 BPS 조회 실패 ({e})")
        bps_e = None

    price = num(basic.get("closePrice")) or num(info.get("lastClosePrice"))
    traded = str(basic.get("localTradedAt") or "")[:10]
    date = traded if re.fullmatch(r"\d{4}-\d{2}-\d{2}", traded) else kst_today().isoformat()

    per, pbr = sane(num(info.get("per"))), sane(num(info.get("pbr")), 100)
    if pbr is None and price and num(info.get("bps")):
        pbr = sane(price / num(info.get("bps")), 100)
    fper = sane(num(info.get("cnsPer")))
    if fper is None and price and (num(info.get("cnsEps")) or 0) > 0:
        fper = sane(price / num(info.get("cnsEps")))
    fpbr = sane(price / bps_e, 100) if price and bps_e else None

    row = {"d": date, "price": price, "per": per, "fper": fper, "pbr": pbr, "fpbr": fpbr}
    missing = [k for k in ("per", "fper", "pbr", "fpbr") if row[k] is None]
    if missing:
        print(f"  경고: 값을 못 읽음 {missing} / 응답에서 찾은 항목 코드: {sorted(info)}")
    return row


def main():
    cfg = load_json(CONFIG, {"stocks": []})
    stocks = cfg.get("stocks", [])
    data = load_json(OUT, {"updated": None, "stocks": {}})
    failed = []
    for s in stocks:
        code, name = s["code"], s.get("name", s["code"])
        print(f"[{code}] {name}")
        try:
            row = snapshot(code)
        except Exception as e:  # 한 종목 실패가 나머지를 막지 않게
            print(f"  실패: {e}")
            failed.append(code)
            continue
        if all(row[k] is None for k in ("per", "fper", "pbr", "fpbr")):
            print("  실패: 읽은 값이 하나도 없어요 (응답 형식이 바뀌었을 수 있어요)")
            failed.append(code)
            continue
        ent = data["stocks"].setdefault(code, {"name": name, "rows": []})
        ent["name"] = name
        ent["rows"] = sorted([r for r in ent["rows"] if r["d"] != row["d"]] + [row], key=lambda r: r["d"])
        print("  기록:", row)
    data["updated"] = kst_today().isoformat()
    save_json(OUT, data)
    if failed:
        sys.exit(f"수집 실패 종목: {failed}")


if __name__ == "__main__":
    main()
