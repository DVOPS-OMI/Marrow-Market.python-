# Security Lab Plan (Local Only)

This project is a Flask + SQLite shopping demo. Keep all intentionally vulnerable exercises separate from the normal storefront and bind the lab to `127.0.0.1` only. Use fictional data. Do not expose the lab to a LAN or public internet. Some items need a separate mock service or proxy chain and cannot be demonstrated faithfully inside this Flask app alone.

## Current application review

- Parameterized SQLite queries are already used in the reviewed catalog, login, orders, wishlist, and admin routes.
- Admin routes require the database role `admin`; order history is scoped to the signed-in user.
- `/api/wishlist-products` is unauthenticated but only returns public catalog fields, so this is not automatically an authorization flaw.
- OTP is time-limited and attempt-limited. The login route logs OTP values to the local server console; keep this local-only and use fake accounts.
- The development server currently has `debug=True`. Never bind this app to `0.0.0.0` or deploy it with debug enabled.

## Requested exercises (21 received; one more can be appended later)

| # | Exercise | Safe local demonstration plan | Notes |
|---|---|---|---|
| 1 | LFI | Read only from a dedicated lab-fixtures directory containing fake text files. | Do not expose arbitrary system files. |
| 2 | RFI | Use a local mock content server and harmless fixture content. | Do not fetch arbitrary internet URLs or execute remote code. |
| 3 | Admin accessible over internet | Demonstrate an unprotected admin route in the isolated lab and verify the normal app remains loopback-only. | Do not make the real app internet-accessible. |
| 4 | HTTP parameter pollution | Add a lab form where duplicate query keys are interpreted inconsistently; record the server's first/last/all-value behavior. | Keep changes within lab routes. |
| 5 | CSV formula injection | Export fake user-controlled values to CSV and demonstrate spreadsheet formula interpretation in a disposable file. | Do not open untrusted exports in a real spreadsheet. |
| 6 | Weak encryption | Store a fake lab secret using a deliberately weak reversible encoding and compare with a secure control. | Do not reuse real credentials or payment data. |
| 7 | Unauthenticated API access | Add a lab-only endpoint returning synthetic private-looking records without login. | Use synthetic records only. |
| 8 | Privilege escalation | Create fake customer/admin lab accounts and show a lab-only role update flaw. | Preserve the storefront's role checks. |
| 9 | IDOR | Add two fake users and lab-only records; demonstrate missing ownership scoping. | Do not use real order records. |
| 10 | SQL injection | Use a separate disposable lab database/table and an unsafe query route. | Keep production storefront queries parameterized. |
| 11 | HTML injection | Render a lab-only user-controlled value without escaping, using harmless text. | Do not use scripts or steal data. |
| 12 | OTP bypass | Make a lab-only fake OTP flow with a documented validation omission. | Keep the real login OTP checks intact. |
| 13 | OS command injection | Simulate the vulnerable command construction with a harmless allowlisted operation in a subprocess-free mock. | Do not execute user-supplied OS commands. |
| 14 | SSRF | Route requests only to a local mock server with a strict destination allowlist. | No cloud metadata, private network, or arbitrary internet targets. |
| 15 | HTTP request smuggling | Demonstrate with a local reverse-proxy/backend pair and saved benign requests. | Requires separate proxy/server infrastructure; Flask alone is insufficient. |
| 16 | XPath injection | Add fake XML records and a lab-only unsafe XPath lookup. | Requires XML fixtures; current app uses SQLite. |
| 17 | Content spoofing / text injection | Reflect a harmless lab input into a page heading or message. | Keep it separate from storefront templates. |
| 18 | CSP header misconfiguration | Apply a deliberately weak CSP only on lab responses and inspect it in browser devtools. | Do not weaken headers globally. |
| 19 | Clickjacking | Permit framing only on a lab page, then test with a local parent page. | Do not weaken the whole site's frame protections. |
| 20 | File upload vulnerability | Accept only small harmless `.txt` lab fixtures into a dedicated temporary directory. | No executable uploads or path traversal outside the lab directory. |
| 21 | CORS | Give a lab endpoint an overly broad CORS response and test from a local second origin. | Do not enable credentialed wildcard CORS on real routes. |
| 22 | Pending | Not included in the list received yet. | Can be added when supplied. |

## Verification checklist

For each exercise, record the route, a harmless input, the observed response, why the behavior is vulnerable, and the secure fix. Verify that lab routes are unavailable when lab mode is off, the normal app stays on loopback, and the standard storefront authorization checks still work. Keep the lab data disposable and reset it after demonstrations.
