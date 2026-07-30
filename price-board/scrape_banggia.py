import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

async def scrape_vndirect():
    print("Khoi dong Playwright...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = await context.new_page()
        
        url = 'https://banggia.vndirect.com.vn/'
        print(f"Dang truy cap {url} ...")
        await page.goto(url, wait_until='domcontentloaded')
        
        print("Cho 3 giay de trang load...")
        await page.wait_for_timeout(3000)
        
        print("Xoa cac popup bang JavaScript...")
        await page.evaluate("""
            () => {
                const elements = document.querySelectorAll('.ReactModalPortal, [class*="modal"], [class*="overlay"], [class*="popup"], [class*="dialog"]');
                elements.forEach(el => {
                    try { el.remove(); } catch(e) {}
                });
            }
        """)
        await page.wait_for_timeout(1000)
        
        # Click ngau nhien vao giua man hinh de dismiss bat ky dropdown nao
        await page.mouse.click(960, 500)
        
        print("Click tab VN30...")
        try:
            # VNDirect tab VN30
            await page.get_by_text("VN30", exact=True).first.click(timeout=3000)
        except Exception as e:
            print(f"Khong the click tab VN30: {e}")
            try:
                await page.get_by_text("HOSE", exact=True).first.click(timeout=2000)
            except:
                pass

        print("Dang cho du lieu bang gia tai xuong (5 giay)...")
        await page.wait_for_timeout(5000) 
        
        html_content = await page.content()
        soup = BeautifulSoup(html_content, 'html.parser')
        
        with open('banggia_raw.html', 'w', encoding='utf-8') as f:
            f.write(soup.prettify())
            
        extracted_data = []
        
        # Cach 1: Tim div co id bat dau bang 'symbol-'
        rows = soup.find_all(lambda tag: tag.has_attr('id') and tag.get('id').startswith('symbol-'))
        
        # Cach 2: Tim theo div co text là mã chứng khoán VN30
        if not rows:
            # Thu lay danh sach tat ca cac div co display: flex va chua dung 3 chu cai dau tien
            candidate_rows = soup.find_all('div')
            rows = []
            for r in candidate_rows:
                # Kiem tra div nay co id ko, o banggia cu la id="symbol-HPG"
                pass
                
        # Neu VNDirect su dung ul/li cho bang gia
        if not rows:
             rows = soup.find_all('li', class_=lambda c: c and 'stock-row' in c)
             
        # Neu van khong ra, thu vet can: tat ca cac row
        if not rows:
            rows = soup.find_all(lambda tag: tag.has_attr('class') and any('row' in cls.lower() for cls in tag.get('class')))

        print(f"So luong element nghi ngo la co phieu: {len(rows)}")
        
        count = 0
        for row in rows:
            text = row.get_text(separator='|', strip=True)
            parts = text.split('|')
            if not parts:
                continue
            
            ticker = parts[0]
            if len(ticker) == 3 and ticker.isupper() and ticker.isalpha() and ticker not in ['HNX', 'HNI', 'VNI']:
                extracted_data.append({
                    'Mã CK': ticker,
                    'Dữ liệu': str(parts[:15]) # In ra 15 phan tu dau tien de quan sat
                })
                count += 1
                if count >= 10: # Chi lay 10 ma de test
                    break
        
        if extracted_data:
            print(f"\nTrich xuat thanh cong. 10 ma dau tien:")
            for item in extracted_data:
                print(item)
        else:
            print("\nKhong thay co phieu nao!")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_vndirect())
