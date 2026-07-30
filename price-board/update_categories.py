import asyncio
import json
import os
from playwright.async_api import async_playwright

async def get_symbols(page, category_name):
    print(f"Clicking {category_name}...")
    await page.evaluate(f'''() => {{
        const a = Array.from(document.querySelectorAll('.tab-item.dropdown .dropdown-content a')).find(el => el.innerText.includes('{category_name}'));
        if(a) a.click();
    }}''')
    await asyncio.sleep(6) # wait for table to update
    js = '''() => {
        return Array.from(document.querySelectorAll('table tbody tr'))
            .filter(tr => tr.id && tr.id.length >= 2)
            .map(tr => tr.id.replace('stock-', ''));
    }'''
    symbols = await page.evaluate(js)
    # clean symbols
    symbols = [s for s in symbols if len(s) > 0 and '-' not in s and not s.startswith(' ')]
    print(f" -> Found {len(symbols)} symbols")
    return symbols

async def run():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        page = await b.new_page()
        
        filepath = 'static/categories.json'
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                categories = json.load(f)
        else:
            categories = {}

        # HOSE sub-indices
        await page.goto('https://banggia.vndirect.com.vn/chung-khoan/hose', timeout=30000)
        await asyncio.sleep(4)
        
        # open HOSE dropdown
        await page.evaluate('''() => {
            const tab = Array.from(document.querySelectorAll('.tab-item')).find(t => t.innerText.includes('HOSE'));
            if(tab) tab.click();
        }''')
        await asyncio.sleep(1)
        
        hose_cats = {
            'vnallshare': 'VNAllShare',
            'vnsmallcap': 'VNSmallCap',
            'vnxallshare': 'VNXAllShare',
            'etf': 'ETF',
            'hose_lo_le': 'Giao dịch lô lẻ',
            'hose_thoa_thuan': 'thỏa thuận'
        }
        for key, text in hose_cats.items():
            syms = await get_symbols(page, text)
            if syms:
                categories[key] = syms
                
        # HNX sub-indices
        await page.goto('https://banggia.vndirect.com.vn/chung-khoan/hnx', timeout=30000)
        await asyncio.sleep(4)
        # open HNX dropdown
        await page.evaluate('''() => {
            const tab = Array.from(document.querySelectorAll('.tab-item')).find(t => t.innerText.includes('HNX'));
            if(tab) tab.click();
        }''')
        await asyncio.sleep(1)
        
        hnx_cats = {
            'bond': 'Trái phiếu',
            'hnx_thoa_thuan': 'thỏa thuận'
        }
        for key, text in hnx_cats.items():
            syms = await get_symbols(page, text)
            if syms:
                categories[key] = syms

        # UPCOM sub-indices
        await page.goto('https://banggia.vndirect.com.vn/chung-khoan/upcom', timeout=30000)
        await asyncio.sleep(4)
        # open UPCOM dropdown
        await page.evaluate('''() => {
            const tab = Array.from(document.querySelectorAll('.tab-item')).find(t => t.innerText.includes('UPCOM'));
            if(tab) tab.click();
        }''')
        await asyncio.sleep(1)
        
        upcom_cats = {
            'upcom_thoa_thuan': 'thỏa thuận'
        }
        for key, text in upcom_cats.items():
            syms = await get_symbols(page, text)
            if syms:
                categories[key] = syms

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(categories, f)
        print("Updated static/categories.json!")
        
        await b.close()

asyncio.run(run())
