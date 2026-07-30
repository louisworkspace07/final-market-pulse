# -*- coding: utf-8 -*-
"""Soi Tin Engine — tổng hợp nhãn factcheck có dẫn chứng.

Quy trình (song song engine của Copilot):
1. extractor.extract_claims() bóc claim + mã + loại.
2. checker.check_claims() đối chiếu market.db → bằng chứng + tín hiệu trung tính.
3. Gọi Gemini (qua gemini_transport.open_session) ép JSON schema cứng: mỗi claim
   1 nhãn TRUNG TÍNH (co_cong_bo/khong_thay/khong_kiem_chung/mau_thuan) + giải
   thích chỉ dựa trên bằng chứng [E..]/[N..] checker đưa. Cấm tự sinh số/nguồn.
4. Validate + quét từ cấm pháp lý (check_payload). Sai → retry (tối đa 2).
5. AI lỗi/tắt kênh → fallback thuần Python từ chính tín hiệu checker (mode=offline).

LƯU Ý PHÁP LÝ: KHÔNG kết luận "tin thật/giả" tuyệt đối, KHÔNG quy kết thao túng,
KHÔNG hô hào mua bán. Chỉ nói dữ liệu công bố nói gì so với tin đồn.
"""
from __future__ import annotations

import json
import re
import time

from modules.common.legal import DISCLAIMER, LEGAL_PROMPT_RULE, check_payload
from . import checker as _checker
from .extractor import extract_claims, all_symbols

# Nhãn hợp lệ AI được phép gán (khớp tín hiệu checker + 1 nhãn mâu thuẫn).
LABELS = {"co_cong_bo", "khong_thay", "khong_kiem_chung", "mau_thuan"}
LABEL_VI = {
    "co_cong_bo": "Có dữ liệu công bố liên quan",
    "khong_thay": "Chưa có công bố xác nhận",
    "khong_kiem_chung": "Không kiểm chứng được",
    "mau_thuan": "Mâu thuẫn với công bố",
}

SYSTEM_PROMPT = """Bạn là Market Pulse — Soi Tin: công cụ ĐỐI CHIẾU tin đồn thị trường với DỮ LIỆU CÔNG BỐ CHÍNH THỨC (KHÔNG phải dịch vụ tư vấn đầu tư, KHÔNG kết luận thật/giả).

NGUYÊN TẮC SẮT (vi phạm = câu trả lời bị từ chối):
1. Với mỗi claim, chỉ dựa trên danh sách BẰNG CHỨNG kèm theo (mã [E..]/[N..]). KHÔNG tự bịa nguồn, số liệu, hay sự kiện không có trong bằng chứng.
2. Mỗi claim gán ĐÚNG 1 nhãn trong: co_cong_bo | khong_thay | khong_kiem_chung | mau_thuan.
3. TUYỆT ĐỐI KHÔNG kết luận tin "đúng" hay "sai/giả" một cách chắc chắn. Chỉ nói dữ liệu công bố cho thấy gì. Dùng "chưa có công bố xác nhận", KHÔNG dùng "tin giả".
4. TUYỆT ĐỐI KHÔNG quy kết thao túng/đội lái/bơm thổi, KHÔNG khuyến nghị mua-bán-nắm giữ, KHÔNG cam kết giá.
5. Khi gán nhãn phải trích mã bằng chứng đã cho dạng [E123]/[N45]. Không có bằng chứng → nhãn khong_thay hoặc khong_kiem_chung.
6. (Ảnh 13) Trả lời PHẢI ĐỦ Ý, không được 1 dòng cụt. Với mỗi claim:
   - Nếu nhãn co_cong_bo hoặc mau_thuan: BẮT BUỘC trích ÍT NHẤT 1 CON SỐ NGUYÊN VĂN
     từ công bố (tỷ lệ, số tiền, ngày) vào trường 'so_lieu_trich'.
   - 'diem_lech': nói rõ tin đồn nói gì SO VỚI công bố nói gì (số vs số, hoặc
     "công bố KHÔNG đề cập nội dung X mà tin đồn nêu"). Không có khác biệt → null.
   - 'boi_canh': 1-2 câu bối cảnh liên quan gần nhất của mã (sự kiện/BCTC/tin) lấy
     TỪ BẰNG CHỨNG đã cho — giúp người đọc tự đánh giá. Không có → null.
""" + LEGAL_PROMPT_RULE + """
TRẢ VỀ DUY NHẤT 1 JSON (không markdown fence, không văn bản ngoài JSON):
{
 "tong_quan": "2-3 câu: bao nhiêu claim có công bố liên quan, bao nhiêu chưa kiểm chứng, điểm đáng lưu ý nhất (không kết luận thật/giả)",
 "claims": [
   {"text": "nguyên văn claim", "nhan": "co_cong_bo|khong_thay|khong_kiem_chung|mau_thuan",
    "giai_thich": "2-3 câu dựa THUẦN trên bằng chứng, có dẫn [E..]/[N..] nếu có",
    "so_lieu_trich": "số liệu nguyên văn từ công bố, hoặc null",
    "diem_lech": "tin đồn nói X, công bố nói Y — hoặc null nếu không lệch",
    "boi_canh": "1-2 câu bối cảnh gần nhất của mã từ bằng chứng, hoặc null",
    "bang_chung": ["E123","N45"]}
 ],
 "disclaimer": "%s"
}""" % DISCLAIMER


