import os
import time
import threading
import pytest
from unittest.mock import MagicMock

from core.download_manager import DownloadManager
from core.download_task import DownloadTask
from core.rate_limiter import GlobalRateLimiter
from core.types import TaskStatus


@pytest.mark.unit
def test_download_resumption_sends_correct_http_206_range_header(tmp_path):
    # Setup initial partial file on disk
    target_filename = "Cyberpunk_2077.part1.rar"
    partial_file_path = str(tmp_path / target_filename)
    initial_bytes_content = b"P" * 512
    with open(partial_file_path, "wb") as file_stream:
        file_stream.write(initial_bytes_content)

    assert os.path.getsize(partial_file_path) == 512

    download_task_instance = DownloadTask(
        f"https://fuckingfast.co/c7o9muwfdksh#{target_filename}",
        str(tmp_path)
    )
    download_task_instance.filepath = partial_file_path

    # Mock direct link extractor
    mock_extractor_client = MagicMock()
    mock_extractor_client.extract_direct_url.return_value = ("https://cdn.example.com/download/file", None)

    # Mock HEAD response reporting total file size of 1024 bytes
    mock_head_response = MagicMock()
    mock_head_response.headers = {"content-length": "1024"}

    # Mock GET response (HTTP 206 Partial Content) delivering remaining 512 bytes
    remaining_bytes_content = b"Q" * 512
    mock_get_response = MagicMock()
    mock_get_response.status_code = 206
    mock_get_response.headers = {"content-length": "512"}
    mock_get_response.iter_content.return_value = [remaining_bytes_content]

    mock_scraper_client = MagicMock()
    mock_scraper_client.head.return_value = mock_head_response
    mock_scraper_client.get.return_value = mock_get_response

    mock_history_save_callback = MagicMock()
    mock_session_bytes_callback = MagicMock()
    mock_rate_limiter_instance = MagicMock()

    download_manager_instance = DownloadManager(
        tasks=[download_task_instance],
        max_workers=1,
        rate_limiter=mock_rate_limiter_instance,
        scraper=mock_scraper_client,
        extractor=mock_extractor_client,
        settings={"download_speed_limit": 0},
        session_bytes_lock_callback=mock_session_bytes_callback,
        trigger_history_save_callback=mock_history_save_callback
    )
    download_manager_instance.is_running = True

    download_manager_instance.download_worker(download_task_instance)

    # Verify Range header was sent with existing offset
    mock_scraper_client.get.assert_called_once_with(
        "https://cdn.example.com/download/file",
        stream=True,
        headers={"Range": "bytes=512-"},
        timeout=(10, 30)
    )

    # Verify task state and data completion
    assert download_task_instance.status == TaskStatus.FINISHED
    assert download_task_instance.downloaded_bytes == 1024
    assert download_task_instance.total_bytes == 1024
    assert download_task_instance.progress == 100.0
    assert download_task_instance.error_message == ""

    # Verify persisted content on disk contains combined stream
    with open(partial_file_path, "rb") as file_stream:
        persisted_file_content = file_stream.read()
    assert persisted_file_content == initial_bytes_content + remaining_bytes_content
    assert len(persisted_file_content) == 1024

    mock_history_save_callback.assert_called()


