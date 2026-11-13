# -*- coding: utf-8 -*-
"""Gemini Transport — 3 kênh gửi prompt, mặc định đi qua LOCAL API.

- `local_api` (MẶC ĐỊNH): HTTP tới server AI local tự phát triển (:4000, kiểu
  OpenAI). Server tự lái Gemini web bên trong → gateway không cần Chrome,
  không Playwright, không dính CAPTCHA/đăng nhập. Xem modules/common/local_api.py.
- `cdp` (dự phòng): tự lái Chrome qua Playwright connect_over_cdp — pattern cũ,
  giữ lại để fallback khi server local tắt.
- `api` (dự phòng cuối): Gemini API key trả phí.

Thứ tự thử khi ask()/open_session():  local_api  →  cdp  →  api.
Ép 1 kênh bằng prefer="local"|"cdp"|"api" hoặc env AI_TRANSPORT_REALTIME.
"""
import asyncio
import concurrent.futures
import json
import os
import queue
import re
import threading

import requests

import random

from modules.common import local_api as _local

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(BASE, "..", ".."))
GEMINI_PROFILE = os.path.normpath(
    os.path.join(ROOT, "..", "price-board", "gemini_profile"))  # giữ tương thích, không còn dùng để launch
ENV_PATH = os.path.normpath(os.path.join(ROOT, "..", "econolens-chat", ".env"))

# Chrome dùng chung. Nút "Bật Gemini Web" TỰ mở Chrome này (không cần chạy tay
# launch_chrome.py nữa) — dùng chung profile để giữ đăng nhập Gemini giữa các lần.
CDP_URL = os.environ.get("CDP_URL", "http://localhost:9222")
CDP_PORT = int(re.search(r":(\d+)", CDP_URL).group(1)) if re.search(r":(\d+)", CDP_URL) else 9222
GEMINI_URL = "https://gemini.google.com/app"
MAX_TABS = int(os.environ.get("CDP_MAX_TABS", "3"))

