# -*- coding: utf-8 -*-
"""
ChromeCDP — điều khiển CHROME THẬT của máy qua Chrome DevTools Protocol.
Vì sao: QtWebEngine không login Google được (Google chặn webview). Chrome thật
thì Google cho login bình thường. Ta launch Chrome (KHÔNG cờ automation, profile
riêng để giữ login) rồi gửi prompt / đọc đáp án qua CDP websocket.
"""
import os
import json
import time
import ctypes
import threading
import subprocess
import urllib.request
from ctypes import wintypes

from websocket import create_connection  # websocket-client

import re

GEMINI_URL = "https://gemini.google.com/app"
DONE = "@@@END@@@"
INPUT_SELS = ["rich-textarea .ql-editor", ".ql-editor",
              'div[contenteditable="true"]', "textarea", '[role="textbox"]']
ANSWER_SELS = [".model-response-text", "message-content",
               '[class*="model-response"]', ".markdown"]


def _sanitize(t):
    if not t:
        return t
    t = t.replace(DONE, "")
    t = re.sub(r"@+\s*END\s*@+", "", t, flags=re.I)
    return t.strip()


CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]


def find_chrome():
    for p in CHROME_PATHS:
        if os.path.isfile(p):
            return p
    return None


class ChromeCDP:
    def __init__(self, port=9222, profile_dir=None, log=print):
        self.port = port
        self.profile = profile_dir or os.path.join(os.path.expanduser("~"), ".finpulse_chrome")
        self.proc = None
        self.ws = None
        self._id = 0
        self._lock = threading.Lock()
        self.log = log

    # ---- vòng đời Chrome ----
    def launch(self, url):
        exe = find_chrome()
        if not exe:
            raise RuntimeError("Không tìm thấy Chrome/Edge trên máy.")
        os.makedirs(self.profile, exist_ok=True)
        args = [
            exe,
            "--remote-debugging-port=%d" % self.port,
            "--remote-allow-origins=*",   # Chrome >=111 cần cờ này để CDP websocket
            "--user-data-dir=%s" % self.profile,
            "--no-first-run", "--no-default-browser-check",
            "--disable-popup-blocking",
            "--app=%s" % url,   # cửa sổ app gọn (không tab/address bar)
        ]
        self.log("[cdp] launch chrome:", exe)
        self.proc = subprocess.Popen(args)

    def is_alive(self):
        return self.proc is not None and self.proc.poll() is None

    def _http_targets(self):
        with urllib.request.urlopen("http://127.0.0.1:%d/json" % self.port, timeout=4) as r:
            return json.loads(r.read())

    def connect(self, match="google", timeout=60):
        """Chờ Chrome lên + tìm tab Gemini rồi mở websocket CDP."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                pages = [t for t in self._http_targets()
                         if t.get("type") == "page" and match in (t.get("url") or "")]
                if pages:
                    self.ws = create_connection(pages[0]["webSocketDebuggerUrl"], timeout=40)
                    self._send("Page.enable")
                    self._send("Runtime.enable")
                    self.log("[cdp] connected:", pages[0].get("url"))
                    return True
            except Exception as e:
                self.log("[cdp] connect retry:", e)
            time.sleep(0.6)
        return False

    # ---- tìm HWND cửa sổ Chrome (để nhúng vào app) ----
    def chrome_pids(self):
        try:
            out = subprocess.check_output([
                "powershell", "-NoProfile", "-Command",
                "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
                "Where-Object { $_.CommandLine -like '*%s*' } | "
                "Select-Object -ExpandProperty ProcessId" % os.path.basename(self.profile)
            ], stderr=subprocess.DEVNULL, timeout=8)
            return set(int(x) for x in out.split())
        except Exception:
            return set()

    def find_hwnd(self, timeout=20):
        user32 = ctypes.windll.user32
        prc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        start = time.time()
        while time.time() - start < timeout:
            pids = self.chrome_pids()
            found = []

            def cb(hwnd, _):
                if not user32.IsWindowVisible(hwnd):
                    return True
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value not in pids:
                    return True
                buf = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, buf, 256)
                if buf.value != "Chrome_WidgetWin_1":
                    return True
                if user32.GetWindowTextLengthW(hwnd) <= 0:
                    return True
                found.append(hwnd)
                return True

            user32.EnumWindows(prc(cb), 0)
            if found:
                self.log("[cdp] hwnd:", found[0])
                return int(found[0])
            time.sleep(0.4)
        return None

    def ensure(self):
        if self.ws is None:
            return self.connect()
        return True

    # ---- giao tiếp CDP ----
    def _send(self, method, params=None):
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(msg["error"].get("message", "cdp error"))
                return msg.get("result", {})
            # bỏ qua event

    def evaluate(self, expr, await_promise=False):
        with self._lock:
            r = self._send("Runtime.evaluate", {
                "expression": expr, "returnByValue": True,
                "awaitPromise": await_promise, "userGesture": True})
        return (r.get("result") or {}).get("value")

    def navigate(self, url):
        with self._lock:
            self._send("Page.navigate", {"url": url})

    # ---- gửi prompt & đọc đáp án (giống bridge QtWebEngine, qua CDP) ----
    def ask(self, prompt, new_chat=True):
        if not self.ensure():
            return {"ok": False, "error": "Chưa kết nối Chrome."}
        marked = prompt + ("\n\n---\nKhi đã viết xong TOÀN BỘ, kết thúc bằng đúng "
                           "MỘT dòng riêng: " + DONE)
        try:
            if new_chat:
                self.navigate(GEMINI_URL)
                time.sleep(2.5)
            # focus + chèn prompt
            ins = ("(function(){var ss=%s;var el=null;"
                   "for(var i=0;i<ss.length;i++){var e=document.querySelector(ss[i]);if(e){el=e;break;}}"
                   "if(!el)return false;el.focus();"
                   "try{document.execCommand('insertText',false,%s);}catch(e){}"
                   "if(el.textContent!==undefined&&el.textContent.trim()===''){el.textContent=%s;"
                   "el.dispatchEvent(new Event('input',{bubbles:true}));}return true;})()"
                   % (json.dumps(INPUT_SELS), json.dumps(marked), json.dumps(marked)))
            if not self.evaluate(ins):
                return {"ok": False, "error": "Không thấy ô nhập — đăng nhập Gemini trong cửa sổ Chrome trước."}
            time.sleep(0.9)
            # đếm số câu trả lời cũ
            cnt = ("(function(){var s=%s;for(var i=0;i<s.length;i++){"
                   "var e=document.querySelectorAll(s[i]);if(e.length)return e.length;}return 0;})()"
                   % json.dumps(ANSWER_SELS))
            base_n = self.evaluate(cnt) or 0
            # gửi
            sub = ("(function(){var bs=document.querySelectorAll('button[aria-label],button[mattooltip]');"
                   "for(var i=0;i<bs.length;i++){var b=bs[i];var a=((b.getAttribute('aria-label')||'')+' '+"
                   "(b.getAttribute('mattooltip')||'')).toLowerCase();"
                   "if(/send|gửi|submit/.test(a)&&!b.disabled){b.click();return 'btn';}}"
                   "var el=document.activeElement;var ev={key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true};"
                   "if(el){el.dispatchEvent(new KeyboardEvent('keydown',ev));el.dispatchEvent(new KeyboardEvent('keyup',ev));}"
                   "return 'enter';})()")
            self.evaluate(sub)
            # poll
            rd = ("(function(){var s=%s;for(var i=0;i<s.length;i++){"
                  "var e=document.querySelectorAll(s[i]);if(e.length){"
                  "return {n:e.length,t:(e[e.length-1].innerText||'').trim()};}}return {n:0,t:''};})()"
                  % json.dumps(ANSWER_SELS))
            last, stable, start = "", 0, time.time()
            while time.time() - start < 150:
                time.sleep(2.0)
                res = self.evaluate(rd) or {}
                n, t = res.get("n", 0), res.get("t", "")
                if n <= base_n:
                    continue
                if DONE in t:
                    return {"ok": True, "text": _sanitize(t.split(DONE)[0])}
                if len(t) >= 1 and t == last:
                    stable += 1
                    if stable >= 3:
                        return {"ok": True, "text": _sanitize(t)}
                else:
                    stable = 0
                    last = t
            return {"ok": True, "text": _sanitize(last)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def close(self):
        try:
            if self.ws:
                self.ws.close()
        except Exception:
            pass
        try:
            if self.proc:
                self.proc.terminate()
        except Exception:
            pass


# ---- self-test ----
if __name__ == "__main__":
    c = ChromeCDP(profile_dir=os.path.join(os.path.expanduser("~"), ".finpulse_chrome_test"))
    c.launch("https://www.google.com/")
    print("connect:", c.connect(match="google", timeout=30))
    print("title:", c.evaluate("document.title"))
    print("ua:", c.evaluate("navigator.userAgent"))
    print("webdriver:", c.evaluate("navigator.webdriver"))
    print("hwnd:", c.find_hwnd(timeout=10))
    time.sleep(1)
    c.close()
