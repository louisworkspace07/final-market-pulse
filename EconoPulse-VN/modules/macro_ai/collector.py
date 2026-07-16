# -*- coding: utf-8 -*-
"""Đóng gói dữ liệu vĩ mô thành text block cho AI (C2).

Gộp: macro_plus (WB + FX + vàng/dầu + seed) + macro_forecast (GDP/CPI SARIMAX)
+ VNINDEX 3 chỉ số + 12 tin [M..] (id hợp lệ để AI trích dẫn). Mỗi nguồn kèm TUỔI
dữ liệu để AI tự nêu độ tươi. Trả (text_block, valid_ids, meta) — valid_ids là tập
[M..] để engine validate citation, tránh AI bịa nguồn.
"""
from __future__ import annotations

import json
import os
import sqlite3


def _fmt(v, nd=2):
    try:
        return f"{float(v):,.{nd}f}"
    except (TypeError, ValueError):
        return "—"


def _macro_plus_block(mp: dict) -> str:
    lines = ["## DỮ LIỆU VĨ MÔ MỞ RỘNG (macro_plus)"]
    ind = mp.get("indicators", {})
    for key, v in ind.items():
        if v.get("available"):
            series = v.get("series", [])
            hist = ", ".join(f"{s['year']}:{_fmt(s['value'])}" for s in series[-5:])
            lines.append(f"- {v['label']} ({v['unit']}): mới nhất {_fmt(v['latest'])} "
                         f"[{v['as_of']}, nguồn {v['source']}]. 5 năm gần: {hist}")
        else:
            lines.append(f"- {v.get('label', key)}: KHÔNG có dữ liệu ({v.get('reason')})")
    fx = mp.get("fx", {})
    if fx.get("available"):
        lines.append(f"- Tỷ giá USD/VND (VCB): mua {_fmt(fx.get('usd_buy'),0)} / "
                     f"bán {_fmt(fx.get('usd_sell'),0)} [{fx.get('as_of')}, {fx.get('source')}]")
    else:
        lines.append(f"- Tỷ giá USD/VND: KHÔNG có ({fx.get('reason')})")
    for key, label, unit in (("gold", "Vàng SJC", "VND/lượng"), ("oil", "Dầu Brent", "USD/thùng")):
        v = mp.get(key, {})
        if v.get("available"):
            val = v.get("sell") or v.get("brent_usd")
            lines.append(f"- {label}: {_fmt(val, 0)} {unit} [{v.get('as_of')}, {v.get('source')}]")
        else:
            lines.append(f"- {label}: KHÔNG có ({v.get('reason')})")
    seed = mp.get("seed", {})
    if seed.get("available"):
        for k, sv in seed.get("data", {}).items():
            lines.append(f"- [SEED, cập nhật tay {sv.get('as_of')}] {k}: "
                         f"{_fmt(sv.get('value'))}{sv.get('unit','')} ({sv.get('period')}, {sv.get('source')})")
    return "\n".join(lines)


def _forecast_block(fc: dict) -> str:
    lines = ["## DỰ BÁO SARIMAX (GDP, CPI — %/năm)"]
    for key, label in (("gdp_growth", "GDP thực"), ("cpi", "CPI")):
        d = fc.get(key)
        if not isinstance(d, dict):
            continue
        hist = d.get("history", {})
        f = d.get("forecast", {})
        if hist:
            last2 = sorted(hist.items())[-2:]
            hist_s = ", ".join(f"{y}:{_fmt(v)}" for y, v in last2)
        else:
            hist_s = "—"
        years = f.get("years", [])
        mean = f.get("mean", [])
        if years and mean:
            lines.append(f"- {label}: thực tế gần ({hist_s}); dự báo {years[0]}≈{_fmt(mean[0])}"
                         f" (khoảng {_fmt((f.get('lower') or [None])[0])}–{_fmt((f.get('upper') or [None])[0])})")
        else:
            lines.append(f"- {label}: thực tế gần ({hist_s})")
    return "\n".join(lines)


def _vnindex_block(db_path: str) -> str:
    try:
        con = sqlite3.connect(db_path)
        rows = con.execute(
            "SELECT time, close, volume, value FROM market_index "
            "WHERE code='VNINDEX' ORDER BY time DESC LIMIT 20").fetchall()
        con.close()
    except sqlite3.Error:
        return "## VNINDEX: không đọc được dữ liệu"
    if not rows:
        return "## VNINDEX: chưa có dữ liệu"
    t0, close, vol, val = rows[0]
    # 3 chỉ số: điểm mới nhất, thay đổi 5 phiên, thanh khoản GTGD phiên.
    chg5 = None
    if len(rows) > 5 and rows[5][1]:
        chg5 = (close / rows[5][1] - 1) * 100
    gtgd_ty = (val or 0) / 1e9  # value đơn vị đồng → tỷ đồng
    return ("## VNINDEX (3 chỉ số)\n"
            f"- Điểm số: {_fmt(close)} [{t0}]\n"
            f"- Thay đổi 5 phiên: {_fmt(chg5)}%\n"
            f"- Thanh khoản (GTGD phiên): {_fmt(gtgd_ty, 0)} tỷ đồng")


def _news_block(db_path: str, limit: int = 12) -> tuple[str, set, dict]:
    """12 tin [M..] mới nhất. Trả (text, valid_ids, id→{title,link})."""
    try:
        con = sqlite3.connect(db_path)
        rows = con.execute(
            "SELECT id, title, source, link, public_date FROM market_news "
            "ORDER BY public_date DESC LIMIT ?", (limit,)).fetchall()
        con.close()
    except sqlite3.Error:
        return "## TIN VĨ MÔ: không đọc được", set(), {}
    lines = ["## TIN VĨ MÔ & THỊ TRƯỜNG (trích dẫn bằng mã [M..])"]
    valid, meta = set(), {}
    for i, (nid, title, source, link, pub) in enumerate(rows, 1):
        mid = f"M{i}"
        valid.add(mid)
        meta[mid] = {"title": title, "link": link, "source": source, "public_date": pub}
        lines.append(f"[{mid}] {title} ({source}, {str(pub)[:16]})")
    return "\n".join(lines), valid, meta


def collect(db_path: str, data_dir: str) -> dict:
    """Gom mọi nguồn → {text_block, valid_ids, news_meta, raw}. data_dir chứa
    macro_plus.json + macro_forecast.json (đã do run_pipeline xuất)."""
    def _load(name):
        try:
            with open(os.path.join(data_dir, name), encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    mp = _load("macro_plus.json")
    fc = _load("macro_forecast.json")
    news_text, valid_ids, news_meta = _news_block(db_path)

    text_block = "\n\n".join([
        _macro_plus_block(mp),
        _forecast_block(fc),
        _vnindex_block(db_path),
        news_text,
    ])
    return {
        "text_block": text_block,
        "valid_ids": sorted(valid_ids),
        "news_meta": news_meta,
        "raw": {"macro_plus": mp, "macro_forecast": fc},
    }


if __name__ == "__main__":
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    db = os.path.normpath(os.path.join(root, "..", "Crawl Data", "database", "market.db"))
    dd = os.path.join(root, "gateway", "static", "data")
    c = collect(db, dd)
    print(c["text_block"])
    print("\nVALID IDS:", c["valid_ids"])
