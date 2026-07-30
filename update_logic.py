from PyQt6.QtCore import QThread, pyqtSignal, QTimer, QMetaObject, Qt, Q_ARG
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QMessageBox
import sys
import os
import time
import json
import urllib.request
import tempfile
import threading
import re
import zipfile
import shutil
import subprocess


_VERSION_PATTERN = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(.*)$", re.IGNORECASE)

def version_key(version):
    match = _VERSION_PATTERN.fullmatch(version.strip())
    if not match:
        return None

    major, minor, patch, suffix = match.groups()
    # major > minor > patch; patch + suffix > patch
    return int(major), int(minor), int(patch), bool(suffix), suffix.casefold()

def is_newer_version(latest_version, current_version):
    latest_key = version_key(latest_version)
    current_key = version_key(current_version)
    return latest_key is not None and current_key is not None and latest_key > current_key

class UpdateCheckerThread(QThread):
    update_available = pyqtSignal(str, str, str) # version, changelog, download_url
    no_update_found = pyqtSignal()
    error_checking = pyqtSignal(str)
    check_finished = pyqtSignal(float) # Emits the new timestamp to save
    
    def __init__(self, current_version, repo, settings_path, force=False):
        super().__init__()
        self.current_version = current_version
        self.repo = repo
        self.settings_path = settings_path
        self.force = force
        
    def _read_last_check(self):
        try:
            if os.path.exists(self.settings_path):
                with open(self.settings_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("last_update_check", 0.0)
        except Exception:
            pass
        return 0.0

    def _write_last_check(self, timestamp):
        data = {}
        try:
            if os.path.exists(self.settings_path):
                with open(self.settings_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
        except Exception:
            pass
        data["last_update_check"] = timestamp
        try:
            with open(self.settings_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception:
            pass
        
    def run(self):
        try:
            if sys.platform != "win32" or (not hasattr(sys, "frozen") and not self.force):
                return
                
            now = time.time()
            last_check = self._read_last_check()
            if not self.force and (now - last_check < 86400):
                return
                
            req = urllib.request.Request(
                f"https://api.github.com/repos/{self.repo}/releases/latest",
                headers={"User-Agent": f"SilverSpoon-Updater/{self.current_version}", "Accept": "application/vnd.github+json"}
            )
            with urllib.request.urlopen(req, timeout=10) as res:
                data = json.loads(res.read().decode())
            
            latest_version = data.get("tag_name", "")
            
            if latest_version and is_newer_version(latest_version, self.current_version):
                assets = data.get("assets", [])
                download_url = None
                for asset in assets:
                    name = asset.get("name", "")
                    if "SilverSpoon" in name and name.endswith(".zip"):
                        download_url = asset.get("browser_download_url")
                        break
                        
                if download_url:
                    self.update_available.emit(latest_version, data.get("body", "No changelog provided."), download_url)
                    self._write_last_check(now)
                    self.check_finished.emit(now)
                    return
                    
            if self.force:
                self.no_update_found.emit()
                    
            self._write_last_check(now)
            self.check_finished.emit(now)
            
        except Exception as e:
            self._write_last_check(time.time())
            self.check_finished.emit(time.time())
            if self.force:
                self.error_checking.emit(str(e))

class UpdateDownloaderDialog(QDialog):
    def __init__(self, download_url, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Downloading Update...")
        self.setFixedSize(400, 100)
        self.download_url = download_url
        
        layout = QVBoxLayout(self)
        self.label = QLabel("Downloading latest version, please wait...")
        layout.addWidget(self.label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)
        
        self.error = None
        self.temp_zip = None
        self.finished = False

        self.timer = QTimer()
        self.timer.timeout.connect(self.check_worker)
        self.timer.start(100)

        self.worker = threading.Thread(target=self.download_update, daemon=True)
        self.worker.start()

    def check_worker(self):
        if self.finished:
            self.timer.stop()
            if self.error:
                QMessageBox.critical(self, "Update Error", f"Failed to download update:\n{self.error}")
                self.reject()
            else:
                self.accept()

    def download_update(self):
        try:
            self.temp_zip = os.path.join(tempfile.gettempdir(), f"silverspoon_update_{int(time.time())}.zip")
            req = urllib.request.Request(self.download_url, headers={"User-Agent": "SilverSpoon-Updater"})
            with urllib.request.urlopen(req, timeout=60) as r:
                total_length = r.headers.get("Content-Length")
                
                with open(self.temp_zip, "wb") as f:
                    if total_length is None:
                        f.write(r.read())
                    else:
                        downloaded = 0
                        total_length = int(total_length)
                        while True:
                            chunk = r.read(8192)
                            if not chunk:
                                break
                            downloaded += len(chunk)
                            f.write(chunk)
                            done = int(100 * downloaded / total_length)
                            QMetaObject.invokeMethod(self.progress_bar, "setValue", Qt.ConnectionType.QueuedConnection, Q_ARG(int, done))
                            
        except Exception as e:
            self.error = str(e)
            if self.temp_zip and os.path.exists(self.temp_zip):
                try: os.remove(self.temp_zip)
                except: pass
        finally:
            self.finished = True

def extract_and_verify_update(zip_path):
    target_extract_directory = os.path.join(tempfile.gettempdir(), f"silverspoon_extract_{int(time.time())}")
    resolved_target_directory = os.path.abspath(target_extract_directory)
    
    with zipfile.ZipFile(zip_path, 'r') as zip_archive:
        for archive_member in zip_archive.infolist():
            destination_path = os.path.abspath(os.path.join(target_extract_directory, archive_member.filename))
            if os.path.commonpath([resolved_target_directory, destination_path]) != resolved_target_directory:
                raise Exception(f"Path traversal security violation detected in archive entry: {archive_member.filename}")
            zip_archive.extract(archive_member, target_extract_directory)
        
    new_exe_path = None
    for root, _, files in os.walk(target_extract_directory):
        for file in files:
            if file.lower() == "silverspoon.exe":
                new_exe_path = os.path.join(root, file)
                break
                
    if not new_exe_path:
        raise Exception("Could not find SilverSpoon.exe inside the downloaded zip.")
    return target_extract_directory, new_exe_path


def perform_exe_replacement(new_exe_path, current_exe, old_exe_path):
    if os.path.exists(old_exe_path):
        try:
            os.remove(old_exe_path)
        except Exception:
            pass
    
    os.rename(current_exe, old_exe_path)
    
    copy_success = False
    for _ in range(10):
        try:
            shutil.copy2(new_exe_path, current_exe)
            copy_success = True
            break
        except PermissionError:
            time.sleep(0.5)
            
    if not copy_success:
        os.rename(old_exe_path, current_exe)
        raise Exception("Could not copy the new executable. It might be locked by your Antivirus.")

def _escape_batch_path(file_path_string):
    abs_path = os.path.abspath(file_path_string)
    return abs_path.replace('%', '%%').replace('"', '""')

def launch_restart_script(current_exe, old_exe_path, cleanup_marker):
    sanitized_current_exe = _escape_batch_path(current_exe)
    sanitized_old_exe_path = _escape_batch_path(old_exe_path)
    sanitized_cleanup_marker = _escape_batch_path(cleanup_marker)

    bat_path = os.path.join(tempfile.gettempdir(), f"silverspoon_restart_{int(time.time())}.bat")
    with open(bat_path, 'w') as bat:
        bat.write('@echo off\n')
        bat.write('set PYINSTALLER_RESET_ENVIRONMENT=1\n')
        bat.write('set _MEIPASS=\n')
        bat.write('set _MEIPASS2=\n')
        bat.write('ping 127.0.0.1 -n 4 > nul\n')
        bat.write(f'start "" /wait "{sanitized_current_exe}"\n')
        bat.write('if errorlevel 1 goto cleanup\n')
        bat.write(f'if exist "{sanitized_cleanup_marker}" del /f /q "{sanitized_old_exe_path}" > nul 2>&1\n')
        bat.write(f'if not exist "{sanitized_old_exe_path}" if exist "{sanitized_cleanup_marker}" del /q "{sanitized_cleanup_marker}" > nul 2>&1\n')
        bat.write(':cleanup\n')
        bat.write('del "%~f0"\n')
    
    CREATE_NO_WINDOW = 0x08000000
    subprocess.Popen(
        [bat_path],
        creationflags=CREATE_NO_WINDOW,
        close_fds=True
    )


