import os
import pytest
from core.download_task import DownloadTask
from core.types import TaskStatus


@pytest.mark.unit
def test_download_task_filename_parsing():
    base_directory = "C:/Downloads"

    # Standard URL without hash fragment
    task_standard = DownloadTask("https://fuckingfast.co/c7o9muwfdksh", base_directory)
    assert task_standard.file_id == "c7o9muwfdksh"
    assert task_standard.filename == "c7o9muwfdksh"

    # URL with hash fragment specifying actual filename
    task_with_hash = DownloadTask("https://fuckingfast.co/c7o9muwfdksh#Cyberpunk_2077.rar", base_directory)
    assert task_with_hash.file_id == "c7o9muwfdksh"
    assert task_with_hash.filename == "Cyberpunk_2077.rar"


@pytest.mark.unit
def test_download_task_multipart_folder_grouping():
    base_directory = "C:/Downloads"

    # Multi-part archive should be grouped into a common folder name stripped of part suffix
    task_part_one = DownloadTask(
        "https://fuckingfast.co/file01#Game_Archive.part01.rar",
        base_directory
    )
    task_part_two = DownloadTask(
        "https://fuckingfast.co/file02#Game_Archive.part02.rar",
        base_directory
    )

    assert task_part_one.folder_name == "Game_Archive"
    assert task_part_two.folder_name == "Game_Archive"
    assert task_part_one.save_dir == os.path.normpath("C:/Downloads/Game_Archive")
    assert task_part_two.save_dir == os.path.normpath("C:/Downloads/Game_Archive")


@pytest.mark.unit
def test_download_task_custom_folder_name_override():
    base_directory = "C:/Downloads"
    task = DownloadTask(
        "https://fuckingfast.co/file01#Sample.rar",
        base_directory,
        folder_name="CustomBatchFolder"
    )
    assert task.folder_name == "CustomBatchFolder"
    assert task.save_dir == os.path.normpath("C:/Downloads/CustomBatchFolder")


@pytest.mark.unit
def test_download_task_serialization_roundtrip():
    base_directory = "C:/Downloads"
    original_task = DownloadTask("https://fuckingfast.co/file01#Sample.rar", base_directory)
    original_task.downloaded_bytes = 1048576
    original_task.total_bytes = 5242880
    original_task.progress = 20.0
    original_task.status = TaskStatus.FINISHED

    serialized_data = original_task.to_dict()
    restored_task = DownloadTask.from_dict(serialized_data)

    assert restored_task.link == original_task.link
    assert restored_task.folder_name == original_task.folder_name
    assert restored_task.downloaded_bytes == 1048576
    assert restored_task.total_bytes == 5242880
    assert restored_task.progress == 20.0
    assert restored_task.status == TaskStatus.FINISHED


@pytest.mark.unit
def test_download_task_restore_active_state_safety():
    base_directory = "C:/Downloads"
    raw_saved_data = {
        "link": "https://fuckingfast.co/file01#Sample.rar",
        "base_save_dir": base_directory,
        "folder_name": "Sample",
        "status": "Downloading",
        "downloaded_bytes": 1000,
        "total_bytes": 2000,
        "progress": 50.0,
        "error_message": "",
        "elapsed_seconds": 12.0
    }

    # Tasks saved while active must be migrated to PAUSED upon restore to avoid auto-starting unexpectedly
    restored_task = DownloadTask.from_dict(raw_saved_data)
    assert restored_task.status == TaskStatus.PAUSED
    assert restored_task.pause_flag is True
