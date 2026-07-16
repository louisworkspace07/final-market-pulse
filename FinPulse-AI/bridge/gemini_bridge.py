# -*- coding: utf-8 -*-
"""
FinPulse — Gemini Web Bridge (PyQt6 QWebEngine).
Mở Gemini trong QWebEngine (Google CHO đăng nhập, khác với Electron webview),
giữ phiên đăng nhập qua profile persistent, và phục vụ HTTP localhost:
  GET  /health        -> {"ok": true}
  POST /ask {prompt}  -> {"ok": true, "text": "<câu trả lời Gemini>"}
Electron gọi sang đây để lấy output mà KHÔNG dùng API trả phí.
"""
import os
import re
import sys
import json
import time
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PyQt6.QtCore import QUrl, QTimer
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage

PORT = 8765
GEMINI_URL = "https://gemini.google.com/app"
DONE = "@@@END@@@"   # marker chữ thường, không bị markdown render méo như <<<DONE>>>


def sanitize(t):
    if not t:
        return t
    t = t.replace(DONE, "")
    # dọn các biến thể marker bị render méo (<<>>, <<<...>>>, @@@...@@@)
    t = re.sub(r"@+\s*END\s*@+", "", t, flags=re.I)
    t = re.sub(r"<{2,}\s*(?:DONE|END)?\s*>{2,}", "", t, flags=re.I)
    return t.strip()

INPUT_SELS = [
    "rich-textarea .ql-editor", ".ql-editor",
    'div[contenteditable="true"]', "textarea", '[role="textbox"]',
]
ANSWER_SELS = [
    ".model-response-text", "message-content",
    '[class*="model-response"]', ".markdown",
]

JOBS: "queue.Queue" = queue.Queue()


class Job:
    def __init__(self, prompt):
        self.prompt = prompt
        self.event = threading.Event()
        self.result = None
        self.error = None


def js_str(s):
    return json.dumps(s)


