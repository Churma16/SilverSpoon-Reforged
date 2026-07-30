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

class BatchStatus(str, Enum):
    STANDBY = "Standby"
    ACTIVE = "Active"
    HAS_FAILURES = "Has Failures"
    EXTRACTING = "Extracting..."
    COMPLETED = "Completed"

    def __str__(self):
        return self.value

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
