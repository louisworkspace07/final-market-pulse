"""Nguồn dữ liệu VNDirect (API công khai).

Đã xác minh hoạt động:
- Giá lịch sử / snapshot (OHLCV + trần/sàn/TC + KL + thay đổi)  -> stock_prices
- Định giá (P/E, P/B, P/S, cổ tức, vốn hóa, số CP)               -> ratios/latest
- Hồ sơ công ty                                                  -> company_profiles

Host: api-finfo.vndirect.com.vn (finfo-api cũ bị chặn).
"""
from __future__ import annotations

import requests

BASE = "https://api-finfo.vndirect.com.vn/v4/"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://banggia.vndirect.com.vn/",
    "Accept": "application/json",
}
TIMEOUT = 12


def _get(path: str, params: dict | None = None) -> dict:
    r = requests.get(BASE + path, params=params, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------- giá

def price_history(symbol: str, start: str, end: str) -> list[dict]:
    """OHLCV ngày trong khoảng [start, end] (YYYY-MM-DD), tăng dần theo ngày."""
    out, page = [], 1
    while True:
        j = _get("stock_prices", {
            "q": f"code:{symbol.upper()}~date:gte:{start}~date:lte:{end}",
            "sort": "date", "size": 1000, "page": page,
        })
        data = j.get("data", [])
        for d in data:
            out.append({
                "time": d.get("date"),
                "open": d.get("open"), "high": d.get("high"),
                "low": d.get("low"), "close": d.get("close"),
                "volume": d.get("nmVolume"),
            })
        if page >= j.get("totalPages", 1) or not data:
            break
        page += 1
    return out


def quotes(symbols: list[str]) -> list[dict]:
    """Snapshot giá mới nhất cho nhiều mã: giá, TC/trần/sàn, KL, thay đổi.

    Lưu ý: REST công khai KHÔNG có dư mua/bán 3 bậc (bid/ask depth).
    """
    if not symbols:
        return []
    codes = ",".join(s.upper() for s in symbols)
    j = _get("stock_prices", {
        "q": f"code:{codes}~date:gte:2000-01-01",
        "sort": "date:desc", "size": len(symbols) * 2,
    })
    seen, rows = set(), []
    for d in j.get("data", []):
        c = d.get("code")
        if c in seen:
            continue
        seen.add(c)
        ref = d.get("basicPrice")
        close = d.get("close")
        rows.append({
            "symbol": c, "ref": _x1000(ref),
            "ceiling": _x1000(d.get("ceilingPrice")),
            "floor": _x1000(d.get("floorPrice")),
            "match_price": _x1000(close), "open": _x1000(d.get("open")),
            "high": _x1000(d.get("high")), "low": _x1000(d.get("low")),
            "avg": _x1000(d.get("average")),
            "change": _x1000(d.get("change")), "pct": d.get("pctChange"),
            "total_vol": d.get("nmVolume"), "date": d.get("date"),
        })
    return rows


def _x1000(v):
    """VNDirect trả giá theo nghìn đồng (76.5) → đổi về đồng để đồng bộ vnstock."""
    try:
        return float(v) * 1000 if v is not None else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- định giá

_RATIO_MAP = {
    "PRICE_TO_EARNINGS": "pe", "PRICE_TO_BOOK": "pb", "PRICE_TO_SALES": "ps",
    "DIVIDEND_YIELD": "dividend_yield", "MARKETCAP": "market_cap",
    "OUTSTANDING_SHARES": "shares",
}


def valuation(symbol: str) -> dict:
    j = _get("ratios/latest", {
        "order": "reportDate", "where": f"code:{symbol.upper()}",
        "filter": "ratioCode:" + ",".join(_RATIO_MAP),
        "fields": "ratioCode,value", "size": 50,
    })
    out: dict = {}
    for d in j.get("data", []):
        key = _RATIO_MAP.get(d.get("ratioCode"))
        if key:
            out[key] = d.get("value")
    # cổ tức VNDirect ở dạng 0.026 → %; pe/pb giữ nguyên
    if out.get("dividend_yield") is not None and out["dividend_yield"] < 1.5:
        out["dividend_yield"] *= 100
    return out


# ---------------------------------------------------------------- hồ sơ

def profile(symbol: str) -> dict:
    j = _get("company_profiles", {"q": f"code:{symbol.upper()}"})
    data = j.get("data", [])
    return data[0] if data else {}


# ---------------------------------------------------------------- chỉ số thị trường

def index_history(code: str, start: str, end: str) -> list[dict]:
    """Lịch sử điểm số + thanh khoản của chỉ số (VNINDEX/VN30/HNXINDEX...).

    Cùng endpoint stock_prices — chỉ số cũng là 1 "code" trên VNDirect.
    Trả list {time, close, volume, value} tăng dần theo ngày.
    """
    out, page = [], 1
    while True:
        # Chỉ số nằm ở endpoint vnmarket_prices (KHÁC stock_prices của cổ phiếu).
        j = _get("vnmarket_prices", {
            "q": f"code:{code.upper()}~date:gte:{start}~date:lte:{end}",
            "sort": "date", "size": 1000, "page": page,
        })
        data = j.get("data", [])
        for d in data:
            out.append({
                "time": d.get("date"),
                "close": d.get("close"),
                "volume": d.get("accumulatedVol"),
                "value": d.get("accumulatedVal"),   # giá trị giao dịch (thanh khoản)
            })
        if page >= j.get("totalPages", 1) or not data:
            break
        page += 1
    out.sort(key=lambda r: str(r.get("time")))   # endpoint trả giảm dần → ép tăng dần
    return out


# ---------------------------------------------------------------- tỷ giá

def exchange_rate() -> dict:
    """Tỷ giá USD/VND từ API công khai Vietcombank (mua/bán chuyển khoản).

    Trả {usd_buy, usd_sell, as_of, source} hoặc {} nếu không lấy được.
    Endpoint có thể đổi/chặn → phía gọi phải chịu được dict rỗng.
    """
    try:
        r = requests.get("https://www.vietcombank.com.vn/api/exchangerates",
                         params={"date": "now"}, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        j = r.json()
        for d in j.get("Data", []):
            if (d.get("currencyCode") or "").upper() == "USD":
                return {
                    "usd_buy": _to_float(d.get("transfer") or d.get("cash")),
                    "usd_sell": _to_float(d.get("sell")),
                    "as_of": j.get("Date") or j.get("UpdatedDate"),
                    "source": "vietcombank",
                }
    except Exception:
        pass
    return {}


def _to_float(v):
    try:
        return float(str(v).replace(",", "")) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None
