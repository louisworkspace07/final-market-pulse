# -*- coding: utf-8 -*-
"""Engine AI "Nhận định bối cảnh vĩ mô" — 2 lượt trong 1 phiên (C2).

Lượt 1 "Bức tranh": tổng hợp điểm sáng/tối kèm bằng chứng [M..].
Lượt 2 "Kênh truyền dẫn tới TTCK": mô tả CƠ CHẾ (tỷ giá/lãi suất/xuất khẩu…) —
tuyệt đối KHÔNG "nên làm gì". Cả 2 lượt: chèn LEGAL_PROMPT_RULE, quét từ cấm
(check_payload), validate citation với tập [M..] từ collector.

Tái dùng gemini_transport.open_session (fail-fast) + legal.check_payload.
"""
from __future__ import annotations

import json
import os
import re
import time

from modules.common import legal
from modules.market_overview.gemini_transport import open_session, parse_json_answer
from . import collector

# Bóc mọi mã trích dẫn dạng [M..] trong text tự do lẫn trong mảng bằng chứng.
_CITE_RE = re.compile(r"\[?(M\d+)\]?")


def _prompt_context(text_block: str) -> str:
    return (
        "Bạn là chuyên gia phân tích kinh tế vĩ mô Việt Nam. Dưới đây là DỮ LIỆU "
        "vĩ mô mới nhất (World Bank, tỷ giá, dự báo SARIMAX, VNINDEX, tin tức có mã "
        "trích dẫn [M..]). HÃY ĐỌC KỸ, chưa trả lời gì cả, chỉ xác nhận đã nắm dữ liệu.\n\n"
        + text_block +
        "\n\nKhi trích dẫn tin, CHỈ dùng đúng các mã [M..] có trong danh sách trên, "
        "KHÔNG bịa mã mới. Trả lời 'ĐÃ NẮM DỮ LIỆU' để tiếp tục."
        + legal.LEGAL_PROMPT_RULE)


_PROMPT_BUC_TRANH = (
    "LƯỢT 1 — BỨC TRANH VĨ MÔ. Chỉ dựa vào dữ liệu đã cung cấp, trả về JSON THUẦN "
    "(không chữ thừa, không markdown) đúng schema:\n"
    "{\n"
    '  "buc_tranh_chung": "3-4 câu tổng hợp bức tranh vĩ mô hiện tại, có số liệu",\n'
    '  "diem_sang": [{"y": "điểm tích cực", "so_lieu": "con số cụ thể", "bang_chung": ["M.."]}],\n'
    '  "diem_toi":  [{"y": "điểm rủi ro/tiêu cực", "so_lieu": "con số", "bang_chung": ["M.."]}],\n'
    '  "do_tuoi_du_lieu": "nhận xét độ tươi/độ trễ của dữ liệu (WB trễ theo năm, tỷ giá realtime...)"\n'
    "}\n"
    "Mỗi diem_sang/diem_toi 2-4 mục. bang_chung chỉ chứa mã [M..] có thật. "
    "Nêu số liệu chính xác từ dữ liệu, không làm tròn sai lệch." + legal.LEGAL_PROMPT_RULE)


_PROMPT_KENH = (
    "LƯỢT 2 — KÊNH TRUYỀN DẪN VĨ MÔ TỚI THỊ TRƯỜNG CHỨNG KHOÁN. Trả JSON THUẦN đúng schema:\n"
    "{\n"
    '  "kenh_truyen_dan": [{"kenh": "tỷ giá|lãi suất|xuất khẩu|FDI|lạm phát|thanh khoản",\n'
    '     "co_che": "mô tả CƠ CHẾ tác động + dữ kiện lịch sử", \n'
    '     "trang_thai_hien_tai": "trạng thái hiện tại kèm số cụ thể"}],\n'
    '  "rui_ro_vi_mo": ["rủi ro vĩ mô cần lưu ý, kèm dữ kiện"],\n'
    '  "theo_doi": ["chỉ báo/mốc dữ liệu nên theo dõi (KHÔNG phải hành động mua bán)"],\n'
    '  "disclaimer": "câu miễn trừ"\n'
    "}\n"
    "3-5 kênh truyền dẫn. CHỈ MÔ TẢ CƠ CHẾ và dữ kiện — TUYỆT ĐỐI không nói người "
    "dùng nên mua/bán/giữ/gia tăng tỷ trọng gì. 'theo_doi' là các mốc DỮ LIỆU để "
    "quan sát, không phải lệnh giao dịch." + legal.LEGAL_PROMPT_RULE)


