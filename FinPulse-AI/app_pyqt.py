# -*- coding: utf-8 -*-
"""
FinPulse AI — phiên bản PyQt6 (1 cửa sổ): TRÁI = giao diện HTML hiện có
(tin tức + skill-tree), PHẢI = Gemini nhúng (QWebEngine, Google cho login).
Backend Python phục vụ UI trái qua HTTP localhost; Python lái panel Gemini bên
phải để gửi prompt & đọc kết quả (giống app MT4 AI Trading).

Chạy:  python app_pyqt.py
"""
import os
import re
import sys
import json
import queue
import threading
import urllib.request
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PyQt6.QtCore import QUrl, QTimer, Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (QApplication, QMainWindow, QSplitter, QWidget,
                             QVBoxLayout, QHBoxLayout, QPushButton, QToolBar)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (
    QWebEngineProfile, QWebEnginePage, QWebEngineScript, QWebEngineSettings)

PORT = 8765
# Khi đóng gói (.exe) file tài nguyên nằm trong thư mục tạm _MEIPASS
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Tắt cơ chế "đóng băng" renderer khi cửa sổ bị ẩn/occluded -> Gemini vẫn
# chạy ngầm khi ta ẩn panel (PHẢI set trước khi QtWebEngine khởi tạo).
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    "--disable-renderer-backgrounding --disable-background-timer-throttling "
    "--disable-backgrounding-occluded-windows "
    "--disable-features=CalculateNativeWinOcclusion")
DEBUG_LOG = os.path.join(BASE_DIR, "debug.log")


def logd(*args):
    import time as _t
    line = "[%s] %s" % (_t.strftime("%H:%M:%S"), " ".join(str(a) for a in args))
    try:
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    try:
        print(line, flush=True)
    except Exception:
        pass


CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".finpulse_qt", "config.json")
GEMINI_URL = "https://gemini.google.com/app"
DONE = "@@@END@@@"
# Google nhận diện Chrome/124 là "trình duyệt được hỗ trợ" -> cho login.
# (Bản Telegram tool dùng đúng 124 trên cùng QtWebEngine 6.11.1 và đăng nhập OK.)
# Claim version quá mới (140) hoặc để lộ token "QtWebEngine" -> bị chặn.
CHROME_VER = "124"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# ---------------------------------------------------------------- feeds -----
CATEGORIES = [
    {"id": "markets", "label": "Markets / Stocks", "icon": "📈", "feeds": [
        "https://www.cnbc.com/id/20910258/device/rss/rss.html",
        "http://feeds.marketwatch.com/marketwatch/topstories/",
        "https://finance.yahoo.com/news/rssindex"]},
    {"id": "crypto", "label": "Crypto", "icon": "🪙", "feeds": [
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "https://cointelegraph.com/rss"]},
    {"id": "forex", "label": "Forex", "icon": "💱", "feeds": [
        "https://www.fxstreet.com/rss/news",
        "https://www.investing.com/rss/news_1.rss"]},
    {"id": "economy", "label": "Economy / Macro", "icon": "🏛️", "feeds": [
        "https://www.cnbc.com/id/20910258/device/rss/rss.html",
        "https://www.investing.com/rss/news_14.rss"]},
    {"id": "commodities", "label": "Commodities", "icon": "🛢️", "feeds": [
        "https://www.investing.com/rss/news_11.rss",
        "http://feeds.marketwatch.com/marketwatch/marketpulse/"]},
    {"id": "business", "label": "Business", "icon": "💼", "feeds": [
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "https://feeds.bbci.co.uk/news/business/rss.xml"]},
]

# ---------------------------------------------------------------- prompts ---
SYSTEM_BILINGUAL = (
    "Bạn là chuyên gia phân tích tài chính. Trả lời chủ yếu bằng tiếng Việt, "
    "GIỮ NGUYÊN các thuật ngữ tài chính tiếng Anh (hawkish, yield, liquidity, "
    "basis points). Ngắn gọn, có cấu trúc, dùng markdown.")


def article_prompt(a):
    return ("Phân tích bài báo tài chính sau:\n"
            "1. Tóm tắt 2-3 câu.\n2. Tác động thị trường (asset class, bullish/bearish).\n"
            "3. Mức quan trọng (Low/Medium/High) + lý do.\n4. Điều cần theo dõi tiếp.\n\n"
            "--- BÀI BÁO ---\nTiêu đề: %s\nNguồn: %s\nNội dung: %s\nLink: %s" % (
                a.get("title", ""), a.get("source", ""),
                a.get("content") or a.get("snippet", ""), a.get("link", "")))


