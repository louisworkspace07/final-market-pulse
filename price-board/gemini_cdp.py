import sys
import json
import asyncio
import os
from playwright.async_api import async_playwright

USER_DATA_DIR = os.path.join(os.getcwd(), "gemini_profile")

async def check_login(p):
    browser = await p.chromium.launch_persistent_context(
        USER_DATA_DIR,
        headless=True,
        args=["--disable-blink-features=AutomationControlled"]
    )
    page = browser.pages[0] if len(browser.pages) > 0 else await browser.new_page()
    try:
        await page.goto("https://gemini.google.com/app", timeout=30000)
        await page.wait_for_selector("rich-textarea", timeout=10000)
        
        # In Gemini Guest Mode, rich-textarea exists but there is a "Sign in" button.
        # We check for the Sign in button to accurately determine if user is logged in.
        sign_in_links = await page.query_selector_all("a[href*='accounts.google.com/ServiceLogin'], a[href*='accounts.google.com/v3/signin']")
        
        # If there are sign in links, user is NOT logged in.
        if len(sign_in_links) > 0:
            is_logged_in = False
        else:
            is_logged_in = True
            
    except:
        is_logged_in = False
    
    await browser.close()
    return is_logged_in

async def do_login_flow():
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = browser.pages[0] if len(browser.pages) > 0 else await browser.new_page()
        
        try:
            await page.goto("https://gemini.google.com/app", timeout=60000)
            
            # Wait until the sign in button disappears
            for _ in range(600): # 600 * 1s = 10 minutes max wait
                await asyncio.sleep(1)
                try:
                    if "gemini.google.com/app" in page.url:
                        sign_in_links = await page.query_selector_all("a[href*='accounts.google.com/ServiceLogin'], a[href*='accounts.google.com/v3/signin']")
                        if len(sign_in_links) == 0:
                            break
                except Exception:
                    # Ignore "Execution context was destroyed" due to navigation
                    pass
                
            print(json.dumps({"result": "LOGIN_SUCCESS"}))
        except Exception as e:
            print(json.dumps({"error": str(e)}))
        finally:
            await browser.close()

async def interact_with_gemini(prompt):
    async with async_playwright() as p:
        
        # Check login status
        is_logged_in = await check_login(p)
        
        if not is_logged_in:
            print(json.dumps({"error": "LOGIN_REQUIRED"}))
            return
            
        browser = await p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = browser.pages[0] if len(browser.pages) > 0 else await browser.new_page()
        
        try:
            await page.goto("https://gemini.google.com/app", timeout=60000)
            
            input_selector = "rich-textarea"
            await page.wait_for_selector(input_selector, timeout=15000)
            
            await page.click(input_selector)
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            
            await page.keyboard.insert_text(prompt)
            await page.wait_for_timeout(500)
            
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(3000)
            
            response_selector = "message-content"
            await page.wait_for_selector(response_selector, timeout=60000)
            
            last_text = ""
            stable_count = 0
            while stable_count < 3:
                await page.wait_for_timeout(2000)
                elements = await page.query_selector_all(response_selector)
                if len(elements) > 0:
                    current_text = await elements[-1].inner_text()
                    if current_text == last_text and current_text.strip() != "":
                        stable_count += 1
                    else:
                        stable_count = 0
                        last_text = current_text
            
            print(json.dumps({"result": last_text}))
            
        except Exception as e:
            print(json.dumps({"error": f"Lỗi trong quá trình lấy kết quả: {str(e)}"}))
            
        finally:
            await browser.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "login" or arg == "--login":
            asyncio.run(do_login_flow())
        elif arg == "--check-status":
            async def run_check():
                async with async_playwright() as p:
                    logged_in = await check_login(p)
                    print(json.dumps({"is_logged_in": logged_in}))
            asyncio.run(run_check())
        else:
            asyncio.run(interact_with_gemini(arg))
    else:
        print(json.dumps({"error": "No prompt provided"}))
