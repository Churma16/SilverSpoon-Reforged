import threading
import time

class GlobalRateLimiter:
    def __init__(self):
        self.lock = threading.Lock()
        self.tokens = 0.0
        self.last_update = time.time()

    def consume(self, chunk_bytes, limit_kb):
        if limit_kb <= 0:
            return
            
        limit_bytes = limit_kb * 1024.0
        
        while True:
            with self.lock:
                now = time.time()
                elapsed = now - self.last_update
                self.last_update = now
                
                self.tokens += elapsed * limit_bytes
                if self.tokens > limit_bytes:
                    self.tokens = limit_bytes
                    
                if self.tokens >= chunk_bytes:
                    self.tokens -= chunk_bytes
                    return
                
                needed = chunk_bytes - self.tokens
                wait_time = needed / limit_bytes

            time.sleep(max(wait_time, 0.005))
