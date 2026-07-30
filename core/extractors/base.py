from abc import ABC, abstractmethod

class BaseExtractor(ABC):
    """
    Abstract base class for file host link extractors.
    """

    @abstractmethod
    def extract_direct_url(self, link: str) -> str | None:
        """
        Extract direct download URL from input link.
        Returns the resolved direct URL string or None if failed.
        """
        pass
