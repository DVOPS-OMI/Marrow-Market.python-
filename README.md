# Morrow Market Shopping Application

This is a small online shopping website made with Python, Flask, and SQLite. It was changed for a local security coursework project. Some routes are intentionally vulnerable so they can be tested with Burp Suite.

Run it only on your own computer with made-up accounts and data. Do not put this version on the public internet.

## Requirements

- Windows 10 or 11
- Python 3.10 or newer
- Internet connection for installing Python packages
- A web browser
- Burp Suite, if you want to inspect requests
- Docker Desktop, only for the request-smuggling exercise

The Python packages are listed in `requirements.txt`.

## Setup and start

Open PowerShell in the project folder and run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Open this address in your browser:

```text
http://127.0.0.1:5000
```

The app creates its SQLite database at `instance/shop.db` when it starts. If PowerShell blocks activation, run this once in that terminal and activate again:

```powershell
Set-ExecutionPolicy -Scope Process RemoteSigned
```

Some checkout steps need Razorpay **test** keys. They are not needed to browse the site or test most vulnerabilities. In PowerShell, set your own test keys before starting the app:

```powershell
$env:RAZORPAY_KEY_ID = "your_test_key_id"
$env:RAZORPAY_KEY_SECRET = "your_test_key_secret"
```

Never put live payment keys in this project.

## How the shopping site works

1. Browse products on the home or Explore page.
2. Open a product page and add the product to your bag.
3. Register an account. Sign-in asks for an OTP; the local OTP is printed in the app's PowerShell window.
4. Use the Profile and Orders pages to view account details and orders.
5. Checkout uses Razorpay test settings when those are configured.
6. Admin pages require an admin account.

## Vulnerability work and endpoints

“Confirmed” means a result was shown in the chat or seen in the project. “Retest” means code or a test route exists, but a successful proof was not confirmed. Some `/security-lab` routes need the lab switch below.

| # | Vulnerability | Endpoint to inspect | Result so far |
|---|---|---|---|
| 1 | LFI (local file read) | `GET /admin/image-preview?file=../app.py` | Added to code; PoC result still needs confirmation. Admin sign-in is required. |
| 2 | RFI (remote template inclusion) | `GET /product/<id>?supplier_note_url=...` | Confirmed: product page displayed the remote note and `42`. |
| 3 | Public admin panel | `GET /admin` | Login message/403 was shown. Internet access was not tested; the app is on localhost. |
| 4 | HPP (duplicate parameters) | `GET /security-lab/params?item=one&item=two` | Route exists; security impact has not been confirmed. |
| 5 | CSV formula injection | `GET /security-lab/export.csv?name=%3D1%2B1` | CSV downloaded with formula text; spreadsheet formula execution was not confirmed. |
| 6 | Weak password hashing | `POST /register`, `POST /login`; `instance/shop.db` | New accounts use unsalted MD5; login worked and a 32-character hash was found. This is weak hashing, not encryption. |
| 7 | Unauthenticated API | `GET /api/customer-orders` and `GET /security-lab/api/private-looking` | Code returns sample records without login; a Burp proof was not confirmed. The records are fake. |
| 8 | Privilege escalation | `POST /profile` with a `role` field | Role update code is present; earlier attempts had issues. Retest with a made-up account. |
| 9 | IDOR | `GET /orders/<order_id>` | Cross-user order visibility was reported earlier. Retest with two test accounts. |
| 10 | SQL injection | `GET /explore?q=...` | SQL injection was not confirmed. The search issue demonstrated is XPath injection (#16); SQL statements use parameters. |
| 11 | HTML injection | `GET /explore?q=...` | Tried with `<b>SALE</b>`; successful HTML rendering was not clearly confirmed. |
| 12 | OTP bypass | `POST /login`, then `POST /verify-otp` | Bypass was not confirmed in the current code; OTP is checked with a hash and attempt limit. |
| 13 | OS command injection | `GET /admin/image-check?name=...` | Vulnerable command call is in code; successful PoC was not confirmed. Admin sign-in is required. |
| 14 | SSRF | `GET /admin/image-preview?url=...` | Preview is restricted to this app on `127.0.0.1:5000`; external SSRF was not confirmed. Admin sign-in is required. |
| 15 | HTTP request smuggling | Docker proxy at `http://127.0.0.1:5001/` | Burp scans reported zero findings; smuggling was not confirmed. |
| 16 | XPath injection | `GET /explore?q=...` | Confirmed: a crafted search changed the product results. This is not SQL injection. |
| 17 | Content spoofing | `GET /?notice=your-text` | Confirmed: supplied notice text appeared in the storefront banner. |
| 18 | Weak CSP header | `GET /` and other pages | Confirmed in Burp: the response allows broad sources and unsafe script settings. |
| 19 | Clickjacking | Store page `/` inside a local iframe | PoC steps were given; a successful iframe result was not confirmed. |
| 20 | File upload validation | `POST /profile` with an `avatar` file | Confirmed: plain text named `hacker.jpg` was accepted and given a public URL; browser showed a broken image. |
| 21 | CORS misconfiguration | `GET /profile` with an `Origin` header | Code reflects the Origin, but the shared response screenshot had no CORS headers. Retest required. |
| 22 | Prototype pollution | `GET /?prefs=...`; browser Console | Confirmed after correcting the URL: `({}).polluted` showed `yes`. |
| 23 | Host header injection | `GET /` with a changed `Host` header | Added to the page's canonical URL; retest in Burp to confirm the response reflects the supplied Host. |

Some exercises, such as HPP and CSV export, are under `/security-lab` in this same Flask app. Enable them in PowerShell before starting the app:

```powershell
$env:SECURITY_LAB = "1"
python app.py
```

The lab endpoints return 404 when the switch is off. Close the app with `Ctrl+C` when finished.

## Optional Docker run

Start Docker Desktop, then run these commands in PowerShell from the project folder:

```powershell
$env:RAZORPAY_KEY_ID = "your_test_key_id"
$env:RAZORPAY_KEY_SECRET = "your_test_key_secret"
docker compose -f compose.smuggling.yml up --build -d
```

Open `http://127.0.0.1:5001`. When finished, stop the containers with:

```powershell
docker compose -f compose.smuggling.yml down
```

The Burp request-smuggling scan in this project did not find a confirmed issue.

## Important

This coursework copy contains intentional security weaknesses. Use fake accounts and local test data only. The app binds to `127.0.0.1`; keep it there. Before using the project as a normal store, remove the vulnerable code and change the development secret and any payment settings.

The submission ZIP leaves out `.venv`, `instance/shop.db`, and generated avatar uploads. The app creates its database when it starts; install the packages from `requirements.txt` instead of copying a virtual environment.