@pytest.mark.unit
def test_download_resumption_fallback_when_server_ignores_range_and_returns_200(tmp_path):
    target_filename = "Game_Archive.iso"
    partial_file_path = str(tmp_path / target_filename)
    stale_initial_bytes = b"STALE" * 60
    with open(partial_file_path, "wb") as file_stream:
        file_stream.write(stale_initial_bytes)

    initial_size_on_disk = len(stale_initial_bytes)
    assert initial_size_on_disk == 300

    download_task_instance = DownloadTask(
        f"https://fuckingfast.co/c7o9muwfdksh#{target_filename}",
        str(tmp_path)
    )
    download_task_instance.filepath = partial_file_path

    mock_extractor_client = MagicMock()
    mock_extractor_client.extract_direct_url.return_value = ("https://cdn.example.com/file.iso", None)

    mock_head_response = MagicMock()
    mock_head_response.headers = {"content-length": "1000"}

    # Server does not support resume, responds with HTTP 200 and full 1000 bytes
    fresh_full_payload = b"F" * 1000
    mock_get_response = MagicMock()
    mock_get_response.status_code = 200
    mock_get_response.headers = {"content-length": "1000"}
    mock_get_response.iter_content.return_value = [fresh_full_payload]

    mock_scraper_client = MagicMock()
    mock_scraper_client.head.return_value = mock_head_response
    mock_scraper_client.get.return_value = mock_get_response

    download_manager_instance = DownloadManager(
        tasks=[download_task_instance],
        max_workers=1,
        rate_limiter=MagicMock(),
        scraper=mock_scraper_client,
        extractor=mock_extractor_client,
        settings={"download_speed_limit": 0},
        session_bytes_lock_callback=MagicMock(),
        trigger_history_save_callback=MagicMock()
    )
    download_manager_instance.is_running = True

    download_manager_instance.download_worker(download_task_instance)

    # Scraper initially requested with Range header
    mock_scraper_client.get.assert_called_once_with(
        "https://cdn.example.com/file.iso",
        stream=True,
        headers={"Range": "bytes=300-"},
        timeout=(10, 30)
    )

    # Because status was 200, file must be overwritten in wb mode from offset 0
    assert download_task_instance.status == TaskStatus.FINISHED
    assert download_task_instance.downloaded_bytes == len(fresh_full_payload)

    with open(partial_file_path, "rb") as file_stream:
        persisted_content = file_stream.read()
    assert persisted_content == fresh_full_payload
    assert not persisted_content.startswith(stale_initial_bytes)


@pytest.mark.unit
def test_download_resumption_handles_http_416_range_not_satisfiable(tmp_path):
    target_filename = "Texture_Pack.zip"
    partial_file_path = str(tmp_path / target_filename)
    with open(partial_file_path, "wb") as file_stream:
        file_stream.write(b"Z" * 700)

    download_task_instance = DownloadTask(
        f"https://fuckingfast.co/c7o9muwfdksh#{target_filename}",
        str(tmp_path)
    )
    download_task_instance.filepath = partial_file_path

    mock_extractor_client = MagicMock()
    mock_extractor_client.extract_direct_url.return_value = ("https://cdn.example.com/texture.zip", None)

    mock_head_response = MagicMock()
    mock_head_response.headers = {"content-length": "800"}

    # First GET returns 416 (Range Not Satisfiable)
    mock_first_response = MagicMock()
    mock_first_response.status_code = 416

    # Second GET retries from scratch and returns 200 with full content
    complete_download_content = b"NEW_TEXTURE_DATA" * 50
    assert len(complete_download_content) == 800
    mock_second_response = MagicMock()
    mock_second_response.status_code = 200
    mock_second_response.headers = {"content-length": str(len(complete_download_content))}
    mock_second_response.iter_content.return_value = [complete_download_content]

    mock_scraper_client = MagicMock()
    mock_scraper_client.head.return_value = mock_head_response
    mock_scraper_client.get.side_effect = [mock_first_response, mock_second_response]

    download_manager_instance = DownloadManager(
        tasks=[download_task_instance],
        max_workers=1,
        rate_limiter=MagicMock(),
        scraper=mock_scraper_client,
        extractor=mock_extractor_client,
        settings={"download_speed_limit": 0},
        session_bytes_lock_callback=MagicMock(),
        trigger_history_save_callback=MagicMock()
    )
    download_manager_instance.is_running = True

    download_manager_instance.download_worker(download_task_instance)

    # Scraper should have been called twice: first with Range, then without Range
    assert mock_scraper_client.get.call_count == 2
    mock_scraper_client.get.assert_any_call(
        "https://cdn.example.com/texture.zip",
        stream=True,
        headers={"Range": "bytes=700-"},
        timeout=(10, 30)
    )
    mock_scraper_client.get.assert_any_call(
        "https://cdn.example.com/texture.zip",
        stream=True,
        timeout=(10, 30)
    )

    assert download_task_instance.status == TaskStatus.FINISHED
    assert download_task_instance.downloaded_bytes == len(complete_download_content)

    with open(partial_file_path, "rb") as file_stream:
        persisted_content = file_stream.read()
    assert persisted_content == complete_download_content


