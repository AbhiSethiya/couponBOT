from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import base64, re, time, os, pickle
from datetime import datetime

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
UNIDAYS_EMAIL = "for.any.purpose2005@gmail.com"
BRAND_URL = "https://www.myunidays.com/IN/en-IN/partners/hm/access/online"
OUTPUT_FILE = r"C:\Users\HP\PycharmProjects\couponBOT\coupons.txt"
CREDENTIALS_FILE = r"C:\Users\HP\PycharmProjects\couponBOT\credentials.json"
TOKEN_FILE = r"C:\Users\HP\PycharmProjects\couponBOT\token.pickle"
# ─────────────────────────────────────────────

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_gmail_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)
    return build("gmail", "v1", credentials=creds)


def fetch_otp_from_gmail(service, after_timestamp, timeout=90):
    start = time.time()
    while time.time() - start < timeout:
        results = service.users().messages().list(
            userId="me",
            q=f"unidays after:{after_timestamp}",
            maxResults=5
        ).execute()
        messages = results.get("messages", [])
        for message in messages:
            msg = service.users().messages().get(
                userId="me", id=message["id"], format="full"
            ).execute()
            msg_time = int(msg["internalDate"]) // 1000
            if msg_time < after_timestamp:
                continue
            parts = msg["payload"].get("parts", [msg["payload"]])
            for part in parts:
                data = part.get("body", {}).get("data", "")
                if data:
                    text = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                    match = re.search(r"\b(\d{6})\b", text)
                    if match:
                        return match.group(1)
        time.sleep(5)
    raise TimeoutError("OTP email not received within timeout.")


def _type_otp(driver, otp_input, otp):
    driver.execute_script("arguments[0].scrollIntoView(true);", otp_input)
    time.sleep(0.5)
    ActionChains(driver).move_to_element(otp_input).click().perform()
    time.sleep(0.5)
    for digit in otp:
        ActionChains(driver).send_keys(digit).perform()
        time.sleep(0.2)
    driver.execute_script("""
            var input = arguments[0];
            var nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
            nativeInputValueSetter.call(input, arguments[1]);
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
        """, otp_input, otp)


def try_enter_otp(driver, wait, otp):
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    try:
        otp_input = driver.find_element(By.ID, "otp-code")
        if otp_input.is_displayed():
            _type_otp(driver, otp_input, otp)
            return
    except:
        pass
    for iframe in iframes:
        try:
            driver.switch_to.frame(iframe)
            time.sleep(1)
            try:
                otp_input = driver.find_element(By.ID, "otp-code")
                _type_otp(driver, otp_input, otp)
                return
            except:
                pass
            driver.switch_to.default_content()
        except:
            driver.switch_to.default_content()
    raise Exception("Could not find OTP input field")


def grab_code(driver):
    """Try multiple strategies to find the coupon code on the page."""
    for attempt in range(15):
        code = driver.execute_script("""
            var codePattern = /^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$/;

            // Strategy 1: Check <input> fields (code is often in an input with Copy button)
            var inputs = document.querySelectorAll('input');
            for (var i = 0; i < inputs.length; i++) {
                var val = (inputs[i].value || '').trim();
                if (codePattern.test(val)) return val;
            }

            // Strategy 2: Look for code pattern in <p> elements
            var allP = document.querySelectorAll('p');
            for (var j = 0; j < allP.length; j++) {
                var text = allP[j].innerText.trim();
                if (codePattern.test(text)) return text;
            }

            // Strategy 3: Look in <span> elements
            var allSpan = document.querySelectorAll('span');
            for (var k = 0; k < allSpan.length; k++) {
                var text2 = allSpan[k].innerText.trim();
                if (codePattern.test(text2)) return text2;
            }

            // Strategy 4: Broad search — any leaf element
            var allEls = document.querySelectorAll('div, p, span, h1, h2, h3, h4, h5, h6, strong, b, code');
            for (var m = 0; m < allEls.length; m++) {
                if (allEls[m].children.length === 0) {
                    var text3 = allEls[m].innerText.trim();
                    if (codePattern.test(text3)) return text3;
                }
            }

            // Strategy 5: Check data-testid or aria-label elements
            var dataEl = document.querySelector('[data-testid*="code"]');
            if (dataEl) {
                var v = (dataEl.value || dataEl.innerText || '').trim();
                if (codePattern.test(v)) return v;
            }

            return null;
        """)
        if code and len(code) > 5:
            return code
        time.sleep(2)
        if attempt % 5 == 4:
            print(f"  grab_code: still searching... (attempt {attempt+1})")
    return None


