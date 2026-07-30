# -*- coding: utf-8 -*-
"""Decision Copilot Engine — Trụ cột 2 (Phản biện có dẫn chứng).

Quy trình:
1. collect_facts() gom số liệu tầng định lượng (kèm id, nguồn, độ tin cậy).
2. Gọi AI (LOCAL API :4000 mặc định, dự phòng Gemini API key) với system prompt
   ép JSON schema cứng:
   { tom_tat_du_kien, luan_diem[], gia_dinh[], rui_ro[], disclaimer }
   — mọi số liệu phải tham chiếu fact id [F1], [F2]... LLM không được bịa số.
3. Validate schema; sai → retry (tối đa 2 lần) kèm thông báo lỗi cho model.
4. API lỗi/hết quota → fallback rule-based từ chính facts (gắn mode="offline")
   để demo không bao giờ chết — và luôn minh bạch đang ở chế độ nào.

LƯU Ý PHÁP LÝ: cố tình KHÔNG sinh "kịch bản xác suất mua/bán" (Base/Bull/Bear
+ %) cho từng mã — dạng output đó có thể bị coi là tư vấn đầu tư (cần giấy phép
UBCKNN). Chỉ cung cấp dữ kiện + phản biện, không dự phóng hành động giao dịch.
"""
import json
import os
import re
import time

import requests

from .facts import collect_facts
from modules.common import local_api
from modules.common.legal import (DISCLAIMER, LEGAL_PROMPT_RULE, check_payload)

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(BASE, "..", ".."))
ENV_PATH = os.path.normpath(os.path.join(ROOT, "..", "econolens-chat", ".env"))

SCHEMA_KEYS = ["tom_tat_du_kien", "luan_diem", "gia_dinh", "rui_ro"]

SYSTEM_PROMPT = """Bạn là Market Pulse Copilot — AI cung cấp THÔNG TIN & PHÂN TÍCH DỮ LIỆU cho nhà đầu tư cá nhân Việt Nam (KHÔNG phải dịch vụ tư vấn đầu tư).

NGUYÊN TẮC SẮT (vi phạm = câu trả lời bị từ chối):
1. CHỈ dùng số liệu từ danh sách FACTS bên dưới. Mỗi lần dùng phải ghi kèm mã fact dạng [F1], [F2].
2. KHÔNG được tự bịa bất kỳ con số nào không có trong FACTS. Nếu thiếu dữ liệu, nói thẳng "chưa đủ dữ liệu".
3. BẮT BUỘC có phần phản biện: giả định của chính bạn + yếu tố khiến bạn SAI.
4. TUYỆT ĐỐI KHÔNG dự phóng kịch bản giá / xác suất tăng-giảm / khuyến nghị mua-bán-nắm giữ cho bất kỳ mã nào. Chỉ mô tả DỮ KIỆN và rủi ro.
""" + LEGAL_PROMPT_RULE + """
TRẢ VỀ DUY NHẤT 1 JSON (không markdown fence, không văn bản ngoài JSON):
{
 "tom_tat_du_kien": "1-2 câu tóm tắt các DỮ KIỆN quan trọng nhất (không kết luận mua/bán), có dẫn fact id",
 "luan_diem": ["quan sát/luận điểm dữ liệu 1 kèm số liệu [Fx]", "quan sát 2 [Fy]", "..."],
 "gia_dinh": ["giả định 1 đang dùng làm căn cứ", "..."],
 "rui_ro": ["yếu tố có thể khiến nhận định sai / rủi ro người dùng dễ bỏ qua", "..."],
 "disclaimer": "%s"
}""" % DISCLAIMER


def _gemini_config():
    if not os.path.exists(ENV_PATH):
        return None, None
    env = open(ENV_PATH, encoding="utf-8").read()
    key = re.search(r"GEMINI_API_KEY=(.+)", env)
    model = re.search(r"GEMINI_MODEL=(.+)", env)
    return (key.group(1).strip() if key else None,
            model.group(1).strip() if model else "gemini-2.5-flash")


def _validate(ans: dict) -> str | None:
    for k in SCHEMA_KEYS:
        if k not in ans:
            return f"thiếu trường '{k}'"
    for k in ["luan_diem", "gia_dinh", "rui_ro"]:
        if not isinstance(ans[k], list) or not ans[k]:
            return f"'{k}' phải là mảng không rỗng"
    return None


