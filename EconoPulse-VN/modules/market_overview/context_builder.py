# -*- coding: utf-8 -*-
"""Context Builder — tầng dữ liệu CHI TIẾT cho phân tích Tổng quan Thị trường.

Vấn đề đang giải: collector.py chỉ múc lớp mỏng (điểm health tổng hợp, title tin).
Trong khi market.db có sẵn 145k dòng BCTC, 1.9k tin kèm short_content/link,
1.1k sự kiện kèm cổ tức. Module này đào sâu các nguồn ĐÃ CÓ (ưu tiên thuần DB,
không crawl mới) thành các "gói ngữ cảnh" theo chủ đề, khớp 7 phần hội thoại CDP.

Mỗi gói kèm metadata {source, as_of, stale} để UI gắn sourceTag() và AI biết
độ tươi dữ liệu. Gói lỗi/rỗng có cờ riêng, KHÔNG làm chết cả pipeline.

Bước 1 (file này, thuần DB — không cần mạng):
- fund_detail(): BCTC từng mã — doanh thu & LNST 4 quý + YoY, biên ròng, ROE/ROA, Nợ/VCSH.
- news_detailed(): tin kèm short_content + source_link (AI đọc nội dung, UI click link gốc).
- dividend_events(): sự kiện cổ tức kèm value_per_share, ưu tiên lịch chốt quyền sắp tới.
- peer_comparison(): trung vị P/E, P/B, ROE theo ngành (tái dùng Crawl Data/src/peers.py).
"""
import datetime as _dt
import os
import re
import sqlite3
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(BASE, "..", ".."))
CRAWL_SRC = os.path.normpath(os.path.join(ROOT, "..", "Crawl Data"))

# peers.py chỉ dùng stdlib + nhận sqlite connection → import chéo an toàn.
if CRAWL_SRC not in sys.path:
    sys.path.insert(0, CRAWL_SRC)
try:
    from src import peers as _peers          # type: ignore
except Exception:
    _peers = None
try:
    from src import news_rss as _news_rss    # type: ignore
except Exception:
    _news_rss = None
try:
    from src import macro as _macro          # type: ignore
except Exception:
    _macro = None

MACRO_CONTEXT_JSON = os.path.join(CRAWL_SRC, "data", "macro", "context.json")


def _today() -> _dt.date:
    return _dt.date.today()


def _iso_date(s: str | None) -> str:
    return (s or "")[:10]


# period trong bảng financials: "2024" (năm) hoặc "2024-Q1" (quý).
_QUARTER_RE = re.compile(r"^(\d{4})\D+([1-4])")
_YEAR_RE = re.compile(r"^(\d{4})\s*$")


def _period_key(period: str) -> int:
    """Khóa sắp xếp số: năm=YYYY, quý=YYYY*10+Q (mới nhất = lớn nhất)."""
    p = str(period).strip()
    mq = _QUARTER_RE.match(p)
    if mq:
        return int(mq.group(1)) * 10 + int(mq.group(2))
    my = _YEAR_RE.match(p)
    if my:
        return int(my.group(1))
    return -1


def _is_quarter(period: str) -> bool:
    return bool(_QUARTER_RE.match(str(period).strip()))


def _fmt_bn(v) -> str:
    """Đổi VND sang tỷ đồng gọn (145276 dòng dùng đơn vị đồng)."""
    if v is None:
        return "n/a"
    try:
        return f"{v / 1e9:,.0f} tỷ"
    except (TypeError, ValueError):
        return "n/a"


def _yoy(cur, prev) -> str:
    if cur is None or prev is None or prev == 0:
        return "n/a"
    return f"{(cur / prev - 1) * 100:+.1f}%"


def _income_series(conn, symbol: str, item_id: str, quarterly: bool):
    """Chuỗi (period, value) của 1 chỉ tiêu income_statement, sắp mới→cũ."""
    rows = conn.execute(
        """SELECT period, value FROM financials
           WHERE symbol=? AND statement='income_statement' AND item_id=?
             AND value IS NOT NULL""", (symbol, item_id)).fetchall()
    rows = [(p, v) for p, v in rows if _is_quarter(p) == quarterly]
    rows.sort(key=lambda pv: _period_key(pv[0]), reverse=True)
    return rows


