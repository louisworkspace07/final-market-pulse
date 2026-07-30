import asyncio
import contextlib
import queue
import concurrent.futures
import threading
import json
import os
import random
import time
from datetime import datetime
from playwright.async_api import async_playwright

import local_api

# Kênh AI: "local_api" (MẶC ĐỊNH — server local :4000, xem local_api.py) hoặc
# "gemini" (tự lái Chrome CDP như trước, giữ lại để dự phòng).
AI_BACKEND = (os.environ.get("AI_BACKEND") or "local_api").strip().lower()
if AI_BACKEND not in ("local_api", "gemini"):
    AI_BACKEND = "local_api"
USE_LOCAL_API = AI_BACKEND == "local_api"

# Chrome dùng chung (mở sẵn bằng data-crawler/scripts/launch_chrome.py, đã đăng nhập Gemini).
CDP_URL = os.environ.get("CDP_URL", "http://localhost:9222")
GEMINI_URL = "https://gemini.google.com/app"
# Trần số lượt phân tích chạy song song (kênh CDP = số tab Chrome). Chỉnh bằng env.
MAX_TABS = int(os.environ.get("CDP_MAX_TABS", "3"))

USER_DATA_DIR = os.path.join(os.getcwd(), "gemini_profile")  # giữ tương thích, không còn dùng để launch
CACHE_FILE = os.path.join("temp_data", "ai_cache.json")

# Semaphore giới hạn số lượt song song; khởi tạo trong worker loop (gắn với event loop).
_sem = None
# Mốc lần cuối kiểm tra kênh AI sẵn sàng (để thử lại định kỳ khi chưa sẵn sàng).
_last_ready_check = [0.0]

manual_queue = queue.Queue()

worker_state = {
    "is_logged_in": False,
    "scan_total": 0,
    "scan_scanned": 0,
    "scan_current_symbol": "",
    "scan_status": "Khởi tạo...",
    "account_info": "Chưa rõ",
    "is_auto_scan_paused": True
}

import urllib.request

def load_target_symbols():
    try:
        # Lấy dữ liệu VN30 trực tiếp từ API của chính Server đang chạy
        import urllib.request
        req = urllib.request.Request('http://127.0.0.1:5555/api/stocks', headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req).read().decode('utf-8')
        data = json.loads(res)
        return data
    except Exception as e:
        print("Loi load_target_symbols:", e)
        return []

target_symbols = []
target_index = 0
last_auto_scan_time = 0
is_auto_scan_paused = True
selected_scan_targets = None

def request_toggle_auto_scan():
    f = concurrent.futures.Future()
    manual_queue.put({"type": "toggle_auto_scan", "future": f})
    return f

def request_set_auto_scan_targets(targets):
    f = concurrent.futures.Future()
    manual_queue.put({"type": "set_targets", "targets": targets, "future": f})
    return f

async def take_chart_screenshot(context, symbol):
    try:
        import tempfile, os, asyncio
        url = f"http://127.0.0.1:5555/static/chart_only.html?symbol={symbol}"
        new_page = await context.new_page()
        await new_page.set_viewport_size({"width": 1280, "height": 720})
        await new_page.goto(url)
        
        # Chờ window.chartReady == true
        await new_page.wait_for_function("window.chartReady === true", timeout=15000)
        
        # Chụp ảnh
        fd, image_path = tempfile.mkstemp(suffix='.png', prefix=f'tdv_{symbol}_')
        os.close(fd)
        await new_page.screenshot(path=image_path)
        
        await new_page.close()
        return image_path
    except Exception as e:
        print(f"Lỗi chụp ảnh chart {symbol}:", e)
        return None