def get_code_tab(driver, main_window):
    """Wait for a non-H&M tab to appear and return its handle. Close H&M tabs."""
    time.sleep(3)
    for handle in list(driver.window_handles):
        if handle != main_window:
            try:
                driver.switch_to.window(handle)
                time.sleep(2)
                if "hm.com" in driver.current_url:
                    print("Closing H&M tab...")
                    driver.close()
                    driver.switch_to.window(main_window)
                else:
                    print(f"Code tab found: {driver.current_url}")
                    return handle
            except:
                driver.switch_to.window(main_window)
    return None


def navigate_to_brand(driver, main_window):
    """Safely navigate to brand page from main window."""
    # Close any extra tabs first
    for handle in list(driver.window_handles):
        if handle != main_window:
            try:
                driver.switch_to.window(handle)
                driver.close()
            except:
                pass
    driver.switch_to.window(main_window)
    time.sleep(1)
    driver.execute_script(f"window.location.href = '{BRAND_URL}';")
    time.sleep(5)
    # Retry if redirected to home
    if "home" in driver.current_url or "rd=true" in driver.current_url:
        print("Redirected to home, retrying...")
        time.sleep(5)
        driver.execute_script(f"window.location.href = '{BRAND_URL}';")
        time.sleep(5)
    return "home" not in driver.current_url and "rd=true" not in driver.current_url


