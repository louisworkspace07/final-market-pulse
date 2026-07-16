# -*- coding: utf-8 -*-
"""Kết nối SQLite dùng chung phía gateway (P4b).

Mọi READER phía gateway (:9999) nên mở market.db bằng connect_readonly():
- mode=ro ở tầng URI → tuyệt đối không thể ghi, an toàn với crawler đang ghi
  (market.db đã bật WAL: reader không chặn writer và ngược lại).
- timeout ngắn: reader không việc gì phải chờ lock lâu.

stock_page/api.py và quantum_lab/api.py đã dùng pattern này; module mới
viết sau NÊN import từ đây thay vì tự sqlite3.connect.
"""
import sqlite3


def connect_readonly(db_path: str, timeout: float = 5.0) -> sqlite3.Connection:
    """Mở market.db chỉ-đọc (URI mode=ro). Ném sqlite3.OperationalError nếu
    file chưa tồn tại — caller tự xử lý thành empty-state."""
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=timeout)


# Cổng 5000 tự tính con số này qua HTTP (/api/analysis_status) mỗi lần người
# dùng bấm xem — nhưng phép tính chỉ là COUNT trên market.db, gateway 9999 đã
# có sẵn kết nối chỉ-đọc tới đúng file đó. Tính thẳng ở đây thay vì gọi HTTP
# sang 5000: nhanh hơn, và vẫn chạy được khi dịch vụ crawl (5000) đang tắt.
_EXCHANGES = {"HOSE", "HNX", "UPCOM"}


def crawl_coverage(db_path: str, group: str = "") -> dict:
    """Tiến độ crawl + phân tích AI. group rỗng/'ALL' → toàn bộ mã đã nạp vào
    market.db. group là HOSE/HNX/UPCOM → lọc theo cột companies.exchange (mã
    thuộc VN30/VN100 cần danh sách chỉ số riêng — src/board.py bên Crawl Data,
    không lặp lại phần đó ở đây; xem GHI CHÚ trong docstring)."""
    group = (group or "").strip().upper()
    if group and group not in _EXCHANGES:
        # VN30/VN100/CUSTOM cần danh sách mã từ src/board.py (Crawl Data) —
        # chưa lọc được ở đây. Trả về đúng nhãn ALL thay vì gắn nhãn group
        # cho số liệu KHÔNG lọc, sẽ đọc sai thành "tiến độ riêng của VN30".
        group = "ALL"
    conn = connect_readonly(db_path)
    try:
        where, args = "", ()
        if group in _EXCHANGES:
            where, args = "WHERE exchange = ?", (group,)
        total = conn.execute(
            f"SELECT COUNT(*) FROM companies {where}", args).fetchone()[0]
        if where:
            sub = f"SELECT symbol FROM companies {where}"
            analyzed = conn.execute(
                f"SELECT COUNT(*) FROM ai_analysis WHERE symbol IN ({sub})", args
            ).fetchone()[0]
            fin_done = conn.execute(
                "SELECT COUNT(*) FROM crawl_state WHERE stage='financials' AND "
                f"status='ok' AND symbol IN ({sub})", args).fetchone()[0]
            co_done = conn.execute(
                "SELECT COUNT(*) FROM crawl_state WHERE stage='company' AND "
                f"status='ok' AND symbol IN ({sub})", args).fetchone()[0]
        else:
            analyzed = conn.execute("SELECT COUNT(*) FROM ai_analysis").fetchone()[0]
            fin_done = conn.execute(
                "SELECT COUNT(*) FROM crawl_state WHERE stage='financials' "
                "AND status='ok'").fetchone()[0]
            co_done = conn.execute(
                "SELECT COUNT(*) FROM crawl_state WHERE stage='company' "
                "AND status='ok'").fetchone()[0]
        return {
            "group": group or "ALL", "total": total, "analyzed": analyzed,
            "remaining_ai": max(0, total - analyzed),
            "crawled_financials": fin_done, "crawled_company": co_done,
        }
    finally:
        conn.close()
