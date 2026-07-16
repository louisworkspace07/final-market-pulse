import sys
import json
import asyncio
import os
import random
import time
from datetime import datetime
from playwright.async_api import async_playwright

import local_api

# Kênh AI: local_api (MẶC ĐỊNH, gọi HTTP tới server local) | gemini (Chrome CDP).
AI_BACKEND = (os.environ.get("AI_BACKEND") or "local_api").strip().lower()
USE_LOCAL_API = AI_BACKEND != "gemini"

# Chrome dùng chung (mở sẵn bằng Crawl Data/scripts/launch_chrome.py, đã đăng nhập Gemini).
CDP_URL = os.environ.get("CDP_URL", "http://localhost:9222")
GEMINI_URL = "https://gemini.google.com/app"
MAX_TABS = int(os.environ.get("CDP_MAX_TABS", "3"))

USER_DATA_DIR = os.path.join(os.getcwd(), "gemini_profile")  # giữ tương thích, không còn dùng để launch
CACHE_FILE = os.path.join("temp_data", "ai_cache.json")
DATA_FILE = os.path.join("temp_data", "data.json")

STATUS_FILE = os.path.join("temp_data", "scan_status.json")

# Lock ghi file cache/status (nhiều tab chạy song song cùng ghi).
_io_lock = asyncio.Lock()


def _build_prompt(item) -> str:
    symbol = item.get("symbol")
    prompt = f"Phân tích nhanh {symbol}:\n"
    prompt += f"- Giá HT: {item.get('matchPrice')}\n"
    prompt += f"- Dư Mua: {item.get('buyP1')} (KL {item.get('buyV1')})\n"
    prompt += f"- Dư Bán: {item.get('sellP1')} (KL {item.get('sellV1')})\n"
    prompt += "TRẢ LỜI NGHIÊM NGẶT THEO ĐỊNH DẠNG JSON. KHÔNG XÀI BACKTICKS:\n"
    prompt += '{"trend": "...", "support_resistance": "...", "supply_demand": "...", "conclusion": "...", "strategy": "..."}'
    return prompt


async def _query_on_page(page, prompt: str) -> str:
    await page.goto(GEMINI_URL, wait_until="domcontentloaded")
    await asyncio.sleep(2)
    input_selector = "rich-textarea"
    await page.wait_for_selector(input_selector, timeout=15000)
    await page.click(input_selector)
    await asyncio.sleep(0.4)
    await page.keyboard.press("Control+A")
    await page.keyboard.press("Backspace")
    await page.keyboard.insert_text(prompt)
    await asyncio.sleep(0.4)
    await page.keyboard.press("Enter")

    await asyncio.sleep(3)
    await page.wait_for_selector("message-content", timeout=45000)
    elements = await page.query_selector_all("message-content")
    if not elements:
        raise RuntimeError("Không lấy được kết quả từ Gemini")
    last_msg = elements[-1]
    prev, stable, cur = "", 0, ""
    for _ in range(40):
        await asyncio.sleep(1)
        cur = await last_msg.inner_text()
        if cur == prev and len(cur) > 0:
            stable += 1
            if stable >= 2:
                break
        else:
            stable, prev = 0, cur
    clean = cur.strip()
    if clean.startswith("```json"):
        clean = clean[7:]
    elif clean.startswith("```"):
        clean = clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]
    return clean.strip()


