"""Dùng Gemini web chat làm "API" qua CDP (Chrome DevTools Protocol).

Kết nối Playwright tới một Chrome đang chạy với --remote-debugging-port,
gõ prompt vào ô chat Gemini và đọc câu trả lời về.

Yêu cầu: Chrome đã mở bằng scripts/launch_chrome.py và bạn đã đăng nhập Gemini.
"""
from __future__ import annotations

import random
import time

from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

CDP_URL = "http://localhost:9222"
GEMINI_URL = "https://gemini.google.com/app"


def cdp_available(cdp_url: str = CDP_URL, timeout: float = 2.0) -> bool:
    """Kiểm tra NHANH Chrome CDP có đang mở không (GET /json/version).

    Dùng làm preflight trước khi chạy hàng loạt phân tích Gemini — tránh treo
    1400+ mã mỗi mã fail connect 3s khi Chrome chưa mở. Không mở Playwright."""
    import urllib.request
    url = cdp_url.rstrip("/") + "/json/version"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


class GeminiEmptyResponse(RuntimeError):
    """Gemini trả về rỗng / JSON dang dở sau khi hết thời gian chờ.

    Đây là lỗi TẠM THỜI (retry được) — phân biệt với lỗi cứng như "Chưa đăng
    nhập Gemini" (không nên retry). Tầng trên bắt exception này để thử lại."""


class GoogleBotBlock(RuntimeError):
    """Google chặn traffic tự động (trang /sorry/ + CAPTCHA) — nguồn thật của lỗi
    Gemini "1095". KHÔNG retry (retry vô ích khi đang bị chặn); người dùng phải mở
    Chrome giải CAPTCHA. Giảm tốc độ request để tránh bị chặn lại."""


# Nghỉ giữa các lần gọi Gemini (giây) để traffic bớt giống bot → giảm nguy cơ bị
# Google chặn (/sorry/ = lỗi 1095). ĐỌC ĐỘNG: ưu tiên file config/gemini_delay.txt
# (dashboard ghi → chỉnh LIVE giữa chừng được), fallback env GEMINI_REQUEST_DELAY,
# fallback 4. 0 = tắt.
import os as _os
REQUEST_DELAY = float(_os.environ.get("GEMINI_REQUEST_DELAY", "4"))   # giữ cho tương thích


def _delay_file():
    from . import config
    return config.ROOT / "config" / "gemini_delay.txt"


def current_delay() -> float:
    """Độ trễ hiện tại (giây) giữa 2 lần gọi Gemini — đọc động để UI chỉnh live."""
    try:
        p = _delay_file()
        if p.exists():
            return max(0.0, float(p.read_text(encoding="utf-8").strip()))
    except Exception:
        pass
    try:
        return max(0.0, float(_os.environ.get("GEMINI_REQUEST_DELAY", "4")))
    except Exception:
        return 4.0


def _pace():
    """Nghỉ current_delay() + jitter (traffic bớt đều/giống bot)."""
    d = current_delay()
    if d > 0:
        time.sleep(d + random.uniform(0, d * 0.5))

# Selector ưu tiên (Gemini đổi giao diện theo thời gian → thử nhiều cái).
INPUT_SELECTORS = [
    "div.ql-editor[contenteditable='true']",
    "rich-textarea div[contenteditable='true']",
    "div[contenteditable='true'][role='textbox']",
]
SEND_SELECTORS = [
    "button.send-button",
    "button[aria-label*='Gửi']",
    "button[aria-label*='Send']",
    "button[mattooltip*='Gửi']",
]
RESPONSE_SELECTOR = "message-content.model-response-text, .model-response-text, message-content"

# Dấu hiệu Gemini ĐANG generate (còn stream) — khi các phần tử này biến mất
# nghĩa là đã sinh xong. Selector có thể đổi theo giao diện → thử nhiều cái.
STOP_SELECTORS = [
    "button[aria-label*='Dừng']",
    "button[aria-label*='Stop']",
    "button.stop",
    "button[mattooltip*='Dừng']",
]
# Vòng xoay / trạng thái đang tạo phản hồi (nếu có).
SPINNER_SELECTORS = [
    ".blinking-cursor",
    ".response-loading",
    "[data-test-id='loading-indicator']",
]