def _latest_ratio(conn, symbol: str, item_id: str):
    """Giá trị tỷ số mới nhất (ưu tiên kỳ năm, fallback quý)."""
    rows = conn.execute(
        """SELECT period, value FROM financials
           WHERE symbol=? AND statement='ratio' AND item_id=? AND value IS NOT NULL""",
        (symbol, item_id)).fetchall()
    if not rows:
        return None
    years = [(p, v) for p, v in rows if not _is_quarter(p)]
    quarters = [(p, v) for p, v in rows if _is_quarter(p)]
    chosen = years or quarters
    if not chosen:
        return None
    chosen.sort(key=lambda pv: _period_key(pv[0]))
    return chosen[-1][1]


def _norm_pct(v):
    """Chuẩn hóa tỷ lệ về %: một số nguồn lưu 0.22 thay vì 22."""
    if v is None:
        return None
    return v * 100 if -1.5 < v < 1.5 else v


def fund_detail(conn, symbol: str) -> dict:
    """BCTC chi tiết 1 mã: doanh thu & LNST 4 quý gần nhất + YoY năm, biên ròng,
    ROE/ROA, Nợ/VCSH. Chỉ đọc market.db — kiểm chứng được, không AI."""
    net_sales_q = _income_series(conn, symbol, "net_sales", quarterly=True)[:4]
    profit_q = _income_series(conn, symbol, "net_profit_loss_after_tax", quarterly=True)[:4]
    net_sales_y = _income_series(conn, symbol, "net_sales", quarterly=False)
    profit_y = _income_series(conn, symbol, "net_profit_loss_after_tax", quarterly=False)

    rev_yoy = _yoy(net_sales_y[0][1], net_sales_y[1][1]) if len(net_sales_y) >= 2 else "n/a"
    lnst_yoy = _yoy(profit_y[0][1], profit_y[1][1]) if len(profit_y) >= 2 else "n/a"

    return {
        "symbol": symbol,
        "revenue_quarters": [{"period": p, "value_bn": _fmt_bn(v)} for p, v in net_sales_q],
        "profit_quarters": [{"period": p, "value_bn": _fmt_bn(v)} for p, v in profit_q],
        "revenue_yoy_year": rev_yoy,
        "profit_yoy_year": lnst_yoy,
        "net_margin_pct": _norm_pct(_latest_ratio(conn, symbol, "net_margin")),
        "roe_pct": _norm_pct(_latest_ratio(conn, symbol, "roe")),
        "roa_pct": _norm_pct(_latest_ratio(conn, symbol, "roa")),
        "debt_to_equity": _latest_ratio(conn, symbol, "debt_to_equity"),
        "pe": _latest_ratio(conn, symbol, "pe_ratio"),
        "pb": _latest_ratio(conn, symbol, "pb_ratio"),
        "ev_ebitda": _latest_ratio(conn, symbol, "ev_to_ebitda"),
    }


def _priced_symbols(conn) -> list[str]:
    return [r[0] for r in conn.execute("SELECT DISTINCT symbol FROM price")]


def fundamentals_pack(db_path: str, symbols: list[str] | None = None) -> dict:
    """Gói BCTC + peer cho các mã có giá (mặc định) hoặc danh sách chỉ định."""
    conn = sqlite3.connect(db_path)
    try:
        syms = symbols or _priced_symbols(conn)
        details = [fund_detail(conn, s) for s in syms]
        peers = {}
        if _peers is not None:
            for s in syms:
                try:
                    peers[s] = _peers.compute(conn, s)
                except Exception:
                    pass
    finally:
        conn.close()
    return {
        "details": details,
        "peers": peers,
        "meta": {"source": "market.db · financials (BCTC crawl vnstock)",
                 "as_of": _db_as_of(db_path), "stale": False,
                 "peer_engine": "Crawl Data/src/peers.py" if _peers else None},
    }


