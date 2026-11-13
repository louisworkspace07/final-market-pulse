import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import time
import datetime
import random
import threading
import json
import os
import asyncio
import gemini_worker
from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
from concurrent.futures import Future
from playwright.async_api import async_playwright

app = Flask(__name__, static_folder='static')
CORS(app)

# AI Cache
ai_cache = {}
CACHE_FILE = 'temp_data/ai_cache.json'
if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            ai_cache = json.load(f)
    except:
        pass

def save_cache():
    try:
        if not os.path.exists('temp_data'):
            os.makedirs('temp_data')
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(ai_cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Error saving cache:", e)

# Bật luồng xử lý Gemini trung tâm (ưu tiên + tự động)
gemini_worker.start_worker_thread()

market_data = []
DATA_FILE = os.path.join(os.path.dirname(__file__), "temp_data", "data.json")
if os.path.exists(DATA_FILE):
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            market_data = json.load(f)
            print(f"[board] Nap san {len(market_data)} ma tu temp_data/data.json")
    except Exception as e:
        print("[board] Khong the doc temp_data/data.json:", e)


async def vndirect_crawler():
    global market_data
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page_hose = await browser.new_page()
        page_hnx = await browser.new_page()
        page_upcom = await browser.new_page()
        try:
            await page_hose.goto('https://banggia.vndirect.com.vn/chung-khoan/hose', timeout=60000)
            await page_hnx.goto('https://banggia.vndirect.com.vn/chung-khoan/hnx', timeout=60000)
            await page_upcom.goto('https://banggia.vndirect.com.vn/chung-khoan/upcom', timeout=60000)
            
            await page_hose.wait_for_selector('table tbody tr', timeout=30000)
            await page_hnx.wait_for_selector('table tbody tr', timeout=30000)
            await page_upcom.wait_for_selector('table tbody tr', timeout=30000)
            
            while True:
                try:
                    js_eval = r'''
                    (exchangeName) => {
                        let rows = Array.from(document.querySelectorAll('table tbody tr')).filter(tr => tr.id && tr.id.length >= 2);
                        return rows.map(tr => {
                            let cells = Array.from(tr.querySelectorAll('td'));
                            if (cells.length < 25) return null;
                            
                            let getText = (idx) => {
                                if (idx >= cells.length) return '';
                                return cells[idx].innerText.trim();
                            };
                            let getVal = (idx) => parseFloat(getText(idx).replace(/,/g, '')) || 0;
                            
                            let symbol = getText(0).replace(/\*/g, '');
                            let ref = getVal(1);
                            let ceil = getVal(2);
                            let floor = getVal(3);
                            
                            // Parse Foreign Buy / Sell (DTNN) from column 25 which contains both separated by newline or space
                            let dtnnText = getText(25);
                            let dtnnParts = dtnnText.trim().split(/[\s]+/);
                            let fBuyText = dtnnParts.length > 0 ? dtnnParts[0].trim() : '';
                            let fSellText = dtnnParts.length > 1 ? dtnnParts[1].trim() : '';
                            
                            let raw = [];
                            for(let i=0; i<25; i++) {
                                let txt = getText(i);
                                if (i === 4 || i === 13) {
                                    txt = txt.split(/[ \\n]+/)[0];
                                }
                                raw.push(txt);
                            }
                            // Push the separated Foreign Buy and Sell into raw[25] and raw[26]
                            raw.push(fBuyText);
                            raw.push(fSellText);
                            
                            return {
                                symbol: symbol,
                                exchange: exchangeName,
                                ref: ref,
                                ceil: ceil,
                                floor: floor,
                                matchPrice: getVal(11),
                                matchVol: getVal(12),
                                totalVol: getVal(4),
                                buyP3: getVal(5), buyV3: getVal(6),
                                buyP2: getVal(7), buyV2: getVal(8),
                                buyP1: getVal(9), buyV1: getVal(10),
                                sellP1: getVal(14), sellV1: getVal(15),
                                sellP2: getVal(16), sellV2: getVal(17),
                                sellP3: getVal(18), sellV3: getVal(19),
                                high: getVal(20), avg: getVal(21), low: getVal(22),
                                remainBuy: getText(23), remainSell: getText(24),
                                foreignBuy: parseFloat(fBuyText.replace(/,/g, '')) || 0,
                                foreignSell: parseFloat(fSellText.replace(/,/g, '')) || 0,
                                raw: raw
                            };
                        }).filter(item => item !== null);
                    }
                    '''
                    res_hose, res_hnx, res_upcom = await asyncio.gather(
                        page_hose.evaluate(js_eval, 'hose'),
                        page_hnx.evaluate(js_eval, 'hnx'),
                        page_upcom.evaluate(js_eval, 'upcom')
                    )
                    
                    if res_hose is not None and res_hnx is not None and res_upcom is not None:
                        market_data = res_hose + res_hnx + res_upcom
                    
                    await asyncio.sleep(1) # Nhảy real-time mỗi 1s (đọc DOM đã mở sẵn, đủ nhanh)
                except Exception as loop_err:
                    print("Loi trong vong lap crawler:", loop_err)
                    await asyncio.sleep(5)
        except Exception as e:
            print("Crawler fatal error:", e)
            await asyncio.sleep(5)
            with open("crawler_error.log", "w", encoding="utf-8") as f:
                f.write(str(e))
        finally:
            await browser.close()

def start_crawler_thread():
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    global playwright_loop
    playwright_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(playwright_loop)
    playwright_loop.run_until_complete(vndirect_crawler())


def vnstock_board_loop():
    """Bảng giá qua vnstock price_board — KHÔNG cần Chrome/Playwright.

    HOSE+HNX làm mới mỗi ~1s (nhóm chính); UPCOM mỗi 3 vòng (đỡ tải). Lỗi tạm
    thời -> giữ dữ liệu cũ, không xóa bảng. Đây là nguồn mặc định (nhẹ hơn nhiều
    so với cào DOM). Đặt BOARD_SOURCE=playwright để quay lại cách cũ."""
    global market_data
    import board_vnstock

    ex_map, allsyms = {}, []
    while not allsyms:
        try:
            ex_map, allsyms = board_vnstock.load_universe()
        except Exception as e:
            print("[board] load_universe loi, thu lai:", str(e)[:80]); time.sleep(3)
    hose_hnx = [s for s in allsyms if ex_map.get(s) in ("hose", "hnx")]
    upcom = [s for s in allsyms if ex_map.get(s) == "upcom"]
    print(f"[board] vnstock: HOSE+HNX {len(hose_hnx)} ma, UPCOM {len(upcom)} ma")

    hh_rows, up_rows, cycle = [], [], 0
    while True:
        t0 = time.time()
        now_dt = datetime.datetime.now()
        is_trading_hour = (now_dt.weekday() < 5 and 9 <= now_dt.hour < 15)
        try:
            hh_rows = board_vnstock.fetch_board(hose_hnx, ex_map)
            if (cycle % 3 == 0 or not is_trading_hour) and upcom:
                try:
                    up_rows = board_vnstock.fetch_board(upcom, ex_map)
                except Exception as e:
                    print("[board] UPCOM loi:", str(e)[:60])
            if hh_rows or up_rows:
                market_data = hh_rows + up_rows      # gán atomic 1 lần
                if cycle % 10 == 0:
                    try:
                        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
                        tmp = DATA_FILE + ".tmp"
                        with open(tmp, "w", encoding="utf-8") as f:
                            json.dump(market_data, f, ensure_ascii=False)
                        os.replace(tmp, DATA_FILE)
                    except Exception:
                        pass
        except Exception as e:
            print("[board] fetch loi, giu du lieu cu:", str(e)[:80])
            time.sleep(2)
        cycle += 1
        sleep_sec = max(0.2, 1.0 - (time.time() - t0)) if is_trading_hour else 30.0
        time.sleep(sleep_sec)


# --- Chọn nguồn bảng giá: vnstock (mặc định, nhẹ) | playwright (fallback) ---
_BOARD_SOURCE = os.environ.get("BOARD_SOURCE", "vnstock").strip().lower()
if _BOARD_SOURCE == "playwright":
    print("[board] Nguon: Playwright (cao DOM VNDirect)")
    threading.Thread(target=start_crawler_thread, daemon=True).start()
else:
    print("[board] Nguon: vnstock price_board (khong can Chrome)")
    threading.Thread(target=vnstock_board_loop, daemon=True).start()

# API Endpoints
@app.route('/api/stocks')
def get_stocks():
    if not market_data:
        return jsonify([])
    return jsonify(market_data)

import subprocess
import urllib.request

DATA_CACHE = {}

@app.route('/api/history/<symbol>')
def get_history(symbol):
    try:
        cache_key = f"history_{symbol}"
        if cache_key in DATA_CACHE:
            data, ts = DATA_CACHE[cache_key]
            if time.time() - ts < 60:
                return jsonify(data)
                
        # Get 3 years of daily data
        today_start = int(time.time()) - 86400 * 365 * 3
        today_end = int(time.time())
        url = f'https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?symbol={symbol}&resolution=1D&from={today_start}&to={today_end}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
        data = json.loads(res)
        
        history_data = []
        if 't' in data and data['t']:
            for i in range(len(data['t'])):
                history_data.append({
                    'time': data['t'][i],
                    'open': data['o'][i],
                    'high': data['h'][i],
                    'low': data['l'][i],
                    'close': data['c'][i],
                    'value': data['v'][i]
                })
        DATA_CACHE[cache_key] = (history_data, time.time())
        return jsonify(history_data)
    except Exception as e:
        print("Loi get_history:", e)
        return jsonify([])

@app.route('/api/vbp/<symbol>')
def get_vbp(symbol):
    try:
        cache_key = f"vbp_{symbol}"
        if cache_key in DATA_CACHE:
            data, ts = DATA_CACHE[cache_key]
            if time.time() - ts < 60:
                return jsonify(data)
                
        today_start = int(time.time()) - 86400 * 5
        today_end = int(time.time())
        url = f'https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?symbol={symbol}&resolution=1&from={today_start}&to={today_end}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req).read().decode('utf-8')
        data = json.loads(res)
        
        vbp = {}
        if 'c' in data and 'v' in data:
            for i in range(len(data['c'])):
                price = data['c'][i]
                vol = data['v'][i]
                if price not in vbp:
                    vbp[price] = 0
                vbp[price] += vol
        
        # Sort by price
        sorted_vbp = [{'price': p, 'volume': v} for p, v in sorted(vbp.items())]
        if len(sorted_vbp) == 0:
            # Fallback: đọc giá và khối lượng thật từ market.db
            try:
                import sqlite3
                db_p = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data-crawler", "database", "market.db"))
                if os.path.exists(db_p):
                    con = sqlite3.connect(f"file:{db_p}?mode=ro", uri=True)
                    rows = con.execute("SELECT close, volume FROM price WHERE symbol=? ORDER BY time DESC LIMIT 30", (symbol.upper(),)).fetchall()
                    con.close()
                    for p, v in rows:
                        if p and v:
                            vbp[float(p)] = vbp.get(float(p), 0) + int(v)
                    sorted_vbp = [{'price': p, 'volume': v} for p, v in sorted(vbp.items())]
            except Exception:
                pass
        
        DATA_CACHE[cache_key] = (sorted_vbp, time.time())
        return jsonify(sorted_vbp)
    except Exception as e:
        print("VBP error:", e)
        return jsonify([])

@app.route('/api/analyze', methods=['POST'])
def analyze_stock():
    try:
        req_data = request.json
        symbol = req_data.get('symbol', 'UNKNOWN')
        force = req_data.get('force', False)
        
        # Reload cache to get latest auto-scan results
        local_cache = {}
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                local_cache = json.load(f)
        except: pass
        
        # Check cache if not forcing
        if not force:
            if symbol in local_cache:
                return jsonify({"status": "success", "data": local_cache[symbol]['data'], "timestamp": local_cache[symbol]['timestamp']})
            else:
                return jsonify({"status": "error", "message": "Not in cache"})
        # Xây dựng prompt chuyên sâu
        item = next((x for x in market_data if x.get('symbol') == symbol), None)
        prompt = gemini_worker.generate_prompt_for_symbol(symbol, item)
        
        # Gửi vào hàng đợi ưu tiên của gemini_worker và chờ kết quả
        future = gemini_worker.request_manual_analysis(symbol, prompt, None)
        res = future.result(timeout=60) # Chờ tối đa 60s
        
        if res.get("status") == "error":
            return jsonify({"status": "error", "message": res.get("error")})
            
        ai_result = res.get("result", "").strip()
        from datetime import datetime
        
        # Save cache properly without overwriting auto-scan
        local_cache = {}
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                local_cache = json.load(f)
        except: pass
        
        local_cache[symbol] = {
            "data": ai_result,
            "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        }
        
        try:
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(local_cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("Error saving cache:", e)
            
        return jsonify({"status": "success", "data": ai_result, "timestamp": local_cache[symbol]['timestamp']})
            
    except Exception as e:
        print("Loi API Analyze:", e)
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/gemini/status', methods=['GET'])
def gemini_status():
    status = gemini_worker.get_status()
    is_logged_in = status.get('is_logged_in', False)
    return jsonify({"status": "success", "is_logged_in": is_logged_in, "data": status})

@app.route('/api/gemini/reset_scan', methods=['POST'])
def gemini_reset_scan():
    future = gemini_worker.request_reset_scan()
    try:
        res = future.result(timeout=60)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/gemini/toggle_auto_scan', methods=['POST'])
def gemini_toggle_auto_scan():
    future = gemini_worker.request_toggle_auto_scan()
    try:
        res = future.result(timeout=60)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/gemini/set_targets', methods=['POST'])
def gemini_set_targets():
    data = request.json
    targets = data.get('targets', [])
    future = gemini_worker.request_set_auto_scan_targets(targets)
    try:
        res = future.result(timeout=60)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})



@app.route('/api/gemini/scan_progress', methods=['GET'])
def gemini_scan_progress():
    try:
        status = gemini_worker.get_status()
        progress_data = {
            "current_symbol": status.get("scan_current_symbol"),
            "scanned": status.get("scan_scanned"),
            "total": status.get("scan_total"),
            "status": status.get("scan_status"),
            "account_info": status.get("account_info")
        }
        return jsonify({"status": "success", "data": progress_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/gemini/screenshot', methods=['GET'])
def gemini_screenshot():
    try:
        future = gemini_worker.request_screenshot()
        res = future.result(timeout=10)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/login_gemini', methods=['POST'])
def login_gemini():
    try:
        future = gemini_worker.request_login()
        res = future.result(timeout=180) # Chờ tối đa 3 phút cho quá trình đăng nhập thủ công
        if res.get('status') == 'error':
            return jsonify({"status": "error", "message": res.get("error")})
        return jsonify({"status": "success", "data": res.get("result", "ok")})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/')
def serve_index():
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

if __name__ == '__main__':
    print("Khoi chay Backend Server tai http://127.0.0.1:5555")
    app.run(port=5555, debug=False)
