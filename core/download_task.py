import os
import re

class DownloadTask:
    def __init__(self, link, base_save_dir, folder_name=None):
        self.link = link.strip()
        self.base_save_dir = base_save_dir
        
        self.file_id = self.link.split('/')[-1].split('#')[0]
        self.filename = self.link.split('#')[-1] if '#' in self.link else self.file_id
        
        if folder_name:
            self.folder_name = folder_name
        else:
            # Fallback calculate smart directory grouping based on prefix
            match = re.search(r'(.*?)(\.part\d+\.rar|\.rar)$', self.filename, re.IGNORECASE)
            if match:
                self.folder_name = match.group(1).strip('._-')
            else:
                self.folder_name = self.filename.rsplit('.', 1)[0]
            
        self.save_dir = os.path.normpath(os.path.join(self.base_save_dir, self.folder_name))
        self.filepath = os.path.normpath(os.path.join(self.save_dir, self.filename))
        
        self.status = "Queued"
        self.progress = 0.0
        self.speed = 0.0
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.error_message = ""
        
        self.pause_flag = False
        self.cancel_flag = False
        self.tree_item = None
        self.is_selected = False

    def to_dict(self):
        return {
            "link": self.link,
            "base_save_dir": self.base_save_dir,
            "folder_name": self.folder_name,
            "status": self.status,
            "error_message": self.error_message,
            "downloaded_bytes": self.downloaded_bytes,
            "total_bytes": self.total_bytes,
            "progress": self.progress
        }
        
    @classmethod
    def from_dict(cls, data):
        task = cls(data["link"], data["base_save_dir"], data["folder_name"])
        # Ensure it doesn't auto-start if it was active when closed
        if data["status"] in ("Downloading", "Pending", "Starting...", "Resolving Container..."):
            task.status = "Paused"
            task.pause_flag = True
        else:
            task.status = data["status"]
            
        task.downloaded_bytes = data.get("downloaded_bytes", 0)
        task.total_bytes = data.get("total_bytes", 0)
        task.progress = data.get("progress", 0.0)
        task.error_message = data.get("error_message", "")
        return task