def _facts_block(checks: list) -> str:
    lines = []
    for i, ch in enumerate(checks, 1):
        c = ch.claim
        lines.append(f"--- CLAIM {i} [{c['kind']}] mã={c['symbols'] or 'không rõ'} ---")
        lines.append(f"Nội dung: {c['text']}")
        lines.append(f"Tín hiệu đối chiếu DB: {ch.signal} — {ch.note}")
        if ch.evidence:
            for e in ch.evidence:
                lines.append(f"  [{e['id']}] ({e['date']}) {e['symbol']}: {e['title']}")
        else:
            lines.append("  (không có công bố khớp trong DB)")
    return "\n".join(lines)


def _validate(ans: dict, n_claims: int) -> str | None:
    if "claims" not in ans or not isinstance(ans["claims"], list):
        return "thiếu mảng 'claims'"
    if len(ans["claims"]) != n_claims:
        return f"'claims' phải có đúng {n_claims} phần tử (đang có {len(ans['claims'])})"
    for i, c in enumerate(ans["claims"]):
        if not isinstance(c, dict):
            return f"claim[{i}] không phải object"
        if c.get("nhan") not in LABELS:
            return f"claim[{i}] nhãn không hợp lệ: {c.get('nhan')!r}"
        if not c.get("giai_thich"):
            return f"claim[{i}] thiếu 'giai_thich'"
    if "tong_quan" not in ans:
        return "thiếu 'tong_quan'"
    return None


def _offline_answer(checks: list) -> dict:
    """Fallback thuần Python: nhãn = chính tín hiệu checker, giải thích = note."""
    claims = []
    for ch in checks:
        claims.append({
            "text": ch.claim["text"],
            "nhan": ch.signal,
            "giai_thich": ch.note,
            "bang_chung": [e["id"] for e in ch.evidence],
        })
    n_pub = sum(1 for c in claims if c["nhan"] == "co_cong_bo")
    n_none = sum(1 for c in claims if c["nhan"] in ("khong_thay", "khong_kiem_chung"))
    return {
        "tong_quan": (f"Chế độ đối chiếu dữ liệu (không có tầng diễn giải AI): "
                      f"{n_pub}/{len(claims)} nhận định có công bố chính thức liên quan, "
                      f"{n_none} chưa được kiểm chứng bằng dữ liệu."),
        "claims": claims,
        "disclaimer": DISCLAIMER,
    }


def factcheck(text: str, prefer: str = "auto", today: str | None = None) -> dict:
    """Soi 1 đoạn tin đồn → nhãn từng claim + bằng chứng + tổng quan."""
    t0 = time.time()
    text = (text or "").strip()
    if not text:
        return {"error": "Chưa có nội dung tin để soi."}

    claims = extract_claims(text)
    checks = _checker.check_claims(claims, today=today)
    evidence = _checker.evidence_map(checks)
    symbols = all_symbols(claims)

    user_msg = ("Dưới đây là các nhận định (claim) tách từ tin người dùng dán, kèm "
                "tín hiệu đối chiếu cơ sở dữ liệu và bằng chứng công bố (nếu có). "
                "Gán nhãn trung tính cho từng claim theo đúng schema.\n\n"
                + _facts_block(checks))

    answer, mode, error, transport = None, "gemini", None, None
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
                    err = _validate(cand, len(claims))
                    if err is None:
                        banned = check_payload(cand)
                        if not banned:
                            answer = cand
                            break
                        err = (f"dùng từ cấm pháp lý: {', '.join(banned)} — "
                               "chỉ mô tả dữ liệu công bố, không quy kết/khuyến nghị")
                    feedback = (f"\n\nLƯU Ý: lần trước bị từ chối ({err}). "
                                "Trả lại đúng JSON theo schema.")
                except Exception as e:
                    error = str(e)[:300]
                    time.sleep(1)
    except Exception as e:
        error = str(e)[:300]

    if answer is None:
        answer = _offline_answer(checks)
        mode = "offline"

    return {
        "input": text,
        "answer": answer,
        "evidence": evidence,
        "symbols": symbols,
        "n_claims": len(claims),
        "mode": mode,
        "transport": transport if mode == "gemini" else "rule-based",
        "error": error,
        "elapsed_s": round(time.time() - t0, 1),
    }


if __name__ == "__main__":
    r = factcheck("Nghe nói HPG sắp chia cổ tức tiền mặt 20%. VNM bị nghi gian lận sổ sách.",
                  prefer="api", today="2026-07-08")
    print(json.dumps(r, ensure_ascii=False, indent=1)[:3000])
