"""수집 스크립트 공용 헬퍼 (표준 라이브러리만 사용)."""
import json
import pathlib
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
KST = timezone(timedelta(hours=9))
UA = "Mozilla/5.0 (compatible; jkj-dashboard-collector/1.0)"


def kst_today():
    return datetime.now(KST).date()


def http_get(url, headers=None, tries=3, timeout=20):
    """GET 후 본문(str) 반환. 일시 오류는 재시도하고, 끝내 실패하면 예외를 던진다."""
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"GET 실패: {url.split('?')[0]} ({last})")


def get_json(url, **kw):
    return json.loads(http_get(url, **kw))


def load_json(path, default):
    p = pathlib.Path(path)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            raise SystemExit(f"{p} 가 올바른 JSON이 아니에요. 덮어쓰지 않고 중단합니다.")
    return default


def save_json(path, obj):
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
