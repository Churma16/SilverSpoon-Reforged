import os
import sys
from unittest.mock import MagicMock, patch
import pytest

from core.download_manager import DownloadManager as CoreDownloadManager
from core.types import TaskStatus
from downloader import (
    calculate_speed,
    SpeedTracker,
    DownloadManager,
    CLIDownloadManager,
    main,
)


@pytest.mark.unit
def test_calculate_speed_basic():
    # 1 MB (1048576 bytes) transferred in 1.0 second equals exactly 1.0 MB/s
    speed = calculate_speed(1048576, 1.0)
    assert pytest.approx(speed, 0.001) == 1.0

    # 5 MB transferred in 2.0 seconds equals 2.5 MB/s
    speed = calculate_speed(5 * 1024 * 1024, 2.0)
    assert pytest.approx(speed, 0.001) == 2.5


@pytest.mark.unit
def test_calculate_speed_edge_cases():
    # Zero bytes or zero/negative elapsed time returns 0.0 without division by zero
    assert calculate_speed(0, 1.0) == 0.0
    assert calculate_speed(1048576, 0.0) == 0.0
    assert calculate_speed(1048576, -1.0) == 0.0
    assert calculate_speed(-500, 1.0) == 0.0


@pytest.mark.unit
def test_speed_calculation_accumulates_interval_chunks_issue_6():
    """Verify Issue #6: Throughput is calculated from accumulated bytes rather than a single chunk.

    In the old bug, dividing a single 64 KB chunk by 1.0 elapsed second yielded ~0.06 MB/s (rendered 0.0 MB/s)
    even when ten 64 KB chunks arrived during that second (totaling 640 KB = ~0.61 MB/s).
    """
    chunk_size = 65536
    chunks_count = 10
    total_bytes = chunk_size * chunks_count
    elapsed_seconds = 1.0

    accumulated_speed = calculate_speed(total_bytes, elapsed_seconds)
    buggy_single_chunk_speed = calculate_speed(chunk_size, elapsed_seconds)

    expected_speed = (65536 * 10 / 1.0) / (1024 * 1024)
    assert pytest.approx(accumulated_speed, 0.001) == expected_speed
    assert accumulated_speed > buggy_single_chunk_speed
    assert pytest.approx(accumulated_speed, 0.01) == 0.625


@pytest.mark.unit
def test_speed_tracker_lifecycle():
    tracker = SpeedTracker(interval=0.5)
    base_time = 1000.0
    tracker.last_time = base_time

    # Add chunks during interval
    tracker.add_bytes(250 * 1024)
    tracker.add_bytes(250 * 1024)

    # Before interval elapsed (0.2s elapsed), speed should remain at initial 0.0
    speed_early = tracker.get_speed(current_time=base_time + 0.2)
    assert speed_early == 0.0

    # Once interval elapsed (0.5s elapsed, 500 KB transferred)
    speed_after_interval = tracker.get_speed(current_time=base_time + 0.5)
    expected_mb_s = (500 * 1024 / 0.5) / (1024 * 1024)
    assert pytest.approx(speed_after_interval, 0.001) == expected_mb_s

    # Next call without new bytes resets speed calculation
    speed_idle = tracker.get_speed(current_time=base_time + 1.0)
    assert speed_idle == 0.0

    # Reset test
    tracker.add_bytes(1000)
    tracker.reset()
    assert tracker.accumulated_bytes == 0
    assert tracker.current_speed == 0.0