def get_coupon():
    gmail_service = get_gmail_service()

    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20)
    main_window = driver.current_window_handle

    try:
        # ── Step 1: Enter email ───────────────────────────────────────
        driver.get("https://www.myunidays.com/IN/en-IN/account/log-in")
        time.sleep(3)

        email_input = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR,
            "input[type='email'], input[name='email'], input[id='emailAddress'], input[inputmode='email']"
        )))
        email_input.clear()
        email_input.send_keys(UNIDAYS_EMAIL)
        time.sleep(1)

        try:
            submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        except:
            submit_btn = driver.find_element(By.XPATH,
                                             "//button[contains(text(),'Continue') or contains(text(),'Next') or contains(text(),'Sign')]")

        otp_wait_start = int(time.time())
        submit_btn.click()
        time.sleep(2)

        # ── Step 2: Get OTP from Gmail ────────────────────────────────
        otp = fetch_otp_from_gmail(gmail_service, after_timestamp=otp_wait_start, timeout=90)
        time.sleep(3)

        # ── Step 3: Enter OTP ─────────────────────────────────────────
        try_enter_otp(driver, wait, otp)
        time.sleep(1)

        # ── Step 4: Submit OTP ────────────────────────────────────────
        try:
            verify_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        except:
            verify_btn = driver.find_element(By.XPATH,
                                             "//button[contains(text(),'Verify') or contains(text(),'Continue') or contains(text(),'Submit')]")
        verify_btn.click()
        driver.switch_to.default_content()
        time.sleep(6)

        # ── Step 5: Navigate to brand page ───────────────────────────
        driver.switch_to.window(main_window)
        ok = navigate_to_brand(driver, main_window)
        if not ok:
            print("Session not established, please run again.")
            return

        # ── Step 6: Click Reveal Code (if present) ─────────────────────
        #    UNiDAYS may show the code directly without a Reveal button
        try:
            reveal_btn = WebDriverWait(driver, 8).until(EC.element_to_be_clickable((
                By.XPATH, "//button[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'reveal')]"
            )))
            reveal_btn.click()
            print("Clicked 'Reveal code' button.")
            time.sleep(3)
        except:
            print("No 'Reveal code' button found — code may already be showing.")

        # Close any extra tabs (like H&M) and stay on UNiDAYS
        time.sleep(2)
        for handle in list(driver.window_handles):
            if handle != main_window:
                try:
                    driver.switch_to.window(handle)
                    time.sleep(1)
                    if "hm.com" in driver.current_url:
                        print("Closing H&M tab...")
                        driver.close()
                except:
                    pass
        driver.switch_to.window(main_window)
        time.sleep(2)

        # ── Step 7: Grab the code ─────────────────────────────────────
        code = grab_code(driver)

        if not code:
            print("Could not find coupon code.")
            return

        print(f"Code found: {code}")

        # ── Step 8: Check if already saved ────────────────────────────
        already_saved = False
        if os.path.exists(OUTPUT_FILE):
            with open(OUTPUT_FILE, "r") as f:
                already_saved = code in f.read()

        if already_saved:
            print(f"Code {code} already saved, getting new code...")

            # The "Get new code" button is on the SAME page — no tab switch needed
            print(f"On page: {driver.current_url}")

            # Click Get new code on the UNiDAYS tab — try MULTIPLE strategies
            new_code_btn = None

            # Strategy 1: XPath with contains (case-insensitive)
            try:
                new_code_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((
                    By.XPATH, "//button[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'new code')]"
                )))
                print("Found 'Get new code' via XPath contains")
            except:
                pass

            # Strategy 2: XPath with various text patterns
            if not new_code_btn:
                for text_pattern in ['Get new code', 'Get New Code', 'get new code', 'New code', 'New Code', 'Generate new code', 'Get another code']:
                    try:
                        new_code_btn = driver.find_element(By.XPATH, f"//button[contains(text(),'{text_pattern}')]")
                        if new_code_btn.is_displayed():
                            print(f"Found button via text: '{text_pattern}'")
                            break
                        else:
                            new_code_btn = None
                    except:
                        new_code_btn = None

            # Strategy 3: Check inside child elements (button might contain a span)
            if not new_code_btn:
                try:
                    new_code_btn = driver.find_element(By.XPATH,
                        "//button[.//span[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'new code')]]"
                    )
                    print("Found 'Get new code' via child span")
                except:
                    pass

            # Strategy 4: CSS selector with data attributes
            if not new_code_btn:
                try:
                    new_code_btn = driver.find_element(By.CSS_SELECTOR,
                        "button[data-testid*='new-code'], button[data-testid*='newCode'], button[data-testid*='generate']"
                    )
                    print("Found button via data-testid")
                except:
                    pass

            # Strategy 5: JavaScript-based search through ALL buttons
            if not new_code_btn:
                try:
                    btn_index = driver.execute_script("""
                        let buttons = document.querySelectorAll('button, a[role="button"], [role="button"]');
                        for (let i = 0; i < buttons.length; i++) {
                            let text = buttons[i].innerText.toLowerCase().trim();
                            if (text.includes('new code') || text.includes('new_code') || text.includes('generate')) {
                                return i;
                            }
                        }
                        return -1;
                    """)
                    if btn_index >= 0:
                        buttons = driver.find_elements(By.CSS_SELECTOR, "button, a[role='button'], [role='button']")
                        new_code_btn = buttons[btn_index]
                        print(f"Found button via JS scan at index {btn_index}")
                except:
                    pass

            # Debug: dump all buttons if none found
            if not new_code_btn:
                all_buttons = driver.execute_script("""
                    let buttons = document.querySelectorAll('button, a[role="button"], [role="button"]');
                    let result = [];
                    for (let b of buttons) {
                        result.push({
                            tag: b.tagName,
                            text: b.innerText.trim().substring(0, 100),
                            classes: b.className.substring(0, 200),
                            visible: b.offsetParent !== null
                        });
                    }
                    return JSON.stringify(result);
                """)
                print(f"DEBUG — All buttons on page: {all_buttons}")
                print(f"DEBUG — Page URL: {driver.current_url}")
                print("Could not find 'Get new code' button with any strategy.")
                return

            print("Clicking Get new code...")
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", new_code_btn)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", new_code_btn)
            except:
                ActionChains(driver).move_to_element(new_code_btn).click().perform()
            print("Clicked! Waiting for new code...")
            time.sleep(6)

            # Code updates on the same tab, just poll for change
            for _ in range(15):
                time.sleep(2)
                new_code = grab_code(driver)
                print(f"Polling... got: {new_code}")
                if new_code and new_code != code:
                    code = new_code
                    print(f"New code found: {code}")
                    break
            else:
                code = grab_code(driver)

            if not code:
                print("Could not grab new code.")
                return

        # ── Step 9: Save to file ──────────────────────────────────────
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        line = f"[{date_str}]  {code}\n"
        with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
            f.write(line)
        print(f"Coupon saved: {code}")

    except Exception as e:
        print(f"Error: {e}")
        error_log = r"C:\Users\HP\PycharmProjects\couponBOT\error_log.txt"
        with open(error_log, "a", encoding="utf-8") as f:
            import traceback
            date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            f.write(f"[{date_str}] ERROR: {e}\n")
            f.write(traceback.format_exc())
            f.write("\n" + "─"*50 + "\n")

    finally:
        driver.quit()


if __name__ == "__main__":
    get_coupon()