class Bridge(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gemini Bridge — FinPulse  (đăng nhập 1 lần, có thể thu nhỏ)")

        storage = os.path.join(os.path.expanduser("~"), ".finpulse_qt")
        os.makedirs(storage, exist_ok=True)
        self.profile = QWebEngineProfile("finpulse-gemini", self)
        self.profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        self.profile.setPersistentStoragePath(storage)
        self.profile.setCachePath(storage)

        self.view = QWebEngineView(self)
        self.page = QWebEnginePage(self.profile, self)
        self.view.setPage(self.page)
        self.setCentralWidget(self.view)
        self.page.load(QUrl(GEMINI_URL))

        self.busy = False
        self.cur = None
        self.pump_timer = QTimer(self)
        self.pump_timer.timeout.connect(self.pump)
        self.pump_timer.start(250)

    # --- nhận job từ HTTP thread (chạy trên GUI thread) ---
    def pump(self):
        if self.busy:
            return
        try:
            job = JOBS.get_nowait()
        except queue.Empty:
            return
        self.busy = True
        self.cur = job
        self.start_job(job)

    def finish(self, text=None, error=None):
        job = self.cur
        if job is not None:
            job.result = sanitize(text) if (text and job.prompt != "__PROBE__") else text
            job.error = error
            job.event.set()
        self.cur = None
        self.busy = False

    def run_js(self, code, cb=None):
        self.page.runJavaScript(code, cb if cb else (lambda _r: None))

    # --- chuỗi thao tác: load -> focus+insert -> submit -> poll ---
    def start_job(self, job):
        if job.prompt == "__PROBE__":
            self.do_probe()
            return
        self.marked = job.prompt + (
            "\n\n---\nKhi đã viết xong TOÀN BỘ nội dung, kết thúc bằng đúng "
            "MỘT dòng riêng: " + DONE)
        self._step_done = False

        def on_load(ok):
            if self._step_done:
                return
            self._step_done = True
            try:
                self.page.loadFinished.disconnect(on_load)
            except Exception:
                pass
            QTimer.singleShot(2200, self.do_focus_insert)

        self.page.loadFinished.connect(on_load)
        self.page.load(QUrl(GEMINI_URL))
        # fallback nếu loadFinished không bắn
        QTimer.singleShot(9000, lambda: on_load(True))

    def do_probe(self):
        code = r"""
        (function(){
          function cnt(s){try{return document.querySelectorAll(s).length;}catch(e){return -1;}}
          var btns=[];var bs=document.querySelectorAll('button');
          for(var i=0;i<bs.length && btns.length<25;i++){
            var a=bs[i].getAttribute('aria-label')||bs[i].getAttribute('mattooltip')||bs[i].getAttribute('data-testid')||'';
            if(a)btns.push(a+(bs[i].disabled?' [disabled]':''));}
          return JSON.stringify({
            url: location.href,
            inputs: {'.ql-editor':cnt('.ql-editor'),'rich-textarea':cnt('rich-textarea'),
                     'contenteditable':cnt('[contenteditable="true"]'),'textarea':cnt('textarea')},
            answers: {'.model-response-text':cnt('.model-response-text'),'message-content':cnt('message-content'),
                      'model-response':cnt('model-response'),'.markdown':cnt('.markdown'),
                      '[class*=model-response]':cnt('[class*="model-response"]')},
            buttons: btns
          });
        })()
        """
        self.run_js(code, lambda r: self.finish(text=r))

    def do_focus_insert(self):
        code = """
        (function(){
          var ss=%s;
          var el=null;
          for(var i=0;i<ss.length;i++){var e=document.querySelector(ss[i]);
            if(e){el=e;break;}}
          if(!el)return false;
          el.focus();
          try{document.execCommand('insertText',false,%s);}catch(e){}
          if(el.textContent!==undefined && el.textContent.trim()===''){
            el.textContent=%s; el.dispatchEvent(new Event('input',{bubbles:true}));}
          if('value' in el && (!el.value||el.value.length<2)){
            el.value=%s; el.dispatchEvent(new Event('input',{bubbles:true}));}
          return true;
        })()
        """ % (json.dumps(INPUT_SELS), js_str(self.marked),
               js_str(self.marked), js_str(self.marked))

        def cb(ok):
            print("[bridge] focus+insert ->", ok, flush=True)
            if not ok:
                self.finish(error="Không thấy ô nhập — hãy đăng nhập Gemini trong cửa sổ này trước.")
                return
            QTimer.singleShot(900, self.do_submit)

        self.run_js(code, cb)

    def do_submit(self):
        code = """
        (function(){
          var el=document.activeElement;
          var ev={key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true,cancelable:true};
          var bs=document.querySelectorAll('button[aria-label],button[mattooltip]');
          for(var i=0;i<bs.length;i++){var b=bs[i];
            var a=((b.getAttribute('aria-label')||'')+' '+(b.getAttribute('mattooltip')||'')).toLowerCase();
            if(/send|gửi|submit/.test(a) && !b.disabled){b.click();return 'btn';}}
          if(el){el.dispatchEvent(new KeyboardEvent('keydown',ev));
                 el.dispatchEvent(new KeyboardEvent('keyup',ev));}
          return 'enter';
        })()
        """
        def cb(r):
            print("[bridge] submit ->", r, flush=True)
            self.poll(0, "")
        self.run_js(code, cb)

    def poll(self, attempt, last):
        if self.cur is None:
            return
        if attempt > 60:  # ~130s
            self.finish(text=last)
            return
        read = """
        (function(){
          var sels=%s;
          for(var s=0;s<sels.length;s++){var els=document.querySelectorAll(sels[s]);
            if(els.length){var t=(els[els.length-1].innerText||'').trim();
              if(t.length>2)return t;}}
          return '';
        })()
        """ % json.dumps(ANSWER_SELS)

        def cb(t):
            t = t or ""
            if attempt % 3 == 0:
                print("[bridge] poll", attempt, "len=", len(t), flush=True)
            if DONE in t:
                self.finish(text=t.split(DONE)[0].strip())
                return
            if len(t) >= 1 and t == last:
                self._stable = getattr(self, "_stable", 0) + 1
                if self._stable >= 3:   # ~6.6s không đổi => Gemini ngừng sinh
                    self.finish(text=t.strip())
                    return
            else:
                self._stable = 0
            QTimer.singleShot(2200, lambda: self.poll(attempt + 1, t))

        self.run_js(read, cb)


class Handler(BaseHTTPRequestHandler):
    def _json(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"ok": True})
        elif self.path == "/probe":
            job = Job("__PROBE__")
            JOBS.put(job)
            job.event.wait(timeout=20)
            self._json(200, {"ok": True, "probe": job.result})
        else:
            self._json(404, {"ok": False})

    def do_POST(self):
        if self.path != "/ask":
            self._json(404, {"ok": False})
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            data = {}
        prompt = (data.get("prompt") or "").strip()
        if not prompt:
            self._json(400, {"ok": False, "error": "empty prompt"})
            return
        job = Job(prompt)
        JOBS.put(job)
        ok = job.event.wait(timeout=150)
        if not ok:
            self._json(504, {"ok": False, "error": "timeout"})
        elif job.error:
            self._json(500, {"ok": False, "error": job.error})
        else:
            self._json(200, {"ok": True, "text": job.result})

    def log_message(self, *a):
        pass


def serve():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    srv.serve_forever()


def main():
    app = QApplication(sys.argv)
    win = Bridge()
    win.resize(1100, 820)
    win.show()
    threading.Thread(target=serve, daemon=True).start()
    print("[gemini_bridge] HTTP server on http://127.0.0.1:%d" % PORT, flush=True)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