@pytest.mark.unit
def test_cli_download_manager_init_from_list_and_file(tmp_path):
    links = [
        "https://fuckingfast.co/file1#archive.part1.rar",
        "https://fuckingfast.co/file2#archive.part2.rar",
    ]

    # Initialize with list
    manager_from_list = DownloadManager(
        links_file=links,
        max_workers=2,
        output_dir=str(tmp_path)
    )
    assert manager_from_list.total_links == 2
    assert len(manager_from_list.tasks) == 2
    assert isinstance(manager_from_list.core_manager, CoreDownloadManager)

    # Initialize with file
    links_file = tmp_path / "test_links.txt"
    links_file.write_text("\n".join(links) + "\n\n", encoding="utf-8")

    manager_from_file = CLIDownloadManager(
        links_file=str(links_file),
        max_workers=3,
        output_dir=str(tmp_path)
    )
    assert manager_from_file.total_links == 2
    assert len(manager_from_file.tasks) == 2
    assert manager_from_file.core_manager.max_workers == 3


@pytest.mark.unit
def test_cli_download_manager_reuses_core_download_manager_issue_8(tmp_path):
    """Verify Issue #8: CLI DownloadManager reuses core.download_manager.DownloadManager."""
    mock_scraper = MagicMock()
    mock_extractor = MagicMock()
    mock_rate_limiter = MagicMock()

    manager = DownloadManager(
        links_file=["https://fuckingfast.co/sample#Sample.rar"],
        output_dir=str(tmp_path),
        scraper=mock_scraper,
        extractor=mock_extractor,
        rate_limiter=mock_rate_limiter,
    )

    assert isinstance(manager.core_manager, CoreDownloadManager)
    assert manager.core_manager.scraper == mock_scraper
    assert manager.core_manager.extractor == mock_extractor
    assert manager.core_manager.rate_limiter == mock_rate_limiter

    # Test extract_direct_url delegation
    mock_extractor.extract_direct_url.return_value = ("https://direct.cdn/file.rar", None)
    extracted_url = manager.extract_direct_url("https://fuckingfast.co/sample#Sample.rar")
    assert extracted_url == "https://direct.cdn/file.rar"
    mock_extractor.extract_direct_url.assert_called_once()


@pytest.mark.unit
def test_download_file_success_and_failure(tmp_path):
    link_success = "https://fuckingfast.co/good#Good.rar"
    link_fail = "https://fuckingfast.co/bad#Bad.rar"

    manager = DownloadManager(
        links_file=[link_success, link_fail],
        output_dir=str(tmp_path)
    )

    def mock_download_worker(task):
        if task.link == link_success:
            task.status = TaskStatus.FINISHED
            task.progress = 100.0
        else:
            task.status = TaskStatus.FAILED
            task.error_message = "Mock connection failure"

    manager.core_manager.download_worker = MagicMock(side_effect=mock_download_worker)

    # Test success download
    success_result = manager.download_file(link_success)
    assert success_result is True
    assert manager.completed_links == 1
    assert link_success not in manager.failed_links

    # Test failure download
    fail_result = manager.download_file(link_fail)
    assert fail_result is False
    assert link_fail in manager.failed_links
    assert manager.completed_links == 1


@pytest.mark.unit
def test_cli_run_orchestration(tmp_path, monkeypatch):
    links = [
        "https://fuckingfast.co/part1#Game.part1.rar",
        "https://fuckingfast.co/part2#Game.part2.rar",
    ]

    manager = DownloadManager(links_file=links, output_dir=str(tmp_path), max_workers=2)

    def mock_download_worker(task):
        task.status = TaskStatus.FINISHED
        task.progress = 100.0

    manager.core_manager.download_worker = MagicMock(side_effect=mock_download_worker)

    manager.run()

    assert manager.completed_links == 2
    assert len(manager.failed_links) == 0
    assert manager.core_manager.is_running is False


@pytest.mark.unit
def test_cli_main_entrypoint(tmp_path, monkeypatch):
    links_file = tmp_path / "links.txt"
    links_file.write_text("https://fuckingfast.co/main#Main.rar\n", encoding="utf-8")

    test_args = ["downloader.py", str(links_file), "--workers", "2", "--limit", "500"]
    monkeypatch.setattr(sys, "argv", test_args)

    with patch("downloader.DownloadManager.run") as mock_run:
        main()
        mock_run.assert_called_once()
