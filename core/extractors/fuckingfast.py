import cloudscraper
import logging
from core.extractors.base import BaseExtractor

class FuckingFastExtractor(BaseExtractor):
    def __init__(self, scraper=None):
        self.scraper = scraper or cloudscraper.create_scraper(browser='chrome')

    def extract_direct_url(self, link: str, file_id: str = None) -> tuple[str | None, str | None]:
        """
        Extract direct URL for fuckingfast.co links.
        Returns tuple of (direct_url, error_message)
        """
        if not file_id:
            file_id = link.split('/')[-1].split('#')[0]

        try:
            res = self.scraper.get(link)
            if res.status_code != 200:
                err_msg = f"Could not open the file page. Server returned HTTP {res.status_code}."
                if res.status_code in (403, 503):
                    error_body_preview = res.content[:500].decode('utf-8', errors='ignore')
                    logging.error(f"Got {res.status_code} for {link}. Response body preview: {error_body_preview}")
                return None, err_msg
            
            post_url = f"https://fuckingfast.co/f/{file_id}/go"
            headers = {
                'HX-Request': 'true',
                'HX-Target': '',
                'HX-Current-URL': link,
                'Referer': link
            }
            res2 = self.scraper.post(post_url, headers=headers)
            if res2.status_code == 200:
                direct_link = res2.headers.get('Hx-Redirect')
                if direct_link:
                    return direct_link, None
                return None, "The file host did not return a direct download link. The link may be expired or unavailable."
            else:
                return None, f"Could not request the direct download link. Server returned HTTP {res2.status_code}."
        except Exception as e:
            logging.error(f"Error getting direct link for {link}: {e}", exc_info=True)
            return None, str(e)
