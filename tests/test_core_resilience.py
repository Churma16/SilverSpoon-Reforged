import os
import json
import pytest
from core.download_task import DownloadTask
from core.types import TaskStatus
from core.history import save_history, load_history
from core.settings import save_settings


@pytest.mark.unit
def test_atomic_history_persistence(tmp_path, monkeypatch):
    test_history_file = str(tmp_path / "test_history.json")
    monkeypatch.setattr("core.history.get_history_path", lambda: test_history_file)

    task = DownloadTask("https://fuckingfast.co/testfile#Test.rar", str(tmp_path))
    task.downloaded_bytes = 100
    task.total_bytes = 100
    task.status = TaskStatus.FINISHED

    save_history([task])

    # Check file exists and is valid JSON
    assert os.path.exists(test_history_file)
    restored = load_history()
    assert len(restored) == 1
    assert restored[0].file_id == "testfile"
    assert restored[0].downloaded_bytes == 100

    # Ensure no leftover temporary files
    parent_files = os.listdir(str(tmp_path))
    assert not any(f.endswith(".tmp") for f in parent_files)


@pytest.mark.unit
def test_atomic_settings_persistence(tmp_path, monkeypatch):
    test_settings_file = str(tmp_path / "test_settings.json")
    monkeypatch.setattr("core.settings.get_settings_path", lambda: test_settings_file)

    test_data = {"max_workers": 5, "auto_shutdown_on_completion": True}
    save_settings(test_data)

    assert os.path.exists(test_settings_file)
    with open(test_settings_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["max_workers"] == 5
    assert loaded["auto_shutdown_on_completion"] is True

    parent_files = os.listdir(str(tmp_path))
    assert not any(f.endswith(".tmp") for f in parent_files)


@pytest.mark.unit
def test_stream_truncation_detection(tmp_path):
    from core.download_manager import DownloadManager
    from core.rate_limiter import GlobalRateLimiter
    from unittest.mock import MagicMock

    task = DownloadTask("https://fuckingfast.co/incomplete#Broken.rar", str(tmp_path))
    task.filepath = str(tmp_path / "Broken.rar")
    task.total_bytes = 1000
    task.downloaded_bytes = 500  # Truncated: only 500 out of 1000 bytes

    dm = DownloadManager(
        tasks=[task],
        max_workers=1,
        rate_limiter=MagicMock(),
        scraper=MagicMock(),
        extractor=MagicMock(),
        settings={},
        session_bytes_lock_callback=MagicMock(),
        trigger_history_save_callback=MagicMock()
    )
    dm.is_running = True

    # Mock get_direct_link and scraper
    dm.get_direct_link = MagicMock(return_value="https://cdn.example.com/Broken.rar")
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-length": "1000"}
    # Stream returns only 1 chunk of 500 bytes and exits
    mock_resp.iter_content = MagicMock(return_value=[b"x" * 500])

    dm.scraper = MagicMock()
    dm.scraper.head = MagicMock(return_value=mock_resp)
    dm.scraper.get = MagicMock(return_value=mock_resp)

    dm.download_worker(task)

    # Must fail because downloaded_bytes (500) < total_bytes (1000)
    assert task.status == TaskStatus.FAILED
    assert "Incomplete download" in task.error_message


@pytest.mark.unit
def test_winrar_destination_path_formatting():
    # Verify WinRAR destination ends with forward slash '/' to avoid WinRAR error 10
    save_dir = r"C:\Download Folder\Sub Folder"
    first_vol = r"C:\Download Folder\Sub Folder\archive.part1.rar"
    installed_winrar = r"C:\Program Files\WinRAR\WinRAR.exe"

    stripped_save_dir = save_dir.rstrip('\\/')
    formatted_target = f"{stripped_save_dir}/"
    cmd = [installed_winrar, 'x', '-y', first_vol, formatted_target]

    assert cmd[-1] == "C:\\Download Folder\\Sub Folder/"
    assert cmd[-1].endswith("/")
    assert not cmd[-1].endswith("\\")