def _invalid_citations(obj, valid: set) -> list[str]:
    """Mã [M..] xuất hiện trong output nhưng KHÔNG thuộc tập hợp lệ."""
    found = set()

    def walk(o):
        if isinstance(o, str):
            found.update(_CITE_RE.findall(o))
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(obj)
    return sorted(m for m in found if m not in valid)


def _ask_json(session, prompt: str, valid: set, label: str) -> dict:
    """Hỏi 1 lượt → parse JSON → check_payload (legal) → validate citation.

    Từ cấm hoặc citation lạ → phản hồi sửa NGAY trong cùng phiên (1 lần), rồi thôi
    (fail-fast, không lặp vô hạn)."""
    raw = session.ask(prompt)
    try:
        data = parse_json_answer(raw)
    except Exception:
        raw = session.ask("Câu trả lời chưa phải JSON hợp lệ. Trả lại ĐÚNG JSON thuần, "
                          "không kèm chữ nào khác.")
        data = parse_json_answer(raw)

    banned = legal.check_payload(data)
    bad_cites = _invalid_citations(data, valid)
    if banned or bad_cites:
        msg = "Sửa lại JSON: "
        if banned:
            msg += f"BỎ các cụm từ cấm {banned} (chỉ mô tả dữ kiện, không ra lệnh hành động). "
        if bad_cites:
            msg += f"BỎ hoặc thay các mã trích dẫn KHÔNG hợp lệ {bad_cites} — chỉ dùng mã [M..] có thật. "
        msg += "Trả lại JSON thuần đúng schema."
        raw = session.ask(msg)
        try:
            data = parse_json_answer(raw)
        except Exception:
            pass
        banned = legal.check_payload(data)
        bad_cites = _invalid_citations(data, valid)

    data.setdefault("_meta", {})
    data["_meta"].update({"part": label, "banned_hits": banned,
                          "invalid_citations": bad_cites})
    return data


def analyze(db_path: str, data_dir: str, prefer: str = "auto",
            progress=None) -> dict:
    """Chạy 2 lượt AI, trả kết quả đầy đủ. progress(step, status, detail) tuỳ chọn.

    Fail-fast: lỗi phiên/AI → ném RuntimeError để tầng job bắt và báo lỗi rõ ràng."""
    def _p(step, status, detail=""):
        if progress:
            progress(step, status, detail)

    packed = collector.collect(db_path, data_dir)
    valid = set(packed["valid_ids"])

    _p("collect", "done", f"{len(valid)} tin [M..]")
    session = open_session(prefer)
    transport = getattr(session, "transport", "?")
    try:
        _p("context", "running", transport)
        session.ask(_prompt_context(packed["text_block"]))
        _p("context", "done", transport)

        _p("buc_tranh", "running")
        buc_tranh = _ask_json(session, _PROMPT_BUC_TRANH, valid, "buc_tranh")
        _p("buc_tranh", "done")

        _p("kenh", "running")
        kenh = _ask_json(session, _PROMPT_KENH, valid, "kenh_truyen_dan")
        _p("kenh", "done")
    finally:
        try:
            session.close()
        except Exception:
            pass

    return {
        "buc_tranh": buc_tranh,
        "kenh_truyen_dan": kenh,
        "news_meta": packed["news_meta"],
        "valid_ids": packed["valid_ids"],
        "disclaimer": legal.DISCLAIMER,
        "transport": transport,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def save_result(data_dir: str, result: dict) -> str:
    path = os.path.join(data_dir, "macro_ai.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    return path
