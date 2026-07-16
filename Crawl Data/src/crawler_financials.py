"""Crawler tài chính qua vnstock: BCĐKT, KQKD, lưu chuyển tiền tệ, chỉ số.

Ghi JSON theo từng công ty + đồng bộ vào SQLite.
"""
from __future__ import annotations

import json

from vnstock import Finance

from . import config, progress, storage
from .runner import _is_ratelimit


def _merge_json_records(cdir, name: str, new_records: list[dict]) -> list[dict]:
    """Gộp records mới với records cũ trong file JSON (nếu có) theo khóa
    (item_id, period) — record mới thắng khi trùng. Giữ kỳ cũ mà batch mới thiếu
    để lịch sử tích lũy dày lên qua các lần crawl (vnstock chỉ trả 4 kỳ/lần)."""
    merged: dict[tuple, dict] = {}
    old_path = cdir / "financials" / f"{name}.json"
    if old_path.exists():
        try:
            old = json.loads(old_path.read_text(encoding="utf-8")).get("records", [])
            for r in old:
                # Lọc kỳ rác từ bug ratio/VCI cũ ("2018.1"...) — không cho rác
                # cũ trong JSON sống lại qua các lần merge.
                if not storage.CLEAN_PERIOD_RE.match(str(r.get("period", ""))):
                    continue
                merged[(r.get("item_id"), r.get("period"))] = r
        except Exception:
            pass   # file cũ hỏng → coi như không có, dùng batch mới
    for r in new_records:
        merged[(r.get("item_id"), r.get("period"))] = r
    return list(merged.values())


def crawl_one(conn, symbol: str) -> dict:
    """Crawl 4 báo cáo tài chính cho 1 mã. Trả về tóm tắt số bản ghi."""
    symbol = symbol.upper()
    cdir = config.company_dir(symbol)
    progress.start(symbol)
    fin = Finance(symbol=symbol, source=config.FINANCE_SOURCE)
    # ratio() của nguồn VCI bị hỏng (cột kỳ toàn "2018"); nguồn KBS trả period
    # chuẩn "YYYY-Năm"/"YYYY-QN" → dùng riêng KBS + ratio_to_records cho ratio.
    fin_ratio = Finance(symbol=symbol, source="KBS")

    methods = {
        "balance_sheet": fin.balance_sheet,
        "income_statement": fin.income_statement,
        "cash_flow": fin.cash_flow,
        "ratio": fin_ratio.ratio,
    }

    summary: dict[str, int] = {}
    for name, method in methods.items():
        # Crawl cả NĂM (xu hướng dài hạn) lẫn QUÝ (YoY, điểm mua).
        combined: list[dict] = []
        seen: set = set()
        dropped = 0
        ok_any = False
        # Riêng ratio dùng converter riêng (dạng long, period "YYYY-Năm"/"YYYY-QN").
        to_records = storage.ratio_to_records if name == "ratio" else storage.statement_to_records
        for ptype in ("year", "quarter"):
            try:
                df = method(period=ptype)
            except Exception as exc:
                # Lỗi rate-limit KHÔNG được nuốt: ném lại để guard() ở runner
                # nhận diện và cooldown 65s. Chỉ nuốt (print+continue) lỗi khác.
                if _is_ratelimit(exc):
                    raise
                print(f"  [!] {symbol} {name} ({ptype}): {str(exc)[:60]}")
                continue
            ok_any = True
            for r in to_records(df):
                # Validate kỳ: chỉ nhận "YYYY" hoặc "YYYY-QN". Kỳ rác (vd cột
                # trùng "2018.1" của ratio VCI) bị loại và đếm để cảnh báo.
                if not storage.CLEAN_PERIOD_RE.match(str(r["period"])):
                    dropped += 1
                    continue
                r["period_type"] = "Q" if "-Q" in r["period"] else "Y"
                key = (r["item_id"], r["period"])
                if key not in seen:
                    seen.add(key)
                    combined.append(r)

        if dropped:
            print(f"  [!] {symbol} {name}: bỏ {dropped} record period không chuẩn")

        # Coi là "thiếu" (-1) khi: mọi lần gọi method đều ném lỗi (not ok_any)
        # HOẶC gọi được nhưng KHÔNG có bản ghi nào (DataFrame rỗng, vd DN đặc thù
        # không có statement chuẩn). Tránh ghi "ok" cho báo cáo rỗng 0 record.
        if not ok_any or not combined:
            summary[name] = -1
            progress.step(symbol, name, "err", 0)
            continue

        # Tích lũy lịch sử: gộp với kỳ cũ trong JSON + upsert DB (không xóa kỳ cũ).
        merged = _merge_json_records(cdir, name, combined)
        storage.write_json(
            cdir / "financials" / f"{name}.json",
            {"symbol": symbol, "statement": name,
             "fetched_at": storage.now_iso(), "records": merged},
        )
        storage.merge_financials(conn, symbol, name, merged)
        summary[name] = len(merged)
        progress.step(symbol, name, "ok", len(merged))

    # Cập nhật profile.json (merge, không xoá overview do P2 ghi).
    pf = cdir / "profile.json"
    data = {}
    if pf.exists():
        try:
            data = json.loads(pf.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data.update({"symbol": symbol, "updated_at": storage.now_iso(),
                 "financials_summary": summary})
    storage.write_json(pf, data)
    storage.upsert_company(conn, symbol)
    conn.commit()
    progress.done(symbol, "err" if any(v == -1 for v in summary.values()) else "ok")
    return summary
