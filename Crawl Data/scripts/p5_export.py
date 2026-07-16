"""P5 — Xuất JSON tổng hợp cho web so sánh.

Đọc SQLite + JSON công ty → web/data/companies.json (bảng so sánh)
và web/data/detail/<MÃ>.json (chi tiết từng công ty).

  python -m scripts.p5_export                 # xuất lại toàn bộ (~12 phút)
  python -m scripts.p5_export --sym FPT       # chỉ 1 mã (~1 giây)
  python -m scripts.p5_export --sym FPT,VNM

VÌ SAO CÓ --sym: trang /app/ đọc file tĩnh, nên phân tích xong 1 mã mà không
xuất lại thì giao diện vẫn hiện dữ liệu cũ. Xuất lại cả 576 mã chỉ vì 1 mã đổi
là lãng phí — chế độ 1 mã ghi đè đúng file chi tiết của mã đó rồi VÁ dòng tương
ứng trong companies.json (giữ nguyên các dòng khác).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, storage

WEB_DATA = config.ROOT / "web" / "data"
DETAIL_DIR = WEB_DATA / "detail"

CF_KEYS = {
    "net_cash_inflows_outflows_from_operating_activities": "cf_operating",
    "net_cash_flows_from_investing_activities": "cf_investing",
    "net_cash_flows_from_financing_activities": "cf_financing",
    "net_increase_decrease_in_cash_and_cash_equivalents": "cf_net",
}


def latest_cashflow(conn, symbol: str) -> dict:
    """Lấy các chỉ tiêu dòng tiền chính của kỳ gần nhất."""
    out: dict = {"period": None}
    rows = conn.execute(
        """SELECT item_id, period, value FROM financials
           WHERE symbol=? AND statement='cash_flow' AND item_id IN ({})
           ORDER BY period DESC""".format(",".join("?" * len(CF_KEYS))),
        (symbol, *CF_KEYS.keys()),
    ).fetchall()
    if not rows:
        return out
    latest = rows[0][1]
    out["period"] = latest
    for item_id, period, value in rows:
        if period == latest:
            out[CF_KEYS[item_id]] = value
    return out


def _items(sym: str, sub: str, name: str, limit: int = 0) -> list:
    p = config.COMPANIES_DIR / sym / sub / f"{name}.json"
    if not p.exists():
        return []
    try:
        rows = json.loads(p.read_text(encoding="utf-8")).get("items", [])
        return rows[:limit] if limit else rows
    except Exception:
        return []


def _merge_table(rows: list[dict]) -> list[dict]:
    """Vá các dòng vừa xuất vào companies.json cũ, giữ nguyên phần còn lại."""
    old = []
    p = WEB_DATA / "companies.json"
    if p.exists():
        try:
            old = json.loads(p.read_text(encoding="utf-8")).get("companies", [])
        except Exception:
            old = []
    by_sym = {r.get("symbol"): r for r in old}
    by_sym.update({r["symbol"]: r for r in rows})
    return sorted(by_sym.values(), key=lambda r: r.get("symbol") or "")


def main(only: list[str] | None = None) -> None:
    DETAIL_DIR.mkdir(parents=True, exist_ok=True)
    conn = storage.connect()

    syms = [r[0] for r in conn.execute(
        "SELECT symbol FROM ai_analysis ORDER BY symbol")]
    if only:
        want = {s.strip().upper() for s in only if s.strip()}
        missing = want - set(syms)
        syms = [s for s in syms if s in want]
        if missing:
            print(f"  [!] Chưa có phân tích, bỏ qua: {', '.join(sorted(missing))}")
        if not syms:
            conn.close()
            print("→ Không có mã nào để xuất.")
            return
    print(f"→ Xuất {len(syms)} công ty đã phân tích")

    table = []
    for sym in syms:
        comp = conn.execute(
            "SELECT organ_name, sector, market_cap, current_price FROM companies WHERE symbol=?",
            (sym,)).fetchone() or ("", "", None, None)
        analysis = json.loads(conn.execute(
            "SELECT analysis FROM ai_analysis WHERE symbol=?", (sym,)).fetchone()[0])
        # PHÁP LÝ (Luật CK 2019 Điều 71): `investment_rating`/`verdict` mang nội
        # dung kết luận đầu tư — analyzer.py đã ép investment_rating=None nhưng
        # KHÓA vẫn tồn tại trong JSON, và verdict luôn có nội dung thật. detail/
        # <mã>.json từng nhúng nguyên `analysis` (bao gồm 2 khoá này) vào file
        # tĩnh công khai qua /app/<file>.json — web/user.html + index.html chỉ ẩn
        # ở tầng hiển thị (đã sửa) nhưng payload gốc vẫn phát tán. Lọc tại nguồn
        # để mọi trang đọc từ đây (kể cả trang mới sau này) không thể vô tình hiện lại.
        for _k in ("investment_rating", "verdict"):
            analysis.pop(_k, None)
        cf = latest_cashflow(conn, sym)

        m = analysis.get("metrics", {}) or {}
        val = m.get("valuation", {}) or {}
        row = {
            "symbol": sym,
            "name": comp[0],
            "sector": comp[1],
            "market_cap": comp[2],
            "current_price": comp[3],
            "risk_level": analysis.get("risk_level"),
            "health_score": m.get("health_score"),
            "fscore": m.get("fscore"),
            "valuation_verdict": m.get("valuation_verdict"),
            "pe": val.get("pe"), "pb": val.get("pb"),
            "roe": (m.get("profitability") or {}).get("roe"),
            "cf_operating": cf.get("cf_operating"),
            "cf_period": cf.get("period"),
            "mode": analysis.get("mode"),
        }
        table.append(row)

        from src.analyzer import _weight
        news = [dict(zip(("title", "date", "link"), r)) for r in conn.execute(
            "SELECT title, public_date, source_link FROM news WHERE symbol=? "
            "ORDER BY public_date DESC LIMIT 12", (sym,))]
        for n in news:
            n["weight"] = _weight(n.get("title"))

        # sự kiện (CBTT/cổ tức) — dùng làm marker mốc-giá trên biểu đồ
        events = []
        for r in conn.execute(
            "SELECT title, event_name, public_date FROM events WHERE symbol=? "
            "ORDER BY public_date DESC LIMIT 20", (sym,)):
            t = r[0] or r[1]
            events.append({"title": t, "kind": r[1], "date": r[2],
                           "weight": _weight(t)})

        # giá: lấy chuỗi close gần nhất (tối đa 260 phiên) cho biểu đồ
        price = [dict(zip(("time", "close", "volume"), r)) for r in conn.execute(
            "SELECT time, close, volume FROM price WHERE symbol=? ORDER BY time", (sym,))]
        price = price[-260:]

        # Bộ chỉ tiêu ĐÚNG THEO NGÀNH + chất lượng lợi nhuận + dải định giá lịch sử
        # — tính TƯƠI (thuần Python, không cần AI) để card hiện ngay cả khi chưa P4.
        sector_model = earnings = val_band = None
        try:
            from src import fundamentals
            fm = fundamentals.compute(sym, sector=comp[1])
            sector_model = fm.get("sector_model")
            earnings = fm.get("earnings_quality")
            val_band = fm.get("valuation_band")
        except Exception as exc:
            print(f"  [!] {sym} sector_model lỗi (bỏ qua): {str(exc)[:70]}")

        detail = {**row, "cashflow": cf, "analysis": analysis, "news": news,
                  "events": events, "price": price,
                  "sector_model": sector_model, "earnings_quality": earnings,
                  "valuation_band": val_band,
                  "officers": _items(sym, "ownership", "officers", 12),
                  "shareholders": _items(sym, "ownership", "shareholders", 12),
                  "subsidiaries": _items(sym, "ownership", "subsidiaries", 15),
                  "affiliate": _items(sym, "ownership", "affiliate", 15)}
        (DETAIL_DIR / f"{sym}.json").write_text(
            json.dumps(detail, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8")

    companies = _merge_table(table) if only else table
    (WEB_DATA / "companies.json").write_text(
        json.dumps({"generated_at": storage.now_iso(), "companies": companies},
                   ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    conn.close()
    print(f"✓ web/data/companies.json ({len(companies)} dòng) + {len(syms)} file chi tiết")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Xuất JSON cho web (toàn bộ hoặc từng mã)")
    ap.add_argument("--sym", default="",
                    help="chỉ xuất các mã này, phân tách bằng dấu phẩy (vd: FPT,VNM)")
    args = ap.parse_args()
    main([s for s in args.sym.replace(";", ",").split(",") if s.strip()] or None)
