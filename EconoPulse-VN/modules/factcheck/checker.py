# -*- coding: utf-8 -*-
"""Đối chiếu mỗi claim với dữ liệu thật trong market.db.

Nguyên tắc TRUNG TÍNH: checker KHÔNG phán tin đồn đúng/sai. Nó chỉ trả về
DỮ LIỆU CÔNG BỐ liên quan (sự kiện/tin CBTT/BCTC/giá) + 1 tín hiệu:
  - "co_cong_bo"        : DB có công bố chính thức khớp loại claim gần đây;
  - "khong_thay"        : có mã thật nhưng DB không có công bố khớp;
  - "khong_kiem_chung"  : không mã/không tra cứu được (macro, tin chung chung).

Mỗi mẩu bằng chứng có id [N..]/[E..] để UI render evidence chip (như overview).
Không mock: DB thiếu → mọi claim về "khong_kiem_chung".
"""
from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass, field, asdict

from .extractor import Claim

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DB_PATH = os.environ.get(
    "MARKET_DB",
    os.path.join(_ROOT, "Crawl Data", "database", "market.db"),
)

# Số ngày lùi coi là "gần đây" khi soi sự kiện/tin công bố.
_LOOKBACK_DAYS = 120

# Loại claim → (từ khóa event_name/title cần tìm trong events, có soi news không).
_KIND_EVENT_KW: dict[str, tuple[str, ...]] = {
    "dividend":  ("cổ tức", "trả thưởng", "cổ phiếu thưởng"),
    "issuance":  ("phát hành", "niêm yết thêm", "chào bán", "tăng vốn"),
    "insider":   ("giao dịch nội bộ", "cổ đông"),
    "ma":        ("góp vốn", "thành lập", "hợp tác", "sáp nhập", "mua lại"),
    "delist":    ("hủy niêm yết", "đình chỉ", "kiểm soát", "cảnh báo"),
    "earnings":  ("kết quả kinh doanh", "báo cáo tài chính"),
}


@dataclass
class Evidence:
    id: str          # [N..] / [E..]
    kind: str        # "news" | "event" | "financial" | "price"
    symbol: str
    title: str
    date: str
    link: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ClaimCheck:
    claim: dict                       # Claim.to_dict()
    signal: str                       # co_cong_bo | khong_thay | khong_kiem_chung
    evidence: list[dict] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _connect(db_path: str):
    if not os.path.exists(db_path):
        return None
    try:
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error:
        return None


def _recent_cutoff(days: int, today: str | None) -> str:
    """Ngày ISO 'YYYY-MM-DD' làm mốc lùi. today truyền vào để test tất định."""
    from datetime import date, timedelta
    if today:
        base = date.fromisoformat(today[:10])
    else:  # dùng ngày thực khi chạy live
        base = date.today()
    return (base - timedelta(days=days)).isoformat()


def _events_for(conn, symbol: str, kws: tuple[str, ...], cutoff: str) -> list[Evidence]:
    rows = conn.execute(
        "SELECT event_id, event_name, title, public_date FROM events "
        "WHERE symbol=? AND substr(public_date,1,10) >= ? "
        "ORDER BY public_date DESC LIMIT 40",
        (symbol, cutoff),
    ).fetchall()
    out = []
    for eid, ename, title, pdate in rows:
        blob = f"{ename or ''} {title or ''}".lower()
        if kws and not any(k in blob for k in kws):
            continue
        out.append(Evidence(id=f"E{eid}", kind="event", symbol=symbol,
                             title=(title or ename or "").strip(),
                             date=(pdate or "")[:10]))
    return out[:5]


def _news_for(conn, symbol: str, kws: tuple[str, ...], cutoff: str) -> list[Evidence]:
    rows = conn.execute(
        "SELECT news_id, title, source_link, public_date FROM news "
        "WHERE symbol=? AND substr(public_date,1,10) >= ? "
        "ORDER BY public_date DESC LIMIT 40",
        (symbol, cutoff),
    ).fetchall()
    out = []
    for nid, title, link, pdate in rows:
        low = (title or "").lower()
        if kws and not any(k in low for k in kws):
            continue
        out.append(Evidence(id=f"N{nid}", kind="news", symbol=symbol,
                            title=(title or "").strip(), date=(pdate or "")[:10],
                            link=link or ""))
    return out[:5]


def check_claim(claim: Claim, db_path: str = DB_PATH, today: str | None = None) -> ClaimCheck:
    """Soi 1 claim: gom bằng chứng công bố + phân loại tín hiệu trung tính."""
    cd = claim.to_dict()
    if not claim.symbols:
        return ClaimCheck(claim=cd, signal="khong_kiem_chung",
                          note="Không xác định được mã cổ phiếu cụ thể để đối chiếu.")
    conn = _connect(db_path)
    if conn is None:
        return ClaimCheck(claim=cd, signal="khong_kiem_chung",
                          note="Chưa truy cập được cơ sở dữ liệu thị trường.")
    # Loại claim có ánh xạ từ khóa công bố → soi khớp được. Macro/price_target/
    # other không kiểm chứng được bằng sự kiện CBTT → chỉ nêu bối cảnh, không phán.
    matchable = claim.kind in _KIND_EVENT_KW
    try:
        cutoff = _recent_cutoff(_LOOKBACK_DAYS, today)
        kws = _KIND_EVENT_KW.get(claim.kind, ())
        evidence: list[Evidence] = []
        for sym in claim.symbols:
            evidence += _events_for(conn, sym, kws, cutoff)
            evidence += _news_for(conn, sym, kws, cutoff)
    finally:
        conn.close()

    if not matchable:
        note = ("Loại tin này (vĩ mô/kỳ vọng giá) không thể xác nhận bằng công bố "
                "chính thức của doanh nghiệp. Dưới đây là bối cảnh gần nhất, nếu có."
                if evidence else
                "Loại tin này không thể xác minh bằng dữ liệu công bố của doanh nghiệp.")
        return ClaimCheck(claim=cd, signal="khong_kiem_chung",
                          evidence=[e.to_dict() for e in evidence[:5]], note=note)

    if evidence:
        signal = "co_cong_bo"
        note = (f"Có {len(evidence)} công bố chính thức gần đây liên quan loại tin này. "
                "Đối chiếu nội dung để xem tin đồn khớp tới đâu.")
    else:
        signal = "khong_thay"
        note = ("Chưa thấy công bố chính thức khớp loại tin này trong "
                f"{_LOOKBACK_DAYS} ngày gần nhất — tin chưa được kiểm chứng bằng dữ liệu.")
    return ClaimCheck(claim=cd, signal=signal,
                      evidence=[e.to_dict() for e in evidence[:8]], note=note)


def check_claims(claims: list[Claim], db_path: str = DB_PATH,
                 today: str | None = None) -> list[ClaimCheck]:
    return [check_claim(c, db_path, today) for c in claims]


def evidence_map(checks: list[ClaimCheck]) -> dict:
    """Gom mọi evidence thành {id: {...}} cho UI render chip (như newsMap)."""
    m: dict = {}
    for ch in checks:
        for e in ch.evidence:
            m[e["id"]] = e
    return m
