import asyncio
import json
from playwright.async_api import async_playwright

async def run():
    categories = {
        'vn100': '/chung-khoan/vn100',
        'vnallshare': '/chung-khoan/vnallshare',
        'vnsmallcap': '/chung-khoan/vnsmallcap',
        'vnxallshare': '/chung-khoan/vnxallshare',
        'etf': '/chung-khoan/etf',
        'hose_lo_le': '/chung-khoan/lo-le-hose',
        'hose_thoa_thuan': '/chung-khoan/thoa-thuan-hose',
        'hnx30': '/chung-khoan/hnx30',
        'bond': '/chung-khoan/trai-phieu',
        'hnx_thoa_thuan': '/chung-khoan/thoa-thuan-hnx',
        'upcom_thoa_thuan': '/chung-khoan/thoa-thuan-upcom'
    }
    
    result = {}
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        for name, path in categories.items():
            print(f"Fetching {name}...")
            try:
                await page.goto("https://banggia.vndirect.com.vn" + path, timeout=30000)
                await page.wait_for_selector("table tbody tr", timeout=15000)
                await asyncio.sleep(2) # Give it time to load all rows
                
                js_get_symbols = """
                () => {
                    return Array.from(document.querySelectorAll('table tbody tr'))
                        .filter(tr => tr.id && tr.id.length >= 2)
                        .map(tr => tr.id.replace('stock-', '')); // Extract exact symbol if prefixed
                }
                """
                symbols = await page.evaluate(js_get_symbols)
                
                # Cleanup symbols (some ids are just the symbol, some might have prefixes)
                clean_symbols = [s for s in symbols if s]
                print(f" -> Found {len(clean_symbols)} symbols")
                result[name] = clean_symbols
            except Exception as e:
                print(f" -> Error: {e}")
                
        await browser.close()
        
    with open('static/categories.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False)
    print("Saved to static/categories.json!")

if __name__ == '__main__':
    asyncio.run(run())
