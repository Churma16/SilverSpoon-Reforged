import os
import sys
from unittest.mock import MagicMock, patch

from services.system_service import SystemService


class TestSystemServicePowerAction:
    """Tests for execute_power_action across supported operating systems."""

    def test_execute_power_action_linux_shutdown(self):
        """Verifies Linux shutdown executes systemctl poweroff non-interactively without sudo."""
        with patch.object(sys, "platform", "linux"):
            with patch("subprocess.run") as mock_subprocess_run:
                execution_result = SystemService.execute_power_action("Shutdown")

                assert execution_result is True
                mock_subprocess_run.assert_called_once_with(["systemctl", "poweroff"], check=False)

    def test_execute_power_action_linux_sleep(self):
        """Verifies Linux sleep executes systemctl suspend non-interactively."""
        with patch.object(sys, "platform", "linux"):
            with patch("subprocess.run") as mock_subprocess_run:
                execution_result = SystemService.execute_power_action("Sleep")

                assert execution_result is True
                mock_subprocess_run.assert_called_once_with(["systemctl", "suspend"], check=False)

    def test_execute_power_action_linux_hibernate(self):
        """Verifies Linux hibernate executes systemctl hibernate non-interactively."""
        with patch.object(sys, "platform", "linux"):
            with patch("subprocess.run") as mock_subprocess_run:
                execution_result = SystemService.execute_power_action("Hibernate")

                assert execution_result is True
                mock_subprocess_run.assert_called_once_with(["systemctl", "hibernate"], check=False)

    def test_execute_power_action_windows_shutdown(self):
        """Verifies Windows shutdown constructs the correct shutdown command."""
        with patch.object(sys, "platform", "win32"):
            with patch("subprocess.run") as mock_subprocess_run:
                execution_result = SystemService.execute_power_action("Shutdown")

                assert execution_result is True
                mock_subprocess_run.assert_called_once_with(["shutdown", "/s", "/t", "0"], check=False)

    def test_execute_power_action_windows_sleep(self):
        """Verifies Windows sleep invokes SetSuspendState via rundll32."""
        with patch.object(sys, "platform", "win32"):
            with patch("subprocess.run") as mock_subprocess_run:
                execution_result = SystemService.execute_power_action("Sleep")

                assert execution_result is True
                mock_subprocess_run.assert_called_once_with(
                    ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
                    check=False,
                )

    def test_execute_power_action_windows_hibernate(self):
        """Verifies Windows hibernate constructs shutdown /h."""
        with patch.object(sys, "platform", "win32"):
            with patch("subprocess.run") as mock_subprocess_run:
                execution_result = SystemService.execute_power_action("Hibernate")

                assert execution_result is True
                mock_subprocess_run.assert_called_once_with(["shutdown", "/h"], check=False)

    def test_execute_power_action_darwin_shutdown(self):
        """Verifies macOS shutdown executes osascript shutdown non-interactively."""
        with patch.object(sys, "platform", "darwin"):
            with patch("subprocess.run") as mock_subprocess_run:
                execution_result = SystemService.execute_power_action("Shutdown")

                assert execution_result is True
                mock_subprocess_run.assert_called_once_with(
                    ["osascript", "-e", 'tell app "System Events" to shut down'],
                    check=False,
                )

    def test_execute_power_action_handles_subprocess_exception(self):
        """Verifies exception during execution is safely caught and returns False."""
        with patch.object(sys, "platform", "linux"):
            with patch("subprocess.run", side_effect=OSError("Command execution denied")):
                execution_result = SystemService.execute_power_action("Shutdown")

                assert execution_result is False


