import os
import sys
import time
import threading
import logging
from typing import List, Set, Optional, Callable
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QSystemTrayIcon
from curl_cffi import requests as cffi_requests

from core.types import TaskStatus, BatchStatus
from core.download_task import DownloadTask
from core.rate_limiter import GlobalRateLimiter
from core.extractors.fuckingfast import FuckingFastExtractor
from core.download_manager import DownloadManager
from core.extraction_manager import ExtractionManager
from core.history import load_history, save_history
from core.settings import load_settings, save_settings
from utils.formatters import format_error_message

logger = logging.getLogger(__name__)


class DownloadController(QObject):
    """Controller orchestrating task lifecycle, background download manager, extraction manager, and persistence."""

    tasks_changed = pyqtSignal()
    task_added = pyqtSignal(object)
    task_removed = pyqtSignal(object)
    notification_requested = pyqtSignal(str, str, object)
    session_stats_updated = pyqtSignal(int, int, int, int)

    def __init__(self, base_dir: str, settings: Optional[dict] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.base_dir = base_dir
        self.settings = settings if settings is not None else load_settings()

        self.tasks: List[DownloadTask] = []
        self.extracted_folders: Set[str] = set()
        self.notified_batches: Set[str] = set()
        self.session_downloaded_bytes: int = 0
        self.session_bytes_lock = threading.Lock()

        self.max_workers = self.settings.get("max_workers", 3)
        self.rate_limiter = GlobalRateLimiter()
        self.scraper = cffi_requests.Session(impersonate="chrome")
        self.extractor = FuckingFastExtractor(self.scraper)

        self.is_downloading = False

        self.extraction_manager = ExtractionManager(
            self.tasks,
            self.extracted_folders,
            self.base_dir,
            self.trigger_history_save
        )

        self.download_manager = DownloadManager(
            self.tasks,
            self.max_workers,
            self.rate_limiter,
            self.scraper,
            self.extractor,
            self.settings,
            self.add_session_downloaded_bytes,
            self.trigger_history_save
        )

    def start_download_manager(self, auto_extract_enabled_check: Optional[Callable[[], bool]] = None):
        """Starts the background download loop."""
        def check_extraction_callback():
            try:
                if auto_extract_enabled_check is None or auto_extract_enabled_check():
                    self.extraction_manager.check_extraction()
            except (RuntimeError, AttributeError):
                pass

        self.download_manager.start(check_extraction_callback)

    def stop_download_manager(self):
        """Stops background download manager and closes network sessions."""
        if hasattr(self, 'download_manager') and self.download_manager:
            self.download_manager.stop()
        if hasattr(self, 'extractor') and hasattr(self.extractor, 'close'):
            try:
                self.extractor.close()
            except Exception as close_error:
                logger.warning(f"Error closing extractor: {close_error}")

    def load_initial_history(self) -> List[DownloadTask]:
        """Loads persistent task history and registers into controller."""
        loaded_tasks = load_history()
        for task in loaded_tasks:
            self.tasks.append(task)
            if task.status == TaskStatus.EXTRACTED:
                self.extracted_folders.add(task.folder_name)
        return self.tasks

    def trigger_history_save(self):
        """Saves current tasks to persistent history file."""
        save_history(self.tasks)

    def add_session_downloaded_bytes(self, size: int):
        """Thread-safe increment of session downloaded bytes."""
        with self.session_bytes_lock:
            self.session_downloaded_bytes += size

    def add_task(self, task: DownloadTask):
        """Adds a single download task to controller state."""
        self.tasks.append(task)
        self.task_added.emit(task)
        self.trigger_history_save()

    def add_tasks(self, tasks: List[DownloadTask]):
        """Adds multiple download tasks to controller state."""
        for task in tasks:
            self.tasks.append(task)
            self.task_added.emit(task)
        self.trigger_history_save()

    def start_downloads(self, target_tasks: Optional[List[DownloadTask]] = None):
        """Queues specified tasks (or all eligible tasks) for downloading."""
        self.is_downloading = True
        tasks_to_start = target_tasks if target_tasks is not None else self.tasks

        for task in tasks_to_start:
            if task.status in (TaskStatus.STANDBY, TaskStatus.PAUSED, TaskStatus.CANCELLED, TaskStatus.FAILED):
                task.status = TaskStatus.IN_QUEUE
                task.pause_flag = False
                task.cancel_flag = False

    def pause_tasks(self, target_tasks: List[DownloadTask]):
        """Pauses the specified tasks."""
        for task in target_tasks:
            if task.status in (TaskStatus.DOWNLOADING, TaskStatus.IN_QUEUE, TaskStatus.CONNECTING, TaskStatus.SOLVING_SESSION):
                task.pause_flag = True
                task.status = TaskStatus.PAUSED

    def cancel_tasks(self, target_tasks: List[DownloadTask]):
        """Cancels the specified tasks."""
        for task in target_tasks:
            task.cancel_flag = True
            task.status = TaskStatus.CANCELLED

    def retry_tasks(self, target_tasks: List[DownloadTask]):
        """Retries failed or cancelled tasks."""
        for task in target_tasks:
            if task.status in (TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.PAUSED):
                task.status = TaskStatus.IN_QUEUE
                task.error_message = ""
                task.cancel_flag = False
                task.pause_flag = False

    def force_redownload_tasks(self, tasks_to_redownload: List[DownloadTask]) -> tuple[int, int, int]:
        """Deletes files from disk and resets tasks to 0% in queue.
        
        Returns:
            (redownloaded_count, skipped_count, failed_count)
        """
        active_statuses = {TaskStatus.DOWNLOADING, TaskStatus.IN_QUEUE, TaskStatus.CONNECTING, TaskStatus.SOLVING_SESSION, TaskStatus.PAUSING, TaskStatus.UNPACKING}
        redownloaded = 0
        skipped = 0
        failed = 0

        for task in tasks_to_redownload:
            if task.status in active_statuses:
                skipped += 1
                continue

            try:
                if os.path.exists(task.filepath):
                    os.remove(task.filepath)
            except Exception as file_delete_error:
                failed += 1
                task.status = TaskStatus.FAILED
                task.error_message = f"Could not delete existing file before redownload. {format_error_message(file_delete_error)}"
                continue

            task.cancel_flag = False
            task.pause_flag = False
            task.progress = 0.0
            task.speed = 0.0
            task.downloaded_bytes = 0
            task.total_bytes = 0
            task.error_message = ""
            task.status = TaskStatus.IN_QUEUE
            self.extracted_folders.discard(task.folder_name)
            redownloaded += 1

        self.trigger_history_save()
        return redownloaded, skipped, failed

    def reextract_folders(self, folder_names: Set[str]) -> int:
        """Triggers manual re-extraction of specified batch folder names."""
        reextracted_count = 0
        for folder_name in folder_names:
            folder_tasks = [t for t in self.tasks if t.folder_name == folder_name]
            if not folder_tasks:
                continue

            self.extracted_folders.discard(folder_name)
            threading.Thread(target=self.extraction_manager.extract_folder, args=(folder_tasks,), daemon=True).start()
            reextracted_count += 1
        return reextracted_count

    def delete_tasks(self, tasks_to_delete: List[DownloadTask], delete_files_from_disk: bool = False):
        """Cancels and deletes tasks from state, optionally removing files on disk."""
        for task in tasks_to_delete:
            task.cancel_flag = True
            task.status = TaskStatus.CANCELLED

            if delete_files_from_disk and os.path.exists(task.filepath):
                try:
                    os.remove(task.filepath)
                except Exception as file_delete_error:
                    logger.warning(f"Failed to delete file {task.filepath}: {file_delete_error}")

            if task in self.tasks:
                self.tasks.remove(task)
                self.task_removed.emit(task)

        self.trigger_history_save()

    def clear_finished_tasks(self) -> List[DownloadTask]:
        """Removes completed and cancelled tasks from state."""
        to_remove = [t for t in self.tasks if t.status in (TaskStatus.FINISHED, TaskStatus.EXTRACTED, TaskStatus.CANCELLED)]
        for t in to_remove:
            if t in self.tasks:
                self.tasks.remove(t)
                self.task_removed.emit(t)
        self.trigger_history_save()
        return to_remove

    def pause_all(self):
        """Pauses all active or queued tasks."""
        for task in self.tasks:
            if task.status in (TaskStatus.DOWNLOADING, TaskStatus.IN_QUEUE, TaskStatus.CONNECTING, TaskStatus.SOLVING_SESSION):
                task.pause_flag = True
                task.status = TaskStatus.PAUSED

    def resume_all(self):
        """Resumes all paused, standby, failed, or cancelled tasks."""
        for task in self.tasks:
            if task.status in (TaskStatus.PAUSED, TaskStatus.STANDBY, TaskStatus.FAILED, TaskStatus.CANCELLED):
                task.status = TaskStatus.IN_QUEUE
                task.pause_flag = False

    def sync_tasks_order(self, ordered_tasks: List[DownloadTask]):
        """Updates internal tasks order."""
        self.tasks.clear()
        self.tasks.extend(ordered_tasks)
        self.trigger_history_save()
