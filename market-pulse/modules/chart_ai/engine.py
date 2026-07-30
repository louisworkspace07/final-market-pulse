"""§18 · Đưa số liệu kỹ thuật cho AI mô tả thành lời (không gửi ảnh biểu đồ)."""
from __future__ import annotations

import json
import re
import time

from modules.common.legal import DISCLAIMER, LEGAL_PROMPT_RULE, check_payload

SYSTEM_PROMPT = """Bạn là Market Pulse — mô tả BIỂU ĐỒ KỸ THUẬT của một cổ phiếu Việt Nam thành lời cho người mới.

NGUYÊN TẮC SẮT (vi phạm = câu trả lời bị từ chối):
1. CHỈ dùng số liệu trong khối DỮ LIỆU bên dưới. Không bịa số, không dùng kiến thức ngoài về doanh nghiệp.
2. Mỗi câu phải gắn với CON SỐ cụ thể lấy từ dữ liệu.
3. Chỉ MÔ TẢ trạng thái ĐANG quan sát được. TUYỆT ĐỐI KHÔNG dự báo giá sẽ tăng/giảm,
   KHÔNG nêu xác suất, KHÔNG khuyến nghị mua/bán/nắm giữ, KHÔNG đặt giá mục tiêu.
4. Viết cho người CHƯA biết gì về phân tích kỹ thuật: thuật ngữ nào dùng thì giải thích
   ngắn ngay trong ngoặc (ví dụ: "RSI 40 (thước đo mua–bán, 0–100, quanh 50 là cân bằng)").
5. 'muc_theo_doi' chỉ liệt kê MỐC GIÁ đã có trong dữ liệu (hỗ trợ/kháng cự/MA), kèm
   ý nghĩa trung tính "nếu giá chạm vùng này thì đó là vùng thị trường từng phản ứng" —
   KHÔNG nói nên làm gì khi chạm.
""" + LEGAL_PROMPT_RULE + """
TRẢ VỀ DUY NHẤT 1 JSON (không markdown fence, không chữ ngoài JSON):
{
 "xu_huong": "2-3 câu: giá đang ở đâu so với trung bình 20/50 phiên, chuỗi gần đây thế nào",
 "vi_tri": "2-3 câu: đang nằm ở đâu giữa vùng hỗ trợ và kháng cự, cách mỗi bên bao nhiêu %",
 "khoi_luong": "1-2 câu: khối lượng phiên gần nhất so với trung bình 20 phiên nói lên điều gì về mức độ quan tâm",
 "bien_52_tuan": "1-2 câu: đang ở phần nào của biên độ 1 năm",
 "muc_theo_doi": ["2-4 mốc giá đáng chú ý, mỗi mốc 1 dòng kèm số"],
 "luu_y": "1 câu nhắc đây là mô tả dữ liệu quá khứ, không dự báo tương lai",
 "disclaimer": \"""" + DISCLAIMER + """\"
}"""


def _facts(sym: str, t: dict) -> str:
    """Khối dữ kiện từ tech_full — đúng những con số UI đang hiển thị."""
    sr = t.get("sr") or {}
    sup = sr.get("support") or []
    res = sr.get("resistance") or []
    L = [f"--- MÃ {sym} (đơn vị giá: nghìn đồng) ---",
         f"Giá gần nhất: {t.get('price')}",
         f"Số phiên lịch sử dùng để tính: {t.get('bars')}",
         f"MA20 (trung bình 20 phiên): {t.get('ma20')}",
         f"MA50 (trung bình 50 phiên): {t.get('ma50')}",
         f"Giá {'TRÊN' if t.get('above_ma20') else 'DƯỚI'} MA20",
         f"RSI14: {t.get('rsi14')}",
         f"Khối lượng phiên gần nhất so với trung bình 20 phiên: {t.get('vol_vs_20')} lần",
         f"Vùng hỗ trợ gần (giá từng bật lên): {sup or 'không có dưới giá hiện tại'}",
         f"Vùng kháng cự gần (giá từng quay đầu): {res or 'không còn đỉnh cũ phía trên'}",
         f"Vùng khối lượng tích tụ dày: {t.get('vbp') or 'chưa xác định'}",
         f"Đỉnh 52 tuần: {t.get('hi52')} (giá hiện cách {t.get('pct_from_hi52')}%)",
         f"Đáy 52 tuần: {t.get('lo52')} (giá hiện cách {t.get('pct_from_lo52')}%)",
         f"Nhãn vị trí do hệ thống gán: {t.get('pos')}"]
    return "\n".join(L)


def _validate(ans: dict) -> str | None:
    if not isinstance(ans, dict):
        return "không phải object"
    for k in ("xu_huong", "vi_tri", "khoi_luong"):
        if not ans.get(k):
            return f"thiếu '{k}'"
    if not isinstance(ans.get("muc_theo_doi"), list) or not ans["muc_theo_doi"]:
        return "'muc_theo_doi' phải là mảng không rỗng"
    return None


def read_chart(symbol: str, tech: dict, prefer: str = "auto") -> dict:
    """Mô tả biểu đồ bằng lời. Trả {symbol, answer, transport, elapsed_s} hoặc {error}."""
    t0 = time.time()
    if not tech or tech.get("skipped"):
        return {"error": f"Chưa đủ dữ liệu kỹ thuật cho {symbol}"
                         + (f" — {tech['skipped']}" if tech and tech.get("skipped") else "")}

    user_msg = ("DỮ LIỆU KỸ THUẬT (chỉ dùng đúng những số này):\n\n"
                + _facts(symbol, tech)
                + "\n\nMô tả lại biểu đồ này thành lời cho người mới, theo đúng schema.")

    answer, error, transport = None, None, None
    try:
        from modules.market_overview.gemini_transport import open_session
        feedback = ""
        with open_session(prefer=prefer) as sess:
            transport = sess.transport
            for _ in range(3):
                try:
                    raw = sess.ask(SYSTEM_PROMPT + "\n\n" + user_msg + feedback)
                    raw = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.M).strip()
                    m = re.search(r"\{.*\}", raw, flags=re.S)
                    cand = json.loads(m.group(0) if m else raw)
                    err = _validate(cand)
                    if err is None:
                        banned = check_payload(cand)
                        if not banned:
                            answer = cand
                            break
                        err = (f"dùng từ cấm pháp lý: {', '.join(banned)} — chỉ MÔ TẢ "
                               "trạng thái, KHÔNG dự báo/khuyến nghị")
                    feedback = (f"\n\nLƯU Ý: lần trước bị từ chối ({err}). "
                                "Trả lại ĐÚNG JSON theo schema.")
                except Exception as e:
                    error = str(e)[:300]
                    time.sleep(1)
    except Exception as e:
        error = str(e)[:300]

    if answer is None:
        return {"error": error or "AI chưa trả kết quả hợp lệ. Kiểm tra kênh Gemini rồi thử lại."}
    answer.setdefault("disclaimer", DISCLAIMER)
    return {"symbol": symbol, "answer": answer, "transport": transport,
            "elapsed_s": round(time.time() - t0, 1)}