def news_detailed(db_path: str, limit: int = 30) -> dict:
    """Tin CBTT mới nhất kèm short_content (cắt 200) + source_link → bằng chứng [N..]."""
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT symbol, title, short_content, source_link, public_date "
            "FROM news ORDER BY public_date DESC LIMIT ?", (limit,)).fetchall()
        latest = conn.execute("SELECT max(public_date) FROM news").fetchone()[0]
    finally:
        conn.close()
    items = [{"id": f"N{i+1}", "symbol": r[0], "title": r[1],
              "summary": (r[2] or "")[:200], "link": r[3] or "",
              "date": _iso_date(r[4]), "type": "tin CBTT"}
             for i, r in enumerate(rows)]
    return {"items": items,
            "meta": {"source": "market.db · news (crawl vnstock)",
                     "as_of": _iso_date(latest), "stale": _is_stale(latest, 7)}}


def dividend_events(db_path: str, limit: int = 15) -> dict:
    """Sự kiện kèm cổ tức tiền mặt (value_per_share); tách nhóm sắp tới (lịch
    chốt quyền tương lai — dữ kiện cho 'theo dõi tuần tới') và gần đây."""
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT symbol, event_name, title, public_date, value_per_share "
            "FROM events ORDER BY public_date DESC LIMIT ?", (limit * 3,)).fetchall()
    finally:
        conn.close()
    today = _today().isoformat()
    upcoming, recent = [], []
    for i, r in enumerate(rows):
        d = _iso_date(r[3])
        item = {"id": f"E{i+1}", "symbol": r[0], "event": r[1],
                "title": r[2], "date": d,
                "value_per_share": r[4]}
        (upcoming if d >= today else recent).append(item)
    return {"upcoming": upcoming[:limit], "recent": recent[:limit],
            "meta": {"source": "market.db · events (crawl vnstock)",
                     "as_of": today, "stale": False}}


def peer_comparison(db_path: str, symbols: list[str]) -> dict:
    """Trung vị P/E, P/B, ROE… theo ngành + vị thế từng mã (tái dùng peers.py)."""
    if _peers is None:
        return {"available": False, "reason": "peers.py không import được",
                "by_symbol": {}}
    conn = sqlite3.connect(db_path)
    try:
        out = {}
        for s in symbols:
            try:
                out[s] = _peers.compute(conn, s)
            except Exception as e:
                out[s] = {"error": str(e)[:120]}
    finally:
        conn.close()
    return {"available": True, "by_symbol": out,
            "meta": {"source": "market.db · peers.py (trung vị ngành)",
                     "as_of": _db_as_of(db_path), "stale": False}}


def _db_as_of(db_path: str) -> str:
    try:
        return _dt.datetime.fromtimestamp(
            os.path.getmtime(db_path)).isoformat(timespec="seconds")
    except OSError:
        return ""


def _is_stale(date_str: str | None, days: int) -> bool:
    d = _iso_date(date_str)
    if not d:
        return True
    try:
        return (_today() - _dt.date.fromisoformat(d)).days > days
    except ValueError:
        return False


# ==================== Bước 2 — nối nguồn sống đã có module ====================
def macro_pack() -> dict:
    """Vĩ mô & chỉ số THẬT: VNINDEX/VN30 (%1D/%1M/YTD + thanh khoản), tỷ giá,
    GDP/CPI. Đọc cache context.json (macro.py cập nhật theo ngày); nếu thiếu/cũ
    → thử build_context() (gọi vndirect). Lỗi mạng → trả gói rỗng có cờ, KHÔNG
    làm chết pipeline. Nhãn nguồn 'seed' của GDP/CPI giữ nguyên để minh bạch."""
    import json
    ctx, err = None, None
    if os.path.exists(MACRO_CONTEXT_JSON):
        try:
            with open(MACRO_CONTEXT_JSON, encoding="utf-8") as f:
                ctx = json.load(f)
        except Exception as e:
            err = f"đọc context.json lỗi: {str(e)[:100]}"
    stale = _is_stale(ctx.get("as_of_date") if ctx else None, 1)
    # cache cũ (>1 ngày) hoặc thiếu → thử làm mới qua macro.build_context
    if (ctx is None or stale) and _macro is not None:
        try:
            ctx = _macro.build_context()
            stale = _is_stale(ctx.get("as_of_date"), 1)
        except Exception as e:
            err = err or f"build_context lỗi: {str(e)[:100]}"
    if ctx is None:
        return {"available": False, "reason": err or "không có dữ liệu vĩ mô",
                "indexes": {}, "fx": {}, "indicators": {}}
    return {
        "available": True,
        "indexes": ctx.get("indexes", {}),
        "fx": ctx.get("fx", {}),
        "indicators": ctx.get("indicators", {}),
        "meta": {"source": "Crawl Data macro (VNDirect index + Vietcombank FX + GSO seed)",
                 "as_of": ctx.get("as_of_date", ""), "stale": stale,
                 "error": err},
    }


