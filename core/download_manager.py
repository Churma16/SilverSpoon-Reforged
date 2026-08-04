import os
import time
import threading
import logging
from core.types import TaskStatus
from utils.formatters import format_error_message

logger = logging.getLogger(__name__)

class DownloadManager:
    def __init__(self, tasks, max_workers, rate_limiter, scraper, extractor, settings, session_bytes_lock_callback, trigger_history_save_callback):
        self.tasks = tasks
        self.max_workers = max_workers
        self.rate_limiter = rate_limiter
        self.scraper = scraper
        self.extractor = extractor
        self.settings = settings
        self.session_bytes_lock_callback = session_bytes_lock_callback
        self.trigger_history_save_callback = trigger_history_save_callback
        
        self.manager_thread = None
        self.is_running = False

    def start(self, extract_check_callback=None):
        self.is_running = True
        self.manager_thread = threading.Thread(target=self._download_manager_loop, args=(extract_check_callback,), daemon=True)
        self.manager_thread.start()

    def stop(self):
        self.is_running = False

    def _download_manager_loop(self, extract_check_callback=None):
        while self.is_running:
            active = sum(1 for t in self.tasks if t.status in (TaskStatus.DOWNLOADING, TaskStatus.CONNECTING, TaskStatus.SOLVING_SESSION))
            if active < self.max_workers:
                for task in self.tasks:
                    if task.status == TaskStatus.IN_QUEUE:
                        task.status = TaskStatus.CONNECTING
                        logger.info(f"Queued task started download worker: {task.link}")
                        threading.Thread(target=self.download_worker, args=(task,), daemon=True).start()
                        active += 1
                        if active >= self.max_workers:
                            break
            
            if extract_check_callback and self.is_running:
                try:
                    extract_check_callback()
                except (RuntimeError, AttributeError):
                    pass
                
            time.sleep(1)

    def get_direct_link(self, task):
        direct_link, err_msg = self.extractor.extract_direct_url(task.link, task.file_id)
        if not direct_link:
            task.error_message = err_msg or "Could not get the direct download link. The link may be expired or blocked."
            logger.warning(f"Failed to obtain direct link for task {task.link}: {task.error_message}")
            return None
        return direct_link

    def download_worker(self, task):
        task.started_at = time.time()
        try:
            # Quick check: If file is already 100% downloaded on disk, finish immediately without network call
            if os.path.exists(task.filepath) and (task.progress >= 100 or (task.total_bytes > 0 and os.path.getsize(task.filepath) >= task.total_bytes)):
                task.downloaded_bytes = task.total_bytes if task.total_bytes > 0 else os.path.getsize(task.filepath)
                task.progress = 100.0
                task.status = TaskStatus.FINISHED
                task.error_message = ""
                logger.info(f"Task already fully downloaded on disk: {task.filepath}")
                self.trigger_history_save_callback()
                return

            task.status = TaskStatus.SOLVING_SESSION
            logger.info(f"Solving Session for task: {task.link}")
            dl_url = self.get_direct_link(task)
            if not dl_url:
                if not task.cancel_flag and not task.pause_flag:
                    task.status = TaskStatus.FAILED
                    if not task.error_message:
                        task.error_message = "Could not get the direct download link."
                return
                
            if task.cancel_flag:
                task.status = TaskStatus.CANCELLED
                logger.info(f"Task cancelled before download: {task.link}")
                return
                
            if task.pause_flag:
                task.status = TaskStatus.PAUSED
                logger.info(f"Task paused before download: {task.link}")
                return

            task.status = TaskStatus.DOWNLOADING
            task.error_message = ""
            logger.info(f"Downloading stream from: {dl_url}")
            
            try:
                if not os.path.exists(task.save_dir):
                    try:
                        os.makedirs(task.save_dir, exist_ok=True)
                    except Exception as e:
                        task.status = TaskStatus.FAILED
                        task.error_message = f"Failed to create save directory '{task.save_dir}'. {format_error_message(e)}"
                        logger.error(f"Directory creation error for {task.save_dir}: {e}", exc_info=True)
                        self.trigger_history_save_callback()
                        return
                    
                initial_size = 0
                if os.path.exists(task.filepath):
                    initial_size = os.path.getsize(task.filepath)
                    
                head_req = self.scraper.head(dl_url)
                total_size = int(head_req.headers.get('content-length', 0))
                task.total_bytes = total_size
                
                if initial_size > 0 and initial_size == total_size:
                    task.downloaded_bytes = total_size
                    task.progress = 100
                    task.status = TaskStatus.FINISHED
                    task.error_message = ""
                    logger.info(f"Task completed based on content length match: {task.filepath}")
                    return
                    
                resume_header = {}
                mode = 'wb'
                if initial_size > 0:
                    resume_header = {'Range': f'bytes={initial_size}-'}
                    mode = 'ab'
                    logger.info(f"Resuming download from byte offset {initial_size} for {task.filepath}")
                    
                resp = self.scraper.get(dl_url, stream=True, headers=resume_header)
                if resp.status_code not in (200, 206):
                    task.status = TaskStatus.FAILED
                    if resp.status_code == 403:
                        task.error_message = f"HTTP 403 (Forbidden): Cloudflare anti-bot blocked your connection. Try toggling your VPN or changing DNS (1.1.1.1)."
                    else:
                        task.error_message = f"Download request failed. Server returned HTTP {resp.status_code}."
                    if resp.status_code in (403, 503):
                        logger.error(f"Download 403/503 for {dl_url}.")
                    return
                    
                if resp.status_code == 200 and initial_size > 0:
                    mode = 'wb'
                    initial_size = 0
                    
                task.downloaded_bytes = initial_size
                if total_size == 0 and 'content-length' in resp.headers:
                    task.total_bytes = int(resp.headers['content-length']) + initial_size
                elif total_size == 0:
                    task.total_bytes = 0
                    
                last_time = time.time()
                bytes_since_last = 0
                
                with open(task.filepath, mode) as f:
                    for chunk in resp.iter_content(chunk_size=8192*8):

                            if task.pause_flag:
                                task.status = TaskStatus.PAUSED
                                task.speed = 0
                                logger.info(f"Download paused during stream: {task.link}")
                                return
                            if task.cancel_flag:
                                task.status = TaskStatus.CANCELLED
                                task.speed = 0
                                logger.info(f"Download cancelled during stream: {task.link}")
                                return
                                
                            if chunk:
                                f.write(chunk)
                                size = len(chunk)
                                task.downloaded_bytes += size
                                bytes_since_last += size
                                
                                if self.session_bytes_lock_callback:
                                    self.session_bytes_lock_callback(size)
                                
                                now = time.time()
                                if now - last_time > 0.5:
                                    task.speed = (bytes_since_last / (now - last_time)) / (1024*1024)
                                    if task.total_bytes > 0:
                                        task.progress = (task.downloaded_bytes / task.total_bytes) * 100
                                    last_time = now
                                    bytes_since_last = 0
                                    
                                self.rate_limiter.consume(size, self.settings.get("download_speed_limit", 0))
                    
                    task.progress = 100
                    task.speed = 0
                    task.status = TaskStatus.FINISHED
                    task.error_message = ""
                    logger.info(f"Download finished successfully: {task.filepath}")
                    self.trigger_history_save_callback()
                    
            except Exception as e:
                logger.error(f"Download worker error for task {task.link}: {e}", exc_info=True)
                if not task.cancel_flag and not task.pause_flag:
                    task.status = TaskStatus.FAILED
                    task.error_message = f"Download failed. {format_error_message(e)}"
                    self.trigger_history_save_callback()
        finally:
            if task.started_at:
                task.elapsed_seconds += time.time() - task.started_at
                task.started_at = None

