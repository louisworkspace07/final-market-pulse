# -*- coding: utf-8 -*-
"""Collector — gom dữ liệu cơ bản + tin tức + vĩ mô cho Tổng quan Thị trường.

Nguồn (đều là output thật của các dự án thành phần):
- market.db (data-crawler): tin CBTT mới nhất toàn thị trường, sự kiện sắp tới,
  phân bố sức khỏe doanh nghiệp theo ngành.
- health_scores.json (pipeline EconoPulse): điểm Z''/F-score đã tính.
- macro_forecast.json / market_forecast.json: dự báo SARIMAX đã backtest.
"""
import json
import os
import sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(BASE, "..", ".."))
DATA_DIR = os.path.join(ROOT, "gateway", "static", "data")
TESTTOOL_AI_CACHE = os.path.normpath(
    os.path.join(ROOT, "..", "price-board", "temp_data", "ai_cache.json"))


def _connect_ro(db_path: str) -> sqlite3.Connection:
    try:
        from modules.common.db import connect_readonly
        return connect_readonly(db_path)
    except Exception:
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def _load(name):
    p = os.path.join(DATA_DIR, name)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return None


def collect_fundamentals(db_path: str) -> dict:
    out = {}

    # ---- vĩ mô + dự báo thị trường (đã có backtest)
    macro = _load("macro_forecast.json")
    if macro:
        g, c = macro["gdp_growth"], macro["cpi"]
        out["macro"] = {
            "gdp_forecast": {"year": g["forecast"]["years"][0],
                             "mean": g["forecast"]["mean"][0],
                             "range80": [g["forecast"]["lower"][0], g["forecast"]["upper"][0]]},
            "cpi_forecast": {"year": c["forecast"]["years"][0],
                             "mean": c["forecast"]["mean"][0],
                             "range80": [c["forecast"]["lower"][0], c["forecast"]["upper"][0]]},
            "gdp_last_actual": {y: v for y, v in sorted(g["history"].items())[-2:]},
            "source": "World Bank + SARIMAX (backtest công khai)",
        }
    mkt = _load("market_range.json")
    if mkt and mkt.get("available"):
        out["market_range"] = {
            "index_now": mkt["base"], "as_of": mkt.get("as_of"),
            "band": mkt["band"], "return_pct": mkt["return_pct"],
            "n_samples": mkt["n_samples"],
            "source": mkt.get("source", "VNINDEX (market_index)") +
                      " — dải thống kê 30 phiên, KHÔNG phải dự báo",
        }

    # ---- sức khỏe doanh nghiệp theo ngành
    health = _load("health_scores.json")
    if health:
        by_sector = {}
        con = _connect_ro(db_path)
        try:
            sectors = dict(con.execute(
                "select symbol, sector from companies where sector is not null"))
        finally:
            con.close()
        for cpy in health["companies"]:
            sec = sectors.get(cpy["symbol"], "Khác")
            b = by_sector.setdefault(sec, {"n": 0, "sum": 0, "danger": 0})
            if cpy["health_score"] is not None:
                b["n"] += 1
                b["sum"] += cpy["health_score"]
            if cpy.get("z_zone") == "Nguy hiểm":
                b["danger"] += 1
        out["health_by_sector"] = sorted(
            [{"sector": s, "n": b["n"],
              "avg_health": round(b["sum"] / b["n"], 1) if b["n"] else None,
              "n_danger": b["danger"]} for s, b in by_sector.items() if b["n"]],
            key=lambda x: -(x["avg_health"] or 0))
        top = [c for c in health["companies"] if c["health_score"]][:5]
        bot = [c for c in health["companies"] if c["health_score"]][-5:]
        out["health_top5"] = [{"symbol": c["symbol"], "score": c["health_score"],
                               "zone": c["z_zone"]} for c in top]
        out["health_bottom5"] = [{"symbol": c["symbol"], "score": c["health_score"],
                                  "zone": c["z_zone"]} for c in bot]
        out["health_source"] = "Altman Z'' + Piotroski F từ BCTC (market.db)"

    return out


def collect_news(db_path: str, limit: int = 15) -> list[dict]:
    """Tin CBTT mới nhất toàn thị trường — làm BẰNG CHỨNG cho phân tích reason."""
    con = _connect_ro(db_path)
    try:
        rows = con.execute(
            "select symbol, title, public_date from news "
            "order by public_date desc limit ?", (limit,)).fetchall()
        events = con.execute(
            "select symbol, event_name, title, public_date from events "
            "order by public_date desc limit ?", (10,)).fetchall()
    finally:
        con.close()
    news = [{"id": f"N{i+1}", "symbol": r[0], "title": r[1],
             "date": (r[2] or "")[:10], "type": "tin CBTT"}
            for i, r in enumerate(rows)]
    news += [{"id": f"E{i+1}", "symbol": r[0],
              "title": f"{r[1]}: {r[2]}", "date": (r[3] or "")[:10],
              "type": "sự kiện"}
             for i, r in enumerate(events)]
    return news


