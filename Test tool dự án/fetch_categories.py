import asyncio
import json
import time
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://banggia.vndirect.com.vn/chung-khoan/vn30")
        
        # Wait for page to load
        await page.wait_for_selector(".menu-link", timeout=15000)
        await asyncio.sleep(2)
        
        categories = {}
        
        # Lấy danh sách các menu dropdown
        js_get_menus = """
        () => {
            let items = [];
            // Lấy các menu: HOSE, HNX, UPCOM, CP ngành, Phái sinh
            document.querySelectorAll('.header-menu .has-sub').forEach(li => {
                let mainLink = li.querySelector('a.menu-link');
                if (!mainLink) return;
                let mainText = mainLink.innerText.trim();
                
                // Bỏ qua Phái sinh
                if (mainText === 'Phái sinh') return;
                
                // Lấy các menu con
                li.querySelectorAll('.sub-menu li a').forEach(sub => {
                    let text = sub.innerText.trim();
                    let href = sub.getAttribute('href');
                    if (text && href) {
                        items.push({ main: mainText, text: text, href: href });
                    }
                });
            });
            return items;
        }
        """
        
        menus = await page.evaluate(js_get_menus)
        print(f"Found {len(menus)} menu items.")
        
        for item in menus:
            print(f"Fetching {item['text']}...")
            try:
                await page.goto("https://banggia.vndirect.com.vn" + item['href'], timeout=15000)
                await page.wait_for_selector("table tbody tr", timeout=10000)
                await asyncio.sleep(1) # wait for table to populate
                
                # Cuộn xuống để tải hết nếu có virtual scroll (VNDirect ít khi dùng virtual scroll cho các tab nhỏ, nhưng tab AllShare thì có thể)
                # Đa số tab trả về all HTML.
                js_get_symbols = """
                () => {
                    return Array.from(document.querySelectorAll('table tbody tr')).filter(tr => tr.id && tr.id.length >= 2).map(tr => tr.id);
                }
                """
                symbols = await page.evaluate(js_get_symbols)
                print(f" -> Found {len(symbols)} symbols")
                categories[item['text']] = symbols
            except Exception as e:
                print(f" -> Error: {e}")
                
        with open('static/categories.json', 'w', encoding='utf-8') as f:
            json.dump(categories, f, ensure_ascii=False)
            
        print("Done!")
        await browser.close()

if __name__ == '__main__':
    asyncio.run(run())
