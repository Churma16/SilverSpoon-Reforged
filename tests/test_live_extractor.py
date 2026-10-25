import os
import re
import logging
import pytest
import requests
from core.extractors.fuckingfast import FuckingFastExtractor

logger = logging.getLogger(__name__)


@pytest.mark.live
def test_fuckingfast_live_extraction():
    """Live probe verifying that direct link extraction on fuckingfast.co

    remains functional and compatible with the host service.
    Iterates through a pool of candidate URLs to prevent false alarms
    caused by individual file expiration on the file host.
    """
    raw_configured_urls = (
        os.environ.get("TEST_FUCKINGFAST_URLS")
        or os.environ.get("TEST_FUCKINGFAST_URL")
    )

    if not raw_configured_urls:
        pytest.skip(
            "Neither TEST_FUCKINGFAST_URLS nor TEST_FUCKINGFAST_URL environment variable is configured. Skipping live probe."
        )

    candidate_urls = [
        single_url.strip()
        for single_url in re.split(r"[,;\n]+", raw_configured_urls)
        if single_url.strip()
    ]

    if not candidate_urls:
        pytest.skip("No valid candidate URLs found in environment configuration.")

    link_extractor = FuckingFastExtractor()

    successful_extraction_results = []
    expired_link_records = []
    extraction_failure_records = []

    try:
        for target_link_url in candidate_urls:
            logger.info(f"Probing candidate link: {target_link_url}")
            direct_download_url, extraction_error_message = link_extractor.extract_direct_url(target_link_url)

            # Check if failure is due to file expiration / deletion on the host
            is_file_not_found = (
                extraction_error_message is not None
                and ("404" in extraction_error_message or "Not Found" in extraction_error_message)
            )

            if is_file_not_found:
                logger.warning(
                    f"[warn] Candidate link {target_link_url} returned 404 (file expired or deleted). Trying next candidate..."
                )
                expired_link_records.append((target_link_url, extraction_error_message))
                continue

            if extraction_error_message is not None:
                logger.error(
                    f"[error] Extraction failed for candidate {target_link_url}: {extraction_error_message}"
                )
                extraction_failure_records.append((target_link_url, extraction_error_message))
                continue

            if not direct_download_url or not (
                direct_download_url.startswith("http://") or direct_download_url.startswith("https://")
            ):
                invalid_schema_message = f"Invalid direct download URL schema received: {direct_download_url}"
                logger.error(f"[error] {invalid_schema_message}")
                extraction_failure_records.append((target_link_url, invalid_schema_message))
                continue

            # Probe the extracted direct link to ensure the file host CDN is reachable and not blocking requests
            try:
                probe_response = requests.head(
                    direct_download_url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                    timeout=15,
                    allow_redirects=True,
                )

                if probe_response.status_code in (200, 206):
                    successful_extraction_results.append({
                        "candidate_url": target_link_url,
                        "direct_download_url": direct_download_url,
                        "status_code": probe_response.status_code,
                    })
                    logger.info(
                        f"[info] Successfully extracted and verified direct download link for {target_link_url} (HTTP {probe_response.status_code})."
                    )
                    # Candidate succeeded, exit loop early
                    break
                else:
                    unexpected_status_message = (
                        f"Direct download link returned unexpected HTTP status {probe_response.status_code}."
                    )
                    logger.error(f"[error] {unexpected_status_message}")
                    extraction_failure_records.append((target_link_url, unexpected_status_message))
            except Exception as probe_exception:
                probe_error_message = f"Direct download probe failed: {probe_exception}"
                logger.error(f"[error] {probe_error_message}")
                extraction_failure_records.append((target_link_url, probe_error_message))

        # Evaluate final outcome across all candidate URLs
        if not successful_extraction_results:
            if len(expired_link_records) == len(candidate_urls):
                pytest.fail(
                    f"All {len(candidate_urls)} candidate URLs returned HTTP 404 (file expired or deleted on host). "
                    f"Please update the test URLs secret in repository settings. "
                    f"Expired links: {[url for url, _ in expired_link_records]}"
                )
            else:
                formatted_failure_details = "\n".join(
                    f"- {url}: {error}" for url, error in extraction_failure_records
                )
                pytest.fail(
                    f"Live extraction failed on {len(extraction_failure_records)} candidate(s):\n{formatted_failure_details}"
                )

    finally:
        link_extractor.close()
