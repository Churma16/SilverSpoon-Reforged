import os
import sys
import subprocess
import logging

logger = logging.getLogger(__name__)


class SystemService:
    """Service to handle operating system level actions such as power control and file explorer navigation."""

    @staticmethod
    def execute_power_action(action: str = "Shutdown") -> bool:
        """Executes the specified power action (Shutdown, Sleep, Hibernate) on the host OS.
        
        Args:
            action: Action string ("Shutdown", "Sleep", "Hibernate")
            
        Returns:
            bool: True if command executed without throwing exception, False otherwise.
        """
        try:
            normalized_action = action.capitalize()
            if sys.platform == "win32":
                if normalized_action == "Sleep":
                    subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], check=False)
                elif normalized_action == "Hibernate":
                    subprocess.run(["shutdown", "/h"], check=False)
                else:
                    subprocess.run(["shutdown", "/s", "/t", "0"], check=False)
            elif sys.platform == "darwin":
                if normalized_action == "Sleep":
                    subprocess.run(["pmset", "sleepnow"], check=False)
                else:
                    subprocess.run(["osascript", "-e", 'tell app "System Events" to shut down'], check=False)
            else:
                if normalized_action == "Sleep":
                    subprocess.run(["systemctl", "suspend"], check=False)
                elif normalized_action == "Hibernate":
                    subprocess.run(["systemctl", "hibernate"], check=False)
                else:
                    subprocess.run(["systemctl", "poweroff"], check=False)
            return True
        except Exception as execution_error:
            logger.error(f"Failed to execute system {action.lower()}: {execution_error}")
            return False

    @staticmethod
    def open_directory(directory_path: str) -> bool:
        """Opens a directory in the default OS file explorer.
        
        Args:
            directory_path: Target directory path to open.
            
        Returns:
            bool: True if launched successfully, False otherwise.
        """
        try:
            cleaned_directory_path = directory_path.strip().strip('"').strip("'").replace('"', "")
            normalized_directory_path = os.path.normpath(cleaned_directory_path)
            if not os.path.exists(normalized_directory_path):
                os.makedirs(normalized_directory_path, exist_ok=True)

            if sys.platform == "win32":
                os.startfile(normalized_directory_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", normalized_directory_path])
            else:
                subprocess.Popen(["xdg-open", normalized_directory_path])
            return True
        except Exception as open_error:
            logger.error(f"Failed to open directory '{directory_path}': {open_error}")
            return False

    @staticmethod
    def open_file_or_folder(file_path: str, fallback_directory: str = "") -> bool:
        """Opens the folder location and selects/highlights the file if it exists; otherwise opens the directory.
        
        Args:
            file_path: Full path to the target file.
            fallback_directory: Directory to open if the specific file does not exist.
            
        Returns:
            bool: True if launched successfully, False otherwise.
        """
        try:
            cleaned_file_path = file_path.strip().strip('"').strip("'").replace('"', "")
            normalized_file_path = os.path.normpath(cleaned_file_path)
            if os.path.exists(normalized_file_path):
                if sys.platform == "win32":
                    subprocess.Popen(["explorer", f"/select,{normalized_file_path}"])
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", "-R", normalized_file_path])
                else:
                    parent_directory = os.path.dirname(normalized_file_path)
                    subprocess.Popen(["xdg-open", parent_directory])
                return True
            else:
                effective_fallback_directory = fallback_directory if fallback_directory else (os.path.dirname(normalized_file_path) or ".")
                return SystemService.open_directory(effective_fallback_directory)
        except Exception as open_error:
            logger.error(f"Failed to open file or folder location for '{file_path}': {open_error}")
            return False

    @staticmethod
    def show_in_file_manager(file_path: str, fallback_directory: str = "") -> bool:
        """Opens the folder location and selects/highlights the file in the OS file manager,
        or opens the fallback directory if the file does not exist.
        
        Args:
            file_path: Full path to the target file.
            fallback_directory: Directory to open if the specific file does not exist.
            
        Returns:
            bool: True if launched successfully, False otherwise.
        """
        return SystemService.open_file_or_folder(file_path, fallback_directory)
