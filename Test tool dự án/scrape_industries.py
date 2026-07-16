import asyncio
from playwright.async_api import async_playwright
import json

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print('Navigating...')
        await page.goto('https://banggia.vndirect.com.vn/chung-khoan/hose', timeout=60000)
        await page.wait_for_timeout(3000)
        
        print('Clicking CP Ngành...')
        # Tìm nút có chữ 'CP ngành'
        await page.evaluate('''() => {
            let els = document.querySelectorAll('li, div, a');
            for(let e of els) {
                if(e.innerText && e.innerText.includes('CP ngành')) {
                    e.click();
                    break;
                }
            }
        }''')
        await page.wait_for_timeout(2000)
        
        js_code = """
        () => {
            let items = Array.from(document.querySelectorAll('a[href^="/chung-khoan/nganh/"]'));
            return items.map(a => {
                return { name: a.innerText.trim(), href: a.getAttribute('href') };
            });
        }
        """
        industries = await page.evaluate(js_code)
        
        result = {}
        for ind in industries:
            if not ind['name']: continue
            print('Scraping', ind['name'], '...')
            await page.goto('https://banggia.vndirect.com.vn' + ind['href'], timeout=60000)
            await page.wait_for_timeout(2000)
            js_code2 = """
            () => {
                return Array.from(document.querySelectorAll('table tbody tr')).map(tr => tr.id).filter(id => id && id.length >= 3);
            }
            """
            symbols = await page.evaluate(js_code2)
            symbols = [s.replace('stock-', '') for s in symbols]
            result[ind['name']] = symbols
            print('   Found', len(symbols), 'symbols')
            
        with open('static/industries.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            
        await browser.close()
        print('Done!')

asyncio.run(main())
