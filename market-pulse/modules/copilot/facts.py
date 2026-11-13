# -*- coding: utf-8 -*-
"""Fact Collector — Trụ cột 1 (Minh bạch) của Decision Copilot.

Thu thập "sự kiện định lượng" (facts) từ tầng A cho một câu hỏi:
- Vĩ mô: dự báo GDP/CPI + backtest (macro_forecast.json)
- Thị trường: chỉ số + dự báo 30 phiên + RMSE (market_forecast.json)
- Doanh nghiệp: điểm sức khỏe, Z''-zone, ROA/ROE các mã được nhắc đến
  (health_scores.json + market.db: ai_analysis, news)

Mỗi fact có: id, label, value, source, updated_at, confidence.
LLM chỉ được trích các fact này (tham chiếu id) — không tự sinh số.
"""
import json
import os
import re
import sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(BASE, "..", ".."))
DATA_DIR = os.path.join(ROOT, "gateway", "static", "data")
DB_PATH = os.path.normpath(os.path.join(ROOT, "..", "data-crawler", "database", "market.db"))

CONF_HIGH = "Cao"        # số đo trực tiếp từ dữ liệu gốc
CONF_MED = "Trung bình"  # kết quả mô hình có backtest
CONF_LOW = "Thấp"        # suy luận định tính


def _load_json(name):
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _connect_ro(db_path: str) -> sqlite3.Connection:
    try:
        from modules.common.db import connect_readonly
        return connect_readonly(db_path)
    except Exception:
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def extract_symbols(question: str, db_path: str = DB_PATH) -> list[str]:
    """Tìm các mã cổ phiếu (3-4 ký tự in hoa) được nhắc trong câu hỏi."""
    candidates = set(re.findall(r"\b[A-Z]{3}[A-Z0-9]?\b", question.upper()))
    if not candidates:
        return []
    con = _connect_ro(db_path)
    try:
        q = "select symbol from companies where symbol in ({})".format(
            ",".join("?" * len(candidates)))
        found = [r[0] for r in con.execute(q, list(candidates))]
    finally:
        con.close()
    # loại từ tiếng Việt viết hoa vô tình khớp (GDP, CPI, HOSE...)
    blacklist = {"GDP", "CPI", "USD", "VND", "HOSE", "HNX", "AI"}
    return [s for s in found if s not in blacklist]


