"""Manifest crawl — bảng kê MINH BẠCH "crawl được gì" cho mỗi công ty.

Quét các file JSON trong companies/<MÃ>/, với mỗi nguồn ghi:
present (có file & có dữ liệu), records (số bản ghi), fetched_at, bytes.
Tính completeness % để debug nhanh nguồn nào thiếu/lỗi.

Web đọc manifest này (GET /api/manifest/<sym>) để hiển thị tab "Dữ liệu".
"""
from __future__ import annotations

import json
from pathlib import Path

from . import config, storage

# (khóa hiển thị, đường dẫn tương đối trong company_dir, nhãn tiếng Việt)
_SOURCES = [
    ("balance_sheet", "financials/balance_sheet.json", "BCĐKT"),
    ("income_statement", "financials/income_statement.json", "Kết quả KD"),
    ("cash_flow", "financials/cash_flow.json", "Lưu chuyển tiền"),
    ("ratio", "financials/ratio.json", "Chỉ số tài chính"),
    ("profile", "profile.json", "Hồ sơ công ty"),
    ("news", "news/news.json", "Tin công bố (vnstock)"),
    ("press", "news/press.json", "Báo chí (RSS)"),
    ("articles", "news/articles.json", "Bài báo Vietstock (có nội dung)"),
    ("events", "disclosures/events.json", "Sự kiện/cổ tức"),
    ("officers", "ownership/officers.json", "Lãnh đạo"),
    ("shareholders", "ownership/shareholders.json", "Cổ đông lớn"),
    ("subsidiaries", "ownership/subsidiaries.json", "Công ty con"),
    ("affiliate", "ownership/affiliate.json", "Công ty liên kết"),
    ("capital_history", "ownership/capital_history.json", "Lịch sử tăng vốn"),
    ("insider_deals", "ownership/insider_deals.json", "Giao dịch nội bộ"),
    ("price", "market/price.json", "Giá lịch sử OHLCV"),
    ("board_snapshot", "market/board_snapshot.json", "Khối ngoại/độ sâu lệnh"),
    ("foreign_history", "market/foreign_history.jsonl", "Khối ngoại theo ngày"),
    ("ai_analysis", "analysis/ai_analysis.json", "Phân tích AI"),
    ("ai_debug", "analysis/debug/index.json", "Debug AI (đa lượt)"),
]


def _count_records(data) -> int:
    """Đếm số bản ghi theo các khóa list thường gặp trong dự án."""
    if isinstance(data, dict):
        for k in ("records", "items"):
            if isinstance(data.get(k), list):
                return len(data[k])
        if isinstance(data.get("count"), int):
            return data["count"]
        # profile / snapshot / ai_analysis: coi như 1 bản ghi nếu có nội dung
        for k in ("overview", "snapshot", "aspects", "overall"):
            if data.get(k):
                return 1
        return 1 if data else 0
    if isinstance(data, list):
        return len(data)
    return 0


def _probe(path: Path) -> dict:
    if not path.exists():
        return {"present": False, "records": 0, "fetched_at": None, "bytes": 0}
    # JSONL (1 record/dòng): đếm số dòng không rỗng, tuổi lấy từ dòng cuối.
    if path.suffix == ".jsonl":
        try:
            raw = path.read_text(encoding="utf-8")
        except Exception as exc:
            return {"present": False, "records": 0, "fetched_at": None,
                    "bytes": path.stat().st_size, "error": str(exc)[:80]}
        lines = [ln for ln in raw.splitlines() if ln.strip()]
        fetched = None
        if lines:
            try:
                fetched = json.loads(lines[-1]).get("fetched_at")
            except Exception:
                pass
        return {"present": len(lines) > 0, "records": len(lines),
                "fetched_at": fetched, "bytes": len(raw.encode("utf-8"))}
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except Exception as exc:
        return {"present": False, "records": 0, "fetched_at": None,
                "bytes": path.stat().st_size, "error": str(exc)[:80]}
    recs = _count_records(data)
    fetched = None
    if isinstance(data, dict):
        fetched = data.get("fetched_at") or data.get("updated_at") or data.get("generated_at")
    return {"present": recs > 0, "records": recs, "fetched_at": fetched,
            "bytes": len(raw.encode("utf-8"))}


_FINANCIAL_KEYS = {"balance_sheet", "income_statement", "cash_flow", "ratio"}


def _history_depth(path: Path) -> dict | None:
    """Đếm độ sâu lịch sử của 1 file BCTC: số năm distinct (kèm min–max) & số quý.
    Trả None nếu file không đọc được. Dùng cho manifest để UI hiển thị trung thực
    "dữ liệu dày N năm / M quý" thay vì luôn tưởng chỉ có 4 kỳ."""
    try:
        recs = json.loads(path.read_text(encoding="utf-8")).get("records", [])
    except Exception:
        return None
    years, quarters = set(), set()
    for r in recs:
        p = str(r.get("period", ""))
        if "-Q" in p:
            quarters.add(p)
            years.add(p[:4])
        elif p[:4].isdigit():
            years.add(p[:4])
    yrs = sorted(y for y in years if y.isdigit())
    depth = {"years": len(yrs), "quarters": len(quarters)}
    if yrs:
        depth["year_min"], depth["year_max"] = yrs[0], yrs[-1]
    return depth


def build(symbol: str, write: bool = True) -> dict:
    """Sinh manifest cho 1 mã. write=True → lưu companies/<MÃ>/manifest.json."""
    symbol = symbol.upper()
    cdir = config.company_dir(symbol)
    sources: dict[str, dict] = {}
    present_cnt = 0
    for key, rel, label in _SOURCES:
        info = _probe(cdir / rel)
        info["label"] = label
        info["path"] = rel
        # BCTC: kèm độ sâu lịch sử (năm/quý) để UI biết dữ liệu dày bao nhiêu.
        if key in _FINANCIAL_KEYS and info["present"]:
            depth = _history_depth(cdir / rel)
            if depth:
                info["history_depth"] = depth
        sources[key] = info
        if info["present"]:
            present_cnt += 1

    manifest = {
        "symbol": symbol,
        "generated_at": storage.now_iso(),
        "n_sources": len(_SOURCES),
        "n_present": present_cnt,
        "completeness_pct": round(present_cnt / len(_SOURCES) * 100, 1),
        "sources": sources,
    }
    if write:
        storage.write_json(cdir / "manifest.json", manifest)
    return manifest


def load(symbol: str) -> dict:
    """Đọc manifest đã lưu; nếu chưa có thì build tại chỗ (không ghi)."""
    p = config.company_dir(symbol) / "manifest.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return build(symbol, write=False)
