import os
import json
import logging
import threading
from typing import List, Optional
from core.download_task import DownloadTask

logger = logging.getLogger(__name__)

_history_lock = threading.Lock()


def get_history_path() -> str:
    """Returns the default user home path for the history json file."""
    return os.path.expanduser("~/.silverspoon_history.json")


def load_history(history_path: Optional[str] = None) -> List[DownloadTask]:
    """Loads persistent task history from disk in a thread-safe manner."""
    if history_path is None:
        history_path = get_history_path()

    tasks: List[DownloadTask] = []
    with _history_lock:
        if os.path.exists(history_path):
            try:
                with open(history_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item_data in data:
                            tasks.append(DownloadTask.from_dict(item_data))
            except Exception as load_error:
                logger.warning(f"Failed to load history from {history_path}: {load_error}")
    return tasks


def save_history(tasks: List[DownloadTask], history_path: Optional[str] = None) -> bool:
    """Atomically and thread-safely writes task history to disk.
    
    Serializes tasks to a temporary file (.tmp) before replacing the target file
    to prevent file truncation or corruption during crashes or concurrent calls.
    """
    if history_path is None:
        history_path = get_history_path()

    temp_path = f"{history_path}.tmp"
    with _history_lock:
        try:
            parent_dir = os.path.dirname(history_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)

            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump([t.to_dict() for t in tasks], f, indent=4)

            os.replace(temp_path, history_path)
            return True
        except Exception as save_error:
            logger.error(f"Failed to save history to {history_path}: {save_error}")
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            return False