# Đường dẫn Chrome + profile CDP (khớp data-crawler/scripts/launch_chrome.py để dùng
# chung phiên đăng nhập). Cho phép override qua biến môi trường nếu Chrome cài chỗ khác.
CHROME_EXE = os.environ.get(
    "CHROME_EXE", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
CHROME_PROFILE = os.path.normpath(
    os.path.join(ROOT, "..", "data-crawler", "chrome_cdp_profile"))

_task_queue: "queue.Queue" = queue.Queue()
_state = {"running": False, "logged_in": False, "account": None, "last_error": None}
_sem = None  # asyncio.Semaphore(MAX_TABS), khởi tạo trong worker loop

# Phiên hội thoại đang mở: session_id -> {page, last_active(loop time)}. Mỗi phiên
# giữ 1 slot _sem suốt vòng đời (open→close) nên tối đa MAX_TABS phiên song song.
_sessions: dict = {}
SESSION_IDLE_TIMEOUT = 600  # giây — phiên không hoạt động quá lâu → tự đóng, tránh rò tab
_session_counter = [0]

# ------------------------------------------------------------ circuit breaker
# Chrome CDP hỏng dây chuyền (crash/treo/mất login) → sau BREAKER_FAIL_MAX lỗi
# trong BREAKER_WINDOW giây, KHÓA kênh CDP BREAKER_COOLDOWN giây: mọi lượt hỏi
# đi thẳng API thay vì chờ timeout CDP từng lần. Hết cooldown → half-open (cho
# thử lại 1 lần; thành công thì reset, lỗi thì khóa tiếp).
import collections
import time as _btime

BREAKER_FAIL_MAX = int(os.environ.get("AI_BREAKER_FAIL_MAX", "3"))
BREAKER_WINDOW = int(os.environ.get("AI_BREAKER_WINDOW_S", "300"))
BREAKER_COOLDOWN = int(os.environ.get("AI_BREAKER_COOLDOWN_S", "600"))
_breaker = {"fails": collections.deque(), "opened_at": None}
_breaker_lock = threading.Lock()


def _breaker_allow_cdp() -> bool:
    """False khi breaker đang mở (CDP tạm khóa). Hết cooldown → half-open."""
    with _breaker_lock:
        if _breaker["opened_at"] is None:
            return True
        if _btime.time() - _breaker["opened_at"] >= BREAKER_COOLDOWN:
            # half-open: cho 1 lượt thử; kết quả sẽ reset hoặc khóa lại
            return True
        return False


def _breaker_record_fail():
    with _breaker_lock:
        now = _btime.time()
        _breaker["fails"].append(now)
        while _breaker["fails"] and now - _breaker["fails"][0] > BREAKER_WINDOW:
            _breaker["fails"].popleft()
        if len(_breaker["fails"]) >= BREAKER_FAIL_MAX and _breaker["opened_at"] is None:
            _breaker["opened_at"] = now
            print(f"[ai_transport] breaker OPEN — CDP khóa {BREAKER_COOLDOWN}s "
                  f"sau {len(_breaker['fails'])} lỗi/{BREAKER_WINDOW}s, "
                  f"chuyển toàn bộ sang API", flush=True)
        elif _breaker["opened_at"] is not None:
            # lỗi trong lúc half-open → khóa lại từ bây giờ
            _breaker["opened_at"] = now


def _breaker_record_ok():
    with _breaker_lock:
        if _breaker["opened_at"] is not None:
            print("[ai_transport] breaker RESET — CDP hoạt động lại", flush=True)
        _breaker["fails"].clear()
        _breaker["opened_at"] = None


def breaker_status() -> dict:
    with _breaker_lock:
        opened = _breaker["opened_at"]
        remaining = 0
        if opened is not None:
            remaining = max(0, int(BREAKER_COOLDOWN - (_btime.time() - opened)))
        return {"open": opened is not None and remaining > 0,
                "fails_in_window": len(_breaker["fails"]),
                "cooldown_remaining_s": remaining}


# ------------------------------------------------------------------ CDP worker
async def _query_gemini_web(context, prompt: str) -> str:
    """Mở 1 TAB MỚI trong Chrome dùng chung → hỏi Gemini → ĐÓNG tab. Trả text sạch.

    Trần song song do _sem (asyncio.Semaphore(MAX_TABS)) kiểm soát."""
    global _sem
    if _sem is None:
        _sem = asyncio.Semaphore(MAX_TABS)
    async with _sem:
        await asyncio.sleep(0.5 + random.random() * 1.5)  # jitter tránh bị chặn
        page = await context.new_page()
        try:
            return await _query_on_page(page, prompt)
        finally:
            try:
                await page.close()
            except Exception:
                pass


async def _open_gemini_page(page) -> None:
    """Mở tab Gemini tới màn chat trống, sẵn sàng nhận prompt."""
    await page.goto(GEMINI_URL, wait_until="domcontentloaded")
    await asyncio.sleep(2)
    await page.wait_for_selector("rich-textarea", timeout=15000)


async def _ask_on_page(page, prompt: str) -> str:
    """Gõ 1 prompt vào tab Gemini ĐANG MỞ, chờ trả lời ổn định, bóc text sạch.

    Không goto — dùng lại đúng tab để Gemini giữ ngữ cảnh hội thoại. Đếm số
    message-content TRƯỚC khi hỏi để biết bong bóng trả lời mới là cái nào
    (hội thoại nhiều lượt có nhiều message-content chồng lên)."""
    prev_count = len(await page.query_selector_all("message-content"))
    await page.click("rich-textarea")
    await asyncio.sleep(0.4)
    await page.keyboard.press("Control+A")
    await page.keyboard.press("Backspace")
    await page.keyboard.insert_text(prompt)
    await asyncio.sleep(0.4)
    await page.keyboard.press("Enter")

    await asyncio.sleep(3)
    # chờ có thêm 1 bong bóng trả lời mới (so với trước khi hỏi)
    for _ in range(60):
        if len(await page.query_selector_all("message-content")) > prev_count:
            break
        await asyncio.sleep(1)
    elements = await page.query_selector_all("message-content")
    last = elements[-1]
    prev, stable, cur = "", 0, ""
    for _ in range(90):
        await asyncio.sleep(1)
        cur = await last.inner_text()
        if cur == prev and len(cur) > 0:
            stable += 1
            if stable >= 2:
                break
        else:
            stable, prev = 0, cur
    text = cur.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


async def _query_on_page(page, prompt: str) -> str:
    """Tương thích ngược: mở màn chat + hỏi 1 lượt trên cùng tab."""
    await _open_gemini_page(page)
    return await _ask_on_page(page, prompt)


async def _check_login(context) -> bool:
    """Mở 1 tab tạm kiểm tra đã đăng nhập Gemini chưa (Chrome dùng chung)."""
    page = await context.new_page()
    try:
        await page.goto(GEMINI_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_selector("rich-textarea", timeout=12000)
        sign_in = await page.query_selector_all(
            "a[href*='accounts.google.com/ServiceLogin'], a[href*='accounts.google.com/v3/signin']")
        return len(sign_in) == 0
    except Exception:
        return False
    finally:
        try:
            await page.close()
        except Exception:
            pass


def _cdp_alive() -> bool:
    """Chrome đã mở với cổng debug chưa? (hỏi endpoint /json/version)."""
    try:
        requests.get(f"{CDP_URL}/json/version", timeout=2)
        return True
    except Exception:
        return False


def _launch_chrome() -> bool:
    """Tự mở Chrome với cổng remote-debugging + profile CDP dùng chung.

    Tái dùng đúng tham số của data-crawler/scripts/launch_chrome.py. Trả True nếu
    đã phát lệnh mở (hoặc Chrome vốn đã chạy sẵn)."""
    import subprocess
    if _cdp_alive():
        return True  # Chrome debug đã chạy sẵn — không mở thêm cửa sổ.
    if not os.path.exists(CHROME_EXE):
        _state["last_error"] = f"Không thấy Chrome tại {CHROME_EXE} (đặt CHROME_EXE nếu cài chỗ khác)."
        return False
    try:
        os.makedirs(CHROME_PROFILE, exist_ok=True)
        subprocess.Popen([
            CHROME_EXE,
            f"--remote-debugging-port={CDP_PORT}",
            "--remote-allow-origins=*",       # Chrome >=111 cần cờ này để CDP websocket kết nối
            f"--user-data-dir={CHROME_PROFILE}",
            "--no-first-run",
            "--no-default-browser-check",
            GEMINI_URL,
        ])
        return True
    except Exception as e:
        _state["last_error"] = f"Không mở được Chrome: {str(e)[:200]}"
        return False


async def _worker_loop():
    from playwright.async_api import async_playwright
    global _sem
    _state["running"] = True
    try:
        # Tự mở Chrome (cổng debug + profile CDP) nếu chưa chạy — người dùng
        # không cần chạy tay launch_chrome.py nữa.
        _launch_chrome()

        async with async_playwright() as p:
            # Kết nối tới Chrome vừa mở (hoặc đã mở sẵn). Thử lại nếu chưa lên.
            browser = None
            for _ in range(60):
                try:
                    browser = await p.chromium.connect_over_cdp(CDP_URL, timeout=3000)
                    break
                except Exception:
                    _state["last_error"] = f"Đang mở Chrome ở {CDP_URL}..."
                    await asyncio.sleep(1)
            if browser is None:
                _state["last_error"] = (
                    f"Không kết nối được Chrome ở {CDP_URL}. "
                    f"Kiểm tra Chrome đã cài tại {CHROME_EXE}.")
                return

            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            _sem = asyncio.Semaphore(MAX_TABS)

            _state["logged_in"] = await _check_login(context)
            if not _state["logged_in"]:
                _state["last_error"] = "Chưa đăng nhập Gemini trong cửa sổ Chrome (launch_chrome)"

            loop = asyncio.get_event_loop()
            pending = set()
            last_idle_sweep = loop.time()
            while True:
                # Dọn task đã xong.
                for t in list(pending):
                    if t.done():
                        pending.discard(t)

                # Dọn phiên idle quá lâu (đóng tab bị bỏ quên).
                if loop.time() - last_idle_sweep > 30:
                    last_idle_sweep = loop.time()
                    for sid in [s for s, v in _sessions.items()
                                if loop.time() - v["last_active"] > SESSION_IDLE_TIMEOUT]:
                        await _close_session_page(sid)

                try:
                    task = _task_queue.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.2)
                    continue

                ttype = task.get("type", "ask_oneshot")
                if ttype == "stop":
                    task["future"].set_result(True)
                    break

                # open/ask/close chạy song song với nhau (open/close nhanh, ask lâu).
                pending.add(asyncio.create_task(_dispatch(context, task, loop)))

            # Chờ các task còn lại xong + đóng mọi phiên còn mở trước khi thoát.
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            for sid in list(_sessions):
                await _close_session_page(sid)
    except Exception as e:
        _state["last_error"] = str(e)[:300]
    finally:
        _state["running"] = False
        _state["logged_in"] = False


async def _close_session_page(session_id: str) -> None:
    """Đóng tab của 1 phiên + nhả slot _sem. An toàn gọi nhiều lần."""
    sess = _sessions.pop(session_id, None)
    if not sess:
        return
    try:
        await sess["page"].close()
    except Exception:
        pass
    try:
        _sem.release()   # trả lại slot đã giữ từ lúc open_session
    except Exception:
        pass


async def _dispatch(context, task, loop):
    """Route 1 task theo type: open | ask | close | ask_oneshot."""
    ttype = task.get("type", "ask_oneshot")
    fut = task["future"]
    try:
        if ttype == "open":
            await _sem.acquire()             # giữ slot suốt phiên (nhả khi close)
            try:
                await asyncio.sleep(0.5 + random.random() * 1.5)  # jitter tránh bị chặn
                page = await context.new_page()
                await _open_gemini_page(page)
            except Exception:
                _sem.release()               # mở lỗi → trả slot ngay
                raise
            _sessions[task["session_id"]] = {"page": page, "last_active": loop.time()}
            fut.set_result({"ok": True})

        elif ttype == "ask":
            sess = _sessions.get(task["session_id"])
            if not sess:
                fut.set_result({"ok": False, "error": "phiên không tồn tại/đã đóng"})
                return
            sess["last_active"] = loop.time()
            text = await _ask_on_page(sess["page"], task["prompt"])
            sess["last_active"] = loop.time()
            fut.set_result({"ok": True, "text": text})

        elif ttype == "close":
            await _close_session_page(task["session_id"])
            fut.set_result({"ok": True})

        else:  # ask_oneshot — tương thích ngược: mở tab → hỏi → đóng
            result = await _query_gemini_web(context, task["prompt"])
            fut.set_result({"ok": True, "text": result})
    except Exception as e:
        if not fut.done():
            fut.set_result({"ok": False, "error": str(e)[:300]})


def start_cdp_worker() -> dict:
    """Bật worker CDP: kết nối tới Chrome dùng chung (mở sẵn bằng launch_chrome)."""
    if _state["running"]:
        return {"ok": True, "already": True, **_state}

    def run():
        import sys
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        asyncio.run(_worker_loop())

    threading.Thread(target=run, daemon=True).start()
    return {"ok": True, "already": False}


def cdp_status() -> dict:
    """Trạng thái kênh AI cho dashboard.

    Giữ nguyên tên/khóa cũ (UI đang đọc) và bổ sung "local_api" — kênh mặc định
    hiện nay — để thấy ngay server local sống/chết mà không phải bật Chrome."""
    return {**_state, "breaker": breaker_status(), "local_api": local_api_status()}


def _ask_cdp(prompt: str, timeout: int = 120) -> str:
    f = concurrent.futures.Future()
    _task_queue.put({"prompt": prompt, "future": f})
    res = f.result(timeout=timeout)
    if not res["ok"]:
        raise RuntimeError(res["error"])
    return res["text"]


# --------------------------------------------------------------- local API mode
def _local_api_ready() -> bool:
    """Kênh local dùng được chưa (chỉ xét cấu hình — không ping mỗi lượt hỏi).

    Server tắt thì lượt hỏi sẽ ném lỗi và ask_gemini tự rơi xuống kênh sau."""
    return _local.configured()


def _ask_local_api(prompt: str) -> str:
    return _local.ask(prompt)


def local_api_status() -> dict:
    return _local.status()


# ------------------------------------------------------------------ API mode
def _gemini_api_config():
    if not os.path.exists(ENV_PATH):
        return None, None
    env = open(ENV_PATH, encoding="utf-8").read()
    key = re.search(r"GEMINI_API_KEY=(.+)", env)
    model = re.search(r"GEMINI_MODEL=(.+)", env)
    return (key.group(1).strip() if key else None,
            model.group(1).strip() if model else "gemini-2.5-flash")


def _call_api_contents(contents: list) -> str:
    """Gọi Gemini API với TOÀN BỘ lịch sử contents[] (API vốn stateless — muốn
    có ngữ cảnh hội thoại phải gửi lại cả lịch sử mỗi lần)."""
    import time as _time
    key, model = _gemini_api_config()
    if not key:
        raise RuntimeError("Không có GEMINI_API_KEY")
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={key}")
    payload = {
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": 16384,
            "responseMimeType": "application/json",
            # gemini-2.5: thinking tokens tính vào maxOutputTokens → tắt để
            # tránh JSON bị cắt cụt giữa chừng
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    # 503/429 là lỗi tạm thời phía Google → retry với backoff
    last_err = None
    for delay in (0, 8, 20, 40):
        if delay:
            _time.sleep(delay)
        r = requests.post(url, json=payload, timeout=90)
        if r.status_code in (429, 500, 502, 503, 504):
            last_err = f"HTTP {r.status_code} (tạm thời, đã thử lại)"
            continue
        if not r.ok:
            raise RuntimeError(f"Gemini API HTTP {r.status_code}")
        parts = r.json()["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)
    raise RuntimeError(f"Gemini API quá tải: {last_err}")


def _ask_api(prompt: str) -> str:
    """Hỏi 1 lượt không ngữ cảnh (tương thích ngược)."""
    return _call_api_contents([{"role": "user", "parts": [{"text": prompt}]}])


# ------------------------------------------------------------------ public
def _resolve_prefer(prefer: str) -> str:
    """Chuẩn hóa prefer + cho env ghi đè.

    prefer: auto | local (=local_api) | cdp | api. Khi prefer="auto", env
    AI_TRANSPORT_REALTIME (local|api|cdp|auto) được quyền ép kênh — dùng cho các
    luồng người-dùng-thấy khi vận hành muốn chốt cứng 1 kênh."""
    if prefer in ("local_api", "localapi"):
        return "local"
    if prefer == "auto":
        env = os.environ.get("AI_TRANSPORT_REALTIME", "auto").strip().lower()
        if env in ("local_api", "localapi"):
            return "local"
        if env in ("api", "cdp", "local"):
            return env
    return prefer


def _order_for(prefer: str) -> list:
    """Thứ tự thử các kênh. Mặc định (auto): local_api trước, CDP/API dự phòng."""
    if prefer == "local":
        return ["local"]
    if prefer == "cdp":
        return ["cdp"]
    if prefer == "api":
        return ["api", "local"]
    return ["local", "cdp", "api"]


def ask_gemini(prompt: str, prefer: str = "auto") -> dict:
    """Gửi 1 prompt → {text, transport}. prefer: auto|local|cdp|api."""
    prefer = _resolve_prefer(prefer)
    errors = {}
    for t in _order_for(prefer):
        try:
            if t == "local":
                if not _local_api_ready():
                    raise RuntimeError("Chưa cấu hình LOCAL_API_KEY cho server AI local")
                return {"text": _ask_local_api(prompt), "transport": "local_api"}
            if t == "cdp":
                if not (_state["running"] and _state["logged_in"]):
                    raise RuntimeError("CDP worker chưa chạy/chưa login "
                                       "(bấm 'Bật Gemini Web' trên dashboard)")
                # breaker mở → bỏ qua CDP (trừ khi user ép prefer="cdp")
                if prefer != "cdp" and not _breaker_allow_cdp():
                    raise RuntimeError("CDP tạm khóa (circuit breaker mở)")
                try:
                    text = _ask_cdp(prompt)
                except Exception:
                    _breaker_record_fail()
                    raise
                _breaker_record_ok()
                return {"text": text, "transport": "cdp (Gemini web)"}
            return {"text": _ask_api(prompt), "transport": "api"}
        except Exception as e:
            errors[t] = str(e)[:200]
    raise RuntimeError(f"Mọi kênh AI đều lỗi: {json.dumps(errors, ensure_ascii=False)}")


# --------------------------------------------------------- phiên hội thoại
def _session_op(op: dict, timeout: int) -> dict:
    """Đẩy 1 op session vào queue worker CDP, chờ kết quả."""
    f = concurrent.futures.Future()
    op["future"] = f
    _task_queue.put(op)
    return f.result(timeout=timeout)


class GeminiSession:
    """1 phiên hội thoại nhiều lượt, giữ ngữ cảnh giữa các câu hỏi.

    - backend "local_api" (mặc định): endpoint kiểu OpenAI vốn stateless → tự
      tích lũy messages[] gửi lại mỗi lượt để mô phỏng ngữ cảnh.
    - backend "cdp": 1 tab Gemini web mở suốt phiên; Gemini tự nhớ hội thoại.
    - backend "api": như local_api nhưng theo định dạng contents[] của Google.

    Cùng interface — orchestrator không cần biết đang chạy kênh nào. Dùng làm
    context manager để chắc chắn đóng tab:
        with open_session() as s:
            s.ask(prompt1); s.ask(prompt2)
    """

    _TRANSPORTS = {"cdp": "cdp (Gemini web)", "local_api": "local_api", "api": "api"}

    def __init__(self, backend: str, session_id: str | None = None):
        self.backend = backend
        self.transport = self._TRANSPORTS.get(backend, backend)
        self.session_id = session_id
        self._history: list = []      # cho backend api / local_api
        self._closed = False

    def ask(self, prompt: str, timeout: int = 180) -> str:
        if self._closed:
            raise RuntimeError("phiên đã đóng")
        if self.backend == "local_api":
            self._history.append({"role": "user", "content": prompt})
            text = _local.ask_messages(self._history, timeout_s=timeout)
            self._history.append({"role": "assistant", "content": text})
            return text
        if self.backend == "cdp":
            res = _session_op({"type": "ask", "session_id": self.session_id,
                               "prompt": prompt}, timeout)
            if not res["ok"]:
                _breaker_record_fail()
                raise RuntimeError(res["error"])
            _breaker_record_ok()
            return res["text"]
        # backend api: gửi lại toàn bộ lịch sử + prompt mới
        self._history.append({"role": "user", "parts": [{"text": prompt}]})
        text = _call_api_contents(self._history)
        self._history.append({"role": "model", "parts": [{"text": text}]})
        return text

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self.backend == "cdp" and self.session_id:
            try:
                _session_op({"type": "close", "session_id": self.session_id}, 30)
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def open_session(prefer: str = "auto", timeout: int = 90) -> GeminiSession:
    """Mở 1 phiên hội thoại. Ưu tiên LOCAL API; dự phòng CDP rồi Gemini API.

    prefer: auto|local|cdp|api. Breaker mở → auto bỏ qua CDP."""
    prefer = _resolve_prefer(prefer)

    # Kênh mặc định: server AI local. Phiên là stateless-có-lịch-sử nên mở được
    # ngay, không cần tab/worker → không có gì để lỗi ở bước mở.
    if prefer in ("auto", "local") and _local_api_ready():
        return GeminiSession("local_api")
    if prefer == "local":
        raise RuntimeError(
            "Thiếu LOCAL_API_KEY — đặt trong data-crawler/.env (hoặc lưu qua bảng "
            "điều khiển :5000) để dùng server AI local.")

    want_cdp = prefer in ("auto", "cdp")
    # breaker mở → không thử CDP (trừ khi user ép prefer="cdp")
    if want_cdp and prefer != "cdp" and not _breaker_allow_cdp():
        want_cdp = False
    if want_cdp and _state["running"] and _state["logged_in"]:
        _session_counter[0] += 1
        sid = f"s{_session_counter[0]}"
        res = _session_op({"type": "open", "session_id": sid}, timeout)
        if res.get("ok"):
            _breaker_record_ok()
            return GeminiSession("cdp", sid)
        _breaker_record_fail()
        # mở tab lỗi → rơi xuống API nếu được phép
        if prefer == "cdp":
            raise RuntimeError(f"Mở phiên CDP lỗi: {res.get('error')}")
    if prefer == "cdp":
        raise RuntimeError("CDP worker chưa chạy/chưa login")
    # API fallback: cần có key
    key, _ = _gemini_api_config()
    if not key:
        raise RuntimeError(
            "Không có kênh AI: thiếu LOCAL_API_KEY (server local :4000), "
            "CDP chưa bật, và không có GEMINI_API_KEY")
    return GeminiSession("api")


def parse_json_answer(text: str) -> dict:
    """Bóc JSON từ câu trả lời (kể cả khi web chat kèm chữ thừa)."""
    text = text.strip()
    text = re.sub(r"^```(json)?|```$", "", text, flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.S)
        if m:
            return json.loads(m.group(0))
        raise
