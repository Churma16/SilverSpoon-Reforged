from abc import ABC, abstractmethod
from typing import Optional, Tuple


class BaseExtractor(ABC):
    """Abstract base class for file host link extractors."""

    @abstractmethod
    def extract_direct_url(self, link: str, file_id: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """Extract direct download URL from input link.
        
        Args:
            link: The target file host URL.
            file_id: Optional file identifier extracted from the URL.

        Returns:
            Tuple[Optional[str], Optional[str]]: A 2-tuple containing:
                - direct_url (str or None): The direct downloadable link if resolved.
                - error_message (str or None): Error description if extraction failed.
        """
        pass
