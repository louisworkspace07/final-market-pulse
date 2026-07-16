"""Bối cảnh vĩ mô & thị trường — dùng CHUNG cho mọi mã (không theo công ty).

Gồm:
- Chỉ số thị trường (VNINDEX/VN30): điểm số mới nhất + %1D/%1M/%YTD + thanh khoản
  → tự động qua VNDirect (vndirect.index_history).
- Tỷ giá USD/VND → tự động qua Vietcombank (vndirect.exchange_rate), có thể rỗng.
- GDP / CPI / lãi suất điều hành → KHÔNG có API tin cậy, đọc file seed cập nhật tay
  config/macro_seed.json, gắn nhãn source='seed' + as_of để AI biết là cập nhật tay.

Kết quả cache theo NGÀY vào data/macro/context.json — trong ngày không crawl lại.
Không bịa số: trường nào không lấy được để None và ghi rõ trong 'sources'.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

from . import config, storage

# Các chỉ số lấy điểm số + thanh khoản (code trên VNDirect).
_INDEXES = ("VNINDEX", "VN30")
_INDEX_YEARS = 1   # đủ để tính %YTD và %1M


def _pct(cur, prev):
    if cur is None or prev in (None, 0):
        return None
    return (cur - prev) / abs(prev) * 100.0


def _nearest_before(series: list[dict], target: str):
    """close của điểm gần nhất có time <= target (series tăng dần theo time)."""
    pick = None
    for d in series:
        if str(d.get("time")) <= target:
            pick = d
        else:
            break
    return (pick or {}).get("close")


def _index_stats(code: str) -> dict:
    from . import vndirect
    today = date.today()
    start = (today - timedelta(days=365 * _INDEX_YEARS + 7)).isoformat()
    series = vndirect.index_history(code, start, today.isoformat())
    if not series:
        return {"code": code, "latest": None, "ok": False}
    latest = series[-1]
    close = latest.get("close")
    d1 = series[-2]["close"] if len(series) >= 2 else None
    m1 = _nearest_before(series, (today - timedelta(days=30)).isoformat())
    ytd_ref = _nearest_before(series, f"{today.year}-01-01")
    return {
        "code": code,
        "date": latest.get("time"),
        "latest": close,
        "pct_1d": _pct(close, d1),
        "pct_1m": _pct(close, m1),
        "pct_ytd": _pct(close, ytd_ref),
        "liquidity_value": latest.get("value"),   # giá trị khớp phiên mới nhất
        "ok": True,
    }


def _load_seed() -> dict:
    """Đọc macro_seed.json (GDP/CPI/lãi suất cập nhật tay)."""
    p = config.MACRO_SEED_FILE
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out = {"as_of": raw.get("as_of"), "source": "seed"}
    for k in ("gdp_growth_yoy", "cpi_yoy", "policy_rate", "credit_growth_ytd"):
        if isinstance(raw.get(k), dict):
            out[k] = raw[k]
    return out


def build_context(force: bool = False) -> dict:
    """Sinh context.json (cache theo ngày). force=True để crawl lại ngay."""
    config.ensure_dirs()
    path = config.MACRO_FILE
    today = date.today().isoformat()
    if not force and path.exists():
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            if str(cached.get("as_of_date")) == today:
                return cached
        except Exception:
            pass

    sources: dict[str, str] = {}
    indexes = {}
    for code in _INDEXES:
        try:
            st = _index_stats(code)
            indexes[code] = st
            sources[code] = "vndirect" if st.get("ok") else "unavailable"
        except Exception as exc:
            indexes[code] = {"code": code, "latest": None, "ok": False}
            sources[code] = f"error: {str(exc)[:60]}"

    try:
        from . import vndirect
        fx = vndirect.exchange_rate()
        sources["fx"] = fx.get("source", "unavailable") if fx else "unavailable"
    except Exception as exc:
        fx = {}
        sources["fx"] = f"error: {str(exc)[:60]}"

    seed = _load_seed()
    sources["macro_indicators"] = "seed (cập nhật tay)" if seed else "unavailable"

    ctx = {
        "as_of_date": today,
        "generated_at": storage.now_iso(),
        "indexes": indexes,
        "fx": fx,
        "indicators": seed,
        "sources": sources,
    }
    storage.write_json(path, ctx)
    return ctx


def load_context() -> dict:
    """Đọc context đã cache (không crawl). Rỗng nếu chưa từng build."""
    p = config.MACRO_FILE
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
