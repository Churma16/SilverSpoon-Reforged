from abc import ABC, abstractmethod
from typing import Optional, Tuple

class BaseExtractor(ABC):
    """
    Abstract base class for file host link extractors.
    """

    @abstractmethod
    def extract_direct_url(self, link: str, file_id: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract direct download URL from input link.
        Returns a tuple of (direct_url, error_message).
        """
        pass
