import pytest
from utils.formatters import format_bytes, format_size_progress, format_error_message


@pytest.mark.unit
def test_format_bytes_boundaries():
    assert format_bytes(-10) == "0 MB"
    assert format_bytes(0) == "0 MB"
    assert format_bytes(512) == "0.5 KB"
    assert format_bytes(1024 * 500) == "500.0 KB"
    assert format_bytes(1024 * 1024 * 15) == "15.0 MB"
    assert format_bytes(1024 * 1024 * 1024 * 2.5) == "2.50 GB"


@pytest.mark.unit
def test_format_size_progress():
    assert format_size_progress(0, 0) == "-"
    assert format_size_progress(500, -1) == "-"
    assert format_size_progress(1024 * 1024 * 5, 1024 * 1024 * 10) == "5.0 MB / 10.0 MB"


@pytest.mark.unit
def test_format_error_message_known_patterns():
    # Socket abort error
    abort_error = ConnectionAbortedError("WinError 10053 An established connection was aborted")
    formatted_abort = format_error_message(abort_error)
    assert "aborted by your computer" in formatted_abort

    # Reset error
    reset_error = ConnectionResetError("Connection reset by peer")
    formatted_reset = format_error_message(reset_error)
    assert "reset by the server" in formatted_reset

    # Timeout error
    timeout_error = TimeoutError("Operation timed out")
    formatted_timeout = format_error_message(timeout_error)
    assert "timed out" in formatted_timeout

    # General error with truncation
    long_message = "A" * 300
    formatted_long = format_error_message(ValueError(long_message), max_length=50)
    assert len(formatted_long) <= 80
    assert formatted_long.endswith("...")