@pytest.mark.unit
def test_download_worker_skips_network_when_file_already_completed(tmp_path):
    target_filename = "Completed_Game.rar"
    completed_file_path = str(tmp_path / target_filename)
    completed_file_bytes = b"COMPLETE_FILE_DATA" * 50
    with open(completed_file_path, "wb") as file_stream:
        file_stream.write(completed_file_bytes)

    total_file_size = len(completed_file_bytes)

    download_task_instance = DownloadTask(
        f"https://fuckingfast.co/c7o9muwfdksh#{target_filename}",
        str(tmp_path)
    )
    download_task_instance.filepath = completed_file_path

    mock_extractor_client = MagicMock()
    mock_extractor_client.extract_direct_url.return_value = ("https://cdn.example.com/file.rar", None)

    mock_head_response = MagicMock()
    mock_head_response.headers = {"content-length": str(total_file_size)}

    mock_scraper_client = MagicMock()
    mock_scraper_client.head.return_value = mock_head_response

    download_manager_instance = DownloadManager(
        tasks=[download_task_instance],
        max_workers=1,
        rate_limiter=MagicMock(),
        scraper=mock_scraper_client,
        extractor=mock_extractor_client,
        settings={"download_speed_limit": 0},
        session_bytes_lock_callback=MagicMock(),
        trigger_history_save_callback=MagicMock()
    )
    download_manager_instance.is_running = True

    download_manager_instance.download_worker(download_task_instance)

    # HEAD request was checked, but GET must never be called since initial_size == total_size
    mock_scraper_client.head.assert_called_once()
    mock_scraper_client.get.assert_not_called()

    assert download_task_instance.status == TaskStatus.FINISHED
    assert download_task_instance.progress == 100.0
    assert download_task_instance.downloaded_bytes == total_file_size


@pytest.mark.unit
def test_download_worker_finishes_immediately_if_already_complete_on_disk(tmp_path):
    target_filename = "PreExisting_Archive.rar"
    existing_file_path = str(tmp_path / target_filename)
    payload_content = b"PRE_EXISTING_DATA" * 64
    with open(existing_file_path, "wb") as file_stream:
        file_stream.write(payload_content)

    total_file_size = len(payload_content)

    download_task_instance = DownloadTask(
        f"https://fuckingfast.co/c7o9muwfdksh#{target_filename}",
        str(tmp_path)
    )
    download_task_instance.filepath = existing_file_path
    download_task_instance.total_bytes = total_file_size
    download_task_instance.progress = 100.0

    mock_extractor_client = MagicMock()
    mock_scraper_client = MagicMock()
    mock_history_save_callback = MagicMock()

    download_manager_instance = DownloadManager(
        tasks=[download_task_instance],
        max_workers=1,
        rate_limiter=MagicMock(),
        scraper=mock_scraper_client,
        extractor=mock_extractor_client,
        settings={"download_speed_limit": 0},
        session_bytes_lock_callback=MagicMock(),
        trigger_history_save_callback=mock_history_save_callback
    )
    download_manager_instance.is_running = True

    download_manager_instance.download_worker(download_task_instance)

    # Must finish immediately without any network calls or extraction
    mock_extractor_client.extract_direct_url.assert_not_called()
    mock_scraper_client.head.assert_not_called()
    mock_scraper_client.get.assert_not_called()

    assert download_task_instance.status == TaskStatus.FINISHED
    assert download_task_instance.downloaded_bytes == total_file_size
    assert download_task_instance.progress == 100.0
    mock_history_save_callback.assert_called_once()


