import os
import json
from core.download_task import DownloadTask

def get_history_path():
    return os.path.expanduser("~/.silverspoon_history.json")

def load_history():
    history_path = get_history_path()
    tasks = []
    if os.path.exists(history_path):
        try:
            with open(history_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item_data in data:
                    tasks.append(DownloadTask.from_dict(item_data))
        except Exception:
            pass
    return tasks

def save_history(tasks):
    history_path = get_history_path()
    try:
        with open(history_path, 'w', encoding='utf-8') as f:
            json.dump([t.to_dict() for t in tasks], f, indent=4)
    except Exception as e:
        print(f"Failed to save history: {e}")
