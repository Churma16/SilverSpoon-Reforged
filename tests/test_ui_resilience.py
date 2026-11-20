import pytest
import math
from PyQt6.QtWidgets import QApplication, QTreeWidgetItem
from ui.widgets import ReorderableTreeWidget
from ui.tree_adapter import TaskTreeAdapter
from ui.dialogs import SettingsDialog


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.mark.unit
def test_format_time_none_and_nan():
    assert TaskTreeAdapter.format_time(None) == "-"
    assert TaskTreeAdapter.format_time(float("nan")) == "-"
    assert TaskTreeAdapter.format_time(float("inf")) == "-"
    assert TaskTreeAdapter.format_time(0) == "-"
    assert TaskTreeAdapter.format_time(-10) == "-"
    assert TaskTreeAdapter.format_time(65) == "1m 5s"


@pytest.mark.unit
def test_settings_dialog_preserves_unmanaged_keys(qapp):
    initial_settings = {
        "default_save_dir": "C:/Downloads",
        "max_workers": 3,
        "download_speed_limit": 0,
        "extract_after_download": True,
        "skip_delete_confirmation": False,
        "enable_notifications": True,
        "minimize_to_tray": False,
        "auto_check_updates": False,
        # Unmanaged settings:
        "auto_shutdown_on_completion": True,
        "auto_shutdown_action": "Sleep",
        "custom_key_for_plugins": 12345
    }

    dialog = SettingsDialog(initial_settings)
    updated = dialog.get_updated_settings()

    # Unmanaged keys must be preserved exactly
    assert updated.get("auto_shutdown_on_completion") is True
    assert updated.get("auto_shutdown_action") == "Sleep"
    assert updated.get("custom_key_for_plugins") == 12345
    assert updated.get("default_save_dir") == "C:/Downloads"


@pytest.mark.unit
def test_reorderable_tree_normalize_structure_preserves_batch_children(qapp):
    tree = ReorderableTreeWidget()

    # Create BatchA with TaskA
    batch_a = QTreeWidgetItem(["BatchA"])
    task_a = QTreeWidgetItem(["TaskA.rar"])
    batch_a.addChild(task_a)
    tree.addTopLevelItem(batch_a)

    # Accidentally nested BatchB (which has TaskB) inside BatchA
    batch_b = QTreeWidgetItem(["BatchB"])
    task_b = QTreeWidgetItem(["TaskB.rar"])
    batch_b.addChild(task_b)
    batch_a.addChild(batch_b)

    assert tree.topLevelItemCount() == 1
    assert batch_a.childCount() == 2  # TaskA and BatchB

    # Normalize structure must promote BatchB to top level without stripping TaskB
    tree.normalize_structure()

    assert tree.topLevelItemCount() == 2
    assert batch_a.childCount() == 1
    assert batch_a.child(0).text(0) == "TaskA.rar"

    assert batch_b.childCount() == 1
    assert batch_b.child(0).text(0) == "TaskB.rar"


@pytest.mark.unit
def test_load_initial_history_suppresses_completed_batch_notifications(qapp, monkeypatch, tmp_path):
    from controllers.download_controller import DownloadController
    from core.download_task import DownloadTask
    from core.types import TaskStatus

    completed_task = DownloadTask("https://fuckingfast.co/done01#File1.rar", str(tmp_path), folder_name="BatchDone")
    completed_task.status = TaskStatus.FINISHED

    failed_task = DownloadTask("https://fuckingfast.co/fail01#File2.rar", str(tmp_path), folder_name="BatchFail")
    failed_task.status = TaskStatus.FAILED

    pending_task = DownloadTask("https://fuckingfast.co/pend01#File3.rar", str(tmp_path), folder_name="BatchPending")
    pending_task.status = TaskStatus.IN_QUEUE

    monkeypatch.setattr("controllers.download_controller.load_history", lambda: [completed_task, failed_task, pending_task])
    monkeypatch.setattr("controllers.download_controller.save_history", lambda tasks: None)

    controller = DownloadController(str(tmp_path), settings={})
    controller.load_initial_history()

    # Completed and failed historical batches must be pre-marked to suppress startup notifications
    assert "BatchDone" in controller.notified_batches
    assert "BatchFail_err" in controller.notified_batches
    assert "BatchPending" not in controller.notified_batches

    # Retrying the failed task must clear the error notification suppression
    controller.start_downloads([failed_task])
    assert "BatchFail_err" not in controller.notified_batches
    assert "BatchFail" not in controller.notified_batches

