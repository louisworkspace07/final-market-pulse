import sys
import json
import asyncio
from playwright.async_api import async_playwright

def parse_number(s):
    try:
        return float(s.replace(',', ''))
    except:
        return 0

async def scrape(symbol):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        # CafeF url
        url = f'https://s.cafef.vn/Lich-su-giao-dich-{symbol}-1.chn'
        try:
            await page.goto(url, timeout=30000)
            # Wait for table to populate
            await page.wait_for_selector('#owner-contents-table tr', timeout=15000)
            await page.wait_for_timeout(1000) # Give it an extra second to render
            
            data = await page.evaluate('''() => {
                let rows = document.querySelectorAll('#owner-contents-table tr');
                let results = [];
                // Skip header rows
                for(let i = 2; i < rows.length; i++) {
                    let cols = rows[i].querySelectorAll('td');
                    if (cols.length >= 12) {
                        results.push({
                            date: cols[1].innerText.trim(),
                            close: cols[2].innerText.trim(),
                            vol: cols[5].innerText.trim(),
                            open: cols[9].innerText.trim(),
                            high: cols[10].innerText.trim(),
                            low: cols[11].innerText.trim()
                        });
                    }
                }
                return results;
            }''')
            
            parsed = []
            for item in data:
                try:
                    # Convert DD/MM/YYYY to YYYY-MM-DD
                    d_parts = item['date'].split('/')
                    iso_date = f"{d_parts[2]}-{d_parts[1]}-{d_parts[0]}"
                    
                    parsed.append({
                        'time': iso_date,
                        'open': parse_number(item['open']),
                        'high': parse_number(item['high']),
                        'low': parse_number(item['low']),
                        'close': parse_number(item['close']),
                        'value': parse_number(item['vol']) # lightweight charts volume
                    })
                except Exception as e:
                    pass
                    
            # Lightweight charts expects data sorted ascending by time
            parsed.reverse()
            print(json.dumps(parsed))
            
        except Exception as e:
            print(json.dumps([]))
        finally:
            await browser.close()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        symbol = sys.argv[1].upper()
        asyncio.run(scrape(symbol))
    else:
        print(json.dumps([]))