@pytest.mark.unit
def test_download_worker_invokes_rate_limiter_and_session_lock(tmp_path):
    target_filename = "Stream_Throttled_File.bin"
    destination_file_path = str(tmp_path / target_filename)

    download_task_instance = DownloadTask(
        f"https://fuckingfast.co/c7o9muwfdksh#{target_filename}",
        str(tmp_path)
    )
    download_task_instance.filepath = destination_file_path

    mock_extractor_client = MagicMock()
    mock_extractor_client.extract_direct_url.return_value = ("https://cdn.example.com/stream.bin", None)

    mock_head_response = MagicMock()
    mock_head_response.headers = {"content-length": "2048"}

    chunk_first = b"A" * 1024
    chunk_second = b"B" * 1024
    mock_get_response = MagicMock()
    mock_get_response.status_code = 200
    mock_get_response.headers = {"content-length": "2048"}
    mock_get_response.iter_content.return_value = [chunk_first, chunk_second]

    mock_scraper_client = MagicMock()
    mock_scraper_client.head.return_value = mock_head_response
    mock_scraper_client.get.return_value = mock_get_response

    mock_rate_limiter_instance = MagicMock()
    mock_session_bytes_callback = MagicMock()

    download_manager_instance = DownloadManager(
        tasks=[download_task_instance],
        max_workers=1,
        rate_limiter=mock_rate_limiter_instance,
        scraper=mock_scraper_client,
        extractor=mock_extractor_client,
        settings={"download_speed_limit": 512},
        session_bytes_lock_callback=mock_session_bytes_callback,
        trigger_history_save_callback=MagicMock()
    )
    download_manager_instance.is_running = True

    download_manager_instance.download_worker(download_task_instance)

    # Verify rate limiter was invoked per chunk for responsiveness, and session lock callback was batched
    assert mock_rate_limiter_instance.consume.call_count == 2
    mock_rate_limiter_instance.consume.assert_any_call(1024, 512)

    assert mock_session_bytes_callback.call_count == 1
    mock_session_bytes_callback.assert_called_once_with(2048)

    assert download_task_instance.status == TaskStatus.FINISHED
    assert download_task_instance.downloaded_bytes == 2048


@pytest.mark.unit
def test_rate_limiter_bypasses_when_limit_is_zero_or_negative():
    rate_limiter_instance = GlobalRateLimiter()

    # Consuming with limit_kb <= 0 should return immediately without mutating tokens
    initial_tokens_value = rate_limiter_instance.tokens
    rate_limiter_instance.consume(chunk_bytes=1048576, limit_kb=0)
    assert rate_limiter_instance.tokens == initial_tokens_value

    rate_limiter_instance.consume(chunk_bytes=1048576, limit_kb=-50)
    assert rate_limiter_instance.tokens == initial_tokens_value


@pytest.mark.unit
def test_rate_limiter_throttles_fractional_tokens_across_multiple_chunks(monkeypatch):
    simulated_clock_time = [2000.0]
    sleep_durations_recorded = []

    def mock_time():
        return simulated_clock_time[0]

    def mock_sleep(duration_seconds):
        sleep_durations_recorded.append(duration_seconds)
        simulated_clock_time[0] += duration_seconds

    monkeypatch.setattr(time, "time", mock_time)
    monkeypatch.setattr(time, "sleep", mock_sleep)

    rate_limiter_instance = GlobalRateLimiter()

    # Limit: 4 KB/s = 4096 bytes/sec
    configured_limit_kb = 4
    half_chunk_byte_size = 2048

    # First consumption: needs 2048 / 4096 = 0.5s wait
    rate_limiter_instance.consume(half_chunk_byte_size, configured_limit_kb)
    assert len(sleep_durations_recorded) == 1
    assert sleep_durations_recorded[0] == pytest.approx(0.5, rel=1e-3)
    assert simulated_clock_time[0] == pytest.approx(2000.5, rel=1e-3)

    # Second consumption: needs another 0.5s wait
    rate_limiter_instance.consume(half_chunk_byte_size, configured_limit_kb)
    assert len(sleep_durations_recorded) == 2
    assert sleep_durations_recorded[1] == pytest.approx(0.5, rel=1e-3)
    assert simulated_clock_time[0] == pytest.approx(2001.0, rel=1e-3)
    assert sum(sleep_durations_recorded) == pytest.approx(1.0, rel=1e-3)