def _resolve_channel() -> tuple[str, str]:
    """Kênh AI dùng cho copilot: local API trước, Gemini API key sau.

    Trả (kênh, nhãn model) — ("local_api", <model local>) hoặc ("api", <model>)
    hoặc ("", "") khi không có kênh nào."""
    if local_api.configured():
        return "local_api", local_api.model()
    key, model = _gemini_config()
    return ("api", model) if key else ("", "")


def _call_ai(channel: str, model: str, system: str, user: str) -> str:
    """1 lượt hỏi theo kênh đã chọn. Cả 2 kênh đều nhận system + user."""
    if channel == "local_api":
        return local_api.ask_messages([{"role": "system", "content": system},
                                       {"role": "user", "content": user}])
    key, _ = _gemini_config()
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={key}")
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"maxOutputTokens": 16384,
                             "responseMimeType": "application/json",
                             "thinkingConfig": {"thinkingBudget": 0}},
    }
    r = requests.post(url, json=payload, timeout=60)
    r.raise_for_status()
    parts = r.json()["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts)


def _offline_answer(question: str, facts: list[dict]) -> dict:
    """Fallback rule-based khi API lỗi — sinh từ chính facts, minh bạch mode."""
    macro = [f for f in facts if "GDP" in f["label"] or "CPI" in f["label"]]
    mkt = [f for f in facts if "chỉ số" in f["label"].lower()]
    sym = [f for f in facts if "điểm sức khỏe" in f["label"]]
    luan_diem = [f"{f['label']}: {f['value']} [{f['id']}]" for f in (macro + mkt + sym)[:4]]
    return {
        "tom_tat_du_kien": "Chế độ ngoại tuyến: dưới đây là tổng hợp thuần định lượng từ "
                           "dữ liệu đã kiểm chứng (không có tầng diễn giải AI).",
        "luan_diem": luan_diem or ["Chưa đủ dữ liệu cho câu hỏi này."],
        "gia_dinh": ["Các mô hình giả định cấu trúc dữ liệu quá khứ còn lặp lại "
                      "trong tương lai gần (không có cú sốc ngoại sinh)."],
        "rui_ro": ["Backtest chứa giai đoạn COVID — sai số thực tế có thể cao hơn.",
                    "Chế độ ngoại tuyến không phân tích được ngữ cảnh câu hỏi."],
        "disclaimer": DISCLAIMER,
    }


def ask(question: str, portfolio: list[dict] | None = None) -> dict:
    t0 = time.time()
    bundle = collect_facts(question, portfolio)
    facts = bundle["facts"]

    facts_txt = "\n".join(
        f"[{f['id']}] {f['label']} = {f['value']} "
        f"(nguồn: {f['source']} · cập nhật: {f['updated_at']} · độ tin cậy: {f['confidence']})"
        for f in facts)
    user_msg = f"FACTS:\n{facts_txt}\n\nCÂU HỎI CỦA NHÀ ĐẦU TƯ:\n{question}"
    if portfolio:
        user_msg += f"\n\nDANH MỤC ĐANG NẮM GIỮ: {json.dumps(portfolio, ensure_ascii=False)}"

    channel, model = _resolve_channel()
    answer, mode, error = None, (channel or "offline"), None
    if channel:
        feedback = ""
        for attempt in range(3):
            try:
                raw = _call_ai(channel, model, SYSTEM_PROMPT, user_msg + feedback)
                raw = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.M).strip()
                cand = json.loads(raw)
                err = _validate(cand)
                if err is None:
                    banned = check_payload(cand)
                    if not banned:
                        answer = cand
                        break
                    err = f"dùng từ cấm pháp lý: {', '.join(banned)} — chỉ mô tả dữ kiện"
                feedback = (f"\n\nLƯU Ý: lần trả lời trước bị từ chối ({err}). "
                            "Trả lại đúng JSON theo yêu cầu.")
            except Exception as e:
                error = str(e)[:300]
                time.sleep(1)
    if answer is None:
        answer = _offline_answer(question, facts)
        mode = "offline"

    return {
        "question": question,
        "answer": answer,
        "facts": facts,
        "symbols": bundle["symbols"],
        "mode": mode,
        "model": model if mode in ("local_api", "api") else "rule-based",
        "error": error,
        "elapsed_s": round(time.time() - t0, 1),
    }


if __name__ == "__main__":
    r = ask("FPT đang có những dữ kiện gì đáng chú ý trong bối cảnh GDP tăng?")
    print(json.dumps(r, ensure_ascii=False, indent=1)[:4000])
