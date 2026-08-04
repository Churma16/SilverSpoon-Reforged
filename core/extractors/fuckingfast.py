import time
import logging
import threading
from core.extractors.base import BaseExtractor

# JS snippet to read the Turnstile token auto-solved by the SeleniumBase UC driver
_GET_TURNSTILE_TOKEN_JS = """
var inp = document.querySelector('[name="cf-turnstile-response"]');
var inputVal = inp ? inp.value : null;
return inputVal || window.turnstileToken || null;
"""

_TURNSTILE_TIMEOUT_SECONDS = 25


class FuckingFastExtractor(BaseExtractor):
    """
    Extracts direct download URLs from fuckingfast.co using a headless
    SeleniumBase UC browser that auto-solves Cloudflare Turnstile.

    A single driver instance is reused across all extractions, protected
    by a threading lock to prevent concurrent navigation conflicts.
    """

    def __init__(self, scraper=None):
        # scraper kept for API compatibility; extraction now uses SeleniumBase UC
        self._driver_lock = threading.Lock()

    def close(self):
        """No-op. Ephemeral drivers are cleaned up per extraction."""
        pass

    def extract_direct_url(self, link: str, file_id: str = None) -> tuple[str | None, str | None]:
        """
        Extract direct download URL from a fuckingfast.co link.
        Returns (direct_url, error_message).
        Thread-safe: serialized through a single shared browser driver lock.
        """
        if not file_id:
            file_id = link.split('/')[-1].split('#')[0]

        with self._driver_lock:
            return self._extract_with_driver(link, file_id)

    def _extract_with_driver(self, link: str, file_id: str) -> tuple[str | None, str | None]:
        from seleniumbase import Driver
        max_retries = 2
        for attempt in range(max_retries):
            driver = None
            try:
                driver = Driver(uc=True, headless=True)
                driver.set_page_load_timeout(45)
                driver.set_script_timeout(20)

                # Navigate to the file page; UC mode handles the Cloudflare cf_clearance challenge
                driver.uc_open_with_reconnect(link, reconnect_time=5)

                # Poll up to TURNSTILE_TIMEOUT seconds for Turnstile to auto-solve
                turnstile_token = None
                for _ in range(_TURNSTILE_TIMEOUT_SECONDS):
                    time.sleep(1)
                    turnstile_token = driver.execute_script(_GET_TURNSTILE_TOKEN_JS)
                    if turnstile_token:
                        break

                if not turnstile_token:
                    if attempt < max_retries - 1:
                        logging.warning(f"Turnstile timeout on attempt {attempt + 1} for {link}. Retrying...")
                        continue
                    return None, "Timed out waiting for Cloudflare Turnstile to solve."

                # Execute the POST from inside the browser (full session context, correct Origin)
                post_path = f"/f/{file_id}/go"
                fetch_js = """
                var callback = arguments[arguments.length - 1];
                var token = arguments[0];
                var postPath = arguments[1];
                var body = new URLSearchParams({'cf-turnstile-response': token});
                fetch(postPath, {
                    method: 'POST',
                    headers: {
                        'HX-Request': 'true',
                        'HX-Target': '',
                        'HX-Current-URL': window.location.href,
                        'Referer': window.location.href,
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                    body: body.toString()
                }).then(response => {
                    var redirectUrl = null;
                    response.headers.forEach(function(value, name) {
                        if (name.toLowerCase() === 'hx-redirect') redirectUrl = value;
                    });
                    return response.text().then(text => {
                        return {status: response.status, redirectUrl: redirectUrl, body: text.substring(0, 200)};
                    });
                }).then(data => callback(data))
                  .catch(err => callback({error: err.toString()}));
                """

                result = driver.execute_async_script(fetch_js, turnstile_token, post_path)

                if result.get('error'):
                    return None, f"In-browser fetch error: {result['error']}"

                if result.get('redirectUrl'):
                    return result['redirectUrl'], None

                status = result.get('status')
                body = result.get('body', '')
                if status == 200:
                    return None, "The file host did not return a direct download link. The link may be expired or unavailable."
                else:
                    return None, f"Could not request the direct download link. Server returned HTTP {status}. Body: {body}"

            except Exception as e:
                logging.error(f"FuckingFastExtractor error for {link}: {e}", exc_info=True)
                if attempt < max_retries - 1:
                    logging.warning(f"Exception on attempt {attempt + 1} for {link}. Retrying...")
                    time.sleep(2)
                    continue
                return None, str(e)
            finally:
                if driver:
                    try:
                        driver.quit()
                    except Exception:
                        pass
        return None, "Max retries exceeded."
