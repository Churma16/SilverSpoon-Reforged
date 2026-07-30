from enum import Enum

class TaskStatus(str, Enum):
    STANDBY = "Standby"
    IN_QUEUE = "In Queue"
    CONNECTING = "Connecting..."
    DOWNLOADING = "Downloading"
    PAUSING = "Pausing..."
    PAUSED = "Paused"
    CANCELLED = "Cancelled"
    FAILED = "Failed"
    FINISHED = "Finished"
    UNPACKING = "Unpacking..."
    EXTRACTED = "Extracted"
    EXTRACT_ERROR = "Extract Error"

    def __str__(self):
        return self.value

    @property
    def color(self) -> str:
        color_map = {
            TaskStatus.STANDBY: "#95a5a6",
            TaskStatus.IN_QUEUE: "#f39c12",
            TaskStatus.CONNECTING: "#3498db",
            TaskStatus.DOWNLOADING: "#2ecc71",
            TaskStatus.PAUSING: "#f1c40f",
            TaskStatus.PAUSED: "#f1c40f",
            TaskStatus.CANCELLED: "#7f8c8d",
            TaskStatus.FAILED: "#e74c3c",
            TaskStatus.FINISHED: "#2ecc71",
            TaskStatus.UNPACKING: "#9b59b6",
            TaskStatus.EXTRACTED: "#8e44ad",
            TaskStatus.EXTRACT_ERROR: "#c0392b",
        }
        return color_map.get(self, "#ffffff")

class BatchStatus(str, Enum):
    STANDBY = "Standby"
    ACTIVE = "Active"
    HAS_FAILURES = "Has Failures"
    EXTRACTING = "Extracting..."
    COMPLETED = "Completed"

    def __str__(self):
        return self.value

    @property
    def color(self) -> str:
        color_map = {
            BatchStatus.STANDBY: "#95a5a6",
            BatchStatus.ACTIVE: "#3498db",
            BatchStatus.HAS_FAILURES: "#e74c3c",
            BatchStatus.EXTRACTING: "#9b59b6",
            BatchStatus.COMPLETED: "#2ecc71",
        }
        return color_map.get(self, "#ffffff")

STATUS_MIGRATION = {
    "Queued": TaskStatus.STANDBY,
    "Pending": TaskStatus.IN_QUEUE,
    "Starting...": TaskStatus.CONNECTING,
    "Resolving Container...": TaskStatus.CONNECTING,
    "Error": TaskStatus.FAILED,
    "Completed": TaskStatus.FINISHED,
    "Extracting...": TaskStatus.UNPACKING,
}

def migrate_status(raw_status: str) -> TaskStatus:
    if raw_status in STATUS_MIGRATION:
        return STATUS_MIGRATION[raw_status]
    try:
        return TaskStatus(raw_status)
    except ValueError:
        return TaskStatus.STANDBY
