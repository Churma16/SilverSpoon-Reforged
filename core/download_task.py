import os
import re
from core.types import TaskStatus, migrate_status

class DownloadTask:
    def __init__(self, link, base_save_dir, folder_name=None):
        self.link = link.strip()
        self.base_save_dir = base_save_dir
        
        raw_file_id = self.link.split('/')[-1].split('#')[0]
        raw_filename = self.link.split('#')[-1] if '#' in self.link else raw_file_id
        
        self.file_id = os.path.basename(raw_file_id)
        self.filename = os.path.basename(raw_filename)
        
        if folder_name:
            self.folder_name = os.path.basename(folder_name)
        else:
            # Fallback calculate smart directory grouping based on prefix
            match = re.search(r'(.*?)(\.part\d+\.rar|\.rar)$', self.filename, re.IGNORECASE)
            if match:
                self.folder_name = match.group(1).strip('._-')
            else:
                self.folder_name = self.filename.rsplit('.', 1)[0]
            self.folder_name = os.path.basename(self.folder_name)
            
        self.save_dir = os.path.normpath(os.path.join(self.base_save_dir, self.folder_name))
        self.filepath = os.path.normpath(os.path.join(self.save_dir, self.filename))
        
        self.status = TaskStatus.STANDBY
        self.progress = 0.0
        self.speed = 0.0
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.error_message = ""
        self.started_at = None
        self.elapsed_seconds = 0.0
        
        self.pause_flag = False
        self.cancel_flag = False
        self.tree_item = None
        self.is_selected = False

    def to_dict(self):
        return {
            "link": self.link,
            "base_save_dir": self.base_save_dir,
            "folder_name": self.folder_name,
            "status": str(self.status),
            "error_message": self.error_message,
            "downloaded_bytes": self.downloaded_bytes,
            "total_bytes": self.total_bytes,
            "progress": self.progress,
            "elapsed_seconds": self.elapsed_seconds
        }
        
    @classmethod
    def from_dict(cls, data):
        task = cls(data["link"], data["base_save_dir"], data["folder_name"])
        raw_status = data.get("status", "Standby")
        migrated = migrate_status(raw_status)
        
        # Ensure it doesn't auto-start if it was active when closed
        if migrated in (TaskStatus.DOWNLOADING, TaskStatus.IN_QUEUE, TaskStatus.CONNECTING, TaskStatus.BYPASSING_CF):
            task.status = TaskStatus.PAUSED
            task.pause_flag = True
        else:
            task.status = migrated
            
        task.downloaded_bytes = data.get("downloaded_bytes", 0)
        task.total_bytes = data.get("total_bytes", 0)
        task.progress = data.get("progress", 0.0)
        task.error_message = data.get("error_message", "")
        task.elapsed_seconds = data.get("elapsed_seconds", 0.0)
        return task