@pytest.mark.unit
def test_rate_limiter_throttles_token_consumption_accurately(monkeypatch):
    simulated_clock_time = [1000.0]
    sleep_durations_recorded = []

    def mock_time():
        return simulated_clock_time[0]

    def mock_sleep(duration_seconds):
        sleep_durations_recorded.append(duration_seconds)
        simulated_clock_time[0] += duration_seconds

    monkeypatch.setattr(time, "time", mock_time)
    monkeypatch.setattr(time, "sleep", mock_sleep)

    rate_limiter_instance = GlobalRateLimiter()

    # Limit: 10 KB/s = 10 * 1024 = 10240 bytes/sec
    configured_limit_kb = 10
    chunk_byte_size = 10240

    # Initial consumption should require waiting ~1.0 second because initial tokens are 0.0
    rate_limiter_instance.consume(chunk_byte_size, configured_limit_kb)

    assert len(sleep_durations_recorded) == 1
    assert sleep_durations_recorded[0] == pytest.approx(1.0, rel=1e-3)
    assert simulated_clock_time[0] == pytest.approx(1001.0, rel=1e-3)

    # Immediately consuming another chunk requires waiting another 1.0 second
    rate_limiter_instance.consume(chunk_byte_size, configured_limit_kb)

    assert len(sleep_durations_recorded) == 2
    assert sleep_durations_recorded[1] == pytest.approx(1.0, rel=1e-3)
    assert simulated_clock_time[0] == pytest.approx(1002.0, rel=1e-3)


@pytest.mark.unit
def test_rate_limiter_burst_capacity_is_capped_at_max_tokens(monkeypatch):
    simulated_clock_time = [1000.0]
    sleep_durations_recorded = []

    def mock_time():
        return simulated_clock_time[0]

    def mock_sleep(duration_seconds):
        sleep_durations_recorded.append(duration_seconds)
        simulated_clock_time[0] += duration_seconds

    monkeypatch.setattr(time, "time", mock_time)
    monkeypatch.setattr(time, "sleep", mock_sleep)

    rate_limiter_instance = GlobalRateLimiter()

    # Limit: 20 KB/s = 20480 bytes/s
    configured_limit_kb = 20
    chunk_byte_size = 4096

    # Advance clock by 100 seconds to generate potential token surplus
    simulated_clock_time[0] += 100.0

    rate_limiter_instance.consume(chunk_byte_size, configured_limit_kb)

    # Because max_tokens = max(20480, 4096 * 2) = 20480,
    # tokens were capped at 20480. Consuming 4096 leaves 20480 - 4096 = 16384.
    # No sleep should have occurred.
    assert len(sleep_durations_recorded) == 0
    assert rate_limiter_instance.tokens == pytest.approx(16384.0, rel=1e-3)


@pytest.mark.unit
def test_rate_limiter_multithreaded_concurrency():
    rate_limiter_instance = GlobalRateLimiter()
    configured_limit_kb = 50000  # High limit so workers don't block for long
    total_chunks_per_thread = 20
    chunk_size = 1024

    threads_list = []
    execution_errors = []

    def worker_routine():
        try:
            for _ in range(total_chunks_per_thread):
                rate_limiter_instance.consume(chunk_size, configured_limit_kb)
        except Exception as error_exception:
            execution_errors.append(error_exception)

    for _ in range(4):
        thread = threading.Thread(target=worker_routine)
        threads_list.append(thread)
        thread.start()

    for thread in threads_list:
        thread.join(timeout=2.0)

    assert len(execution_errors) == 0


