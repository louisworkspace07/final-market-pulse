# -*- coding: utf-8 -*-
"""D-3 · AI viết lời dẫn cho biểu đồ — PLAN-F0-TRUC-QUAN Phụ lục D.

RÀNG BUỘC D0 — AI KHÔNG SINH SỐ. Ở đây AI chỉ được:
  - đặt tiêu đề nói thẳng biểu đồ cho thấy điều gì,
  - viết cách đọc cho người mới,
  - so sánh với chính quá khứ của mã,
  - chỉ ra kỳ đáng chú ý BẰNG NHÃN KỲ (không phải bằng con số nó tự đọc).

Mọi số vẽ lên biểu đồ vẫn do `chart_data.py` lấy từ market.db. Lời dẫn nào tham
chiếu `chart_id` hoặc kỳ KHÔNG có thật đều bị `validate()` loại bỏ — sai tên thì
mất lời dẫn, không bao giờ thành đường kẻ sai trên hình.

Chia 9 lượt theo NHÓM (A…I) thay vì 1 lượt/1 biểu đồ: mỗi lượt AI thấy cả nhóm
nên lời dẫn trong nhóm mới nhất quán — đúng chỗ 4 lượt phân tích chữ hiện tại
đang nói ngược nhau về cùng một con số tăng trưởng.

Hỏng tầng này thì biểu đồ vẫn hiện, chỉ mất lời — `merge()` luôn an toàn.
"""
import json
import os
import re

from modules.common import legal

MAX_POINTS = 14          # số điểm tóm tắt gửi kèm mỗi chuỗi
MAX_NOTE = 400           # cắt lời dẫn quá dài (AI đôi khi viết cả đoạn)


def _brief(chart: dict) -> dict:
    """Tóm tắt 1 biểu đồ đủ để AI viết lời — KHÔNG gửi toàn bộ chuỗi.

    Gửi đầu–cuối–min–max thay vì mọi điểm: AI cần biết xu hướng và điểm bất
    thường, không cần đọc lại từng số (mà cũng không được phép đọc ra)."""
    out = {"id": chart["id"], "title": chart["title"], "kind": chart["kind"],
           "unit": chart.get("unit", ""), "series": []}
    x = chart.get("x") or []
    if x:
        out["periods"] = x if len(x) <= MAX_POINTS else [x[0], "…", x[-1]]
    for s in chart.get("series", [])[:4]:
        data = s.get("data") or []
        nums = [(i, v) for i, v in enumerate(data)
                if isinstance(v, (int, float))]
        if not nums:
            continue
        lo = min(nums, key=lambda t: t[1])
        hi = max(nums, key=lambda t: t[1])
        item = {"name": s.get("name"),
                "đầu": nums[0][1], "cuối": nums[-1][1],
                "thấp nhất": {"kỳ": x[lo[0]] if lo[0] < len(x) else "?", "giá trị": lo[1]},
                "cao nhất": {"kỳ": x[hi[0]] if hi[0] < len(x) else "?", "giá trị": hi[1]}}
        out["series"].append(item)
    return out


_SCHEMA = [{
    "chart_id": "đúng id trong danh sách trên",
    "title": "1 câu nói thẳng biểu đồ cho thấy điều gì (KHÔNG phải tên trục)",
    "read_this": "2-3 câu: nhìn vào đâu, đường/cột nào nghĩa là gì (cho người mới)",
    "history_note": "1 câu so với chính quá khứ của mã, vd 'thấp nhất trong chuỗi'",
    "annotations": [{"period": "nhãn kỳ có thật", "note": "vì sao kỳ này đáng chú ý"}],
}]


def build_prompt(symbol: str, group_title: str, charts: list[dict]) -> str:
    """Prompt cho MỘT nhóm biểu đồ."""
    briefs = [_brief(c) for c in charts]
    return (
        f"Bạn viết lời dẫn cho các biểu đồ của mã {symbol}, nhóm \"{group_title}\".\n\n"
        f"DỮ LIỆU TÓM TẮT (đã tính sẵn từ báo cáo tài chính — KHÔNG tự tính lại, "
        f"KHÔNG bịa thêm số):\n"
        f"{json.dumps(briefs, ensure_ascii=False, indent=1)}\n\n"
        "Yêu cầu:\n"
        "1. Viết cho người CHƯA BIẾT GÌ về chứng khoán: câu ngắn, tiếng Việt thường "
        "ngày, không dùng từ chuyên môn để giải thích từ chuyên môn.\n"
        "2. `history_note` BẮT BUỘC với mọi biểu đồ có trục thời gian — đó là phần "
        "so sánh với quá khứ.\n"
        "3. `annotations` chỉ được dùng NHÃN KỲ có trong `periods` của chính biểu đồ đó.\n"
        "4. TUYỆT ĐỐI không dự đoán tương lai, không nói nên mua/bán/nắm giữ, không "
        "gợi ý mức giá mục tiêu. Chỉ mô tả điều biểu đồ đang cho thấy.\n"
        "5. Biểu đồ nào không có gì đáng nói thì BỎ QUA, đừng viết cho đủ.\n\n"
        f"Trả về DUY NHẤT một mảng JSON hợp lệ (không markdown) theo schema:\n"
        f"{json.dumps(_SCHEMA, ensure_ascii=False)}\n"
        + legal.LEGAL_PROMPT_RULE)


