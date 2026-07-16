"""Ảnh 8 · Tên ngành ICB: tiếng Anh (trong market.db) → tiếng Việt hiển thị.

Đây là NGUỒN SỰ THẬT DUY NHẤT cho tên ngành trong toàn hệ thống:
  - API trả kèm ``sector_vi`` cạnh ``sector`` (giữ key gốc để code cũ không vỡ).
  - Prompt AI chèn ``prompt_rule()`` để text sinh ra cũng dùng tên tiếng Việt.
  - Frontend có bản sao trong ``common.js`` (SECTOR_VI) — sửa ở đây thì sửa cả đó.

Wording lấy theo card "Chỉ số & nhóm ngành" ở trang chủ (bản người dùng đã quen).
"""

SECTOR_VI = {
    "Banks": "Ngân hàng",
    "Real Estate": "Bất động sản",
    "Construction & Materials": "Xây dựng & Vật liệu",
    "Industrial Goods & Services": "Hàng & Dịch vụ công nghiệp",
    "Food & Beverage": "Thực phẩm & Đồ uống",
    "Utilities": "Điện, nước & Tiện ích",
    "Basic Resources": "Tài nguyên cơ bản",
    "Personal & Household Goods": "Hàng tiêu dùng cá nhân",
    "Chemicals": "Hóa chất",
    "Health Care": "Y tế",
    "Financial Services": "Dịch vụ tài chính",
    "Travel & Leisure": "Du lịch & Giải trí",
    "Media": "Truyền thông",
    "Technology": "Công nghệ",
    "Retail": "Bán lẻ",
    "Automobiles & Parts": "Ô tô & Phụ tùng",
    "Insurance": "Bảo hiểm",
    "Oil & Gas": "Dầu khí",
    "Telecommunications": "Viễn thông",
    "Khác": "Khác",
}


def vi(sector: str | None) -> str:
    """Tên ngành tiếng Việt; ngành lạ → giữ nguyên (không nuốt dữ liệu)."""
    if not sector:
        return "Khác"
    return SECTOR_VI.get(sector.strip(), sector.strip())


def annotate(items, key: str = "sector", out: str = "sector_vi"):
    """Thêm ``sector_vi`` vào từng dict trong list (sửa tại chỗ, trả lại list)."""
    for it in items or []:
        if isinstance(it, dict) and key in it:
            it[out] = vi(it.get(key))
    return items


def prompt_rule() -> str:
    """Đoạn chèn vào prompt LLM để AI viết tên ngành bằng tiếng Việt."""
    pairs = ", ".join(f"{en}={vn}" for en, vn in SECTOR_VI.items() if en != "Khác")
    return ("\nTÊN NGÀNH (BẮT BUỘC): khi nhắc tới ngành, luôn viết bằng TIẾNG VIỆT "
            f"theo bảng sau, không dùng tên tiếng Anh: {pairs}.\n")