@pytest.mark.unit
def test_download_worker_batches_writes_and_session_lock_callback(tmp_path):
    target_filename = "Batched_Write_File.bin"
    destination_file_path = str(tmp_path / target_filename)

    download_task_instance = DownloadTask(
        f"https://fuckingfast.co/c7o9muwfdksh#{target_filename}",
        str(tmp_path)
    )
    download_task_instance.filepath = destination_file_path

    mock_extractor_client = MagicMock()
    mock_extractor_client.extract_direct_url.return_value = ("https://cdn.example.com/batched.bin", None)

    # 16 chunks of 64 KB = 1048576 bytes (1 MB)
    chunk_size = 64 * 1024
    chunks_list = [b"X" * chunk_size for _ in range(16)]
    total_data_bytes = chunk_size * 16

    mock_head_response = MagicMock()
    mock_head_response.headers = {"content-length": str(total_data_bytes)}

    mock_get_response = MagicMock()
    mock_get_response.status_code = 200
    mock_get_response.headers = {"content-length": str(total_data_bytes)}
    mock_get_response.iter_content.return_value = chunks_list

    mock_scraper_client = MagicMock()
    mock_scraper_client.head.return_value = mock_head_response
    mock_scraper_client.get.return_value = mock_get_response
    mock_rate_limiter_instance = MagicMock()
    mock_session_bytes_callback = MagicMock()

    download_manager_instance = DownloadManager(
        tasks=[download_task_instance],
        max_workers=1,
        rate_limiter=mock_rate_limiter_instance,
        scraper=mock_scraper_client,
        extractor=mock_extractor_client,
        settings={"download_speed_limit": 0, "write_buffer_size": 512 * 1024},
        session_bytes_lock_callback=mock_session_bytes_callback,
        trigger_history_save_callback=MagicMock()
    )
    download_manager_instance.is_running = True

    download_manager_instance.download_worker(download_task_instance)

    # Rate limiter consumed 16 times (for each 64 KB chunk)
    assert mock_rate_limiter_instance.consume.call_count == 16

    # Session bytes callback batched every 512 KB: exactly 2 calls of 512 KB each
    assert mock_session_bytes_callback.call_count == 2
    mock_session_bytes_callback.assert_any_call(512 * 1024)

    assert download_task_instance.status == TaskStatus.FINISHED
    assert os.path.getsize(destination_file_path) == total_data_bytes


@pytest.mark.unit
def test_download_worker_flushes_buffer_on_pause(tmp_path):
    target_filename = "Paused_Stream_File.bin"
    destination_file_path = str(tmp_path / target_filename)

    download_task_instance = DownloadTask(
        f"https://fuckingfast.co/c7o9muwfdksh#{target_filename}",
        str(tmp_path)
    )
    download_task_instance.filepath = destination_file_path

    mock_extractor_client = MagicMock()
    mock_extractor_client.extract_direct_url.return_value = ("https://cdn.example.com/paused.bin", None)

    # 3 chunks of 64 KB = 192 KB (less than 512 KB buffer threshold)
    chunk_size = 64 * 1024
    chunk_data = b"P" * chunk_size

    def chunk_generator():
        for chunk_index in range(5):
            if chunk_index == 3:
                download_task_instance.pause_flag = True
            yield chunk_data

    mock_head_response = MagicMock()
    mock_head_response.headers = {"content-length": str(chunk_size * 5)}

    mock_get_response = MagicMock()
    mock_get_response.status_code = 200
    mock_get_response.headers = {"content-length": str(chunk_size * 5)}
    mock_get_response.iter_content.return_value = chunk_generator()

    mock_scraper_client = MagicMock()
    mock_scraper_client.head.return_value = mock_head_response
    mock_scraper_client.get.return_value = mock_get_response
    mock_session_bytes_callback = MagicMock()

    download_manager_instance = DownloadManager(
        tasks=[download_task_instance],
        max_workers=1,
        rate_limiter=MagicMock(),
        scraper=mock_scraper_client,
        extractor=mock_extractor_client,
        settings={"download_speed_limit": 0, "write_buffer_size": 512 * 1024},
        session_bytes_lock_callback=mock_session_bytes_callback,
        trigger_history_save_callback=MagicMock()
    )
    download_manager_instance.is_running = True

    download_manager_instance.download_worker(download_task_instance)

    assert download_task_instance.status == TaskStatus.PAUSED
    # Exactly 3 chunks delivered before pause was handled
    assert download_task_instance.downloaded_bytes == chunk_size * 3
    # Buffer was flushed to disk despite being below 512 KB threshold
    assert os.path.getsize(destination_file_path) == chunk_size * 3
    assert mock_session_bytes_callback.call_count == 1
    mock_session_bytes_callback.assert_called_once_with(chunk_size * 3)