def branch_prompt(root, path):
    trail = "  →  ".join(path) if path else "(chưa chọn nhánh nào)"
    return ('Chủ đề gốc: "%s".\nĐường dẫn đã chọn: %s.\n\n'
            "Hãy đề xuất ĐÚNG 10 nhánh phụ cụ thể, đa dạng góc nhìn, mỗi nhánh "
            "3-7 từ.\nChỉ trả JSON thuần: {\"branches\":[\"nhánh 1\", ... \"nhánh 10\"]}"
            % (root, trail))


def final_prompt(root, path, note):
    lines = "\n".join("  %d. %s" % (i + 1, l) for i, l in enumerate(path))
    return ('Người dùng xây flow phân tích theo cây nhánh.\nChủ đề gốc: "%s".\n'
            "Flow đã chọn (tổng quát → cụ thể):\n%s%s\n\n"
            "Dựa trên TOÀN BỘ flow trên, đưa ra phân tích tài chính tổng hợp:\n"
            "- **Bối cảnh & luận điểm chính**\n- **Phân tích chi tiết theo flow**\n"
            "- **Rủi ro & yếu tố theo dõi**\n- **Hàm ý giao dịch / hành động**\n"
            "Trình bày markdown, heading rõ ràng."
            % (root, lines, ("\n\nGhi chú thêm: " + note) if note else ""))


# ---------------------------------------------------------------- config ----
def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"mode": "web-auto", "provider": "gemini", "apiKey": "",
                "model": "gemini-2.5-flash"}


def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return cfg


