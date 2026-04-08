# UNiDAYS Coupon Bot 🤖

An automated bot that logs into UNiDAYS, grabs your daily H&M student discount code, and saves it to a text file — fully hands-free using Gmail API for OTP authentication.

## What it does

- Logs into UNiDAYS automatically using your email + OTP
- Fetches the OTP from Gmail using the Gmail API (no manual input needed)
- Navigates to the H&M brand page and reveals the coupon code
- Saves the code with a timestamp to `coupons.txt`
- Skips saving if the code was already collected today
- Logs any errors to `errors.txt`
- Runs daily via Windows Task Scheduler — fully unattended

## Tech Stack

- Python 3
- Selenium (browser automation)
- Gmail API (OTP fetching)
- Google Auth (OAuth2)
- Windows Task Scheduler (scheduling)

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/AbhiSethiya/couponBOT.git
cd couponBOT
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up Gmail API

- Go to [Google Cloud Console](https://console.cloud.google.com)
- Create a new project
- Enable the **Gmail API**
- Go to **APIs & Services → Credentials → Create OAuth 2.0 Client ID** (Desktop App)
- Download the JSON and rename it to `credentials.json`
- Place it in the project folder
- Add your Gmail to **Audience → Test Users**

### 4. Configure the script

Open `unidays_scraper.py` and fill in the config at the top:

```python
UNIDAYS_EMAIL    = "your_email@gmail.com"
BRAND_URL        = "https://www.myunidays.com/IN/en-IN/partners/hm/access/online"
OUTPUT_FILE      = r"C:\path\to\coupons.txt"
CREDENTIALS_FILE = r"C:\path\to\credentials.json"
TOKEN_FILE       = r"C:\path\to\token.pickle"
```

### 5. First run

```bash
python unidays_scraper.py
```

A browser window will open asking you to authorize Gmail access. Do this once — after that it saves a `token.pickle` and never asks again.

### 6. Schedule with Task Scheduler (Windows)

- Open **Task Scheduler → Create Basic Task**
- Trigger: **Daily** at your preferred time
- Action: Start a program
  - Program: `python`
  - Arguments: `C:\path\to\unidays_scraper.py`
  - Start in: `C:\path\to\couponBOT`

## Output

Codes are saved to `coupons.txt` like this:

```
[2026-04-08 09:00]  AS98-LCA2-BHCN-6JHW
[2026-04-09 09:00]  B711-F8K2-C9WX-1MNP
```

Errors are logged to `errors.txt` with timestamps.

## Notes

- UNiDAYS allows one new code per 24 hours
- `credentials.json` and `token.pickle` are excluded from the repo — never upload these
- Currently configured for H&M India — change `BRAND_URL` for other brands or region