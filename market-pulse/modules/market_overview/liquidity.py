# -*- coding: utf-8 -*-
"""Phân hạng thanh khoản — lọc "cổ phiếu chết" khỏi các bảng cho F0.

VÌ SAO CẦN: trung vị toàn thị trường chỉ ~22 triệu đồng khớp lệnh/phiên; chỉ
~19% số mã đạt trên 1 tỷ/phiên. Bảng "Top tăng giá" sắp xếp thuần theo %phiên
nên gần như luôn bị mã chết chiếm chỗ — đo ngày 2026-07-26: 8/10 mã top tăng có
từ 16/20 phiên KHÔNG có giao dịch nào (KHD: 20/20 phiên khối lượng = 0), trong
khi vẫn hiện "+14,74%". Người mới đọc con số đó tưởng là cơ hội, thực tế mua vào
là kẹt hàng.

TIÊU CHÍ (2 điều kiện, phải đạt CẢ HAI):
- GTGD bình quân 20 phiên gần nhất >= F0_MIN_GTGD (mặc định 500 triệu đồng)
- Số phiên khối lượng = 0 trong 20 phiên <= F0_MAX_ZERO_DAYS (mặc định 2)

Điều kiện thứ hai quan trọng không kém: nó bắt được mã "thỉnh thoảng có 1 lệnh
to rồi im" — loại mà chỉ nhìn bình quân sẽ lọt lưới.

ĐÂY LÀ DỮ KIỆN, KHÔNG PHẢI KHUYẾN NGHỊ: module chỉ đo mã có giao dịch đều đặn
hay không, không nói mã nào nên/không nên mua (tuân thủ modules/common/legal.py).

Lưu ý đơn vị: cột `price.close` trong market.db lưu theo NGHÌN ĐỒNG
(FPT = 62.9 ⇒ 62.900đ), nên GTGD = close * 1000 * volume.
"""
import os
import sqlite3

# Ngưỡng chỉnh được bằng biến môi trường (không cần sửa code).
MIN_GTGD = float(os.environ.get("F0_MIN_GTGD", 500_000_000))   # đồng/phiên
MAX_ZERO_DAYS = int(os.environ.get("F0_MAX_ZERO_DAYS", 2))     # phiên KL=0
WINDOW = int(os.environ.get("F0_LIQ_WINDOW", 20))              # số phiên xét
MIN_SESSIONS = 10        # ít hơn ngần này phiên → không đủ cơ sở kết luận

_SQL = """
SELECT symbol,
       AVG(close * 1000.0 * COALESCE(volume, 0))            AS gtgd,
       SUM(CASE WHEN COALESCE(volume, 0) = 0 THEN 1 ELSE 0 END) AS zero_days,
       COUNT(*)                                             AS n
FROM (SELECT symbol, close, volume,
             ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY time DESC) rn
      FROM price WHERE close IS NOT NULL)
WHERE rn <= ?
GROUP BY symbol
HAVING n >= ?
"""

import threading

# Bảng price chỉ đổi sau mỗi lần crawl → nhớ theo mtime của market.db.
_cache: dict = {"mtime": None, "data": None}
_tiers_lock = threading.Lock()


def tiers(db_path: str) -> dict:
    """{symbol: {gtgd20, zero_days, sessions, tradable}} cho toàn thị trường.

    `tradable=False` nghĩa là "giao dịch quá thưa để người mới mua bán được",
    KHÔNG phải đánh giá tốt/xấu về doanh nghiệp."""
    try:
        mtime = os.path.getmtime(db_path)
    except OSError:
        return {}
    if _cache["mtime"] == mtime and _cache["data"] is not None:
        return _cache["data"]

    with _tiers_lock:
        if _cache["mtime"] == mtime and _cache["data"] is not None:
            return _cache["data"]
        out: dict = {}
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
            try:
                for sym, gtgd, zero_days, n in conn.execute(_SQL, (WINDOW, MIN_SESSIONS)):
                    gtgd = float(gtgd or 0)
                    zero_days = int(zero_days or 0)
                    out[sym] = {
                        "gtgd20": round(gtgd),
                        "zero_days": zero_days,
                        "sessions": int(n),
                        "tradable": gtgd >= MIN_GTGD and zero_days <= MAX_ZERO_DAYS,
                    }
            finally:
                conn.close()
        except sqlite3.Error:
            return {}          # DB đang bị khóa/hỏng → coi như không có phân hạng

        _cache.update(mtime=mtime, data=out)
        return out


def annotate_rows(rows: list, db_path: str) -> dict:
    """Gắn thẳng `tradable` + `gtgd20` + `zero_days` vào từng dòng bảng giá.

    Mã KHÔNG có trong lịch sử giá (mới niêm yết…) để `tradable=None` — nghĩa là
    "chưa đủ dữ liệu để kết luận", phía UI xử lý riêng, không gộp vào mã chết.
    Trả về thống kê để UI hiện được "đang ẩn N mã"."""
    t = tiers(db_path)
    n_tradable = n_thin = n_unknown = 0
    for r in rows or []:
        info = t.get((r or {}).get("symbol"))
        if not info:
            r["tradable"] = None
            n_unknown += 1
            continue
        r["tradable"] = info["tradable"]
        r["gtgd20"] = info["gtgd20"]
        r["zero_days"] = info["zero_days"]
        if info["tradable"]:
            n_tradable += 1
        else:
            n_thin += 1
    return {"tradable": n_tradable, "thin": n_thin, "unknown": n_unknown,
            "min_gtgd": MIN_GTGD, "max_zero_days": MAX_ZERO_DAYS, "window": WINDOW}
