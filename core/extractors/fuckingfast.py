import os
import sys
import time
import logging
import threading
from core.extractors.base import BaseExtractor

logger = logging.getLogger(__name__)

# JS snippet to check if a Cloudflare Turnstile widget or response input is present
_HAS_TURNSTILE_JS = """
var inputElement = document.querySelector('[name="cf-turnstile-response"]');
var widgetElement = document.querySelector('.cf-turnstile');
return (inputElement !== null || widgetElement !== null);
"""

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
    SeleniumBase UC browser that handles Cloudflare clearance and optional Turnstile challenges.

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
                logger.info(f"Starting SeleniumBase UC driver for {link} (attempt {attempt + 1}/{max_retries})")
                is_headless = True
                if sys.platform != "win32" and os.environ.get("DISPLAY"):
                    is_headless = False
                driver = Driver(uc=True, headless=is_headless)
                driver.set_page_load_timeout(45)
                driver.set_script_timeout(20)

                # Navigate to the file page; UC mode handles the Cloudflare cf_clearance challenge
                driver.uc_open_with_reconnect(link, reconnect_time=5)

                # Define in-browser fetch execution snippet
                post_path = f"/f/{file_id}/go"
                fetch_js = """
                var callback = arguments[arguments.length - 1];
                var token = arguments[0] || '';
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

                # Attempt 1: Check if token is already present or try with session cookies immediately
                initial_token = driver.execute_script(_GET_TURNSTILE_TOKEN_JS) or ""
                result = driver.execute_async_script(fetch_js, initial_token, post_path)

                if result.get('redirectUrl'):
                    logger.info(f"Successfully extracted direct URL for {link}")
                    return result['redirectUrl'], None

                # Attempt 2: If no redirect was returned, check whether Turnstile challenge requires solving
                has_turnstile_widget = driver.execute_script(_HAS_TURNSTILE_JS)
                if has_turnstile_widget:
                    logger.info(f"Turnstile widget detected on page for {link}, resolving challenge...")
                    turnstile_token = None
                    for second in range(_TURNSTILE_TIMEOUT_SECONDS):
                        time.sleep(1)
                        turnstile_token = driver.execute_script(_GET_TURNSTILE_TOKEN_JS)
                        if turnstile_token:
                            break
                        if second in (3, 10):
                            try:
                                driver.uc_gui_handle_cf()
                            except Exception as click_error:
                                logger.debug(f"Turnstile GUI click attempt: {click_error}")

                    if turnstile_token:
                        retry_result = driver.execute_async_script(fetch_js, turnstile_token, post_path)
                        if retry_result.get('redirectUrl'):
                            logger.info(f"Successfully extracted direct URL for {link} after Turnstile challenge")
                            return retry_result['redirectUrl'], None
                        result = retry_result

                if result.get('error'):
                    logger.error(f"In-browser fetch error for {link}: {result['error']}")
                    return None, f"In-browser fetch error: {result['error']}"

                status = result.get('status')
                body = result.get('body', '')
                if status == 200:
                    logger.warning(f"File host returned HTTP 200 without redirect for {link}")
                    return None, "The file host did not return a direct download link. The link may be expired or unavailable."
                else:
                    logger.warning(f"File host returned HTTP {status} for {link}. Body: {body}")
                    return None, f"Could not request the direct download link. Server returned HTTP {status}. Body: {body}"

            except Exception as e:
                logger.error(f"FuckingFastExtractor error for {link}: {e}", exc_info=True)
                if attempt < max_retries - 1:
                    logger.warning(f"Exception on attempt {attempt + 1} for {link}. Retrying...")
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
