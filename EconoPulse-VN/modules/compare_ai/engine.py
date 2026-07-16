"""Ảnh 17 · So sánh 2 mã bằng AI — nạp số liệu thật rồi ép JSON schema cứng."""
from __future__ import annotations

import json
import re
import time

from modules.common.legal import DISCLAIMER, LEGAL_PROMPT_RULE, check_payload
from modules.common.sector_vi import vi as sector_vi

ASPECTS = ["Quy mô", "Tăng trưởng", "Hiệu quả", "Sức khỏe tài chính", "Định giá"]

SYSTEM_PROMPT = """Bạn là Market Pulse — công cụ SO SÁNH DỮ LIỆU giữa 2 cổ phiếu Việt Nam.

NGUYÊN TẮC SẮT (vi phạm = câu trả lời bị từ chối):
1. CHỈ dùng số liệu trong khối DỮ LIỆU bên dưới. Không bịa số, không dùng kiến thức ngoài.
2. Mỗi nhận định phải kèm CON SỐ lấy từ dữ liệu (vd "ROE 21,3% so với 12,1%").
3. TUYỆT ĐỐI KHÔNG kết luận nên chọn/mua/bán/nắm giữ mã nào, KHÔNG xếp hạng "tốt hơn"
   theo nghĩa khuyến nghị đầu tư. Chỉ MÔ TẢ khác biệt định lượng.
4. Trường 'note' chỉ được nói: nhà đầu tư quan tâm KHÍA CẠNH nào thì nên TÌM HIỂU THÊM
   dữ liệu gì — KHÔNG được gợi ý chọn mã.
5. Thiếu dữ liệu ở khía cạnh nào thì ghi rõ "chưa đủ dữ liệu", không suy đoán.
""" + LEGAL_PROMPT_RULE + """
TRẢ VỀ DUY NHẤT 1 JSON (không markdown fence, không chữ ngoài JSON):
{
 "same": ["3-5 điểm GIỐNG nhau, mỗi điểm kèm số"],
 "diff": [
   {"aspect": "Quy mô|Tăng trưởng|Hiệu quả|Sức khỏe tài chính|Định giá",
    "a": "1 câu về mã A kèm số", "b": "1 câu về mã B kèm số",
    "gap": "chênh lệch nói bằng số (vd 'gấp 2,4 lần' hoặc 'cách 9,2 điểm %')"}
 ],
 "risks": {"a": ["2-3 rủi ro riêng của A, kèm số"], "b": ["2-3 rủi ro riêng của B, kèm số"]},
 "note": "1 câu: quan tâm khía cạnh nào thì tìm hiểu thêm dữ liệu gì (KHÔNG gợi ý chọn mã)",
 "disclaimer": \"""" + DISCLAIMER + """\"
}
Bắt buộc có đủ 5 phần tử 'diff' theo đúng 5 aspect trên."""


def _num(v):
    try:
        f = float(v)
        return f if f == f else None      # loại NaN
    except (TypeError, ValueError):
        return None


def _fmt(v, unit=""):
    n = _num(v)
    if n is None:
        return "chưa có dữ liệu"
    if abs(n) >= 1e9:
        return f"{n/1e9:,.0f} tỷ".replace(",", ".")
    if abs(n) >= 1000:
        return f"{n:,.0f}{unit}".replace(",", ".")
    return f"{n:,.2f}{unit}".replace(",", "X").replace(".", ",").replace("X", ".")


def _facts_one(sym: str, d: dict) -> str:
    """Dựng khối dữ kiện của 1 mã từ payload stock_detail (đã có sẵn ở compare)."""
    info = d.get("info") or {}
    fund = d.get("fund") or {}
    health = d.get("health") or {}
    price = d.get("price") or {}
    L = [f"--- MÃ {sym} ---",
         f"Tên: {info.get('name') or '?'}",
         f"Ngành: {sector_vi(info.get('sector'))} | Sàn: {info.get('exchange') or '?'}",
         f"Vốn hóa: {_fmt(info.get('market_cap'))}",
         f"Giá gần nhất: {_fmt(price.get('last') or info.get('current_price'))} đ"
         f" ({price.get('as_of') or 'không rõ ngày'})"]
    for label, key in (("P/E", "pe"), ("P/B", "pb"), ("ROE %", "roe"), ("ROA %", "roa"),
                       ("Biên LN gộp %", "gross_margin"), ("Biên LN ròng %", "net_margin"),
                       ("Nợ/VCSH", "debt_equity"), ("EPS", "eps"),
                       ("Tăng trưởng doanh thu %", "revenue_growth"),
                       ("Tăng trưởng LNST %", "profit_growth")):
        if key in fund:
            L.append(f"{label}: {_fmt(fund.get(key))}")
    if health:
        L.append(f"Điểm sức khỏe (0-100): {_fmt(health.get('health_score'))}"
                 f" | Altman Z'': {_fmt(health.get('z_score'))} ({health.get('z_zone') or '?'})"
                 f" | Piotroski F: {_fmt(health.get('f_score'))}")
        if health.get("group") == "TCTC":
            L.append("Lưu ý: là tổ chức tài chính — Z''-score không áp dụng.")
    return "\n".join(L)


def _validate(ans: dict) -> str | None:
    if not isinstance(ans, dict):
        return "không phải object"
    for k in ("same", "diff", "risks"):
        if k not in ans:
            return f"thiếu '{k}'"
    if not isinstance(ans["diff"], list) or len(ans["diff"]) < 3:
        return "'diff' phải là mảng ≥3 khía cạnh"
    for i, x in enumerate(ans["diff"]):
        if not isinstance(x, dict) or not x.get("aspect"):
            return f"diff[{i}] thiếu 'aspect'"
        if not (x.get("a") and x.get("b")):
            return f"diff[{i}] thiếu mô tả cho 1 trong 2 mã"
    return None


def compare_ai(sym_a: str, sym_b: str, data_a: dict, data_b: dict,
               prefer: str = "auto") -> dict:
    """So sánh 2 mã; trả {a, b, answer, mode, transport, elapsed_s} hoặc {error}."""
    t0 = time.time()
    user_msg = ("DỮ LIỆU 2 MÃ CẦN SO SÁNH (chỉ dùng đúng những số này):\n\n"
                + _facts_one(sym_a, data_a) + "\n\n" + _facts_one(sym_b, data_b)
                + f"\n\nSo sánh theo đúng 5 khía cạnh: {', '.join(ASPECTS)}. "
                  f"Trong JSON, 'a' là {sym_a}, 'b' là {sym_b}.")

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
                        err = (f"dùng từ cấm pháp lý: {', '.join(banned)} — chỉ mô tả "
                               "khác biệt định lượng, KHÔNG khuyến nghị chọn mã")
                    feedback = (f"\n\nLƯU Ý: lần trước bị từ chối ({err}). "
                                "Trả lại ĐÚNG JSON theo schema.")
                except Exception as e:
                    error = str(e)[:300]
                    time.sleep(1)
    except Exception as e:
        error = str(e)[:300]

    if answer is None:
        return {"error": error or "AI chưa trả về kết quả hợp lệ. "
                                  "Kiểm tra kênh Gemini (CDP :9222) rồi thử lại."}
    answer.setdefault("disclaimer", DISCLAIMER)
    return {"a": sym_a, "b": sym_b, "answer": answer, "mode": "gemini",
            "transport": transport, "elapsed_s": round(time.time() - t0, 1)}
