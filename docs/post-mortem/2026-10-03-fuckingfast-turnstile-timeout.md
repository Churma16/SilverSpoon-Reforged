# Post Mortem: Cloudflare Turnstile Timeout on fuckingfast.co Extractor

**Incident Date:** 2026-10-03  
**Status:** Resolved  
**Severity:** P1 (High)  
**Impacted Area:** `core/extractors/fuckingfast.py`  
**Reporter:** User  
**Handler:** Antigravity Assistant  

---

## 1. Incident Summary

File download tasks from the `fuckingfast.co` host experienced repeated failures with the error:
```text
WARNING - Failed to obtain direct link for task ...: Timed out waiting for Cloudflare Turnstile to solve.
```
Users observed that multipart batch download tasks (e.g. `Cyberpunk_2077_--_fitgirl-repacks.site_--_.part021.rar`, `part022.rar`, `part023.rar`) failed to extract direct download URLs and stopped after exhausting retry attempts (taking approximately 88 seconds per file).

---

## 2. Impact

- **Impacted Users:** All users downloading files hosted on `fuckingfast.co`.
- **Impacted Data:** All download links from `fuckingfast.co` failed to resolve into direct download links.
- **Functionality:** Downloads stopped during the link resolution phase (`Solving Session...`), causing download queues to stall and tasks to be marked as failed.

---

## 3. Chronological Timeline

| Time (UTC+7) | Event / Action |
|--------------|----------------|
| 21:33 | Application logs recorded recurring `Timed out waiting for Cloudflare Turnstile to solve` errors across batch download tasks. |
| 21:36 | User reported the issue and requested log analysis. |
| 21:37 | Application log inspection in `logs/silverspoon.log` identified a 25-second timeout per attempt during Turnstile token polling. |
| 21:40 | DOM analysis of `fuckingfast.co` confirmed the absence of Turnstile input widgets (`turnstileInputs: 0`, `turnstileClass: 0`). |
| 21:42 | In-browser POST testing to `/f/{file_id}/go` demonstrated that the server responds with HTTP 200 and an `HX-Redirect` direct URL without requiring a Turnstile token. |
| 21:44 | Fix plan drafted and presented to the user. |
| 21:46 | User approved the proposed fix plan. |
| 21:47 | Fix applied to `core/extractors/fuckingfast.py` introducing adaptive Turnstile widget presence detection. |
| 21:48 | End-to-end verification succeeded; direct URLs from previously failing links extracted in ~2 seconds without timing out. |

---

## 4. Root Cause Analysis

1. **Host Page Architecture Change (`fuckingfast.co`):**  
   The file host updated its download page architecture so that the interactive Cloudflare Turnstile captcha widget (`[name="cf-turnstile-response"]`) is no longer rendered in the DOM on initial file page loads.
2. **Strict Turnstile Prerequisite in Extractor:**  
   In `core/extractors/fuckingfast.py`, the extractor previously assumed a Turnstile widget is always present. The logic strictly polled for up to 25 seconds per attempt waiting for the token value:
   ```python
   for _ in range(_TURNSTILE_TIMEOUT_SECONDS):
       time.sleep(1)
       turnstile_token = driver.execute_script(_GET_TURNSTILE_TOKEN_JS)
       if turnstile_token:
           break
   if not turnstile_token:
       # Treated as a timeout failure and aborted
   ```
   Because the element was never rendered, `turnstile_token` remained `None`, causing the extractor to treat this as a timeout and fail the task, even though the server accepted the download request immediately.

---

## 5. Debugging Steps

1. **Application Log Inspection:**  
   Examined `logs/silverspoon.log` to identify the failing URLs and isolate the warning source in `core.extractors.fuckingfast`.
2. **DOM and Storage Analysis:**  
   Ran headless SeleniumBase in UC mode to inspect active iframes, `.cf-turnstile` CSS classes, and form elements on a live file page (`https://fuckingfast.co/c7o9muwfdksh`). Findings confirmed 0 Turnstile input elements existed.
3. **Embedded Script Deobfuscation:**  
   Extracted and decoded the obfuscated client-side JavaScript on the page; verified it only handled pop-under ad mechanisms and did not render a client-side Turnstile challenge.
4. **Direct In-Browser POST Verification:**  
   Dispatched a test POST request to `/f/<file_id>/go` from within the browser session containing Cloudflare clearance cookies with an empty token (`token = ''`). The server returned HTTP 200 and an `HX-Redirect` header with the direct download link `https://dl.fuckingfast.co/dl/...`.

---

## 6. Resolution

Implemented adaptive presence detection in [`core/extractors/fuckingfast.py`](file:///d:/Document/Coding/silverspoon-reforged/core/extractors/fuckingfast.py):

1. **Widget Presence Detection Snippet (`_HAS_TURNSTILE_JS`):**
   ```python
   _HAS_TURNSTILE_JS = """
   var inputElement = document.querySelector('[name="cf-turnstile-response"]');
   var widgetElement = document.querySelector('.cf-turnstile');
   var turnstileIframe = document.querySelector('iframe[src*="challenges.cloudflare.com"]');
   return (inputElement !== null || widgetElement !== null || turnstileIframe !== null);
   """
   ```

2. **Conditional Polling Branch:**
   - If the widget is present: Poll up to `_TURNSTILE_TIMEOUT_SECONDS` as before (retaining backward compatibility if Turnstile is re-enabled).
   - If no widget is detected: Skip the 25-second wait, set `turnstile_token = ""`, and proceed directly to the download POST request.

3. **In-Browser Fetch Adjustment:**
   Updated the fetch snippet to handle optional tokens (`var token = arguments[0] || '';`) so the form payload remains valid when the token is empty.

---

## 7. Action Items & Lessons Learned

- **Action Items:**
  - Continue monitoring download logs across large batches to ensure consistent link extraction performance.
  - Retain ephemeral browser instances to ensure clean Cloudflare clearance state per download task.
- **Lessons Learned:**
  - Do not assume third-party security challenges (CAPTCHA/Turnstile) will remain static. Extractor modules should dynamically check for the presence of protection mechanisms before entering blocking polling timeouts.