def collect_flow_outputs(db_path: str) -> tuple[list[dict], dict]:
    """Kết quả AI mà CÁC LUỒNG KHÁC đã chạy ra — dùng làm bằng chứng chuyên gia.

    - [TT-mã] : phân tích kỹ thuật kháng cự/hỗ trợ/cung cầu từng mã do luồng
      quét Gemini của app Bảng giá (Test tool) sinh ra → ai_cache.json.
    - [CD-mã] : phân tích cơ bản (rủi ro, định giá) từng mã do luồng P4 của
      app data-crawler sinh ra → bảng ai_analysis trong market.db.

    Trả về (out, meta). meta["skipped"] = số dòng bị bỏ (mock / parse lỗi) để
    bước 1 của job hiển thị minh bạch, không nuốt lặng.

    LƯU Ý minh bạch: KHÔNG đưa `investment_rating` (mua/bán/nắm giữ) vào bằng
    chứng — đó là khuyến nghị, dễ bị coi là tư vấn đầu tư. Bỏ luôn dòng
    `mode == "mock"` (dữ liệu giả) để AI không suy luận trên số bịa.
    """
    out = []
    skipped = 0
    # ĐÃ THÊM: độ phủ + độ cũ THẬT của nguồn TT- (quét Gemini app Bảng giá).
    # Trước đây collect_flow_outputs() gom cache này làm bằng chứng chuyên gia
    # mà không tính coverage — đo thật (28/07/2026): cache chỉ có 3/1.430 mã,
    # bản ghi cũ nhất 29 ngày, nhưng AI đọc [TT-mã] không có gì báo điều đó,
    # dễ suy diễn "đã quét kỹ thuật toàn thị trường" từ vài mã lẻ tẻ.
    tt_dates: list[str] = []

    # ---- Test tool: phân tích kỹ thuật S/R từng mã (Gemini web scan)
    if os.path.exists(TESTTOOL_AI_CACHE):
        try:
            with open(TESTTOOL_AI_CACHE, encoding="utf-8") as f:
                cache = json.load(f)
            for sym, item in cache.items():
                try:
                    d = json.loads(item["data"])
                except Exception:
                    skipped += 1
                    continue
                lines = "; ".join(
                    f"{l.get('label')} {l.get('price')}"
                    for l in d.get("chart_lines", []))
                ts = item.get("timestamp", "")[:10]
                if ts:
                    tt_dates.append(ts)
                out.append({
                    "id": f"TT-{sym}", "symbol": sym,
                    "type": "kỹ thuật (app Bảng giá)",
                    "date": ts,
                    "title": (f"S/R: {d.get('support_resistance', '')[:200]} · "
                              f"Mức giá: {lines} · "
                              f"Kết luận: {d.get('conclusion', '')[:200]}"),
                })
        except Exception:
            pass

    # ---- data-crawler: phân tích cơ bản từng mã (P4)
    # chỉ lấy mã có dữ liệu giá (nhóm theo dõi chính) để prompt không phình to
    con = _connect_ro(db_path)
    try:
        rows = con.execute(
            "select symbol, analysis, updated_at from ai_analysis "
            "where symbol in (select distinct symbol from price) limit 25").fetchall()
    finally:
        con.close()
    for sym, analysis, updated in rows:
        try:
            a = json.loads(analysis)
        except Exception:
            skipped += 1
            continue
        if a.get("mode") == "mock":     # dữ liệu giả — không dùng làm bằng chứng
            skipped += 1
            continue
        out.append({
            "id": f"CD-{sym}", "symbol": sym,
            "type": "cơ bản (app data-crawler)",
            "date": (updated or "")[:10],
            "title": (f"Rủi ro {a.get('risk_level')} · "
                      f"{a.get('valuation_comment', '')} "
                      f"{a.get('growth_comment', '')}").strip()[:280],
        })
    tt_dates.sort()
    return out, {
        "skipped": skipped,
        "tt_count": len(tt_dates),
        "tt_oldest": tt_dates[0] if tt_dates else None,
        "tt_newest": tt_dates[-1] if tt_dates else None,
    }


if __name__ == "__main__":
    db = os.path.join(ROOT, "..", "data-crawler", "database", "market.db")
    f = collect_fundamentals(db)
    print(json.dumps(f, ensure_ascii=False)[:800])
    n = collect_news(db, 5)
    print(json.dumps(n[:5], ensure_ascii=False, indent=1))
