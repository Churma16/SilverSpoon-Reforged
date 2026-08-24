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
                    os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
                elif normalized_action == "Hibernate":
                    os.system("shutdown /h")
                else:
                    os.system("shutdown /s /t 0")
            elif sys.platform == "darwin":
                if normalized_action == "Sleep":
                    os.system("pmset sleepnow")
                else:
                    os.system("sudo shutdown -h now")
            else:
                if normalized_action == "Sleep":
                    os.system("systemctl suspend")
                elif normalized_action == "Hibernate":
                    os.system("systemctl hibernate")
                else:
                    os.system("shutdown -h now")
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
            normalized_directory_path = os.path.normpath(directory_path)
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
    def open_file_or_folder(file_path: str, fallback_directory: str) -> bool:
        """Opens the folder location and selects/highlights the file if it exists; otherwise opens the directory.
        
        Args:
            file_path: Full path to the target file.
            fallback_directory: Directory to open if the specific file does not exist.
            
        Returns:
            bool: True if launched successfully, False otherwise.
        """
        try:
            normalized_file_path = os.path.normpath(file_path)
            if os.path.exists(normalized_file_path):
                if sys.platform == "win32":
                    subprocess.Popen(f'explorer /select,"{normalized_file_path}"')
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", "-R", normalized_file_path])
                else:
                    parent_directory = os.path.dirname(normalized_file_path)
                    subprocess.Popen(["xdg-open", parent_directory])
                return True
            else:
                return SystemService.open_directory(fallback_directory)
        except Exception as open_error:
            logger.error(f"Failed to open file or folder location for '{file_path}': {open_error}")
            return False

