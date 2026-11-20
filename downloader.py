import os
import sys
import time
import threading
import concurrent.futures
from typing import List, Optional, Union, Any
from curl_cffi import requests as cffi_requests

from core.download_manager import DownloadManager as CoreDownloadManager
from core.download_task import DownloadTask
from core.rate_limiter import GlobalRateLimiter
from core.extractors.fuckingfast import FuckingFastExtractor
from core.types import TaskStatus


def calculate_speed(bytes_count: int, elapsed_seconds: float) -> float:
    """Calculate transfer speed in MB/s from accumulated bytes over elapsed seconds.

    Addresses Issue #6 by calculating throughput over an interval rather than
    dividing an instantaneous chunk size by total elapsed time.
    """
    if elapsed_seconds <= 0 or bytes_count <= 0:
        return 0.0
    return (bytes_count / elapsed_seconds) / (1024 * 1024)


class SpeedTracker:
    """Tracks elapsed time and accumulated byte counts across download chunks,

    applying Exponential Moving Average (EMA) smoothing to prevent volatile
    speed fluctuations across sampling intervals.
    """

    def __init__(self, interval: float = 0.5, alpha: float = 0.3):
        self.interval = max(0.001, float(interval))
        self.alpha = max(0.0, min(1.0, float(alpha)))
        self.accumulated_bytes = 0
        self.last_time = time.time()
        self.current_speed = 0.0
        self.has_initial_sample = False
        self.lock = threading.Lock()

    def add_bytes(self, size: int) -> None:
        """Accumulate received chunk size."""
        with self.lock:
            self.accumulated_bytes += size

    def get_speed(self, current_time: Optional[float] = None) -> float:
        """Compute current smoothed speed in MB/s using EMA if interval has passed."""
        with self.lock:
            evaluation_time = time.time() if current_time is None else current_time
            elapsed_seconds = evaluation_time - self.last_time
            if elapsed_seconds >= self.interval:
                instantaneous_speed = calculate_speed(self.accumulated_bytes, elapsed_seconds)
                if not self.has_initial_sample:
                    if instantaneous_speed > 0.0:
                        self.current_speed = instantaneous_speed
                        self.has_initial_sample = True
                    else:
                        self.current_speed = 0.0
                else:
                    self.current_speed = (self.alpha * instantaneous_speed) + ((1.0 - self.alpha) * self.current_speed)
                    if self.current_speed < 0.001 and instantaneous_speed == 0.0:
                        self.current_speed = 0.0
                        self.has_initial_sample = False

                self.accumulated_bytes = 0
                self.last_time = evaluation_time
            return self.current_speed

    def reset(self, current_time: Optional[float] = None) -> None:
        """Reset byte counter, timing, and smoothed speed."""
        with self.lock:
            self.accumulated_bytes = 0
            self.last_time = time.time() if current_time is None else current_time
            self.current_speed = 0.0
            self.has_initial_sample = False


