import os
import json
import tempfile
import threading
import unittest
from core.download_task import DownloadTask
from core.history import load_history, save_history


class TestHistoryPersistence(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.history_file = os.path.join(self.test_dir.name, "test_history.json")
        self.base_download_dir = os.path.join(self.test_dir.name, "downloads")

    def tearDown(self):
        self.test_dir.cleanup()

    def test_save_and_load_roundtrip(self):
        task1 = DownloadTask("https://fuckingfast.co/abc123#File1.rar", self.base_download_dir)
        task1.downloaded_bytes = 1024
        task1.total_bytes = 2048
        task1.progress = 50.0

        task2 = DownloadTask("https://fuckingfast.co/xyz789#File2.rar", self.base_download_dir)

        success = save_history([task1, task2], history_path=self.history_file)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(self.history_file))
        self.assertFalse(os.path.exists(f"{self.history_file}.tmp"))

        loaded = load_history(history_path=self.history_file)
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0].link, task1.link)
        self.assertEqual(loaded[0].downloaded_bytes, 1024)
        self.assertEqual(loaded[1].link, task2.link)

    def test_load_nonexistent_file_returns_empty(self):
        non_existent = os.path.join(self.test_dir.name, "non_existent.json")
        loaded = load_history(history_path=non_existent)
        self.assertEqual(loaded, [])

    def test_load_corrupt_json_returns_empty(self):
        with open(self.history_file, "w", encoding="utf-8") as f:
            f.write("{invalid json content---")

        loaded = load_history(history_path=self.history_file)
        self.assertEqual(loaded, [])

    def test_concurrent_save_threads_integrity(self):
        num_threads = 10
        errors = []

        def worker(thread_idx):
            try:
                task = DownloadTask(
                    f"https://fuckingfast.co/link_{thread_idx}#File_{thread_idx}.rar",
                    self.base_download_dir
                )
                task.downloaded_bytes = thread_idx * 100
                save_history([task], history_path=self.history_file)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        self.assertTrue(os.path.exists(self.history_file))
        self.assertFalse(os.path.exists(f"{self.history_file}.tmp"))

        # File must be valid JSON readable by load_history
        loaded = load_history(history_path=self.history_file)
        self.assertEqual(len(loaded), 1)
        self.assertTrue(loaded[0].link.startswith("https://fuckingfast.co/link_"))


if __name__ == "__main__":
    unittest.main()