def collect_facts(question: str, portfolio: list[dict] | None = None) -> dict:
    """Trả về {facts: [...], symbols: [...]} cho câu hỏi + danh mục (nếu có)."""
    facts = []
    fid = [0]

    def add(label, value, source, updated_at, confidence):
        fid[0] += 1
        facts.append({"id": f"F{fid[0]}", "label": label, "value": value,
                      "source": source, "updated_at": updated_at,
                      "confidence": confidence})

    # ---------- vĩ mô ----------
    macro = _load_json("macro_forecast.json")
    if macro:
        g, c = macro["gdp_growth"], macro["cpi"]
        y = g["forecast"]["years"][0]
        add(f"Dự báo tăng trưởng GDP {y}",
            f"{g['forecast']['mean'][0]}% (KTC 80%: {g['forecast']['lower'][0]}–{g['forecast']['upper'][0]}%)",
            "SARIMAX trên World Bank 41 năm; backtest walk-forward MAE "
            f"{g['backtest']['mae_model']:.2f} điểm %", macro["updated_at"], CONF_MED)
        add(f"Dự báo lạm phát CPI {y}",
            f"{c['forecast']['mean'][0]}% (KTC 80%: {c['forecast']['lower'][0]}–{c['forecast']['upper'][0]}%)",
            "SARIMAX trên World Bank", macro["updated_at"], CONF_MED)
        last_y = max(g["history"], key=int)
        add(f"GDP thực tế năm {last_y}", f"{g['history'][last_y]}%",
            "World Bank Open Data (NY.GDP.MKTP.KD.ZG)", macro["updated_at"], CONF_HIGH)

    # ---------- chế độ tiền tệ [M-REG] (PILLAR-M · M3) ----------
    # Trạng thái MÔI TRƯỜNG theo ngưỡng công khai — dữ kiện, không phải nhận định.
    try:
        from modules.macro_regime.detector import detect
        reg = detect(DATA_DIR)
        if reg.get("available"):
            comp = " · ".join(
                f"{c['label']} {c['value']}{c['unit']}"
                for c in reg["components"] if c.get("value") is not None)
            add("Chế độ tiền tệ (đèn 3 màu — M-REG)",
                f"{reg['state']} (điểm {reg['score']:+d}/±3, tin cậy dữ liệu "
                f"{reg['confidence_pct']}%) — {comp}",
                "modules/macro_regime · ngưỡng công khai tại /methodology#regime",
                reg.get("updated_at"), CONF_MED)
    except Exception:
        pass  # thiếu macro_plus.json → copilot vẫn chạy với các facts khác

    # ---------- thị trường (dải thống kê, KHÔNG dự báo) ----------
    mkt = _load_json("market_range.json")
    if mkt and mkt.get("available"):
        rp, band = mkt["return_pct"], mkt["band"]
        add("VNINDEX hiện tại", f"{mkt['base']} điểm",
            mkt.get("source", "market_index · VNDirect"), mkt.get("as_of"), CONF_HIGH)
        add("Dải thống kê lợi suất 30 phiên (lịch sử — không phải dự báo)",
            f"P5 {band['p5']} / P25 {band['p25']} / trung vị {band['p50']} / "
            f"P75 {band['p75']} / P95 {band['p95']} điểm "
            f"(lợi suất {rp['p5']}%…+{rp['p95']}%)",
            f"Phân phối {mkt['n_samples']} đoạn 30 phiên lịch sử VNINDEX — thống kê mô tả",
            mkt["updated_at"], CONF_HIGH)

    # ---------- mã cụ thể trong câu hỏi + danh mục ----------
    symbols = extract_symbols(question)
    if portfolio:
        symbols += [h["symbol"].strip().upper() for h in portfolio
                    if h.get("symbol")]
    symbols = list(dict.fromkeys(symbols))[:8]

    health = _load_json("health_scores.json")
    hmap = {c["symbol"]: c for c in health["companies"]} if health else {}
    con = _connect_ro(DB_PATH)
    try:
        for s in symbols:
            h = hmap.get(s)
            if h:
                add(f"{s} — điểm sức khỏe tổng hợp",
                    f"{h['health_score']}/100 · Z''={h['z_score']} ({h['z_zone']}) · "
                    f"F-score {h['f_score']}/{h['f_max']} · ROA {h['roa']}% · ROE {h['roe']}%",
                    f"BCTC năm {h['year']} (market.db) → Altman Z'' + Piotroski F",
                    health.get("updated_at"), CONF_MED)
            row = con.execute(
                "select analysis from ai_analysis where symbol=?", (s,)).fetchone()
            if row:
                try:
                    a = json.loads(row[0])
                    m = a.get("metrics", {})
                    v = m.get("valuation", {})
                    add(f"{s} — định giá & tăng trưởng",
                        f"P/E {v.get('pe'):.1f} · P/B {v.get('pb'):.1f} · "
                        f"{a.get('growth_comment', '')} · Định giá: {m.get('valuation_verdict')}",
                        f"ai_analysis (chế độ {a.get('mode')}) từ BCTC crawl",
                        a.get("generated_at", "")[:10], CONF_MED)
                except Exception:
                    pass
            news = con.execute(
                "select title, public_date from news where symbol=? "
                "order by public_date desc limit 2", (s,)).fetchall()
            for title, d in news:
                add(f"{s} — tin công bố thông tin", title,
                    "market.db · tin CBTT (crawl vnstock)", (d or "")[:10], CONF_HIGH)
    finally:
        con.close()

    return {"facts": facts, "symbols": symbols}