def rss_pack(db_path: str, symbols: list[str], per_symbol: int = 3) -> dict:
    """Tin báo chí Google News RSS cho các mã nổi bật → bằng chứng [R-mã].
    Nguồn ngoài, phụ thuộc mạng → timeout 10s, lỗi trả rỗng (đúng thiết kế module)."""
    if _news_rss is None:
        return {"available": False, "reason": "news_rss.py không import được", "items": []}
    conn = sqlite3.connect(db_path)
    try:
        names = dict(conn.execute(
            "SELECT symbol, organ_name FROM companies WHERE symbol in ({})".format(
                ",".join("?" * len(symbols))), symbols)) if symbols else {}
    finally:
        conn.close()
    items, n_ok = [], 0
    for s in symbols:
        try:
            arts = _news_rss.fetch(s, names.get(s, ""), limit=per_symbol)
        except Exception:
            arts = []
        if arts:
            n_ok += 1
        for a in arts:
            items.append({"id": f"R-{s}", "symbol": s, "title": a["title"],
                          "link": a.get("link", ""), "date": a.get("public_date", "")[:16],
                          "press": a.get("source", ""), "type": "báo chí (RSS)"})
    return {"available": True, "items": items,
            "meta": {"source": "Google News RSS (news_rss.py)",
                     "as_of": _today().isoformat(),
                     "stale": False, "n_symbols_ok": n_ok}}


if __name__ == "__main__":
    import json
    db = os.path.normpath(os.path.join(CRAWL_SRC, "database", "market.db"))
    print("DB:", db, "exists:", os.path.exists(db))

    conn = sqlite3.connect(db)
    syms = _priced_symbols(conn)
    conn.close()
    print(f"\n{len(syms)} mã có giá: {syms[:10]}...")

    sample = syms[0] if syms else "FPT"
    conn = sqlite3.connect(db)
    print(f"\n=== fund_detail({sample}) ===")
    print(json.dumps(fund_detail(conn, sample), ensure_ascii=False, indent=1))
    conn.close()

    nd = news_detailed(db, 5)
    print(f"\n=== news_detailed (meta: {nd['meta']}) ===")
    for n in nd["items"][:3]:
        print(f"  [{n['id']}] {n['symbol']} {n['date']}: {n['title'][:60]}")
        print(f"       link={n['link'][:60]} | summary={n['summary'][:60]}")

    dv = dividend_events(db, 5)
    print(f"\n=== dividend_events: {len(dv['upcoming'])} sắp tới, {len(dv['recent'])} gần đây ===")

    pc = peer_comparison(db, [sample])
    print(f"\n=== peer_comparison({sample}) ===")
    print(json.dumps(pc["by_symbol"].get(sample, {}), ensure_ascii=False, indent=1))

    mp = macro_pack()
    print(f"\n=== macro_pack (available={mp.get('available')}) ===")
    if mp.get("available"):
        vni = mp["indexes"].get("VNINDEX", {})
        print(f"  VNINDEX {vni.get('latest')} · 1D {vni.get('pct_1d'):+.2f}% · "
              f"YTD {vni.get('pct_ytd'):+.2f}% · meta as_of={mp['meta']['as_of']} stale={mp['meta']['stale']}")
        print(f"  FX USD/VND bán: {mp['fx'].get('usd_sell')} · GDP: {mp['indicators'].get('gdp_growth_yoy',{}).get('value')}%")

    print("\n=== rss_pack (mạng — có thể rỗng nếu offline) ===")
    rp = rss_pack(db, [sample], per_symbol=2)
    print(f"  available={rp.get('available')} · items={len(rp.get('items', []))} · "
          f"meta={rp.get('meta', {}).get('n_symbols_ok', '—')} mã có tin")