class DownloadManager:
    """CLI Download Manager runner that imports and reuses CoreDownloadManager."""

    def __init__(
        self,
        links_file: Union[str, List[str]],
        max_workers: int = 4,
        chunk_size: int = 8192 * 8,
        speed_limit_kb: int = 0,
        output_dir: Optional[str] = None,
        scraper: Optional[cffi_requests.Session] = None,
        extractor: Optional[Any] = None,
        rate_limiter: Optional[GlobalRateLimiter] = None
    ):
        self.max_workers = max_workers
        self.chunk_size = chunk_size
        self.speed_limit_kb = speed_limit_kb
        self.output_dir = output_dir or os.getcwd()
        self.lock = threading.Lock()
        self.speed_tracker = SpeedTracker(interval=0.5, alpha=0.3)

        # Parse links from list or file
        if isinstance(links_file, (list, tuple)):
            self.links = [line.strip() for line in links_file if line.strip()]
        elif isinstance(links_file, str):
            if os.path.isfile(links_file):
                with open(links_file, "r", encoding="utf-8") as f:
                    self.links = [line.strip() for line in f if line.strip()]
            else:
                self.links = []
        else:
            self.links = []

        self.total_links = len(self.links)
        self.completed_links = 0
        self.failed_links = []
        self._completed_links_set = set()

        # Build DownloadTasks
        self.tasks: List[DownloadTask] = []
        for link in self.links:
            task = DownloadTask(link=link, base_save_dir=self.output_dir)
            task.save_dir = os.path.abspath(self.output_dir)
            task.filepath = os.path.normpath(os.path.join(task.save_dir, task.filename))
            self.tasks.append(task)

        # Shared core components
        self.rate_limiter = rate_limiter or GlobalRateLimiter()
        self.scraper = scraper or cffi_requests.Session(impersonate="chrome")
        self.extractor = extractor or FuckingFastExtractor(self.scraper)

        self.settings = {"download_speed_limit": self.speed_limit_kb}
        self.core_manager = CoreDownloadManager(
            tasks=self.tasks,
            max_workers=self.max_workers,
            rate_limiter=self.rate_limiter,
            scraper=self.scraper,
            extractor=self.extractor,
            settings=self.settings,
            session_bytes_lock_callback=self._on_chunk_received,
            trigger_history_save_callback=self._on_history_save,
        )

    def _on_chunk_received(self, size: int) -> None:
        self.speed_tracker.add_bytes(size)

    def _on_history_save(self) -> None:
        pass

    def extract_direct_url(self, link: str) -> Optional[str]:
        """Convenience method delegating to extractor."""
        raw_url = link.split('#')[0].split('?')[0].rstrip('/')
        file_id = os.path.basename(raw_url) if '/' in raw_url else raw_url
        dl_url, _ = self.extractor.extract_direct_url(link, file_id)
        return dl_url

    def download_file(self, link: str) -> bool:
        """Download a single link using core download manager worker."""
        task = next((t for t in self.tasks if t.link == link), None)
        if task is None:
            task = DownloadTask(link=link, base_save_dir=self.output_dir)
            task.save_dir = os.path.abspath(self.output_dir)
            task.filepath = os.path.normpath(os.path.join(task.save_dir, task.filename))
            self.tasks.append(task)

        self.core_manager.is_running = True
        task.status = TaskStatus.IN_QUEUE
        task.pause_flag = False
        task.cancel_flag = False

        self.core_manager.download_worker(task)

        if task.status == TaskStatus.FINISHED:
            with self.lock:
                if link not in self._completed_links_set:
                    self._completed_links_set.add(link)
                    self.completed_links = len(self._completed_links_set)
                sys.stdout.write(f"\r[{task.filename}] 100% | Downloaded successfully{' ' * 30}\n")
                sys.stdout.flush()
            return True
        else:
            with self.lock:
                if link not in self.failed_links:
                    self.failed_links.append(link)
                error_msg = task.error_message or "Download failed"
                sys.stdout.write(f"\r[!] Error downloading {task.filename}: {error_msg}{' ' * 30}\n")
                sys.stdout.flush()
            return False

    def run(self) -> None:
        """Run multi-threaded batch download of all configured links."""
        print(f"Starting download of {self.total_links} files with {self.max_workers} concurrent workers...")
        if not self.links:
            print("No links to download.")
            return

        self.core_manager.is_running = True
        stop_progress_monitor = threading.Event()

        def progress_monitor():
            while not stop_progress_monitor.is_set():
                speed = self.speed_tracker.get_speed()
                active_tasks = [
                    t for t in self.tasks
                    if t.status in (TaskStatus.DOWNLOADING, TaskStatus.CONNECTING, TaskStatus.SOLVING_SESSION)
                ]
                if active_tasks:
                    first_active = active_tasks[0]
                    total_mb = first_active.total_bytes / (1024 * 1024) if first_active.total_bytes > 0 else 0.0
                    dl_mb = first_active.downloaded_bytes / (1024 * 1024)
                    percent = first_active.progress
                    active_count = len(active_tasks)
                    extra = f" (+{active_count - 1} more)" if active_count > 1 else ""
                    with self.lock:
                        sys.stdout.write(
                            f"\r[{first_active.filename}{extra}] {percent:.1f}% | {dl_mb:.1f}/{total_mb:.1f} MB | {speed:.1f} MB/s{' ' * 20}"
                        )
                        sys.stdout.flush()
                time.sleep(0.5)

        monitor_thread = threading.Thread(target=progress_monitor, daemon=True)
        monitor_thread.start()

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = [executor.submit(self.download_file, link) for link in self.links]
                concurrent.futures.wait(futures)
        finally:
            stop_progress_monitor.set()
            monitor_thread.join(timeout=1.0)
            self.core_manager.stop()

        print("\n" + "=" * 50)
        print(f"Finished! Completed: {self.completed_links}/{self.total_links}")
        if self.failed_links:
            print("Failed links:")
            for link in self.failed_links:
                print(link)


CLIDownloadManager = DownloadManager


def main():
    import argparse

    parser = argparse.ArgumentParser(description="SilverSpoon Reforged CLI Bulk Downloader")
    parser.add_argument("links_file", nargs="?", default="link.txt", help="Path to links text file (default: link.txt)")
    parser.add_argument("-w", "--workers", type=int, default=4, help="Number of concurrent download workers (default: 4)")
    parser.add_argument("-l", "--limit", type=int, default=0, help="Download speed limit in KB/s (default: 0 = unlimited)")
    parser.add_argument("-o", "--output-dir", type=str, default=None, help="Output directory for downloaded files")
    args = parser.parse_args()

    if not os.path.exists(args.links_file):
        print(f"Error: Links file '{args.links_file}' not found.")
        sys.exit(1)

    manager = DownloadManager(
        links_file=args.links_file,
        max_workers=args.workers,
        speed_limit_kb=args.limit,
        output_dir=args.output_dir
    )
    manager.run()


if __name__ == "__main__":
    main()