async def perform_gemini_query(context, prompt, image_path=None):
    """Hỏi AI 1 lượt. Mặc định đi qua LOCAL API (HTTP), dự phòng Chrome CDP.

    Kênh local_api: gọi HTTP trong thread phụ (client là urllib đồng bộ) → không
    cần tab Chrome, không cần đăng nhập Gemini.
    Kênh gemini: mở 1 TAB MỚI trong Chrome dùng chung → hỏi → ĐÓNG tab.
    Trần song song do _sem (asyncio.Semaphore(MAX_TABS)) kiểm soát ở cả 2 kênh."""
    global _sem
    if _sem is None:
        _sem = asyncio.Semaphore(MAX_TABS)

    if USE_LOCAL_API:
        async with _sem:
            try:
                text = await asyncio.to_thread(local_api.ask, prompt, image_path)
                return {"status": "success", "result": text}
            except Exception as e:
                return {"status": "error", "error": str(e)[:300]}

    async with _sem:
        # jitter nhỏ tránh nhiều tab gõ cùng lúc → giảm rủi ro bị chặn
        await asyncio.sleep(0.5 + random.random() * 1.5)
        page = await context.new_page()
        try:
            return await _query_on_page(page, prompt, image_path)
        finally:
            try:
                await page.close()
            except Exception:
                pass


