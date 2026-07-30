# -*- coding: utf-8 -*-
"""Đưa NỐT dữ liệu data-crawler lên cổng 9999.

`/api/stock/<mã>` chỉ trả phần đã dựng sẵn (info/price/fund/peers/health/news/
events/ai). Nhưng data-crawler còn giữ nhiều tệp per-company mà gateway chưa hề
phơi ra — lãnh đạo, công ty con, công ty liên kết, lịch sử tăng vốn, giao dịch
nội bộ, báo chí RSS, và toàn bộ 4 báo cáo tài chính thô.

Module này đọc THẲNG từ `data-crawler/companies/<MÃ>/` (cùng gốc với market.db mà
gateway đang dùng) chứ không gọi qua cổng 5000 — để trang cổ phiếu không phụ
thuộc việc dịch vụ crawl có đang chạy hay không.

Chỉ đọc, không ghi. Cắt số bản ghi trả về để một mã có 1.744 dòng cân đối kế
toán không làm nghẽn trang.
"""
import json
import os

MAX_ROWS = 400          # trần bản ghi mỗi nguồn dạng bảng

# 18 nguồn trải thành một hàng pill phẳng thì không đọc được là cái gì thuộc về
# đâu. Gom thành 4 nhóm theo CÂU HỎI người dùng đang hỏi, không theo thư mục.
GROUPS = (
    ("ownership", "Sở hữu & quản trị"),
    ("news", "Tin, sự kiện & báo chí"),
    ("financials", "Báo cáo tài chính thô"),
    ("market", "Giá & giao dịch"),
    ("operations", "Vận hành pipeline"),
)

# key → (đường dẫn tương đối, nhãn tiếng Việt, hiện mặc định, nhóm)
SOURCES = {
    "officers": ("ownership/officers.json", "Ban lãnh đạo", True, "ownership"),
    "subsidiaries": ("ownership/subsidiaries.json", "Công ty con", True, "ownership"),
    "affiliate": ("ownership/affiliate.json", "Công ty liên kết", True, "ownership"),
    "shareholders": ("ownership/shareholders.json", "Cổ đông lớn", True, "ownership"),
    "capital_history": ("ownership/capital_history.json", "Lịch sử tăng vốn", True, "ownership"),
    "insider_deals": ("ownership/insider_deals.json", "Giao dịch nội bộ (nguồn KBS)", True, "ownership"),
    "profile": ("profile.json", "Hồ sơ công ty", False, "ownership"),
    "press": ("news/press.json", "Báo chí (RSS)", True, "news"),
    "articles": ("news/articles.json", "Bài báo Vietstock", True, "news"),
    "news": ("news/news.json", "Tin công bố", False, "news"),
    "events": ("disclosures/events.json", "Sự kiện & cổ tức", False, "news"),
    "reasons": ("insights/reasons.jsonl", "Tin & sự kiện đã chấm trọng số", False, "news"),
    "balance_sheet": ("financials/balance_sheet.json", "Bảng cân đối kế toán", False, "financials"),
    "income_statement": ("financials/income_statement.json", "Kết quả kinh doanh", False, "financials"),
    "cash_flow": ("financials/cash_flow.json", "Lưu chuyển tiền tệ", False, "financials"),
    "ratio": ("financials/ratio.json", "Chỉ số tài chính", False, "financials"),
    "price": ("market/price.json", "Giá lịch sử", False, "market"),
    "board_snapshot": ("market/board_snapshot.json", "Khối ngoại phiên gần nhất", False, "market"),
    "foreign_history": ("market/foreign_history.jsonl", "Khối ngoại theo ngày", False, "market"),
    # Hai nguồn dưới đây trước đây CHỈ xem được ở cổng 5000 (/api/manifest,
    # /api/debug) — đúng "dữ liệu từ cổng 5000" chưa lên 9999. Đọc file thẳng,
    # KHÔNG gọi HTTP sang 5000: manifest.json + debug/index.json do crawler ghi
    # sẵn trong lúc chạy P2/P4, không phụ thuộc :5000 có đang chạy hay không.
    "manifest": ("manifest.json", "Độ phủ nguồn (manifest)", True, "operations"),
    "ai_debug": ("analysis/debug/index.json", "Lượt phân tích AI đã lưu", True, "operations"),
}

# Nguồn rỗng KHÔNG được im lặng biến mất — "đã hỏi, nguồn không có" khác hẳn
# "chưa crawl". Nhưng cũng không được đứng ngang hàng nguồn có dữ liệu: pill
# "Giao dịch nội bộ 0" từng khiến người đọc tưởng mã này không có giao dịch nội
# bộ nào, trong khi 21 giao dịch nằm trong `events`. Ghi chú thẳng chỗ cần nhìn.
EMPTY_HINTS = {
    "insider_deals": "Nguồn KBS không trả dữ liệu cho hầu hết mã. "
                     "Giao dịch nội bộ THẬT nằm trong nguồn “Sự kiện & cổ tức”.",
}

