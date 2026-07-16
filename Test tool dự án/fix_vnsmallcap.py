import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        page = await b.new_page(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
        print('Navigating to HOSE...')
        await page.goto('https://banggia.vndirect.com.vn/chung-khoan/hose', timeout=30000)
        await asyncio.sleep(4)
        
        js_get_syms = '''() => {
            return Array.from(document.querySelectorAll('table tbody tr')).map(tr => tr.id.replace('stock-', ''));
        }'''
        
        hose_syms = await page.evaluate(js_get_syms)
        print(f"HOSE symbols: {len(hose_syms)}")
        
        print('Opening dropdown...')
        await page.evaluate('''() => {
            const tab = Array.from(document.querySelectorAll('.tab-item')).find(t => t.innerText.includes('HOSE'));
            if(tab) tab.click();
        }''')
        await asyncio.sleep(1)
        
        print('Clicking VNSmallCap...')
        await page.evaluate('''() => {
            const a = Array.from(document.querySelectorAll('.tab-item.dropdown .dropdown-content a')).find(el => el.innerText.includes('VNSmallCap'));
            if(a) a.click();
        }''')
        
        print('Waiting for table to change...')
        changed = False
        for i in range(15):
            await asyncio.sleep(1)
            syms = await page.evaluate(js_get_syms)
            if syms != hose_syms:
                changed = True
                print(f"Changed! Found {len(syms)} symbols.")
                print(f"First 10: {syms[:10]}")
                break
                
        if not changed:
            print("Table never changed!")
            
        await b.close()
asyncio.run(run())
