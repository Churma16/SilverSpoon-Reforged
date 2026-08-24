import os
import sys
import logging

logger = logging.getLogger(__name__)


class SystemService:
    """Service to handle operating system level power actions."""

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
