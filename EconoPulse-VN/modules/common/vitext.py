# -*- coding: utf-8 -*-
"""Chuẩn hóa tiếng Việt + ánh xạ tên công ty → mã CK — nền tảng cho P1 Soi Tin.

Bài toán: người dùng gõ tin đồn/tít báo không dấu, teencode, viết tắt
("Hoa Phat sap chia co tuc", "cp HPG", "ngân hàng vcb"). Module này:
1. strip_accents / normalize      — bỏ dấu, hạ chữ thường, gom khoảng trắng;
2. index tên công ty từ market.db — bỏ tiền tố pháp lý (CTCP, Ngân hàng TMCP…)
   để lấy phần lõi ("Tập đoàn Hòa Phát" → "hoa phat"), map về symbol;
3. find_symbols(text)             — dò mọi mã CK được nhắc trong 1 đoạn text,
   qua cả mã trần (HPG) lẫn tên công ty không dấu.

Đọc trực tiếp `data-crawler/database/market.db` (bảng companies: symbol, organ_name),
cache trong bộ nhớ. Không mock — DB thiếu thì index rỗng, find_symbols vẫn chạy
với riêng lớp mã trần.
"""
from __future__ import annotations

import os
import re
import sqlite3
import unicodedata
from functools import lru_cache

# ── Đường dẫn DB ────────────────────────────────────────────────────────────
# .../EconoPulse-VN/modules/common/vitext.py  →  gốc "Final Market Pulse"
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_DB_PATH = os.environ.get(
    "MARKET_DB",
    os.path.join(_ROOT, "data-crawler", "database", "market.db"),
)

# Tiền tố loại hình DN cần bỏ để lấy phần lõi tên (xếp dài trước ngắn khi quét).
_LEGAL_PREFIXES = [
    "ngan hang thuong mai co phan",
    "ngan hang tmcp",
    "cong ty co phan tap doan",
    "cong ty co phan",
    "cong ty tnhh mtv",
    "cong ty tnhh",
    "cong ty",
    "tong cong ty",
    "tap doan",
    "ctcp",
    "tcty",
    "cty",
]
# Hậu tố địa lý/pháp lý hay gặp, bỏ để tăng tỉ lệ khớp.
_LEGAL_SUFFIXES = [
    "viet nam",
    "vn",
]

# Teencode / viết tắt phổ biến trong tin thị trường (không dấu → chuẩn).
_TEENCODE = {
    "cp": "co phieu",
    "ck": "chung khoan",
    "ttck": "thi truong chung khoan",
    "ndt": "nha dau tu",
    "co tuc": "co tuc",
    "ctuc": "co tuc",
    "dhcd": "dai hoi co dong",
    "bctc": "bao cao tai chinh",
    "ln": "loi nhuan",
    "dt": "doanh thu",
    "vdl": "von dieu le",
    "tt": "thi truong",
}

# Ký tự "mã CK" hợp lệ: 3 ký tự chữ (HPG, FPT). Một số mã 3 chữ + không có ở đây;
# ta chỉ nhận [A-Z]{3} ở ranh giới từ để tránh dính từ tiếng Anh viết hoa.
_TICKER_RE = re.compile(r"\b([A-Z]{3})\b")

# Mã viết thường (vcb, hpg) chỉ nhận khi có cue phía trước — nếu không, những mã
# trùng từ thông dụng (LAI, TIN, TAN) sẽ dính oan. Cue đã qua normalize+teencode.
_CUE_TICKER_RE = re.compile(
    r"\b(?:co phieu|chung khoan|ma ck|ma|cp|ck|mck|ngan hang|tap doan|cong ty)\s+([a-z]{3})\b"
)


def strip_accents(text: str) -> str:
    """Bỏ dấu tiếng Việt, chuẩn hóa đ→d. Giữ nguyên chữ hoa/thường."""
    if not text:
        return ""
    text = text.replace("đ", "d").replace("Đ", "D")
    nfkd = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in nfkd if unicodedata.category(ch) != "Mn")