def _first_json_array(text: str):
    """Mảng [...] cân bằng ngoặc đầu tiên — AI đôi khi kèm lời dẫn ngoài JSON."""
    s = (text or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-z]*\s*|\s*```$", "", s, flags=re.S)
    i = s.find("[")
    if i < 0:
        return None
    depth, in_str, esc = 0, False, False
    for j in range(i, len(s)):
        ch = s[j]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(s[i:j + 1])
                except ValueError:
                    return None
    return None


def validate(raw: str, charts: list[dict]) -> tuple[dict, list[str]]:
    """(lời dẫn hợp lệ theo chart_id, danh sách lý do bị loại).

    Loại bỏ — KHÔNG sửa chữa — mọi mục sai. Sửa hộ AI là cách nhanh nhất để một
    lời dẫn nói về biểu đồ khác lọt lên giao diện."""
    items = _first_json_array(raw)
    if not isinstance(items, list):
        return {}, ["không đọc được mảng JSON từ phản hồi"]

    by_id = {c["id"]: c for c in charts}
    notes, bad = {}, []
    for it in items:
        if not isinstance(it, dict):
            bad.append("mục không phải object")
            continue
        cid = str(it.get("chart_id") or "").strip()
        if cid not in by_id:
            bad.append(f"chart_id không có thật: {cid!r}")
            continue
        if cid in notes:
            bad.append(f"trùng chart_id: {cid}")
            continue

        text = {k: str(it.get(k) or "").strip()[:MAX_NOTE]
                for k in ("title", "read_this", "history_note")}
        if not text["title"] and not text["read_this"]:
            bad.append(f"{cid}: rỗng")
            continue

        # Chỉ giữ chú thích trỏ vào kỳ CÓ THẬT của chính biểu đồ đó.
        periods = set(by_id[cid].get("x") or [])
        anns = []
        for a in (it.get("annotations") or [])[:4]:
            if not isinstance(a, dict):
                continue
            p = str(a.get("period") or "").strip()
            if p and p not in periods:
                bad.append(f"{cid}: kỳ không có thật {p!r}")
                continue
            note = str(a.get("note") or "").strip()[:200]
            if note:
                anns.append({"period": p, "note": note})

        hits = legal.check_payload({**text, "annotations": anns})
        if hits:
            bad.append(f"{cid}: vi phạm pháp lý {hits}")
            continue

        notes[cid] = {**text, "annotations": anns}
    return notes, bad


def groups_of(payload: dict) -> list[tuple[str, str, list[dict]]]:
    """[(khóa nhóm, tên nhóm, các biểu đồ)] — bỏ nhóm không có biểu đồ nào."""
    out = []
    for g in payload.get("groups", []):
        cs = [c for c in payload.get("charts", []) if c["group"] == g["key"]]
        if cs:
            out.append((g["key"], g["title"], cs))
    return out


def generate(payload: dict, ask, symbol: str, log=None) -> dict:
    """Chạy 9 lượt (mỗi nhóm 1 lượt). `ask(prompt) -> str` do phía gọi truyền vào.

    Một nhóm hỏng KHÔNG được làm hỏng các nhóm khác — trang vẫn có lời dẫn cho
    phần chạy được."""
    notes, report = {}, []
    for key, title, charts in groups_of(payload):
        prompt = build_prompt(symbol, title, charts)
        try:
            raw = ask(prompt)
            got, bad = validate(raw, charts)
        except Exception as exc:                     # noqa: BLE001 — mọi lỗi đều nuốt
            got, bad = {}, [f"gọi AI lỗi: {str(exc)[:120]}"]
        notes.update(got)
        report.append({"group": key, "charts": len(charts), "ok": len(got),
                       "rejected": bad})
        if log:
            log(f"  · nhóm {key} ({title}): {len(got)}/{len(charts)} biểu đồ có lời"
                + (f" — loại {len(bad)}" if bad else ""))
    return {"symbol": symbol, "notes": notes, "report": report}


def merge(payload: dict, notes: dict) -> dict:
    """Gắn lời dẫn vào payload biểu đồ. Không có lời dẫn thì trả nguyên payload."""
    if not notes:
        return payload
    for c in payload.get("charts", []):
        n = notes.get(c["id"])
        if not n:
            continue
        # `title` gốc là tên kỹ thuật; giữ lại để còn đối chiếu nguồn.
        c["title_data"] = c["title"]
        if n.get("title"):
            c["title"] = n["title"]
        for k in ("read_this", "history_note", "annotations"):
            if n.get(k):
                c[k] = n[k]
        c["narrated"] = True
    payload["narrated_count"] = sum(1 for c in payload.get("charts", []) if c.get("narrated"))
    return payload


# ---------------------------------------------------------------- lưu trữ
def path_for(db_path: str, symbol: str) -> str:
    """companies/<MÃ>/analysis/chart_notes.json — cùng chỗ với phân tích chữ."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(db_path)))
    return os.path.join(root, "companies", symbol.upper(), "analysis", "chart_notes.json")


def load(db_path: str, symbol: str) -> dict:
    p = path_for(db_path, symbol)
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return (json.load(f) or {}).get("notes") or {}
    except (OSError, ValueError):
        return {}


def save(db_path: str, symbol: str, data: dict) -> str:
    p = path_for(db_path, symbol)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return p