@pytest.mark.unit
def test_download_worker_flushes_buffer_on_cancel(tmp_path):
    target_filename = "Cancelled_Stream_File.bin"
    destination_file_path = str(tmp_path / target_filename)

    download_task_instance = DownloadTask(
        f"https://fuckingfast.co/c7o9muwfdksh#{target_filename}",
        str(tmp_path)
    )
    download_task_instance.filepath = destination_file_path

    mock_extractor_client = MagicMock()
    mock_extractor_client.extract_direct_url.return_value = ("https://cdn.example.com/cancel.bin", None)

    chunk_size = 64 * 1024
    chunk_data = b"C" * chunk_size

    def chunk_generator():
        for chunk_index in range(4):
            if chunk_index == 2:
                download_task_instance.cancel_flag = True
            yield chunk_data

    mock_head_response = MagicMock()
    mock_head_response.headers = {"content-length": str(chunk_size * 4)}

    mock_get_response = MagicMock()
    mock_get_response.status_code = 200
    mock_get_response.headers = {"content-length": str(chunk_size * 4)}
    mock_get_response.iter_content.return_value = chunk_generator()

    mock_scraper_client = MagicMock()
    mock_scraper_client.head.return_value = mock_head_response
    mock_scraper_client.get.return_value = mock_get_response
    mock_session_bytes_callback = MagicMock()

    download_manager_instance = DownloadManager(
        tasks=[download_task_instance],
        max_workers=1,
        rate_limiter=MagicMock(),
        scraper=mock_scraper_client,
        extractor=mock_extractor_client,
        settings={"download_speed_limit": 0, "write_buffer_size": 512 * 1024},
        session_bytes_lock_callback=mock_session_bytes_callback,
        trigger_history_save_callback=MagicMock()
    )
    download_manager_instance.is_running = True

    download_manager_instance.download_worker(download_task_instance)

    assert download_task_instance.status == TaskStatus.CANCELLED
    assert download_task_instance.downloaded_bytes == chunk_size * 2
    assert os.path.getsize(destination_file_path) == chunk_size * 2
    assert mock_session_bytes_callback.call_count == 1
    mock_session_bytes_callback.assert_called_once_with(chunk_size * 2)


@pytest.mark.unit
def test_download_worker_flushes_buffer_on_stream_error(tmp_path):
    target_filename = "Stream_Error_File.bin"
    destination_file_path = str(tmp_path / target_filename)

    download_task_instance = DownloadTask(
        f"https://fuckingfast.co/c7o9muwfdksh#{target_filename}",
        str(tmp_path)
    )
    download_task_instance.filepath = destination_file_path

    mock_extractor_client = MagicMock()
    mock_extractor_client.extract_direct_url.return_value = ("https://cdn.example.com/err.bin", None)

    chunk_size = 64 * 1024
    chunk_data = b"E" * chunk_size

    def error_chunk_generator():
        yield chunk_data
        yield chunk_data
        raise ConnectionResetError("Connection reset by peer mid-stream")

    mock_head_response = MagicMock()
    mock_head_response.headers = {"content-length": str(chunk_size * 5)}

    mock_get_response = MagicMock()
    mock_get_response.status_code = 200
    mock_get_response.headers = {"content-length": str(chunk_size * 5)}
    mock_get_response.iter_content.return_value = error_chunk_generator()

    mock_scraper_client = MagicMock()
    mock_scraper_client.head.return_value = mock_head_response
    mock_scraper_client.get.return_value = mock_get_response
    mock_session_bytes_callback = MagicMock()

    download_manager_instance = DownloadManager(
        tasks=[download_task_instance],
        max_workers=1,
        rate_limiter=MagicMock(),
        scraper=mock_scraper_client,
        extractor=mock_extractor_client,
        settings={"download_speed_limit": 0, "write_buffer_size": 512 * 1024},
        session_bytes_lock_callback=mock_session_bytes_callback,
        trigger_history_save_callback=MagicMock()
    )
    download_manager_instance.is_running = True

    download_manager_instance.download_worker(download_task_instance)

    assert download_task_instance.status == TaskStatus.FAILED
    assert "Connection was reset" in download_task_instance.error_message
    # Flushed 2 chunks before exception was raised
    assert os.path.getsize(destination_file_path) == chunk_size * 2
    assert mock_session_bytes_callback.call_count == 1
    mock_session_bytes_callback.assert_called_once_with(chunk_size * 2)