# PHÁP LÝ: `profile.json` chứa `rating` / `target_price` / `upside_to_target_percent`
# do công ty chứng khoán khuyến nghị. Trang cổ phiếu đã lọc chúng qua whitelist
# `_SAFE_PROFILE_KEYS`; ở đây phải lọc lại, nếu không thì mở đúng cái cửa vừa khoá.
# Xem modules/common/legal.py · Luật CK 2019 Điều 71.
_BANNED_KEYS = {"rating", "target_price", "upside_to_target_percent",
                "recommend", "recommendation", "investment_rating"}


def _companies_dir(db_path: str) -> str:
    """`<...>/data-crawler/database/market.db` → `<...>/data-crawler/companies`."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(db_path))),
                        "companies")


def _scrub(obj):
    """Bỏ đệ quy mọi khóa mang khuyến nghị đầu tư."""
    if isinstance(obj, dict):
        return {k: _scrub(v) for k, v in obj.items()
                if str(k).strip().lower() not in _BANNED_KEYS}
    if isinstance(obj, list):
        return [_scrub(x) for x in obj]
    return obj


def _read(path: str) -> tuple[list | None, dict, int]:
    """(rows, meta, tổng) — `rows=None` khi nguồn không phải dạng bảng."""
    if path.endswith(".jsonl"):
        rows = []
        with open(path, encoding="utf-8") as f:
            for ln in f:
                if ln.strip():
                    try:
                        rows.append(json.loads(ln))
                    except ValueError:
                        pass
        return rows, {}, len(rows)

    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data, {}, len(data)
    if isinstance(data, dict):
        # "passes": analysis/debug/index.json — danh sách lượt AI (title/ok/
        # secs/prompt_chars/raw_chars). Nhận thêm khóa này thì bảng debug tự
        # render qua đúng cơ chế bảng chung, không cần hàm riêng.
        for k in ("records", "items", "data", "passes"):
            if isinstance(data.get(k), list):
                meta = {a: b for a, b in data.items() if not isinstance(b, (list, dict))}
                return data[k], meta, len(data[k])
        return None, data, 0
    return None, {}, 0


def available(db_path: str, symbol: str) -> list[dict]:
    """Nguồn nào có thật cho mã này, kèm số bản ghi — để UI biết mà vẽ tab."""
    base = os.path.join(_companies_dir(db_path), symbol.upper())
    out = []
    for key, (rel, label, primary, group) in SOURCES.items():
        p = os.path.join(base, rel.replace("/", os.sep))
        if not os.path.exists(p):
            continue
        try:
            rows, _meta, total = _read(p)
        except (OSError, ValueError):
            continue
        kind = "table" if rows is not None else "object"
        item = {"key": key, "label": label, "primary": primary, "group": group,
                "kind": kind, "total": total, "path": rel,
                "bytes": os.path.getsize(p)}
        if kind == "table" and total == 0:
            item["empty"] = True
            item["hint"] = EMPTY_HINTS.get(key, "Nguồn không trả dữ liệu cho mã này.")
        out.append(item)
    return out


def groups() -> list[dict]:
    """Thứ tự và nhãn nhóm cho giao diện — server giữ, client không tự bịa."""
    return [{"key": k, "label": v} for k, v in GROUPS]


def fetch(db_path: str, symbol: str, key: str, limit: int = MAX_ROWS) -> dict:
    """Nội dung một nguồn. Khóa lạ hoặc thiếu tệp → dict rỗng (phía gọi trả 404)."""
    if key not in SOURCES:
        return {}
    rel, label, _, _group = SOURCES[key]
    p = os.path.join(_companies_dir(db_path), symbol.upper(), rel.replace("/", os.sep))
    if not os.path.exists(p):
        return {}
    try:
        rows, meta, total = _read(p)
    except (OSError, ValueError) as exc:
        return {"error": str(exc)[:160]}

    limit = max(1, min(int(limit or MAX_ROWS), 2000))
    out = {"symbol": symbol.upper(), "key": key, "label": label, "path": rel,
           "total": total, "meta": _scrub(meta),
           "source": f"data-crawler · companies/{symbol.upper()}/{rel}"}
    if rows is None:
        out["kind"] = "object"
        out["data"] = _scrub(meta)
    else:
        out["kind"] = "table"
        out["truncated"] = total > limit
        out["rows"] = _scrub(rows[:limit])
    return out
