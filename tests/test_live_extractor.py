import os
import pytest
import requests
from core.extractors.fuckingfast import FuckingFastExtractor


@pytest.mark.live
def test_fuckingfast_live_bypass_and_extraction():
    """Live canary probe verifying that Cloudflare Turnstile bypass and direct link

    extraction on fuckingfast.co remain functional against the live host.
    """
    target_link_url = os.environ.get("TEST_FUCKINGFAST_URL")

    if not target_link_url:
        pytest.skip(
            "TEST_FUCKINGFAST_URL environment variable is not configured. Skipping live canary probe."
        )

    link_extractor = FuckingFastExtractor()

    try:
        direct_download_url, extraction_error_message = link_extractor.extract_direct_url(target_link_url)

        assert extraction_error_message is None, (
            f"Bypass failed with error message: {extraction_error_message}"
        )
        assert direct_download_url is not None, (
            "Extractor returned None for direct download URL."
        )
        assert direct_download_url.startswith("http://") or direct_download_url.startswith("https://"), (
            f"Invalid direct download URL schema received: {direct_download_url}"
        )

        # Probe the extracted direct link to ensure the file host CDN is reachable and not blocking requests
        probe_response = requests.head(
            direct_download_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            timeout=15,
            allow_redirects=True,
        )

        assert probe_response.status_code in (200, 206), (
            f"Direct download link returned unexpected HTTP status {probe_response.status_code}."
        )

    finally:
        link_extractor.close()