async def _query_on_page(page, prompt, image_path=None):
    try:
        # Bắt đầu chat mới bằng cách tải lại trang chủ
        await page.goto("https://gemini.google.com/app")
        await asyncio.sleep(2)

        if image_path:
            try:
                import base64
                with open(image_path, 'rb') as f:
                    b64_data = base64.b64encode(f.read()).decode('utf-8')
                
                await page.wait_for_selector('rich-textarea', timeout=15000)
                await page.evaluate(f'''(b64) => {{
                    function b64toBlob(b64Data, contentType='', sliceSize=512) {{
                        const byteCharacters = atob(b64Data);
                        const byteArrays = [];
                        for (let offset = 0; offset < byteCharacters.length; offset += sliceSize) {{
                            const slice = byteCharacters.slice(offset, offset + sliceSize);
                            const byteNumbers = new Array(slice.length);
                            for (let i = 0; i < slice.length; i++) {{
                                byteNumbers[i] = slice.charCodeAt(i);
                            }}
                            const byteArray = new Uint8Array(byteNumbers);
                            byteArrays.push(byteArray);
                        }}
                        return new Blob(byteArrays, {{type: contentType}});
                    }}
                    const blob = b64toBlob(b64, 'image/jpeg');
                    const file = new File([blob], 'chart.jpg', {{ type: 'image/jpeg' }});
                    
                    const dataTransfer = new DataTransfer();
                    dataTransfer.items.add(file);
                    
                    const editor = document.querySelector('rich-textarea');
                    const pasteEvent = new ClipboardEvent('paste', {{
                        clipboardData: dataTransfer,
                        bubbles: true,
                        cancelable: true
                    }});
                    editor.dispatchEvent(pasteEvent);
                }}''', b64_data)
                
                await asyncio.sleep(4) # Wait for image to attach
            except Exception as e:
                print("Lỗi đính kèm ảnh vào Gemini:", e)
        
        # Nhập prompt
        input_selector = "rich-textarea"
        await page.wait_for_selector(input_selector, timeout=10000)
        await page.click(input_selector)
        await asyncio.sleep(0.5)
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        
        await page.keyboard.insert_text(prompt)
        await asyncio.sleep(0.5)
        await page.keyboard.press("Enter")
        
        # Chờ sinh kết quả (chờ thẻ message-content mới nhất)
        await asyncio.sleep(3)
        await page.wait_for_selector("message-content", timeout=45000)
        
        elements = await page.query_selector_all("message-content")
        if elements:
            last_msg = elements[-1]
            previous_text = ""
            stable_count = 0
            current_text = ""
            
            # Đợi đến khi văn bản không còn thay đổi trong 2 giây (đã generate xong)
            for _ in range(40):
                await asyncio.sleep(1)
                current_text = await last_msg.inner_text()
                if current_text == previous_text and len(current_text) > 0:
                    stable_count += 1
                    if stable_count >= 2:
                        break
                else:
                    stable_count = 0
                    previous_text = current_text
                    
            raw_text = current_text
            
            clean_text = raw_text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            elif clean_text.startswith("```"):
                clean_text = clean_text[3:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
                
            return {"status": "success", "result": clean_text.strip()}
    except Exception as e:
        return {"status": "error", "error": str(e)}
    return {"status": "error", "error": "Không lấy được kết quả từ Gemini"}

async def _check_login(context) -> bool:
    """Kênh AI đã sẵn sàng chưa → cập nhật worker_state.

    - local_api: "sẵn sàng" = có LOCAL_API_KEY và server local phản hồi. Không
      có khái niệm đăng nhập Google ở đây.
    - gemini: mở 1 tab tạm kiểm tra đã đăng nhập Gemini chưa (Chrome dùng chung
      do launch_chrome mở + user đăng nhập sẵn)."""
    if USE_LOCAL_API:
        st = await asyncio.to_thread(local_api.status)
        ready = bool(st["has_key"] and st["up"])
        worker_state["is_logged_in"] = ready
        worker_state["account_info"] = f"Local API · {st['model']}" if ready else "Chưa sẵn sàng"
        if not ready:
            worker_state["scan_status"] = (
                "Thiếu LOCAL_API_KEY (data-crawler/.env)" if not st["has_key"]
                else f"Server AI local không phản hồi ở {st['url']}")
        return ready

    page = await context.new_page()
    try:
        await page.goto(GEMINI_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_selector("rich-textarea", timeout=12000)
        sign_in = await page.query_selector_all(
            "a[href*='accounts.google.com/ServiceLogin'], a[href*='accounts.google.com/v3/signin']")
        logged_in = len(sign_in) == 0
        worker_state["is_logged_in"] = logged_in
        if logged_in:
            try:
                account_info = await page.evaluate('''() => {
                    const el = document.querySelector('a[aria-label^="Tài khoản Google:"]');
                    return el ? el.getAttribute('aria-label') : null;
                }''')
                if account_info:
                    worker_state["account_info"] = account_info.replace("Tài khoản Google:", "").strip()
            except Exception:
                pass
        return logged_in
    except Exception:
        worker_state["is_logged_in"] = False
        return False
    finally:
        try:
            await page.close()
        except Exception:
            pass


async def _run_analysis(context, symbol, prompt, image_path=None):
    """1 phân tích hoàn chỉnh: chụp chart (tab riêng) → hỏi Gemini (tab riêng) → lưu cache.
    Trả về dict {status, result|error}. Dùng cho cả manual lẫn auto-scan (chạy song song)."""
    own_image = False
    try:
        # context=None (kênh local_api mà không mở nổi trình duyệt chụp ảnh) →
        # bỏ qua ảnh biểu đồ, vẫn phân tích bằng số liệu trong prompt.
        if not image_path and context is not None:
            image_path = await take_chart_screenshot(context, symbol or "UNKNOWN")
            own_image = True
        res = await perform_gemini_query(context, prompt, image_path)
    except Exception as e:
        res = {"status": "error", "error": str(e)}
    finally:
        if own_image and image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception:
                pass

    if res.get("status") == "success" and symbol:
        ai_cache = {}
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    ai_cache = json.load(f)
            except Exception:
                pass
        ai_cache[symbol] = {
            "data": res["result"],
            "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        }
        try:
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(ai_cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    return res


async def worker_main_loop():
    global target_symbols, target_index, worker_state, last_auto_scan_time, is_auto_scan_paused, selected_scan_targets, _sem

    print(f"Khoi dong AI Worker (backend={AI_BACKEND})...")
    _sem = asyncio.Semaphore(MAX_TABS)

    # Kênh local_api không đụng trình duyệt → không khởi động cả driver Playwright.
    async with contextlib.AsyncExitStack() as stack:
        p = None if USE_LOCAL_API else await stack.enter_async_context(async_playwright())
        browser = None
        context = None

        if USE_LOCAL_API:
            # Kênh local_api KHÔNG cần trình duyệt: không cần Chrome đăng nhập
            # Gemini, và cũng không chụp chart vì server local chỉ nhận TEXT
            # (xem local_api.py) — ảnh gửi lên sẽ bị nội suy thành rác.
            context = None
        else:
            # Kết nối tới Chrome ĐÃ MỞ SẴN (launch_chrome.py). Thử lại nếu chưa lên.
            for _ in range(60):
                try:
                    browser = await p.chromium.connect_over_cdp(CDP_URL, timeout=3000)
                    break
                except Exception:
                    worker_state["scan_status"] = f"Chờ Chrome ở {CDP_URL} (chạy launch_chrome)..."
                    await asyncio.sleep(1)
            if browser is None:
                worker_state["scan_status"] = f"Không kết nối được Chrome ở {CDP_URL}."
                print(worker_state["scan_status"])
                return
            context = browser.contexts[0] if browser.contexts else await browser.new_context()

        await _check_login(context)
        if USE_LOCAL_API:
            print("AI Worker: " + ("Local API san sang." if worker_state["is_logged_in"]
                                   else "Local API CHUA san sang - " + worker_state["scan_status"]))
        else:
            print("Gemini Worker: " + ("Da dang nhap." if worker_state["is_logged_in"] else "Chua dang nhap."))

        target_symbols = load_target_symbols()
        worker_state["scan_total"] = len(target_symbols)

        inflight = {}   # symbol -> asyncio.Task cho auto-scan

        while True:
            # 1. Manual tasks (ưu tiên). analyze chạy dạng task song song, không chặn loop.
            try:
                task = manual_queue.get_nowait()
                if task["type"] == "analyze":
                    worker_state["scan_status"] = "Đang xử lý yêu cầu thủ công..."

                    async def _manual(t):
                        res = await _run_analysis(context, t.get("symbol"), t["prompt"], t.get("image_path"))
                        t["future"].set_result(res)
                    asyncio.create_task(_manual(task))

                elif task["type"] == "login":
                    # local_api: "đăng nhập" = kiểm tra lại server local + API key.
                    # gemini: đăng nhập nằm ở cửa sổ Chrome dùng chung (launch_chrome).
                    logged = await _check_login(context)
                    if logged:
                        task["future"].set_result({"status": "success",
                            "result": "Local API sẵn sàng!" if USE_LOCAL_API else "Đã đăng nhập sẵn rồi!"})
                    elif USE_LOCAL_API:
                        task["future"].set_result({"status": "error",
                            "error": worker_state["scan_status"] or "Server AI local chưa sẵn sàng."})
                    else:
                        task["future"].set_result({"status": "error",
                            "error": "Chưa đăng nhập. Hãy đăng nhập Gemini trong cửa sổ Chrome (launch_chrome)."})

                elif task["type"] == "status":
                    task["future"].set_result(worker_state)

                elif task["type"] == "screenshot":
                    # Ảnh màn hình tab Gemini chỉ có nghĩa ở kênh CDP.
                    if USE_LOCAL_API or context is None:
                        task["future"].set_result({"status": "error",
                            "message": "Kênh Local API không có tab Gemini để chụp màn hình."})
                        manual_queue.task_done()
                        continue

                    async def _shot(t):
                        pg = await context.new_page()
                        try:
                            await pg.goto(GEMINI_URL, wait_until="domcontentloaded", timeout=30000)
                            img_bytes = await pg.screenshot(type='jpeg', quality=40)
                            import base64
                            b64 = base64.b64encode(img_bytes).decode('utf-8')
                            t["future"].set_result({"status": "success", "data": "data:image/jpeg;base64," + b64})
                        except Exception as e:
                            t["future"].set_result({"status": "error", "message": str(e)})
                        finally:
                            try: await pg.close()
                            except Exception: pass
                    asyncio.create_task(_shot(task))

                elif task["type"] == "reset_scan":
                    target_symbols.clear() # Force reload from API
                    target_index = 0
                    worker_state["scan_scanned"] = 0
                    worker_state["scan_status"] = "Đang bắt đầu quét lại..."
                    
                    # Clear cache to force rescan
                    try:
                        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                            f.write('{}')
                    except: pass
                    
                    is_auto_scan_paused = False
                    worker_state["is_auto_scan_paused"] = is_auto_scan_paused
                    
                    task["future"].set_result({"status": "success"})
                    
                elif task["type"] == "toggle_auto_scan":
                    is_auto_scan_paused = not is_auto_scan_paused
                    worker_state["is_auto_scan_paused"] = is_auto_scan_paused
                    task["future"].set_result({"status": "success", "paused": is_auto_scan_paused})
                    
                elif task["type"] == "set_targets":
                    selected_scan_targets = task.get("targets", [])
                    target_symbols.clear()
                    target_index = 0
                    task["future"].set_result({"status": "success"})
                
                manual_queue.task_done()
                continue # process next manual task first
            except queue.Empty:
                pass

            # 2. Auto-scan: điều phối tối đa MAX_TABS mã chạy SONG SONG.
            # Dọn các task đã xong.
            for sym, t in list(inflight.items()):
                if t.done():
                    inflight.pop(sym, None)
                    worker_state["scan_scanned"] += 1
                    exc = t.exception() if not t.cancelled() else None
                    if exc:
                        print(f"Loi khi quet ma {sym}: {exc}")

            if worker_state["is_logged_in"] and not is_auto_scan_paused:
                if len(target_symbols) == 0:
                    loaded = load_target_symbols()
                    if selected_scan_targets is not None:
                        loaded = [s for s in loaded if s.get('symbol') in selected_scan_targets]
                    target_symbols = loaded
                    if len(target_symbols) == 0:
                        worker_state["scan_status"] = "Không có mã nào được chọn để quét..."
                        await asyncio.sleep(2)
                        continue
                    worker_state["scan_total"] = len(target_symbols)
                    target_index = 0

                if target_index >= len(target_symbols):
                    if inflight:
                        await asyncio.sleep(0.5)   # chờ các mã đang chạy xong
                        continue
                    worker_state["scan_status"] = "Đã quét xong toàn bộ"
                    # Danh sách 1 mã (Crawler đang khởi động trả MOCK) → thử lấy lại liên tục.
                    if len(target_symbols) <= 1:
                        await asyncio.sleep(5)
                        loaded = load_target_symbols()
                        if selected_scan_targets is not None:
                            loaded = [s for s in loaded if s.get('symbol') in selected_scan_targets]
                        target_symbols = loaded
                        worker_state["scan_total"] = len(target_symbols)
                        worker_state["scan_scanned"] = 0
                        target_index = 0
                        continue
                    # Đã quét xong danh sách thật → chỉ lặp lại 1 lần/giờ để tránh ban.
                    if time.time() - last_auto_scan_time > 3600:
                        loaded = load_target_symbols()
                        if selected_scan_targets is not None:
                            loaded = [s for s in loaded if s.get('symbol') in selected_scan_targets]
                        target_symbols = loaded
                        worker_state["scan_total"] = len(target_symbols)
                        worker_state["scan_scanned"] = 0
                        target_index = 0
                        last_auto_scan_time = time.time()
                    else:
                        await asyncio.sleep(1)
                    continue

                # Còn slot song song → dispatch mã kế tiếp (không chờ nó xong).
                if len(inflight) < MAX_TABS:
                    item = target_symbols[target_index]
                    symbol = item.get("symbol")
                    target_index += 1
                    worker_state["scan_current_symbol"] = symbol
                    worker_state["scan_status"] = f"Đang phân tích ({len(inflight)+1} luồng)"

                    # Bỏ qua nếu cache còn hạn 1 giờ.
                    ai_cache = {}
                    if os.path.exists(CACHE_FILE):
                        try:
                            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                                ai_cache = json.load(f)
                        except Exception:
                            pass
                    cached_valid = False
                    if symbol in ai_cache:
                        try:
                            ct = datetime.strptime(ai_cache[symbol].get("timestamp", ""), "%d/%m/%Y %H:%M:%S")
                            if (datetime.now() - ct).total_seconds() < 3600:
                                cached_valid = True
                        except Exception:
                            pass
                    if cached_valid:
                        worker_state["scan_scanned"] += 1
                        continue

                    prompt = generate_prompt_for_symbol(symbol, item)
                    if symbol not in inflight:
                        inflight[symbol] = asyncio.create_task(_run_analysis(context, symbol, prompt))
                    await asyncio.sleep(0.2)   # nhịp nhẹ giữa các lần dispatch
                else:
                    await asyncio.sleep(0.5)   # đủ luồng, chờ slot
            else:
                await asyncio.sleep(1)
                # Kênh chưa sẵn sàng (server local chưa bật / chưa có key) → thử
                # lại mỗi 15s để tự chạy tiếp khi server lên, khỏi restart worker.
                if (not worker_state["is_logged_in"]
                        and time.time() - _last_ready_check[0] > 15):
                    _last_ready_check[0] = time.time()
                    await _check_login(context)

def start_worker_thread():
    def run_loop():
        import sys
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        asyncio.run(worker_main_loop())
    t = threading.Thread(target=run_loop, daemon=True)
    t.start()

def request_manual_analysis(symbol, prompt, image_path=None):
    future = concurrent.futures.Future()
    manual_queue.put({
        "type": "analyze",
        "symbol": symbol,
        "prompt": prompt,
        "image_path": image_path,
        "future": future
    })
    return future

def request_login():
    future = concurrent.futures.Future()
    manual_queue.put({
        "type": "login",
        "future": future
    })
    return future

def generate_prompt_for_symbol(symbol, item=None):
    try:
        import urllib.request, json, time
        import concurrent.futures
        from datetime import datetime
        
        end_time = int(time.time())
        start_time_w = end_time - 86400 * 365 * 2
        start_time_d = end_time - 86400 * 180
        
        urls = {
            'vbp': f'http://127.0.0.1:5555/api/vbp/{symbol}',
            'weekly': f'https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?symbol={symbol}&resolution=1W&from={start_time_w}&to={end_time}',
            'daily': f'https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?symbol={symbol}&resolution=1D&from={start_time_d}&to={end_time}'
        }
        if not item:
            urls['item'] = 'https://bdcapi.vndirect.com.vn/api/v1/stock/stock?symbols=' + symbol
            
        def fetch_url_json(url):
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                res = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
                return json.loads(res)
            except Exception as e:
                print(f"Error fetching {url}:", e)
                return None
                
        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            future_to_key = {executor.submit(fetch_url_json, url): key for key, url in urls.items()}
            for future in concurrent.futures.as_completed(future_to_key):
                key = future_to_key[future]
                results[key] = future.result()
                
        if not item:
            item_data = results.get('item')
            item = item_data[0] if item_data and isinstance(item_data, list) else {}
            
        prompt = f"Bạn là chuyên gia phân tích kỹ thuật chứng khoán DÀI HẠN. Dựa vào ảnh biểu đồ 3 năm đính kèm (nếu có) và dữ liệu dưới đây, hãy phân tích xu hướng DÀI HẠN của cổ phiếu {symbol} theo lý thuyết Cung Cầu và các mốc Kháng cự/Hỗ trợ quan trọng nhất.\n\n"
        prompt += f"DỮ LIỆU THỊ TRƯỜNG {symbol}:\n"
        prompt += f"- Giá HT: {item.get('matchPrice')} (KL khớp: {item.get('matchVol')})\n"
        prompt += f"- Giá Tham chiếu: {item.get('ref')}, Trần: {item.get('ceil')}, Sàn: {item.get('floor')}\n"
        prompt += f"- Giá Cao/Thấp/TB: {item.get('high')} / {item.get('low')} / {item.get('avg')}\n"
        prompt += f"- Tổng KLGD: {item.get('totalVol')}\n"
        prompt += f"- Nước ngoài Mua/Bán: {item.get('foreignBuy')} / {item.get('foreignSell')}\n"
        prompt += f"- Tổng Dư Mua / Dư Bán: {item.get('remainBuy')} / {item.get('remainSell')}\n\n"
        
        prompt += f"[SỔ LỆNH - 3 MỨC]\n"
        prompt += f"+ Dư Mua:\n"
        prompt += f"  Mức 1: Giá {item.get('buyP1')} - KL {item.get('buyV1')}\n"
        prompt += f"  Mức 2: Giá {item.get('buyP2')} - KL {item.get('buyV2')}\n"
        prompt += f"  Mức 3: Giá {item.get('buyP3')} - KL {item.get('buyV3')}\n"
        prompt += f"+ Dư Bán:\n"
        prompt += f"  Mức 1: Giá {item.get('sellP1')} - KL {item.get('sellV1')}\n"
        prompt += f"  Mức 2: Giá {item.get('sellP2')} - KL {item.get('sellV2')}\n"
        prompt += f"  Mức 3: Giá {item.get('sellP3')} - KL {item.get('sellV3')}\n\n"
        
        vbp_data = results.get('vbp')
        prompt += f"[KHỐI LƯỢNG THEO MỨC GIÁ (VBP)]\n"
        if vbp_data and isinstance(vbp_data, list):
            for v in vbp_data:
                prompt += f"Giá {v.get('price')}: {v.get('volume')} (KL)\n"
        else:
            prompt += "Không có dữ liệu\n"
            
        weekly_data = results.get('weekly')
        prompt += "\n[XU HƯỚNG DÀI HẠN - NẾN TUẦN 2 NĂM QUA (Giá đóng cửa)]\n"
        if weekly_data and 't' in weekly_data and weekly_data['t']:
            w_str = []
            for i in range(len(weekly_data['t'])):
                dt = datetime.fromtimestamp(weekly_data['t'][i]).strftime('%m/%y')
                c = weekly_data['c'][i]
                w_str.append(f"{dt}:{c}")
            prompt += " | ".join(w_str) + "\n"
        else:
            prompt += "Không có dữ liệu nến tuần\n"

        daily_data = results.get('daily')
        prompt += "\n[XU HƯỚNG NGẮN HẠN - NẾN NGÀY 6 THÁNG QUA (Giá đóng cửa)]\n"
        if daily_data and 't' in daily_data and daily_data['t']:
            d_str = []
            for i in range(len(daily_data['t'])):
                dt = datetime.fromtimestamp(daily_data['t'][i]).strftime('%d/%m')
                c = daily_data['c'][i]
                d_str.append(f"{dt}:{c}")
            prompt += " | ".join(d_str) + "\n"
        else:
            prompt += "Không có dữ liệu nến ngày\n"
            
        prompt += "\nTRẢ LỜI NGHIÊM NGẶT THEO ĐỊNH DẠNG JSON. KHÔNG DÙNG BACKTICKS:\n"
        prompt += '{"trend": "Mô tả xu hướng chính (dài hạn). Nhận diện các mẫu hình lớn...", "support_resistance": "Liệt kê các vùng Hỗ trợ/Kháng cự mạnh nhất trên khung Tuần/Tháng và ý nghĩa...", "supply_demand": "Phân tích dòng tiền lớn, áp lực cung/cầu dài hạn dựa trên Volume Profile (VBP) và nến...", "conclusion": "Kết luận tổng quan cho nhà đầu tư...", "strategy": "Chiến lược giao dịch trung và dài hạn...", "chart_lines": [{"price": 25.5, "type": "resistance", "label": "Kháng cự dài hạn"}, {"price": 23.0, "type": "support", "label": "Hỗ trợ nền"}]}'
        
        return prompt
    except Exception as e:
        print("Loi tao prompt:", e)
        prompt = f"Bạn là chuyên gia phân tích kỹ thuật DÀI HẠN. Phân tích mã {symbol} theo lý thuyết Cung Cầu và Kháng cự/Hỗ trợ dài hạn.\n"
        prompt += "\nTRẢ LỜI NGHIÊM NGẶT THEO ĐỊNH DẠNG JSON. KHÔNG DÙNG BACKTICKS:\n"
        prompt += '{"trend": "...", "support_resistance": "...", "supply_demand": "...", "conclusion": "...", "strategy": "...", "chart_lines": [{"price": 25.5, "type": "resistance", "label": "Kháng cự mạnh"}, {"price": 23.0, "type": "support", "label": "Hỗ trợ cứng"}]}'
        return prompt

def get_status():
    return worker_state.copy()
        
def request_status():
    future = concurrent.futures.Future()
    manual_queue.put({"type": "status", "future": future})
    return future

def request_reset_scan():
    future = concurrent.futures.Future()
    manual_queue.put({"type": "reset_scan", "future": future})
    return future
        
def request_screenshot():
    f = concurrent.futures.Future()
    manual_queue.put({"type": "screenshot", "future": f})
    return f
