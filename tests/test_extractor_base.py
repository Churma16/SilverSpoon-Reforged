import unittest
from typing import Optional, Tuple
from core.extractors.base import BaseExtractor


class DummyExtractor(BaseExtractor):
    def extract_direct_url(self, link: str, file_id: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        if "good_link" in link:
            return f"https://direct.example.com/{file_id or 'file'}", None
        return None, "File not found"


class TestBaseExtractor(unittest.TestCase):
    def test_cannot_instantiate_base_extractor_directly(self):
        with self.assertRaises(TypeError):
            BaseExtractor()

    def test_concrete_extractor_returns_tuple_roundtrip(self):
        extractor = DummyExtractor()
        url, err = extractor.extract_direct_url("https://example.com/good_link", file_id="abc")
        self.assertEqual(url, "https://direct.example.com/abc")
        self.assertIsNone(err)

        failed_url, failed_err = extractor.extract_direct_url("https://example.com/bad_link")
        self.assertIsNone(failed_url)
        self.assertEqual(failed_err, "File not found")


if __name__ == "__main__":
    unittest.main()
