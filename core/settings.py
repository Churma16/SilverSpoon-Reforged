import os
import sys
import json

CURRENT_VERSION = "v1.3.0"
GITHUB_REPO = "billysams21/SilverSpoon"
OLD_EXE_CLEANUP_MARKER_SUFFIX = ".delete_old_on_start"

def get_settings_path():
    return os.path.expanduser("~/.silverspoon_settings.json")

def load_settings():
    if sys.platform == "win32":
        default_downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        if not os.path.exists(default_downloads):
            try:
                os.makedirs(default_downloads, exist_ok=True)
            except Exception:
                default_downloads = os.path.abspath(".")
    else:
        default_downloads = os.path.abspath(".")
        
    default_settings = {
        "default_save_dir": default_downloads,
        "max_workers": 3,
        "download_speed_limit": 0,
        "extract_after_download": False,
        "column_widths": {},
        "skip_delete_confirmation": False,
        "show_warning_dialog": True,
        "enable_notifications": True,
        "minimize_to_tray": False,
        "last_update_check": 0.0
    }
    settings_path = get_settings_path()
    if os.path.exists(settings_path):
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                default_settings.update(loaded)
        except Exception:
            pass
            
    save_settings(default_settings)
    return default_settings

def save_settings(settings):
    settings_path = get_settings_path()
    try:
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        print(f"Failed to save settings: {e}")