class TestSystemServiceFileManager:
    """Tests for file manager opening and item selection across operating systems."""

    def test_show_in_file_manager_windows_argument_list_construction(self):
        """Verifies Windows Explorer receives arguments as a list with /select."""
        sample_file_path = os.path.normpath(r"C:\Downloads\Videos\example_video.mp4")
        with patch.object(sys, "platform", "win32"):
            with patch("os.path.exists", return_value=True):
                with patch("subprocess.Popen") as mock_subprocess_popen:
                    result = SystemService.show_in_file_manager(sample_file_path)

                    assert result is True
                    mock_subprocess_popen.assert_called_once_with(
                        ["explorer", f"/select,{sample_file_path}"]
                    )

    def test_show_in_file_manager_windows_sanitizes_complex_path_with_quotes_and_spaces(self):
        """Verifies Windows Explorer sanitizes extra quotes and spaces in file paths."""
        raw_complex_file_path = '  "C:\\Downloads\\My Folder\\file "with" quotes.mp4"  '
        expected_sanitized_path = os.path.normpath(r"C:\Downloads\My Folder\file with quotes.mp4")

        with patch.object(sys, "platform", "win32"):
            with patch("os.path.exists", return_value=True):
                with patch("subprocess.Popen") as mock_subprocess_popen:
                    result = SystemService.show_in_file_manager(raw_complex_file_path)

                    assert result is True
                    mock_subprocess_popen.assert_called_once_with(
                        ["explorer", f"/select,{expected_sanitized_path}"]
                    )

    def test_show_in_file_manager_linux_argument_construction(self):
        """Verifies Linux launches xdg-open with the parent directory."""
        sample_file_path = "/home/user/downloads/sample_document.pdf"
        expected_parent_directory = os.path.dirname(os.path.normpath(sample_file_path))

        with patch.object(sys, "platform", "linux"):
            with patch("os.path.exists", return_value=True):
                with patch("subprocess.Popen") as mock_subprocess_popen:
                    result = SystemService.show_in_file_manager(sample_file_path)

                    assert result is True
                    mock_subprocess_popen.assert_called_once_with(
                        ["xdg-open", expected_parent_directory]
                    )

    def test_show_in_file_manager_darwin_argument_construction(self):
        """Verifies macOS launches open -R to highlight the target file."""
        sample_file_path = "/Users/sample/Downloads/archive.zip"
        expected_target_path = os.path.normpath(sample_file_path)

        with patch.object(sys, "platform", "darwin"):
            with patch("os.path.exists", return_value=True):
                with patch("subprocess.Popen") as mock_subprocess_popen:
                    result = SystemService.show_in_file_manager(sample_file_path)

                    assert result is True
                    mock_subprocess_popen.assert_called_once_with(
                        ["open", "-R", expected_target_path]
                    )

    def test_show_in_file_manager_file_missing_uses_fallback_directory(self):
        """Verifies that if target file does not exist, fallback directory is opened."""
        missing_file_path = os.path.normpath(r"C:\NonExistent\Folder\file.mp4")
        fallback_directory_path = os.path.normpath(r"C:\Downloads")

        with patch("os.path.exists", return_value=False):
            with patch.object(SystemService, "open_directory", return_value=True) as mock_open_directory:
                result = SystemService.show_in_file_manager(missing_file_path, fallback_directory_path)

                assert result is True
                mock_open_directory.assert_called_once_with(fallback_directory_path)

    def test_open_file_or_folder_backward_compatibility_alias(self):
        """Verifies open_file_or_folder functions identically as an alias."""
        sample_file_path = os.path.normpath(r"C:\Downloads\file.txt")
        with patch.object(sys, "platform", "win32"):
            with patch("os.path.exists", return_value=True):
                with patch("subprocess.Popen") as mock_subprocess_popen:
                    result = SystemService.open_file_or_folder(sample_file_path)

                    assert result is True
                    mock_subprocess_popen.assert_called_once_with(
                        ["explorer", f"/select,{sample_file_path}"]
                    )

    def test_show_in_file_manager_handles_process_launch_exception(self):
        """Verifies exception during process launch is caught gracefully and returns False."""
        sample_file_path = os.path.normpath(r"C:\Downloads\file.txt")
        with patch.object(sys, "platform", "win32"):
            with patch("os.path.exists", return_value=True):
                with patch("subprocess.Popen", side_effect=OSError("Process creation failed")):
                    result = SystemService.show_in_file_manager(sample_file_path)

                    assert result is False

    def test_open_directory_sanitizes_quotes(self):
        """Verifies open_directory sanitizes quotes and opens directory."""
        directory_with_quotes = '  "C:\\Downloads\\Special Directory"  '
        expected_directory = os.path.normpath(r"C:\Downloads\Special Directory")

        with patch.object(sys, "platform", "win32"):
            with patch("os.path.exists", return_value=True):
                with patch("os.startfile") as mock_startfile:
                    result = SystemService.open_directory(directory_with_quotes)

                    assert result is True
                    mock_startfile.assert_called_once_with(expected_directory)
