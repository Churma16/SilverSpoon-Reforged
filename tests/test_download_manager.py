import os
import tempfile
import unittest
from unittest.mock import MagicMock
from core.download_task import DownloadTask
from core.download_manager import DownloadManager
from core.types import TaskStatus


class MockResponse:
    def __init__(self, status_code=200, headers=None, content=b"", chunks=None):
        self.status_code = status_code
        self.headers = headers or {}
        if chunks is not None:
            self.chunks = chunks
        else:
            self.chunks = [content] if content else [b""]
        self.closed = False

    def iter_content(self, chunk_size=65536):
        for chunk in self.chunks:
            yield chunk

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


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
        with open(task.filepath, "wb") as f:
            f.write(b"x" * 2000)

        self.extractor.extract_direct_url.return_value = ("https://direct.example.com/sample.bin", None)
        head_response = MagicMock()
        head_response.headers = {"content-length": "1000"}
        self.scraper.head.return_value = head_response

        get_response = MockResponse(status_code=200, headers={"content-length": "1000"}, content=b"y" * 1000)
        self.scraper.get.return_value = get_response

        self.manager.download_worker(task)

        self.assertEqual(task.status, TaskStatus.FINISHED)
        self.assertEqual(task.progress, 100)
        self.scraper.get.assert_called_with("https://direct.example.com/sample.bin", stream=True, headers={})
        self.assertEqual(os.path.getsize(task.filepath), 1000)
        self.assertTrue(get_response.closed)

    def test_http_416_recovery_falls_back_to_byte_zero(self):
        task = DownloadTask("https://fuckingfast.co/test#sample416.bin", self.save_dir, folder_name="batch")
        os.makedirs(task.save_dir, exist_ok=True)
        with open(task.filepath, "wb") as f:
            f.write(b"x" * 500)

        self.extractor.extract_direct_url.return_value = ("https://direct.example.com/sample416.bin", None)
        head_response = MagicMock()
        head_response.headers = {"content-length": "1000"}
        self.scraper.head.return_value = head_response

        resp_416 = MockResponse(status_code=416)
        resp_200 = MockResponse(status_code=200, headers={"content-length": "1000"}, content=b"z" * 1000)
        self.scraper.get.side_effect = [resp_416, resp_200]

        self.manager.download_worker(task)

        self.assertEqual(task.status, TaskStatus.FINISHED)
        self.assertEqual(task.progress, 100)
        self.assertEqual(self.scraper.get.call_count, 2)
        self.assertEqual(self.scraper.get.call_args_list[1][1]["headers"], {})
        self.assertEqual(os.path.getsize(task.filepath), 1000)
        self.assertTrue(resp_416.closed)
        self.assertTrue(resp_200.closed)

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
        self.assertTrue(resp_206.closed)

    def test_response_closed_when_download_paused_midway(self):
        task = DownloadTask("https://fuckingfast.co/test#pause.bin", self.save_dir, folder_name="batch")
        os.makedirs(task.save_dir, exist_ok=True)

        self.extractor.extract_direct_url.return_value = ("https://direct.example.com/pause.bin", None)
        head_response = MagicMock()
        head_response.headers = {"content-length": "1000"}
        self.scraper.head.return_value = head_response

        class PausingResponse(MockResponse):
            def iter_content(self, chunk_size=65536):
                yield b"part1"
                task.pause_flag = True
                yield b"part2"

        resp = PausingResponse(status_code=200, headers={"content-length": "1000"})
        self.scraper.get.return_value = resp

        self.manager.download_worker(task)

        self.assertEqual(task.status, TaskStatus.PAUSED)
        self.assertTrue(resp.closed)

    def test_response_closed_when_download_cancelled_midway(self):
        task = DownloadTask("https://fuckingfast.co/test#cancel.bin", self.save_dir, folder_name="batch")
        os.makedirs(task.save_dir, exist_ok=True)

        self.extractor.extract_direct_url.return_value = ("https://direct.example.com/cancel.bin", None)
        head_response = MagicMock()
        head_response.headers = {"content-length": "1000"}
        self.scraper.head.return_value = head_response

        class CancellingResponse(MockResponse):
            def iter_content(self, chunk_size=65536):
                yield b"part1"
                task.cancel_flag = True
                yield b"part2"

        resp = CancellingResponse(status_code=200, headers={"content-length": "1000"})
        self.scraper.get.return_value = resp

        self.manager.download_worker(task)

        self.assertEqual(task.status, TaskStatus.CANCELLED)
        self.assertTrue(resp.closed)


if __name__ == "__main__":
    unittest.main()
