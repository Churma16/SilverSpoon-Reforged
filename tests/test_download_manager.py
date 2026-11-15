import os
import tempfile
import unittest
from unittest.mock import MagicMock
from core.download_task import DownloadTask
from core.download_manager import DownloadManager
from core.types import TaskStatus


class MockResponse:
    def __init__(self, status_code=200, headers=None, content=b""):
        self.status_code = status_code
        self.headers = headers or {}
        self.content = content

    def iter_content(self, chunk_size=65536):
        yield self.content

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class TestDownloadResumptionAnd416Recovery(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.save_dir = self.test_dir.name
        self.rate_limiter = MagicMock()
        self.scraper = MagicMock()
        self.extractor = MagicMock()
        self.settings = {"download_speed_limit": 0}
        self.tasks = []
        self.manager = DownloadManager(
            tasks=self.tasks,
            max_workers=1,
            rate_limiter=self.rate_limiter,
            scraper=self.scraper,
            extractor=self.extractor,
            settings=self.settings,
            session_bytes_lock_callback=None,
            trigger_history_save_callback=MagicMock()
        )
        self.manager.is_running = True

    def tearDown(self):
        self.test_dir.cleanup()

    def test_oversized_local_file_resets_to_byte_zero(self):
        task = DownloadTask("https://fuckingfast.co/test#sample.bin", self.save_dir, folder_name="batch")
        os.makedirs(task.save_dir, exist_ok=True)
        # Create an oversized local file (2000 bytes)
        with open(task.filepath, "wb") as f:
            f.write(b"x" * 2000)

        self.extractor.extract_direct_url.return_value = ("https://direct.example.com/sample.bin", None)
        # Remote content-length is 1000 bytes (smaller than local 2000 bytes)
        head_response = MagicMock()
        head_response.headers = {"content-length": "1000"}
        self.scraper.head.return_value = head_response

        # GET should be called without Range header (bytes 0-), returning 200
        get_response = MockResponse(status_code=200, headers={"content-length": "1000"}, content=b"y" * 1000)
        self.scraper.get.return_value = get_response

        self.manager.download_worker(task)

        self.assertEqual(task.status, TaskStatus.FINISHED)
        self.assertEqual(task.progress, 100)
        # Scraper GET must have been called with empty headers (not Range)
        self.scraper.get.assert_called_with("https://direct.example.com/sample.bin", stream=True, headers={})
        # The file on disk should now be overwritten to 1000 bytes
        self.assertEqual(os.path.getsize(task.filepath), 1000)

    def test_http_416_recovery_falls_back_to_byte_zero(self):
        task = DownloadTask("https://fuckingfast.co/test#sample416.bin", self.save_dir, folder_name="batch")
        os.makedirs(task.save_dir, exist_ok=True)
        # Create partial local file (500 bytes)
        with open(task.filepath, "wb") as f:
            f.write(b"x" * 500)

        self.extractor.extract_direct_url.return_value = ("https://direct.example.com/sample416.bin", None)
        head_response = MagicMock()
        head_response.headers = {"content-length": "1000"}
        self.scraper.head.return_value = head_response

        # First GET with Range returns 416, fallback GET without Range returns 200
        resp_416 = MockResponse(status_code=416)
        resp_200 = MockResponse(status_code=200, headers={"content-length": "1000"}, content=b"z" * 1000)
        self.scraper.get.side_effect = [resp_416, resp_200]

        self.manager.download_worker(task)

        self.assertEqual(task.status, TaskStatus.FINISHED)
        self.assertEqual(task.progress, 100)
        self.assertEqual(self.scraper.get.call_count, 2)
        # Second call must be without Range header
        self.assertEqual(self.scraper.get.call_args_list[1][1]["headers"], {})
        # The file on disk should be written from 0 (1000 bytes)
        self.assertEqual(os.path.getsize(task.filepath), 1000)

    def test_valid_partial_download_resumes_with_range_header(self):
        task = DownloadTask("https://fuckingfast.co/test#resume.bin", self.save_dir, folder_name="batch")
        os.makedirs(task.save_dir, exist_ok=True)
        with open(task.filepath, "wb") as f:
            f.write(b"a" * 400)

        self.extractor.extract_direct_url.return_value = ("https://direct.example.com/resume.bin", None)
        head_response = MagicMock()
        head_response.headers = {"content-length": "1000"}
        self.scraper.head.return_value = head_response

        resp_206 = MockResponse(status_code=206, headers={"content-length": "600"}, content=b"b" * 600)
        self.scraper.get.return_value = resp_206

        self.manager.download_worker(task)

        self.assertEqual(task.status, TaskStatus.FINISHED)
        self.scraper.get.assert_called_with(
            "https://direct.example.com/resume.bin",
            stream=True,
            headers={"Range": "bytes=400-"}
        )
        self.assertEqual(os.path.getsize(task.filepath), 1000)


if __name__ == "__main__":
    unittest.main()