class GeminiCDP:
    def __init__(self, cdp_url: str = CDP_URL, headless_ok: bool = False):
        self.cdp_url = cdp_url
        self._pw = None
        self._browser = None
        self.page = None

    def __enter__(self):
        self._pw = sync_playwright().start()
        try:
            self._browser = self._pw.chromium.connect_over_cdp(self.cdp_url, timeout=3000)
        except Exception as e:
            raise RuntimeError(f"Không thể kết nối Chrome ở {self.cdp_url}. Bạn đã chạy scripts/launch_chrome.py chưa?") from e
        # KHÔNG bám 1 tab cố định nữa: mỗi phân tích tự mở 1 tab mới rồi đóng
        # (analyze_with_new_tab) → cho phép chạy song song, các tab chia sẻ profile đã login.
        self._ctx = self._browser.contexts[0] if self._browser.contexts else self._browser.new_context()
        return self

    def _context(self):
        return self._browser.contexts[0] if self._browser.contexts else self._ctx

    def __exit__(self, *exc):
        # Không đóng browser của người dùng; chỉ ngắt Playwright.
        try:
            self._browser.close()
        except Exception:
            pass
        if self._pw:
            self._pw.stop()

    # ------------------------------------------------------------------
    @staticmethod
    def _find(page, selectors):
        for sel in selectors:
            loc = page.locator(sel).first
            try:
                if loc.count() > 0 and loc.is_visible():
                    return loc
            except Exception:
                continue
        return None

    @staticmethod
    def _is_generating(page) -> bool:
        """True nếu Gemini còn đang sinh phản hồi (nút Dừng/spinner còn hiện)."""
        for sel in STOP_SELECTORS + SPINNER_SELECTORS:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    return True
            except Exception:
                continue
        return False

    @staticmethod
    def _looks_complete_json(text: str) -> bool:
        """Heuristic: text trông giống JSON hoàn chỉnh (ngoặc { } cân bằng).

        Bỏ qua ngoặc nằm trong chuỗi để không đếm nhầm."""
        if not text:
            return False
        start = text.find("{")
        if start < 0:
            return False
        depth, in_str, esc = 0, False, False
        for c in text[start:]:
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return True
        return False

    @staticmethod
    def _response_count(page) -> int:
        return page.locator(RESPONSE_SELECTOR).count()

    @staticmethod
    def _last_response_text(page) -> str:
        loc = page.locator(RESPONSE_SELECTOR)
        n = loc.count()
        if n == 0:
            return ""
        try:
            return loc.nth(n - 1).inner_text().strip()
        except Exception:
            return ""

    def preflight(self) -> tuple[bool, str]:
        """Mở 1 tab kiểm tra Gemini đã ĐĂNG NHẬP + có ô nhập chưa. (ok, thông điệp).

        Gọi trước khi phân tích hàng loạt: nếu chưa đăng nhập / giao diện đổi
        selector thì báo NGAY thay vì để 1400+ mã cùng fail."""
        page = None
        try:
            page = self._context().new_page()
            page.goto(GEMINI_URL, wait_until="domcontentloaded")
            self._check_logged_in(page)   # raise nếu bị đẩy sang trang đăng nhập
            box = self._wait_for_input(page, timeout_ms=15000)
            if box is None:
                self._check_logged_in(page)
                return False, ("Không thấy ô nhập Gemini (chưa đăng nhập, "
                               "hoặc giao diện Gemini đã đổi selector).")
            return True, "Gemini sẵn sàng."
        except Exception as exc:
            return False, str(exc)[:160]
        finally:
            if page is not None:
                try:
                    page.close()
                except Exception:
                    pass

    # ---- Phiên RAG dùng CHUNG 1 tab cho nhiều lượt (giữ ngữ cảnh hội thoại) ----
    def open_session_tab(self):
        """Mở 1 tab Gemini để hỏi NHIỀU lượt trong CÙNG hội thoại (RAG 1 phiên).
        Trả `page`. Ném GoogleBotBlock/RuntimeError nếu bị chặn/chưa đăng nhập."""
        _pace()
        page = self._context().new_page()
        page.goto(GEMINI_URL, wait_until="domcontentloaded")
        self._check_logged_in(page)   # raise nếu /sorry/ (bị chặn) hoặc chưa login
        return page

    def ask_on_tab(self, page, prompt: str, timeout: float = 180.0,
                   stable_secs: float = 5.0) -> str:
        """Hỏi 1 lượt trên tab đã mở (KHÔNG mở tab mới) — Gemini tự nhớ ngữ cảnh
        các lượt trước trong cùng hội thoại. NGHỈ trước mỗi lượt (current_delay) để
        không bắn dồn dập giữa 2 lượt → tránh Google chặn (1095)."""
        _pace()
        return self._ask_on(page, prompt, timeout, stable_secs)

    @staticmethod
    def close_session_tab(page):
        try:
            if page is not None:
                page.close()
        except Exception:
            pass

    def analyze_with_new_tab(self, prompt: str, timeout: float = 180.0,
                             stable_secs: float = 5.0, retries: int = 2) -> str:
        """Mở 1 TAB MỚI trong Chrome dùng chung → hỏi Gemini → ĐÓNG tab.

        Mỗi phân tích 1 luồng CDP riêng nên nhiều tab chạy song song được
        (trần song song do phía gọi kiểm soát: ThreadPoolExecutor(3)).

        `retries`: số lần THỬ LẠI khi gặp lỗi tạm thời (rỗng/timeout). Mỗi lần
        thử lại đóng tab cũ, chờ backoff tăng dần (5s, 15s + jitter) rồi mở tab
        mới. Lỗi "Chưa đăng nhập Gemini" là lỗi cứng → ném ngay, không retry."""
        attempts = max(1, retries + 1)   # tổng số lần thử = 1 lần đầu + retries
        last_exc: Exception | None = None
        # Nghỉ có jitter TRƯỚC mỗi request → traffic bớt đều/giống bot, giảm nguy cơ
        # bị Google chặn (/sorry/ = lỗi 1095). Chỉnh live qua config/gemini_delay.txt.
        _pace()
        for i in range(attempts):
            page = self._context().new_page()
            try:
                page.goto(GEMINI_URL, wait_until="domcontentloaded")
                self._check_logged_in(page)   # bị đẩy sang accounts.google → báo rõ
                return self._ask_on(page, prompt, timeout, stable_secs)
            except (GeminiEmptyResponse, PlaywrightTimeoutError) as exc:
                # Lỗi tạm thời → thử lại (nếu còn lượt). Đóng tab trước khi chờ.
                last_exc = exc
                try:
                    page.close()
                except Exception:
                    pass
                page = None
                if i < attempts - 1:
                    backoff = (5.0 if i == 0 else 15.0) + random.uniform(0, 3.0)
                    print(f"  [retry] Gemini lỗi tạm thời ({type(exc).__name__}: "
                          f"{str(exc)[:80]}) — thử lại sau {backoff:.0f}s "
                          f"(lượt {i + 2}/{attempts}).")
                    time.sleep(backoff)
                    continue
                # Hết lượt thử → ném để tầng trên xử lý (ghi partial).
                raise
            finally:
                if page is not None:
                    try:
                        page.close()
                    except Exception:
                        pass
        # Về lý thuyết không tới đây (vòng lặp luôn return hoặc raise).
        raise last_exc if last_exc else GeminiEmptyResponse("Không có phản hồi từ Gemini.")

    def _wait_for_input(self, page, timeout_ms: int = 25000):
        """Gemini là SPA → ô nhập render sau khi DOM load. Chờ nó xuất hiện.

        Thử lần lượt các selector trong INPUT_SELECTORS; selector nào bắt được
        trước thì dùng. Nếu hết giờ mà không có → nhiều khả năng chưa đăng nhập."""
        deadline = time.time() + timeout_ms / 1000.0
        per_try = max(1000, int(timeout_ms / max(1, len(INPUT_SELECTORS))))
        while time.time() < deadline:
            for sel in INPUT_SELECTORS:
                try:
                    page.wait_for_selector(sel, timeout=per_try, state="visible")
                except Exception:
                    continue
                box = self._find(page, [sel])
                if box is not None:
                    return box
            time.sleep(0.3)
        return None

    @staticmethod
    def _check_logged_in(page) -> None:
        """Phát hiện (a) Google CHẶN traffic tự động (trang /sorry/ + CAPTCHA) hoặc
        (b) chưa đăng nhập → raise lỗi RÕ RÀNG (không để biến thành "lỗi 1095" khó hiểu)."""
        try:
            url = page.url or ""
        except Exception:
            url = ""
        # (a) Trang chống bot của Google = nguồn gốc thật của "Đã xảy ra lỗi (1095)".
        if "/sorry/" in url or "sorry/index" in url:
            raise GoogleBotBlock(
                "GOOGLE CHẶN TRAFFIC TỰ ĐỘNG (đây chính là lỗi Gemini '1095'). Chrome CDP "
                "đang bị đẩy sang trang xác minh CAPTCHA của Google. HÃY: mở cửa sổ Chrome "
                "(profile CDP), vào gemini.google.com, GIẢI CAPTCHA/xác minh là người thật, "
                "rồi chạy lại. Giảm tốc độ (1 worker + nghỉ giữa các lần) để tránh bị chặn lại. "
                f"URL: {url[:80]}")
        # (b) Chưa đăng nhập.
        if "accounts.google" in url or "signin" in url or "ServiceLogin" in url:
            raise RuntimeError(
                "Chưa đăng nhập Gemini (trình duyệt bị chuyển hướng sang trang đăng nhập "
                f"Google): {url}. Hãy đăng nhập Gemini rồi thử lại.")

    def _ask_on(self, page, prompt: str, timeout: float = 120.0,
                stable_secs: float = 5.0) -> str:
        """Gửi 1 prompt trên `page` đã có, chờ trả lời ổn định, trả về text.

        Cơ chế "đã sinh xong" kết hợp 3 tín hiệu (chọn cách bền nhất có thể):
        1. Nút Dừng/spinner không còn hiện (_is_generating == False), HOẶC
        2. Text đứng yên >= stable_secs (nâng 3s -> 5s để tránh cắt giữa chừng),
        VÀ chỉ coi là hoàn tất nếu text trông giống JSON cân bằng ngoặc; nếu chưa
        đủ điều kiện thì chờ tiếp tới khi hết timeout."""
        # Chờ ô nhập xuất hiện trước khi thao tác (tránh box=None trên SPA).
        box = self._wait_for_input(page)
        if box is None:
            self._check_logged_in(page)   # có thể raise "Chưa đăng nhập Gemini"
            raise RuntimeError(
                "Không tìm thấy ô nhập Gemini sau khi chờ. Có thể chưa đăng nhập, "
                "giao diện đã đổi selector, hoặc trang tải lỗi.")

        before = self._response_count(page)
        box.click()
        # insert_text không kích hoạt Enter → an toàn cho prompt nhiều dòng.
        page.keyboard.insert_text(prompt)
        time.sleep(0.4)

        # Verify prompt đã vào ô; nếu rỗng thì thử lại 1 lần (cảnh báo).
        try:
            typed = (box.inner_text() or "").strip()
        except Exception:
            typed = ""
        if not typed:
            print("  [cảnh báo] Ô nhập trống sau insert_text — thử nhập lại lần 2.")
            box.click()
            page.keyboard.insert_text(prompt)
            time.sleep(0.4)
            try:
                typed = (box.inner_text() or "").strip()
            except Exception:
                typed = ""
            if not typed:
                print("  [cảnh báo] Vẫn không xác nhận được text trong ô nhập, vẫn gửi thử.")

        send = self._find(page, SEND_SELECTORS)
        if send is not None:
            send.click()
        else:
            page.keyboard.press("Enter")

        # Chờ có khối trả lời mới.
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self._response_count(page) > before:
                break
            time.sleep(0.5)

        # Chờ tới khi sinh xong: ưu tiên tín hiệu ngừng generate; fallback là
        # text đứng yên + JSON cân bằng.
        last, stable_since = "", None
        while time.time() - t0 < timeout:
            cur = self._last_response_text(page)
            generating = self._is_generating(page)

            if cur and cur == last:
                stalled = stable_since and (time.time() - stable_since >= stable_secs)
                # Đã ngừng generate rõ ràng → xong (miễn có text).
                if not generating and cur:
                    return cur
                # Không xác định được trạng thái generate → dựa vào đứng yên +
                # JSON hoàn chỉnh để tránh trả về câu dang dở.
                if stalled and self._looks_complete_json(cur):
                    return cur
            else:
                last, stable_since = cur, time.time()
            time.sleep(0.7)

        # Hết giờ mà chưa "xong": KHÔNG trả chuỗi rỗng/JSON dang dở nữa. Ném
        # GeminiEmptyResponse để tầng trên retry (đây là lỗi tạm thời).
        waited = time.time() - t0
        n = len(last or "")
        if not last:
            raise GeminiEmptyResponse(
                f"Gemini không trả về nội dung sau {waited:.0f}s "
                f"(0 ký tự, timeout={timeout:.0f}s).")
        if not self._looks_complete_json(last):
            raise GeminiEmptyResponse(
                f"Gemini trả về JSON dang dở sau {waited:.0f}s "
                f"({n} ký tự, ngoặc {{ }} chưa cân bằng).")
        return last  # có text + JSON cân bằng nhưng chưa qua các nhánh return trên

    def ask(self, prompt: str, timeout: float = 120.0, stable_secs: float = 5.0) -> str:
        """Tương thích ngược: mở tab mới, hỏi, đóng tab."""
        return self.analyze_with_new_tab(prompt, timeout, stable_secs)


def quick_test(prompt: str = "Trả lời ngắn: 2+2 bằng mấy?") -> str:
    with GeminiCDP() as g:
        return g.ask(prompt, timeout=60)
