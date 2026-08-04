from curl_cffi import requests as cffi_requests
import concurrent.futures
import threading
import time
import sys
import os

from core.rate_limiter import GlobalRateLimiter
from core.extractors.fuckingfast import FuckingFastExtractor

class DownloadManager:
    def __init__(self, links_file, max_workers=3, chunk_size=8192*8, speed_limit_kb=0):
        self.links_file = links_file
        self.max_workers = max_workers
        self.chunk_size = chunk_size
        self.speed_limit_kb = speed_limit_kb
        self.rate_limiter = GlobalRateLimiter()
        self.scraper = cffi_requests.Session(impersonate="chrome")
        self.extractor = FuckingFastExtractor(self.scraper)

        self.total_links = 0
        self.completed_links = 0
        self.failed_links = []
        self.lock = threading.Lock()
        
        # Read links
        with open(links_file, 'r') as f:
            self.links = [line.strip() for line in f if line.strip()]
        self.total_links = len(self.links)

    def extract_direct_url(self, link):
        dl_url, _ = self.extractor.extract_direct_url(link)
        return dl_url

    def download_file(self, link):
        raw_filename = link.split('#')[-1] if '#' in link else link.split('/')[-1]
        filename = os.path.basename(raw_filename)
        
        dl_url = self.extract_direct_url(link)
        if not dl_url:
            with self.lock:
                print(f"[!] Failed to get direct URL for {filename}")
                self.failed_links.append(link)
            return False

        try:
            resume_header = {}
            mode = 'wb'
            initial_size = 0
            
            if os.path.exists(filename):
                initial_size = os.path.getsize(filename)
                
            head_req = self.scraper.head(dl_url)
            total_size = int(head_req.headers.get('content-length', 0))
            
            if initial_size > 0 and initial_size == total_size:
                with self.lock:
                    print(f"[*] {filename} already fully downloaded.")
                    self.completed_links += 1
                return True
                
            if initial_size > 0:
                resume_header = {'Range': f'bytes={initial_size}-'}
                mode = 'ab'

            with self.scraper.get(dl_url, stream=True, headers=resume_header) as r:
                if r.status_code not in (200, 206):
                    with self.lock:
                        print(f"[!] Failed to download {filename}, HTTP {r.status_code}")
                        self.failed_links.append(link)
                    return False
                
                if r.status_code == 200 and initial_size > 0:
                    mode = 'wb'
                    initial_size = 0
                
                dl = initial_size
                if total_size == 0 and 'content-length' in r.headers:
                    total_size = int(r.headers['content-length']) + initial_size
                    
                start_time = time.time()
                last_print = 0
                
                with open(filename, mode) as f:
                    for chunk in r.iter_content(chunk_size=self.chunk_size):
                        if chunk:
                            f.write(chunk)
                            size = len(chunk)
                            dl += size
                            
                            now = time.time()
                            if now - last_print > 1:
                                speed = (size) / (now - last_print + 0.0001) / (1024*1024) if last_print > 0 else 0
                                percent = (dl / total_size) * 100 if total_size > 0 else 0
                                with self.lock:
                                    sys.stdout.write(f"\r[{filename}] {percent:.1f}% | {dl/(1024*1024):.1f}/{total_size/(1024*1024):.1f} MB | {speed:.1f} MB/s{' ' * 20}")
                                    sys.stdout.flush()
                                last_print = now
                                
                            self.rate_limiter.consume(size, self.speed_limit_kb)
                                
                with self.lock:
                    sys.stdout.write(f"\r[{filename}] 100% | Downloaded successfully{' ' * 30}\n")
                    sys.stdout.flush()
                    self.completed_links += 1
                return True
                
        except Exception as e:
            with self.lock:
                print(f"\n[!] Error downloading {filename}: {e}")
                self.failed_links.append(link)
            return False

    def run(self):
        print(f"Starting download of {self.total_links} files with {self.max_workers} concurrent workers...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(self.download_file, link) for link in self.links]
            concurrent.futures.wait(futures)
            
        print("\n" + "="*50)
        print(f"Finished! Completed: {self.completed_links}/{self.total_links}")
        if self.failed_links:
            print("Failed links:")
            for link in self.failed_links:
                print(link)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        links_file = sys.argv[1]
    else:
        links_file = 'link.txt'
    
    manager = DownloadManager(links_file, max_workers=4)
    manager.run()
