#!/usr/bin/env python3
"""관심 아파트의 실거래가를 국토교통부 API에서 받아 data/realestate.json 에 누적한다.

환경변수 DATA_GO_KR_KEY 에 공공데이터포털 서비스키(일반 인증키)가 필요합니다.
사용: python collect/apt.py [--months N]   (최근 N개월, 기본 3)
"""
import argparse
import os
import re
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET

from util import ROOT, http_get, kst_today, load_json, save_json

ENDPOINT = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
OUT = ROOT / "data" / "realestate.json"
CONFIG = ROOT / "config" / "watch.json"


def norm(s):
    return re.sub(r"[\s()\[\]·.\-]", "", s or "")


def parse_page(xml_text):
    """-> (totalCount, [item dict]). API 오류 응답이면 이유를 담아 예외."""
    root = ET.fromstring(xml_text)
    code = (root.findtext(".//resultCode") or "").strip()
    if code not in ("00", "000"):
        why = root.findtext(".//resultMsg") or root.findtext(".//returnAuthMsg") or root.findtext(".//errMsg") or "알 수 없음"
        raise RuntimeError(f"API 오류 {code or '(코드 없음)'}: {why}")
    total = int((root.findtext(".//totalCount") or "0").strip() or 0)
    items = [{c.tag: (c.text or "").strip() for c in it} for it in root.iter("item")]
    return total, items


def to_trade(it):
    try:
        price = int(it["dealAmount"].replace(",", ""))
        d = f"{int(it['dealYear']):04d}-{int(it['dealMonth']):02d}-{int(it['dealDay']):02d}"
        return {"d": d, "p": price, "f": int(it["floor"]) if it.get("floor", "").lstrip("-").isdigit() else None}
    except (KeyError, ValueError):
        return None


def matches(it, apt):
    if norm(apt["aptNm"]) not in norm(it.get("aptNm")):
        return False
    if apt.get("dong") and apt["dong"] != it.get("umdNm"):
        return False
    if it.get("cdealType", "").strip().upper() == "O":  # 해제(취소)된 거래
        return False
    try:
        return abs(float(it.get("excluUseAr", "x")) - float(apt["area"])) <= float(apt.get("areaTol", 1.5))
    except ValueError:
        return False


def fetch_month(key, lawd, ym):
    k = key if "%" in key else urllib.parse.quote(key, safe="")
    items, page = [], 1
    while True:
        url = f"{ENDPOINT}?serviceKey={k}&LAWD_CD={lawd}&DEAL_YMD={ym}&numOfRows=1000&pageNo={page}"
        total, got = parse_page(http_get(url))
        items += got
        if not got or len(items) >= total:
            return items
        page += 1
        time.sleep(0.3)


def months_back(n):
    t = kst_today()
    y, m = t.year, t.month
    for _ in range(n):
        yield f"{y:04d}{m:02d}"
        m -= 1
        if m == 0:
            y, m = y - 1, 12


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", default="3")
    n = int(re.sub(r"\D", "", ap.parse_args().months) or 3)
    n = max(1, min(n, 120))

    apts = [a for a in load_json(CONFIG, {}).get("apartments", []) if a.get("aptNm")]
    if not apts:
        print("config/watch.json 에 관심 단지(apartments)가 없어서 건너뜁니다.")
        return
    key = os.environ.get("DATA_GO_KR_KEY", "").strip()
    if not key:
        sys.exit("DATA_GO_KR_KEY 가 설정되지 않았어요. (저장소 Settings → Secrets → Actions)")

    data = load_json(OUT, {"updated": None, "complexes": {}})
    cache, failed = {}, []
    for apt in apts:
        cid = apt.get("id") or norm(apt["aptNm"])
        ent = data["complexes"].setdefault(cid, {"name": apt.get("name") or apt["aptNm"], "trades": []})
        ent["name"] = apt.get("name") or apt["aptNm"]
        ent["area"] = apt["area"]
        seen = {(t["d"], t["p"], t.get("f")) for t in ent["trades"]}
        added = 0
        for ym in months_back(n):
            ck = (apt["lawdCd"], ym)
            try:
                if ck not in cache:
                    cache[ck] = fetch_month(key, apt["lawdCd"], ym)
            except Exception as e:
                print(f"[{cid}] {ym} 실패: {e}")
                failed.append((cid, ym))
                continue
            for it in cache[ck]:
                if not matches(it, apt):
                    continue
                t = to_trade(it)
                if t and (t["d"], t["p"], t["f"]) not in seen:
                    seen.add((t["d"], t["p"], t["f"]))
                    ent["trades"].append(t)
                    added += 1
        ent["trades"].sort(key=lambda t: (t["d"], t["p"]))
        print(f"[{cid}] {ent['name']} {apt['area']}㎡: 새 거래 {added}건 (누적 {len(ent['trades'])}건)")
        if not ent["trades"]:
            print("  참고: 일치하는 거래가 없어요. aptNm(단지명), lawdCd(시군구 코드), area(전용면적)를 확인하세요.")
    data["updated"] = kst_today().isoformat()
    save_json(OUT, data)
    if failed:
        sys.exit(f"일부 월 조회 실패: {failed}")


if __name__ == "__main__":
    main()