def normalize(text: str) -> str:
    """Chuẩn hóa để so khớp: bỏ dấu → chữ thường → chỉ giữ [a-z0-9 ] → gom space."""
    if not text:
        return ""
    s = strip_accents(text).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _strip_legal(name_norm: str) -> str:
    """Từ tên đã normalize, bỏ tiền tố loại hình DN + hậu tố địa lý → phần lõi."""
    s = name_norm
    changed = True
    while changed:
        changed = False
        for p in _LEGAL_PREFIXES:
            if s.startswith(p + " "):
                s = s[len(p) + 1:]
                changed = True
                break
    for suf in _LEGAL_SUFFIXES:
        if s.endswith(" " + suf):
            s = s[: -(len(suf) + 1)]
    return s.strip()


@lru_cache(maxsize=1)
def _load_index() -> tuple[dict[str, str], set[str]]:
    """Trả về (name_core → symbol, set mọi symbol). Cache 1 lần.

    Xây map từ phần lõi tên công ty (không dấu) về mã. Nếu 2 công ty đụng lõi,
    giữ cái đầu (hiếm; tên lõi thường phân biệt). DB thiếu → map rỗng.
    """
    name_map: dict[str, str] = {}
    symbols: set[str] = set()
    if not os.path.exists(_DB_PATH):
        return name_map, symbols
    try:
        conn = sqlite3.connect(f"file:{_DB_PATH}?mode=ro", uri=True)
    except sqlite3.Error:
        return name_map, symbols
    try:
        rows = conn.execute(
            "SELECT symbol, organ_name FROM companies "
            "WHERE symbol IS NOT NULL AND organ_name IS NOT NULL"
        ).fetchall()
    except sqlite3.Error:
        return name_map, symbols
    finally:
        conn.close()

    for symbol, organ_name in rows:
        sym = (symbol or "").strip().upper()
        if not sym:
            continue
        symbols.add(sym)
        core = _strip_legal(normalize(organ_name))
        if core and len(core) >= 3:
            name_map.setdefault(core, sym)
    return name_map, symbols


def _apply_teencode(text_norm: str) -> str:
    """Thay teencode theo ranh giới từ trên chuỗi đã normalize."""
    tokens = text_norm.split()
    return " ".join(_TEENCODE.get(t, t) for t in tokens)


def find_symbols(text: str) -> list[str]:
    """Dò mọi mã CK được nhắc trong text (giữ thứ tự xuất hiện, không trùng).

    Hai lớp:
    1. Mã trần viết hoa trong text gốc ([A-Z]{3}) — chỉ nhận nếu là symbol thật.
    2. Tên công ty không dấu khớp phần lõi trong index (khớp cụm dài trước).
    """
    if not text:
        return []
    name_map, symbols = _load_index()
    found: list[str] = []
    seen: set[str] = set()

    def _add(sym: str) -> None:
        if sym and sym not in seen:
            seen.add(sym)
            found.append(sym)

    # Lớp 1: mã trần trong text gốc (trước khi hạ chữ thường).
    for m in _TICKER_RE.finditer(text):
        cand = m.group(1)
        if not symbols or cand in symbols:
            _add(cand)

    norm = _apply_teencode(normalize(text))

    # Lớp 1b: mã viết thường có cue phía trước ("ngan hang vcb", "cp hpg").
    if norm:
        for m in _CUE_TICKER_RE.finditer(norm):
            cand = m.group(1).upper()
            if not symbols or cand in symbols:
                _add(cand)

    # Lớp 2: khớp tên công ty. Quét các cụm dài trước để "hoa phat" thắng "hoa".
    if norm and name_map:
        # sort core names dài trước để ưu tiên khớp cụ thể hơn
        for core in sorted(name_map, key=len, reverse=True):
            if re.search(r"\b" + re.escape(core) + r"\b", norm):
                _add(name_map[core])
    return found


def recognizes(text: str, symbol: str) -> bool:
    """Tiện ích test: text có nhận ra `symbol` không."""
    return (symbol or "").strip().upper() in find_symbols(text)


if __name__ == "__main__":  # kiểm tra nhanh
    for t in [
        "Hoa Phat sap chia co tuc",
        "cp HPG va FPT dang hut dong tien",
        "ngan hang vcb bao lai ky luc",
        "Sua Viet Nam VNM tang truong",
    ]:
        print(f"{t!r:45} -> {find_symbols(t)}")