async def _scan_one(context, sem, item):
    """1 mã = 1 lượt hỏi AI. Semaphore giới hạn số lượt song song.

    Kênh local_api: gọi HTTP (client đồng bộ → chạy trong thread phụ).
    Kênh gemini: mở 1 tab CDP mới → hỏi → đóng tab."""
    symbol = item.get("symbol")
    async with sem:
        if USE_LOCAL_API:
            try:
                clean = await asyncio.to_thread(local_api.ask, _build_prompt(item))
                json.loads(clean)  # validate
            except Exception as ex:
                print(f"Lỗi khi quét {symbol}:", ex)
                return False
        else:
            await asyncio.sleep(0.5 + random.random() * 1.5)  # jitter tránh bị chặn
            page = await context.new_page()
            try:
                clean = await _query_on_page(page, _build_prompt(item))
                json.loads(clean)  # validate
            except Exception as ex:
                print(f"Lỗi khi quét {symbol}:", ex)
                return False
            finally:
                try:
                    await page.close()
                except Exception:
                    pass

    # Lưu cache (an toàn dưới lock).
    async with _io_lock:
        ai_cache = {}
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    ai_cache = json.load(f)
            except Exception:
                pass
        ai_cache[symbol] = {
            "data": clean.strip(),
            "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        }
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(ai_cache, f, ensure_ascii=False, indent=2)
    print(f"Đã lưu {symbol}")
    return True


def _cache_valid(symbol) -> bool:
    if not os.path.exists(CACHE_FILE):
        return False
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            ai_cache = json.load(f)
    except Exception:
        return False
    if symbol not in ai_cache:
        return False
    try:
        ct = datetime.strptime(ai_cache[symbol].get("timestamp", ""), "%d/%m/%Y %H:%M:%S")
        return (datetime.now() - ct).total_seconds() < 3600
    except Exception:
        return False


async def run_auto_analyze():
    if not os.path.exists(DATA_FILE):
        print("Không có data.json, kết thúc.")
        return

    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            market_data = json.load(f)
    except Exception as e:
        print("Lỗi đọc data.json:", e)
        return

    # Chỉ quét 30 mã đầu tiên (VN30)
    target_symbols = market_data[:30]
    if len(target_symbols) == 0:
        return

    # Bỏ qua mã đã phân tích trong 1 giờ qua.
    pending = [it for it in target_symbols if not _cache_valid(it.get("symbol"))]
    print(f"Bắt đầu tự động quét {len(pending)}/{len(target_symbols)} mã "
          f"(song song tối đa {MAX_TABS} luồng)...")
    if not pending:
        print("Tất cả đã có phân tích gần đây.")
        return

    # Kênh local_api: không cần Chrome/đăng nhập — quét thẳng qua HTTP.
    if USE_LOCAL_API:
        st = local_api.status()
        if not st["has_key"]:
            print("Thiếu LOCAL_API_KEY (Crawl Data/.env) — không quét được.")
            return
        if not st["up"]:
            print(f"Server AI local không phản hồi ở {st['url']} — không quét được.")
            return
        sem = asyncio.Semaphore(MAX_TABS)
        results = await asyncio.gather(
            *(_scan_one(None, sem, it) for it in pending), return_exceptions=True)
        print(f"Đã quét xong: {sum(1 for r in results if r is True)}/{len(pending)} mã thành công.")
        return

    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(CDP_URL, timeout=3000)
        except Exception as e:
            print(f"Không kết nối được Chrome ở {CDP_URL} (chạy launch_chrome trước): {e}")
            return
        context = browser.contexts[0] if browser.contexts else await browser.new_context()

        # Kiểm tra đăng nhập bằng 1 tab tạm.
        check = await context.new_page()
        try:
            await check.goto(GEMINI_URL, wait_until="domcontentloaded", timeout=60000)
            await check.wait_for_selector("rich-textarea", timeout=15000)
            sign_in = await check.query_selector_all("a[href*='accounts.google.com/ServiceLogin']")
            if sign_in:
                print("Chưa đăng nhập, không thể quét.")
                return
        except Exception:
            print("Không mở được Gemini / chưa đăng nhập.")
            return
        finally:
            try:
                await check.close()
            except Exception:
                pass

        sem = asyncio.Semaphore(MAX_TABS)
        results = await asyncio.gather(
            *(_scan_one(context, sem, it) for it in pending),
            return_exceptions=True,
        )
        ok = sum(1 for r in results if r is True)
        print(f"Đã quét xong: {ok}/{len(pending)} mã thành công.")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(run_auto_analyze())
