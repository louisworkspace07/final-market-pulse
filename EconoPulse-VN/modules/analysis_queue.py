"""§18 · Hàng đợi yêu cầu phân tích BCTC (P4) cho mã chưa có `ai_analysis`.

Trước đây mã chưa chạy P4 chỉ hiện card xám "chưa có phân tích" — người dùng
không làm gì được. Nay bấm nút là mã vào hàng đợi, worker P4 nhặt về chạy.

Thiết kế cố ý đơn giản (2 file JSON trong Crawl Data/temp/):
  analysis_queue.json   — hàng đợi FIFO các mã chờ
  analysis_status.json  — {mã: {state, ts, msg}} để UI hỏi tiến độ
Không dùng DB vì SQLite ở đây chỉ 1 writer, mà P4 đang giữ quyền ghi.
"""
from __future__ import annotations

import json
import os
import time

_TEMP = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "Crawl Data", "temp")
QUEUE_FILE = os.path.join(_TEMP, "analysis_queue.json")
STATUS_FILE = os.path.join(_TEMP, "analysis_status.json")

MAX_QUEUE = 50          # chặn spam: hàng đợi dài hơn thì từ chối nhận thêm


def _read(path, fallback):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return fallback


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)          # ghi nguyên tử, không để lại file dở


def enqueue(symbol: str) -> dict:
    """Đưa 1 mã vào hàng đợi. Trả trạng thái hiện tại của mã đó."""
    sym = symbol.upper().strip()
    if not sym:
        return {"error": "Thiếu mã."}
    q = _read(QUEUE_FILE, [])
    st = _read(STATUS_FILE, {})

    cur = st.get(sym)
    if cur and cur.get("state") == "running":
        return {"symbol": sym, "state": "running", "msg": "Đang phân tích…"}
    if sym in q:
        return {"symbol": sym, "state": "queued", "position": q.index(sym) + 1,
                "msg": f"Đã xếp hàng (#{q.index(sym) + 1})"}
    if len(q) >= MAX_QUEUE:
        return {"error": f"Hàng đợi đang đầy ({len(q)} mã). Thử lại sau."}

    q.append(sym)
    _write(QUEUE_FILE, q)
    st[sym] = {"state": "queued", "ts": time.time()}
    _write(STATUS_FILE, st)
    return {"symbol": sym, "state": "queued", "position": len(q),
            "msg": f"Đã xếp hàng (#{len(q)})"}


def status(symbol: str) -> dict:
    """Trạng thái 1 mã: queued | running | done | error | none."""
    sym = symbol.upper().strip()
    st = _read(STATUS_FILE, {}).get(sym)
    if not st:
        return {"symbol": sym, "state": "none"}
    out = {"symbol": sym, "state": st.get("state", "none"), "msg": st.get("msg", "")}
    if out["state"] == "queued":
        q = _read(QUEUE_FILE, [])
        if sym in q:
            out["position"] = q.index(sym) + 1
            out["msg"] = f"Đã xếp hàng (#{out['position']})"
    return out


# ------------------------------------------------------------------ phía worker
def pop() -> str | None:
    """Worker lấy mã tiếp theo và đánh dấu đang chạy."""
    q = _read(QUEUE_FILE, [])
    if not q:
        return None
    sym = q.pop(0)
    _write(QUEUE_FILE, q)
    st = _read(STATUS_FILE, {})
    st[sym] = {"state": "running", "ts": time.time()}
    _write(STATUS_FILE, st)
    return sym


def finish(symbol: str, ok: bool, msg: str = "") -> None:
    """Worker báo kết quả để UI dừng poll."""
    st = _read(STATUS_FILE, {})
    st[symbol.upper().strip()] = {
        "state": "done" if ok else "error", "ts": time.time(),
        "msg": msg or ("Đã phân tích xong" if ok else "Phân tích lỗi"),
    }
    _write(STATUS_FILE, st)


def pending() -> list:
    return _read(QUEUE_FILE, [])