@pytest.mark.unit
def test_download_worker_ema_speed_calculation(tmp_path, monkeypatch):
    target_filename = "Ema_Speed_File.bin"
    destination_file_path = str(tmp_path / target_filename)

    download_task_instance = DownloadTask(
        f"https://fuckingfast.co/c7o9muwfdksh#{target_filename}",
        str(tmp_path)
    )
    download_task_instance.filepath = destination_file_path

    mock_extractor_client = MagicMock()
    mock_extractor_client.extract_direct_url.return_value = ("https://cdn.example.com/speed.bin", None)

    # 2 intervals:
    # Chunk 1: 1 MB transferred, clock advances by 0.5s -> instantaneous = 2.0 MB/s
    # Chunk 2: 0.2 MB transferred, clock advances by 0.5s -> instantaneous = 0.4 MB/s
    chunk_1 = b"1" * (1024 * 1024)
    chunk_2 = b"2" * int(0.2 * 1024 * 1024)
    total_data_size = len(chunk_1) + len(chunk_2)

    current_simulated_time = [1000.0]

    def mock_time():
        return current_simulated_time[0]

    def mock_generator():
        # Advance time by 0.5s before yielding chunk 1
        current_simulated_time[0] += 0.5
        yield chunk_1
        # Advance time by 0.5s before yielding chunk 2
        current_simulated_time[0] += 0.5
        yield chunk_2

    monkeypatch.setattr(time, "time", mock_time)

    mock_head_response = MagicMock()
    mock_head_response.headers = {"content-length": str(total_data_size)}

    mock_get_response = MagicMock()
    mock_get_response.status_code = 200
    mock_get_response.headers = {"content-length": str(total_data_size)}
    mock_get_response.iter_content.return_value = mock_generator()

    mock_scraper_client = MagicMock()
    mock_scraper_client.head.return_value = mock_head_response
    mock_scraper_client.get.return_value = mock_get_response

    download_manager_instance = DownloadManager(
        tasks=[download_task_instance],
        max_workers=1,
        rate_limiter=MagicMock(),
        scraper=mock_scraper_client,
        extractor=mock_extractor_client,
        settings={"download_speed_limit": 0, "speed_ema_alpha": 0.3},
        session_bytes_lock_callback=MagicMock(),
        trigger_history_save_callback=MagicMock()
    )
    download_manager_instance.is_running = True

    speeds_observed = []

    def track_speed_after_chunk(size, limit):
        speeds_observed.append(download_task_instance.speed)

    download_manager_instance.rate_limiter.consume = MagicMock(side_effect=track_speed_after_chunk)

    download_manager_instance.download_worker(download_task_instance)

    assert len(speeds_observed) == 2
    # After chunk 1: instantaneous speed = 2.0 MB/s, initial sample sets speed = 2.0 MB/s
    assert pytest.approx(speeds_observed[0], 0.001) == 2.0

    # After chunk 2: instantaneous speed = 0.4 MB/s
    # EMA: 0.3 * 0.4 + 0.7 * 2.0 = 0.12 + 1.40 = 1.52 MB/s
    expected_ema_speed = 0.3 * 0.4 + 0.7 * 2.0
    assert pytest.approx(speeds_observed[1], 0.001) == expected_ema_speed
