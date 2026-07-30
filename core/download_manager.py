import os
import time
import threading
import logging
from core.types import TaskStatus
from utils.formatters import format_error_message

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

    def _download_manager_loop(self, extract_check_callback=None):
        while self.is_running:
            active = sum(1 for t in self.tasks if t.status in (TaskStatus.DOWNLOADING, TaskStatus.CONNECTING))
            if active < self.max_workers:
                for task in self.tasks:
                    if task.status == TaskStatus.IN_QUEUE:
                        task.status = TaskStatus.CONNECTING
                        threading.Thread(target=self.download_worker, args=(task,), daemon=True).start()
                        active += 1
                        if active >= self.max_workers:
                            break
            
            if extract_check_callback:
                extract_check_callback()
                
            time.sleep(1)

    def get_direct_link(self, task):
        direct_link, err_msg = self.extractor.extract_direct_url(task.link, task.file_id)
        if not direct_link:
            task.error_message = err_msg or "Could not get the direct download link. The link may be expired or blocked."
            return None
        return direct_link

    def download_worker(self, task):
        # Quick check: If file is already 100% downloaded on disk, finish immediately without network call
        if os.path.exists(task.filepath) and (task.progress >= 100 or (task.total_bytes > 0 and os.path.getsize(task.filepath) >= task.total_bytes)):
            task.downloaded_bytes = task.total_bytes if task.total_bytes > 0 else os.path.getsize(task.filepath)
            task.progress = 100.0
            task.status = TaskStatus.FINISHED
            task.error_message = ""
            self.trigger_history_save_callback()
            return

        dl_url = self.get_direct_link(task)
        if not dl_url:
            if not task.cancel_flag and not task.pause_flag:
                task.status = TaskStatus.FAILED
                if not task.error_message:
                    task.error_message = "Could not get the direct download link."
            return
            
        if task.cancel_flag:
            task.status = TaskStatus.CANCELLED
            return
            
        if task.pause_flag:
            task.status = TaskStatus.PAUSED
            return

        task.status = TaskStatus.DOWNLOADING
        task.error_message = ""
        
        try:
            if not os.path.exists(task.save_dir):
                try:
                    os.makedirs(task.save_dir, exist_ok=True)
                except Exception as e:
                    task.status = TaskStatus.FAILED
                    task.error_message = f"Failed to create save directory '{task.save_dir}'. {format_error_message(e)}"
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
                return
                
            resume_header = {}
            mode = 'wb'
            if initial_size > 0:
                resume_header = {'Range': f'bytes={initial_size}-'}
                mode = 'ab'
                
            with self.scraper.get(dl_url, stream=True, headers=resume_header) as r:
                if r.status_code not in (200, 206):
                    task.status = TaskStatus.FAILED
                    if r.status_code == 403:
                        task.error_message = f"HTTP 403 (Forbidden): Cloudflare anti-bot blocked your connection. Try toggling your VPN or changing DNS (1.1.1.1)."
                    else:
                        task.error_message = f"Download request failed. Server returned HTTP {r.status_code}."
                    if r.status_code in (403, 503):
                        preview = r.text[:500] if hasattr(r, 'text') else "No text body"
                        logging.error(f"Download 403/503 for {dl_url}. Body preview: {preview}")
                    return
                    
                if r.status_code == 200 and initial_size > 0:
                    mode = 'wb'
                    initial_size = 0
                    
                task.downloaded_bytes = initial_size
                if total_size == 0 and 'content-length' in r.headers:
                    task.total_bytes = int(r.headers['content-length']) + initial_size
                elif total_size == 0:
                    task.total_bytes = 0
                    
                start_time = time.time()
                last_time = start_time
                bytes_since_last = 0
                
                with open(task.filepath, mode) as f:
                    for chunk in r.iter_content(chunk_size=8192*8):
                        if task.pause_flag:
                            task.status = TaskStatus.PAUSED
                            task.speed = 0
                            return
                        if task.cancel_flag:
                            task.status = TaskStatus.CANCELLED
                            task.speed = 0
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
                self.trigger_history_save_callback()
                
        except Exception as e:
            logging.error(f"Download worker error for task {task.link}: {e}", exc_info=True)
            if not task.cancel_flag and not task.pause_flag:
                task.status = TaskStatus.FAILED
                task.error_message = f"Download failed. {format_error_message(e)}"
                self.trigger_history_save_callback()
