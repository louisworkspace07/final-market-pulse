# -*- coding: utf-8 -*-
"""Lớp an toàn pháp lý — dùng chung toàn hệ thống Market Pulse.

Ranh giới UBCKNN: sản phẩm CUNG CẤP THÔNG TIN & PHÂN TÍCH DỮ LIỆU, tuyệt đối
KHÔNG khuyến nghị mua/bán. Mọi module sinh nội dung cho người dùng phải:
1. dùng DISCLAIMER chuẩn dưới đây (viết 1 nơi, import khắp nơi);
2. chèn LEGAL_PROMPT_RULE vào prompt gửi LLM;
3. output được quét bằng check_text() — dính từ cấm là lỗi phải sửa prompt.
"""

DISCLAIMER = ("Market Pulse cung cấp thông tin và phân tích dữ liệu, KHÔNG phải "
              "khuyến nghị đầu tư. Quyết định và trách nhiệm thuộc về nhà đầu tư.")

# Câu ngắn dùng cuối phần đọc voice (TTS)
DISCLAIMER_SHORT = "Đây là thông tin tham khảo, không phải khuyến nghị đầu tư."

# Luật chèn vào MỌI prompt LLM sinh nội dung người dùng đọc
LEGAL_PROMPT_RULE = (
    "\nLUẬT PHÁP LÝ (BẮT BUỘC, vi phạm = câu trả lời bị từ chối): bạn CHỈ mô tả "
    "dữ kiện, kịch bản và rủi ro. TUYỆT ĐỐI KHÔNG dùng các cụm từ ra lệnh hành động: "
    "'nên mua', 'nên bán', 'nên giữ', 'khuyến nghị', 'chốt lời ngay', 'vào lệnh', "
    "'cắt lỗ ngay', 'gia tăng tỷ trọng', 'giải ngân'. Kịch bản chỉ nêu điều kiện "
    "kích hoạt và diễn biến dữ liệu, không nêu hành động người dùng phải làm.\n")

# Blacklist quét output (chữ thường, quét substring sau lower())
BANNED = [
    "nên mua", "nên bán", "nên giữ", "nên chốt", "khuyến nghị mua",
    "khuyến nghị bán", "khuyến nghị đầu tư vào", "chốt lời ngay", "cắt lỗ ngay",
    "vào lệnh", "xuống tiền", "giải ngân ngay", "gia tăng tỷ trọng",
    "mua vào ngay", "bán ra ngay", "mua gom",
    # ── Soi Tin: nhãn factcheck phải TRUNG TÍNH. Cấm AI (a) quy kết thao túng,
    # (b) cam kết/chắc chắn về giá, (c) hô hào theo tin đồn. Các cụm này nếu lọt
    # vào nhãn/giải thích claim là vi phạm — sửa prompt, không phải sửa dữ liệu.
    "thao túng giá", "đội lái", "bơm thổi", "bơm giá", "lùa gà", "phím hàng",
    "hàng nóng", "kèo thơm", "ăn bằng lần", "x2 tài khoản", "x3 tài khoản",
    "cam kết lợi nhuận", "bao lãi", "chắc chắn tăng", "chắc chắn giảm",
    "chắc chắn lãi", "đảm bảo sinh lời", "sóng thần", "tất tay", "full margin",
    "đu lệnh", "múc mạnh", "gom ngay",
]


def check_text(text: str) -> list[str]:
    """Trả về danh sách từ cấm xuất hiện trong text (rỗng = đạt)."""
    low = (text or "").lower()
    return [b for b in BANNED if b in low]


def check_payload(obj) -> list[str]:
    """Quét đệ quy mọi chuỗi trong dict/list JSON output của AI."""
    hits = []
    if isinstance(obj, str):
        hits += check_text(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            hits += check_payload(v)
    elif isinstance(obj, list):
        for v in obj:
            hits += check_payload(v)
    return sorted(set(hits))


# ─────────────────────────────────────────────────────────────────────────────
# LỚP THỨ HAI: quét TÊN KHOÁ, không chỉ giá trị.
#
# VÌ SAO CẦN: check_text/check_payload chỉ soi GIÁ TRỊ string. Payload
# {"investment_rating": "mua"} trả về [] = "sạch", vì "mua" đứng một mình không
# nằm trong BANNED — nhưng cặp khoá+giá trị đó CHÍNH LÀ một khuyến nghị đầu tư.
# Hệ quả: mọi call site phải tự hardcode drop-list, chỗ nào quên thì rò rỉ ra
# API. check_keys()/scrub() dưới đây tập trung drop-list về một nơi.
#
# Lưu ý: KHÔNG thay đổi hành vi check_text/check_payload (126 test phụ thuộc).
# ─────────────────────────────────────────────────────────────────────────────

# Tên khoá bị cấm xuất ra người dùng: mang ngữ nghĩa xếp hạng / giá mục tiêu /
# chọn mã thay người dùng. So khớp không phân biệt hoa-thường.
BANNED_KEYS = [
    "investment_rating",
    "target_price",
    "upside_to_target_percent",
    "rating",
    "recommendation",
    "winner",
]

_BANNED_KEYS_LOWER = frozenset(k.lower() for k in BANNED_KEYS)


def is_banned_key(key) -> bool:
    """Tên khoá này có bị cấm? (so khớp chính xác, bỏ qua hoa-thường)."""
    return isinstance(key, str) and key.strip().lower() in _BANNED_KEYS_LOWER


def check_keys(payload) -> list[str]:
    """Trả danh sách TÊN KHOÁ bị cấm xuất hiện ở mọi độ sâu (rỗng = đạt).

    Bổ sung cho check_payload(): bắt được {"investment_rating": "mua"} — case
    mà check_payload() bỏ sót vì chỉ quét giá trị.
    """
    hits: list[str] = []
    if isinstance(payload, dict):
        for k, v in payload.items():
            if is_banned_key(k):
                hits.append(k.strip().lower())
            hits += check_keys(v)
    elif isinstance(payload, (list, tuple)):
        for v in payload:
            hits += check_keys(v)
    return sorted(set(hits))


def scrub(payload, extra_keys=None):
    """Trả BẢN SAO của payload đã loại mọi khoá bị cấm ở MỌI độ sâu.

    Đệ quy vào cả list of dict. Không sửa payload gốc (tránh tác dụng phụ lên
    cache/DB row của caller). Kiểu không phải dict/list được trả nguyên trạng.

    extra_keys: thêm khoá cần loại cho riêng một call site (vd "verdict" ở nơi
    đã có quyết định gỡ) mà không phải nới BANNED_KEYS toàn hệ thống.
    """
    extra = frozenset(str(k).strip().lower() for k in (extra_keys or ()))

    def _drop(key) -> bool:
        return is_banned_key(key) or (
            isinstance(key, str) and key.strip().lower() in extra)

    def _walk(obj):
        if isinstance(obj, dict):
            return {k: _walk(v) for k, v in obj.items() if not _drop(k)}
        if isinstance(obj, list):
            return [_walk(v) for v in obj]
        if isinstance(obj, tuple):
            return tuple(_walk(v) for v in obj)
        return obj

    return _walk(payload)


def check_all(payload) -> dict:
    """Quét CẢ HAI lớp: từ cấm trong giá trị + tên khoá bị cấm.

    Trả {"banned_text": [...], "banned_keys": [...], "ok": bool}.
    """
    text_hits = check_payload(payload)
    key_hits = check_keys(payload)
    return {"banned_text": text_hits, "banned_keys": key_hits,
            "ok": not text_hits and not key_hits}