# ---------------------------------------------------------------- RSS -------
def strip_html(s):
    s = re.sub(r"<[^>]*>", " ", s or "")
    s = s.replace("&nbsp;", " ").replace("&amp;", "&")
    s = re.sub(r"&#\d+;", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _lt(el):
    return el.tag.split("}")[-1]


def fetch_feed(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    data = urllib.request.urlopen(req, timeout=12).read()
    root = ET.fromstring(data)
    src = ""
    for ch in root.iter():
        if _lt(ch) == "title":
            src = strip_html(ch.text or "")
            break
    items = []
    for it in root.iter():
        if _lt(it) not in ("item", "entry"):
            continue
        title = link = desc = date = ""
        for c in it:
            t = _lt(c)
            if t == "title":
                title = strip_html(c.text or "")
            elif t == "link":
                link = (c.text or c.get("href") or "").strip()
            elif t in ("description", "summary", "content", "encoded"):
                if not desc:
                    desc = strip_html(c.text or "")
            elif t in ("pubDate", "published", "updated", "date"):
                if not date:
                    date = (c.text or "").strip()
        if title:
            items.append({"title": title, "link": link,
                          "snippet": desc[:400], "content": desc,
                          "source": src or url, "date": date})
    return items


def fetch_category(cid):
    cat = next((c for c in CATEGORIES if c["id"] == cid), None)
    if not cat:
        return {"items": [], "errors": ["unknown"]}
    items, errors, seen = [], [], set()
    for url in cat["feeds"]:
        try:
            for it in fetch_feed(url):
                k = it["title"].lower()
                if k in seen:
                    continue
                seen.add(k)
                items.append(it)
        except Exception as e:
            errors.append("%s — %s" % (url, e))
    return {"items": items[:60], "errors": errors}


# ---------------------------------------------------------------- Gemini API
def gemini_api(system, prompt, model, key, max_tokens=1500):
    url = ("https://generativelanguage.googleapis.com/v1beta/models/%s:"
           "generateContent?key=%s" % (model or "gemini-2.5-flash", key))
    body = json.dumps({
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.7,
                             "thinkingConfig": {"thinkingBudget": 0}},
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    res = urllib.request.urlopen(req, timeout=60).read()
    data = json.loads(res)
    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts).strip()


def parse_branches(text):
    clean = re.sub(r"```json", "", text or "", flags=re.I).replace("```", "").strip()
    m = re.search(r"\{[\s\S]*\}", clean)
    try:
        obj = json.loads(m.group(0) if m else clean)
        if isinstance(obj.get("branches"), list):
            return [str(b).strip() for b in obj["branches"] if str(b).strip()][:10]
    except Exception:
        pass
    q = re.findall(r'"([^"]{3,})"', clean)
    if len(q) >= 3:
        return [x.strip() for x in q if x.strip().lower() != "branches"][:10]
    out = []
    for l in clean.split("\n"):
        l = re.sub(r'^[\s\-*\d.)\]\[{}",]+', "", l).strip().strip('",')
        if l and l.lower() != "branches" and not l.startswith("{"):
            out.append(l)
    return out[:10]


def sanitize(t):
    if not t:
        return t
    t = t.replace(DONE, "")
    t = re.sub(r"@+\s*END\s*@+", "", t, flags=re.I)
    t = re.sub(r"<{2,}\s*(?:DONE|END)?\s*>{2,}", "", t, flags=re.I)
    return t.strip()


# ---------------------------------------------------------------- main window
JOBS = queue.Queue()
BRIDGE = None   # ChromeCDP — đặt khi MainWindow khởi tạo, dùng trong HTTP handler
INPUT_SELS = ["rich-textarea .ql-editor", ".ql-editor",
              'div[contenteditable="true"]', "textarea", '[role="textbox"]']
ANSWER_SELS = [".model-response-text", "message-content",
               '[class*="model-response"]', ".markdown"]


class Job:
    def __init__(self, prompt, new_chat=True):
        self.prompt = prompt
        self.new_chat = new_chat
        self.event = threading.Event()
        self.result = None
        self.error = None


class OverlayCentral(QWidget):
    """Vùng trung tâm: tự đặt lại vị trí trái/phải mỗi khi đổi kích thước."""
    def __init__(self, win):
        super().__init__()
        self.win = win

    def resizeEvent(self, e):
        self.win._relayout()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FinPulse AI")
        self.resize(1500, 900)

        cv = CHROME_VER
        storage = os.path.join(os.path.expanduser("~"), ".finpulse_qt")
        os.makedirs(storage, exist_ok=True)

        # ===== Profile 1: UI TRÁI (HTTP localhost) — có shim, settings nới lỏng =====
        self.uiprofile = QWebEngineProfile("finpulse_ui", self)
        ui_store = os.path.join(os.path.expanduser("~"), ".finpulse_ui")
        os.makedirs(ui_store, exist_ok=True)
        self.uiprofile.setPersistentStoragePath(ui_store)
        self.uiprofile.setCachePath(ui_store)
        shim = QWebEngineScript()
        shim.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        shim.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        shim.setRunsOnSubFrames(False)
        shim.setSourceCode(self._shim_js())
        self.uiprofile.scripts().insert(shim)

        # ===== Profile Gemini (QtWebEngine) — sạch riêng + full stealth =====
        self.gprofile = QWebEngineProfile("finpulse_gemini", self)
        # BỎ QUAN TRỌNG: Không set UA tùy chỉnh để Google không báo lỗi "not secure"
        # self.gprofile.setHttpUserAgent(UA)
        self.gprofile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        self.gprofile.setPersistentStoragePath(storage)
        self.gprofile.setCachePath(storage)
        # logd("UA set:", UA)

        # BỎ QUAN TRỌNG: Không inject anti-script để tránh việc navigator properties bị mismatch
        # anti = QWebEngineScript()
        # anti.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        # anti.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        # anti.setRunsOnSubFrames(True)
        # ...
        # self.gprofile.scripts().insert(anti)

        vis = QWebEngineScript()
        vis.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        vis.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        vis.setRunsOnSubFrames(True)
        vis.setSourceCode("""
        (function(){if(location.hostname.indexOf('google')<0)return;
          try{Object.defineProperty(document,'visibilityState',{get:function(){return 'visible';},configurable:true});}catch(e){}
          try{Object.defineProperty(document,'hidden',{get:function(){return false;},configurable:true});}catch(e){}
          document.addEventListener('visibilitychange',function(e){e.stopImmediatePropagation();},true);})();
        """)
        self.gprofile.scripts().insert(vis)

        # Container overlay: trái + phải đặt thủ công, khi ẩn thì trái phủ lên phải
        # (KHÔNG reparent webview -> không bị đen; webview luôn real-size -> không freeze)
        self.central = OverlayCentral(self)

        # TRÁI: UI HTML hiện có
        self.left = QWebEngineView()
        self.lpage = QWebEnginePage(self.uiprofile, self.left)
        self.lpage.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        self.lpage.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        self.left.setPage(self.lpage)
        # Load UI QUA HTTP (cùng origin với API) -> không dính CORS/file://
        self.left.load(QUrl("http://127.0.0.1:%d/" % PORT))

        # PHẢI: Gemini (QtWebEngine)
        self.right = QWebEngineView()
        self.gpage = QWebEnginePage(self.gprofile, self.right)
        self.right.setPage(self.gpage)
        self.right.load(QUrl(GEMINI_URL))

        self.left.setParent(self.central)
        self.right.setParent(self.central)
        self._gem_hidden = False
        self.setCentralWidget(self.central)
        QTimer.singleShot(0, self._relayout)

        # Thanh công cụ trên cùng — LUÔN hiện, kể cả khi đã ẩn Gemini
        tb = QToolBar()
        tb.setMovable(False)
        tb.setStyleSheet(
            "QToolBar{background:#161d2e;border-bottom:1px solid #263048;padding:4px;spacing:6px;}"
            "QToolButton{color:#e6ecf5;background:#1c2438;border:1px solid #263048;"
            "border-radius:7px;padding:5px 12px;font-size:12px;}"
            "QToolButton:hover{border-color:#4f8cff;}")
        self.addToolBar(tb)
        self.act_toggle = QAction("🙈 Ẩn Gemini", self)
        self.act_toggle.triggered.connect(self.toggle_gemini)
        act_new = QAction("🆕 Chat mới", self)
        act_new.triggered.connect(lambda: self.right.load(QUrl(GEMINI_URL)))
        act_switch = QAction("👤 Đổi tài khoản", self)
        act_switch.triggered.connect(self.switch_account)
        tb.addAction(self.act_toggle)
        tb.addAction(act_new)
        tb.addAction(act_switch)

        # mở link bài báo ra trình duyệt hệ thống
        self.lpage.newWindowRequested.connect(
            lambda req: __import__("webbrowser").open(req.requestedUrl().toString()))

        # vòng lặp xử lý job Gemini (GUI thread)
        self.busy = False
        self.cur = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.pump)
        self.timer.start(250)

    def _shim_js(self):
        return ("""
        (function(){
          if(location.hostname!=='127.0.0.1')return; // chỉ tiêm vào UI của app
          function get(p){return fetch(p).then(function(r){return r.json();});}
          function post(p,b){return fetch(p,{method:'POST',headers:{'Content-Type':'application/json'},
            body:JSON.stringify(b||{})}).then(function(r){return r.json();});}
          window.api={
            getCategories:function(){return get('/api/categories');},
            fetchCategory:function(id){return get('/api/feed?id='+encodeURIComponent(id));},
            getConfig:function(){return get('/api/config');},
            saveConfig:function(c){return post('/api/config',c);},
            aiRun:function(task,payload){return post('/api/airun',{task:task,payload:payload});},
            qtbridgeAsk:function(prompt,newChat){return post('/api/ask',{prompt:prompt,newChat:newChat!==false});},
            qtbridgeStart:function(){return Promise.resolve({ok:true});},
            qtbridgeHealth:function(){return Promise.resolve({ok:true});},
            openDevTools:function(){},aiwinShow:function(){},aiwinSend:function(){},
            onAiwinStatus:function(){}
          };
        })();
        """)

    def _relayout(self):
        c = self.central
        W, H = c.width(), c.height()
        if W <= 0 or H <= 0:
            return
        if self._gem_hidden:
            # Trái phủ TOÀN BỘ; phải vẫn real-size nằm dưới (render ngầm, không freeze)
            rw = max(520, int(W * 0.4))
            self.right.setGeometry(W - rw, 0, rw, H)
            self.left.setGeometry(0, 0, W, H)
        else:
            lw = int(W * 0.60)
            self.left.setGeometry(0, 0, lw, H)
            self.right.setGeometry(lw, 0, W - lw, H)
        self.right.lower()
        self.left.raise_()

    def toggle_gemini(self):
        # KHÔNG reparent (tránh đen). Chỉ đổi bố cục: ẩn = trái phủ lên phải.
        self._gem_hidden = not self._gem_hidden
        self.act_toggle.setText("👁 Hiện Gemini" if self._gem_hidden else "🙈 Ẩn Gemini")
        self._relayout()

    def switch_account(self):
        # Xoá cookie + cache phiên Gemini rồi nạp lại -> hiện màn đăng nhập mới.
        self.gprofile.cookieStore().deleteAllCookies()
        self.gprofile.clearHttpCache()
        QTimer.singleShot(300, lambda: self.right.load(QUrl(GEMINI_URL)))

    # ---- Gemini drive (giống bridge) ----
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
        if self.cur is not None:
            self.cur.result = sanitize(text) if text else text
            self.cur.error = error
            self.cur.event.set()
        self.cur = None
        self.busy = False

    def run_js(self, code, cb):
        self.gpage.runJavaScript(code, cb)

    def start_job(self, job):
        self.marked = job.prompt + ("\n\n---\nKhi đã viết xong TOÀN BỘ, kết thúc "
                                    "bằng đúng MỘT dòng riêng: " + DONE)
        if not job.new_chat:
            # GÕ TIẾP trong cùng phiên -> liền mạch + nhanh (không reload)
            logd("start_job: cùng phiên (gõ tiếp)")
            QTimer.singleShot(300, self.do_insert)
            return
        logd("start_job: mở chat mới")
        self._step = False

        def on_load(ok):
            if self._step:
                return
            self._step = True
            try:
                self.gpage.loadFinished.disconnect(on_load)
            except Exception:
                pass
            QTimer.singleShot(2200, self.do_insert)

        self.gpage.loadFinished.connect(on_load)
        self.gpage.load(QUrl(GEMINI_URL))
        QTimer.singleShot(9000, lambda: on_load(True))

    def do_insert(self):
        code = """
        (function(){var ss=%s;var el=null;
          for(var i=0;i<ss.length;i++){var e=document.querySelector(ss[i]);if(e){el=e;break;}}
          if(!el)return false;el.focus();
          try{document.execCommand('insertText',false,%s);}catch(e){}
          if(el.textContent!==undefined&&el.textContent.trim()===''){el.textContent=%s;
            el.dispatchEvent(new Event('input',{bubbles:true}));}
          return true;})()""" % (json.dumps(INPUT_SELS), json.dumps(self.marked),
                                 json.dumps(self.marked))

        def cb(ok):
            logd("  focus+insert ->", ok)
            if not ok:
                self.finish(error="Không thấy ô nhập — đăng nhập Gemini ở panel phải.")
                return
            QTimer.singleShot(900, self.do_submit)
        self.run_js(code, cb)

    def do_submit(self):
        # Đếm số câu trả lời ĐANG có (để biết câu mới khi cùng phiên)
        def got_count(n):
            self._base_n = n or 0
            logd("  base answers =", self._base_n)
            code = """
            (function(){var el=document.activeElement;
              var ev={key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true,cancelable:true};
              var bs=document.querySelectorAll('button[aria-label],button[mattooltip]');
              for(var i=0;i<bs.length;i++){var b=bs[i];
                var a=((b.getAttribute('aria-label')||'')+' '+(b.getAttribute('mattooltip')||'')).toLowerCase();
                if(/send|gửi|submit/.test(a)&&!b.disabled){b.click();return 'btn';}}
              if(el){el.dispatchEvent(new KeyboardEvent('keydown',ev));el.dispatchEvent(new KeyboardEvent('keyup',ev));}
              return 'enter';})()"""

            def cb(r):
                logd("  submit ->", r)
                self._stable = 0
                self.poll(0, "")
            self.run_js(code, cb)
        self.run_js(self.count_js(), got_count)

    def count_js(self):
        return ("(function(){var sels=%s;for(var s=0;s<sels.length;s++){"
                "var els=document.querySelectorAll(sels[s]);if(els.length)return els.length;}"
                "return 0;})()" % json.dumps(ANSWER_SELS))

    def poll(self, attempt, last):
        if self.cur is None:
            return
        if attempt > 70:
            self.finish(text=last)
            return
        read = """(function(){var sels=%s;
          for(var s=0;s<sels.length;s++){var els=document.querySelectorAll(sels[s]);
            if(els.length){return JSON.stringify({n:els.length,
              t:(els[els.length-1].innerText||'').trim()});}}
          return JSON.stringify({n:0,t:''});})()""" % json.dumps(ANSWER_SELS)

        def cb(res):
            try:
                o = json.loads(res or "{}")
            except Exception:
                o = {"n": 0, "t": ""}
            n, t = o.get("n", 0), o.get("t", "")
            # Câu trả lời MỚI chưa xuất hiện (vẫn là câu cũ) -> chờ tiếp
            if n <= getattr(self, "_base_n", 0):
                QTimer.singleShot(1500, lambda: self.poll(attempt + 1, last))
                return
            if DONE in t:
                self.finish(text=t.split(DONE)[0])
                return
            if len(t) >= 1 and t == last:
                self._stable = getattr(self, "_stable", 0) + 1
                if self._stable >= 3:
                    self.finish(text=t)
                    return
            else:
                self._stable = 0
            QTimer.singleShot(2000, lambda: self.poll(attempt + 1, t))
        self.run_js(read, cb)


# ---------------------------------------------------------------- HTTP API --
class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        # CORS preflight cho POST từ origin file://
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def do_GET(self):
        if self.path == "/api/categories":
            self._send(200, [{"id": c["id"], "label": c["label"], "icon": c["icon"]}
                             for c in CATEGORIES])
        elif self.path.startswith("/api/feed"):
            from urllib.parse import urlparse, parse_qs
            cid = parse_qs(urlparse(self.path).query).get("id", [""])[0]
            self._send(200, fetch_category(cid))
        elif self.path == "/api/config":
            self._send(200, load_config())
        elif self.path.startswith("/api/"):
            self._send(404, {"ok": False})
        else:
            self._serve_static(self.path)

    def _serve_static(self, path):
        p = path.split("?")[0]
        if p in ("/", ""):
            p = "/index.html"
        rdir = os.path.join(BASE_DIR, "renderer")
        fp = os.path.normpath(os.path.join(rdir, p.lstrip("/")))
        if not fp.startswith(rdir) or not os.path.isfile(fp):
            self.send_response(404)
            self.end_headers()
            return
        ext = os.path.splitext(fp)[1].lower()
        ctype = {".html": "text/html; charset=utf-8", ".css": "text/css",
                 ".js": "application/javascript", ".json": "application/json",
                 ".png": "image/png", ".svg": "image/svg+xml"}.get(ext, "text/plain")
        with open(fp, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path == "/api/config":
            self._send(200, save_config(self._body()))
        elif self.path == "/api/airun":
            self._send(200, self._airun(self._body()))
        elif self.path == "/api/ask":
            data = self._body()
            prompt = (data.get("prompt") or "").strip()
            new_chat = data.get("newChat", True)
            logd("POST /api/ask  prompt_len=", len(prompt), "new_chat=", new_chat)
            job = Job(prompt, new_chat)
            JOBS.put(job)
            ok = job.event.wait(timeout=150)
            logd("POST /api/ask done ok=", ok, "err=", job.error,
                 "text_len=", len(job.result or "") if job.result else 0)
            if not ok:
                self._send(200, {"ok": False, "error": "timeout"})
            elif job.error:
                self._send(200, {"ok": False, "error": job.error})
            else:
                self._send(200, {"ok": True, "text": job.result})
        else:
            self._send(404, {"ok": False})

    def _airun(self, data):
        task = data.get("task")
        payload = data.get("payload", {})
        cfg = load_config()
        logd("POST /api/airun task=", task, "mode=", cfg.get("mode"))
        try:
            if task == "article":
                prompt, mx = article_prompt(payload.get("article", {})), 1500
            elif task == "branches":
                prompt, mx = branch_prompt(payload.get("rootTopic", ""),
                                           payload.get("path", [])), 1000
            elif task == "final":
                prompt, mx = final_prompt(payload.get("rootTopic", ""),
                                          payload.get("path", []), payload.get("note", "")), 2500
            else:
                return {"ok": False, "error": "unknown task"}

            if cfg.get("mode", "").startswith("web"):
                return {"ok": True, "mode": "web-auto", "prompt": prompt}

            text = gemini_api(SYSTEM_BILINGUAL, prompt, cfg.get("model"),
                              cfg.get("apiKey", ""), mx)
            if task == "branches":
                return {"ok": True, "mode": "api", "branches": parse_branches(text)}
            return {"ok": True, "mode": "api", "text": text}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def log_message(self, *a):
        pass


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    # BIND server TRƯỚC khi tạo cửa sổ -> webview load chắc chắn có server.
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    logd("server bound on", PORT)
    app = QApplication(sys.argv)
    app.setApplicationName("")  # Ngăn QtWebEngine tự động thêm tên file exe vào cuối User-Agent
    win = MainWindow()
    win.show()
    print("[FinPulse] http://127.0.0.1:%d ready" % PORT, flush=True)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
