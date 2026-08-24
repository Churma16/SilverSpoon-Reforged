import os
import time
import textwrap
from typing import List, Set, Callable, Optional, Dict
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import QTreeWidgetItem, QTreeWidget, QSystemTrayIcon

from core.types import TaskStatus, BatchStatus
from core.download_task import DownloadTask
from utils.formatters import format_size_progress


class TaskTreeAdapter:
    """Adapter/Presenter responsible for populating, formatting, and updating the task tree view."""

    def __init__(self, tree_widget: QTreeWidget, get_tasks_callback: Callable[[], List[DownloadTask]]):
        self.tree = tree_widget
        self.get_tasks = get_tasks_callback
        self.is_all_selected = False

    def get_or_create_batch_item(self, folder_name: str) -> QTreeWidgetItem:
        """Retrieves an existing batch item by folder name or creates a new top-level tree item."""
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            stored_folder = item.data(0, Qt.ItemDataRole.UserRole) or item.text(0)
            if stored_folder == folder_name:
                return item

        batch_item = QTreeWidgetItem(self.tree)
        batch_item.setFlags(
            Qt.ItemFlag.ItemIsDragEnabled |
            Qt.ItemFlag.ItemIsDropEnabled |
            Qt.ItemFlag.ItemIsUserCheckable |
            Qt.ItemFlag.ItemIsEnabled |
            Qt.ItemFlag.ItemIsSelectable
        )
        batch_item.setData(0, Qt.ItemDataRole.UserRole, folder_name)
        batch_item.setText(0, folder_name)
        batch_item.setCheckState(1, Qt.CheckState.Unchecked)
        batch_item.setExpanded(False)
        return batch_item

    def add_task_item(self, task: DownloadTask) -> QTreeWidgetItem:
        """Creates and attaches a QTreeWidgetItem representing the download task."""
        batch_item = self.get_or_create_batch_item(task.folder_name)

        child_item = QTreeWidgetItem(batch_item)
        child_item.setFlags(
            Qt.ItemFlag.ItemIsDragEnabled |
            Qt.ItemFlag.ItemIsDropEnabled |
            Qt.ItemFlag.ItemIsUserCheckable |
            Qt.ItemFlag.ItemIsEnabled |
            Qt.ItemFlag.ItemIsSelectable
        )

        child_item.setText(0, task.filename)

        check_state = Qt.CheckState.Checked if task.is_selected else Qt.CheckState.Unchecked
        child_item.setCheckState(1, check_state)

        status_val = getattr(task.status, 'value', str(task.status))
        child_item.setText(2, status_val)
        status_color = getattr(task.status, 'color', '#ffffff')
        child_item.setForeground(2, QBrush(QColor(status_color)))
        child_item.setText(3, "0%")
        child_item.setText(4, "-")
        child_item.setText(5, "-")
        child_item.setText(6, "-")
        child_item.setText(7, "-")

        task.tree_item = child_item
        return child_item

    def remove_task_item(self, task: DownloadTask):
        """Removes the task item and cleans up parent batch item if empty."""
        if task.tree_item:
            parent = task.tree_item.parent()
            if parent:
                parent.removeChild(task.tree_item)
                if parent.childCount() == 0:
                    idx = self.tree.indexOfTopLevelItem(parent)
                    if idx >= 0:
                        self.tree.takeTopLevelItem(idx)
            task.tree_item = None

    def toggle_select_all(self):
        """Toggles checkbox selection for all items across the tree."""
        all_checked = True
        total_items = 0

        for i in range(self.tree.topLevelItemCount()):
            batch_item = self.tree.topLevelItem(i)
            if batch_item.checkState(1) != Qt.CheckState.Checked:
                all_checked = False
            for j in range(batch_item.childCount()):
                total_items += 1
                if batch_item.child(j).checkState(1) != Qt.CheckState.Checked:
                    all_checked = False

        if total_items == 0:
            return

        self.is_all_selected = not all_checked
        state = Qt.CheckState.Checked if self.is_all_selected else Qt.CheckState.Unchecked

        for i in range(self.tree.topLevelItemCount()):
            batch_item = self.tree.topLevelItem(i)
            batch_item.setCheckState(1, state)
            for j in range(batch_item.childCount()):
                child_item = batch_item.child(j)
                child_item.setCheckState(1, state)

        tasks = self.get_tasks()
        for task in tasks:
            task.is_selected = self.is_all_selected

    def handle_item_clicked(self, item: QTreeWidgetItem, col: int):
        """Handles checkbox click propagation between parent batch and children."""
        if col == 1:
            state = item.checkState(1)
            tasks = self.get_tasks()

            if item.parent() is None:
                for i in range(item.childCount()):
                    child = item.child(i)
                    child.setCheckState(1, state)
                    task = next((t for t in tasks if t.tree_item == child), None)
                    if task:
                        task.is_selected = (state == Qt.CheckState.Checked)
            else:
                task = next((t for t in tasks if t.tree_item == item), None)
                if task:
                    task.is_selected = (state == Qt.CheckState.Checked)

    def handle_item_selection_changed(self):
        """Synchronizes checkbox state with tree item highlight selections."""
        tasks = self.get_tasks()
        for i in range(self.tree.topLevelItemCount()):
            top_item = self.tree.topLevelItem(i)
            if top_item.isSelected():
                top_item.setCheckState(1, Qt.CheckState.Checked)
            else:
                top_item.setCheckState(1, Qt.CheckState.Unchecked)

            for j in range(top_item.childCount()):
                child = top_item.child(j)
                if top_item.isSelected() or child.isSelected():
                    child.setCheckState(1, Qt.CheckState.Checked)
                    task = next((t for t in tasks if t.tree_item == child), None)
                    if task:
                        task.is_selected = True
                else:
                    child.setCheckState(1, Qt.CheckState.Unchecked)
                    task = next((t for t in tasks if t.tree_item == child), None)
                    if task:
                        task.is_selected = False

    def get_selected_tasks(self) -> List[DownloadTask]:
        """Returns currently checked or selected tasks."""
        tasks = self.get_tasks()
        checked = [t for t in tasks if t.tree_item and t.tree_item.checkState(1) == Qt.CheckState.Checked]
        if checked:
            return checked

        selected_items = self.tree.selectedItems()
        selected_tasks = []
        for item in selected_items:
            if item.parent() is None:
                for i in range(item.childCount()):
                    child = item.child(i)
                    task = next((t for t in tasks if t.tree_item == child), None)
                    if task and task not in selected_tasks:
                        selected_tasks.append(task)
            else:
                task = next((t for t in tasks if t.tree_item == item), None)
                if task and task not in selected_tasks:
                    selected_tasks.append(task)
        return selected_tasks

    def get_reordered_tasks(self) -> List[DownloadTask]:
        """Extracts task ordering based on current tree top-to-bottom layout."""
        tasks = self.get_tasks()
        reordered_task_list = []
        for batch_index in range(self.tree.topLevelItemCount()):
            top_level_batch_item = self.tree.topLevelItem(batch_index)
            current_folder_name = top_level_batch_item.data(0, Qt.ItemDataRole.UserRole) or top_level_batch_item.text(0)

            for child_index in range(top_level_batch_item.childCount()):
                child_task_item = top_level_batch_item.child(child_index)
                matching_task = next((task for task in tasks if task.tree_item == child_task_item), None)
                if matching_task:
                    if matching_task.folder_name != current_folder_name:
                        matching_task.folder_name = current_folder_name
                    reordered_task_list.append(matching_task)

        for task in tasks:
            if task not in reordered_task_list:
                reordered_task_list.append(task)

        return reordered_task_list

    @staticmethod
    def format_time(seconds: float) -> str:
        """Formats seconds into human-readable duration string."""
        if seconds <= 0 or seconds == float('inf'):
            return "-"
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}h {m}m"
        elif m > 0:
            return f"{m}m {s}s"
        else:
            return f"{s}s"

    def update_tree_display(
        self,
        global_speed: float,
        notified_batches: Set[str],
        send_notification_callback: Optional[Callable[[str, str, object], None]] = None
    ) -> Dict[str, float]:
        """Refreshes all tree items, progress text, speeds, ETAs, and returns folder estimated sizes."""
        tasks = self.get_tasks()
        folder_estimated_sizes = {}
        folder_tasks_map = {}
        all_known_sizes = [t.total_bytes for t in tasks if getattr(t, 'total_bytes', 0) > 0]
        global_avg_size = (sum(all_known_sizes) / len(all_known_sizes)) if all_known_sizes else 0

        for task in tasks:
            fn = getattr(task, 'folder_name', 'Default')
            if fn not in folder_tasks_map:
                folder_tasks_map[fn] = []
            folder_tasks_map[fn].append(task)

        for fn, f_tasks in folder_tasks_map.items():
            known = [t.total_bytes for t in f_tasks if getattr(t, 'total_bytes', 0) > 0]
            if known:
                folder_estimated_sizes[fn] = sum(known) / len(known)
            else:
                folder_estimated_sizes[fn] = global_avg_size

        for task in tasks:
            if not task.tree_item:
                continue

            prog_str = f"{task.progress:.1f}%" if task.status not in (TaskStatus.EXTRACTED, TaskStatus.UNPACKING, TaskStatus.EXTRACT_ERROR) else "-"
            speed_str = f"{task.speed:.2f} MB/s" if task.status == TaskStatus.DOWNLOADING else "-"
            size_str = format_size_progress(task.downloaded_bytes, task.total_bytes) if task.total_bytes > 0 else "-"

            elapsed_sec = getattr(task, 'elapsed_seconds', 0.0)
            if getattr(task, 'started_at', None):
                elapsed_sec += time.time() - task.started_at
            elapsed_str = self.format_time(elapsed_sec) if elapsed_sec > 0 else "-"

            eta_str = "-"
            if task.status == TaskStatus.DOWNLOADING:
                remaining_bytes = max(0, task.total_bytes - task.downloaded_bytes)
                if task.speed > 0 and task.total_bytes > 0:
                    eta_seconds = remaining_bytes / (task.speed * 1024 * 1024)
                    eta_str = self.format_time(eta_seconds)
                task.tree_item.setToolTip(6, "")
            elif task.status in (TaskStatus.IN_QUEUE, TaskStatus.STANDBY, TaskStatus.CONNECTING, TaskStatus.SOLVING_SESSION):
                eta_str = "-"
                task.tree_item.setToolTip(6, "Waiting in queue")
            elif task.status in (TaskStatus.FINISHED, TaskStatus.EXTRACTED, TaskStatus.UNPACKING):
                eta_str = "-"
                task.tree_item.setToolTip(6, "")

            task.tree_item.setText(2, str(task.status))
            status_color = getattr(task.status, 'color', '#ffffff')
            task.tree_item.setForeground(2, QBrush(QColor(status_color)))

            if ("Failed" in str(task.status) or "Error" in str(task.status)) and task.error_message:
                wrapped_text = "\n".join(textwrap.wrap(task.error_message, width=60))
                task.tree_item.setToolTip(2, wrapped_text)
            else:
                task.tree_item.setToolTip(2, "")

            task.tree_item.setText(3, prog_str)
            task.tree_item.setText(4, speed_str)
            task.tree_item.setText(5, elapsed_str)
            task.tree_item.setText(6, eta_str)
            task.tree_item.setText(7, size_str)

        # Update batch level rows
        for i in range(self.tree.topLevelItemCount()):
            batch_item = self.tree.topLevelItem(i)
            total_dl = 0
            total_size = 0
            total_speed = 0.0
            total_elapsed = 0.0

            all_completed = True
            any_error = False
            any_downloading = False

            child_count = batch_item.childCount()
            if child_count == 0:
                continue

            for j in range(child_count):
                child = batch_item.child(j)
                task = next((t for t in tasks if t.tree_item == child), None)
                if task:
                    total_dl += task.downloaded_bytes
                    if task.total_bytes > 0:
                        total_size += task.total_bytes
                    else:
                        fn = getattr(task, 'folder_name', 'Default')
                        total_size += folder_estimated_sizes.get(fn, 0)
                    total_speed += getattr(task, 'speed', 0.0)

                    task_elapsed = getattr(task, 'elapsed_seconds', 0.0)
                    if getattr(task, 'started_at', None):
                        task_elapsed += time.time() - task.started_at
                    total_elapsed += task_elapsed

                    if task.status not in (TaskStatus.FINISHED, TaskStatus.EXTRACTED):
                        all_completed = False
                    if "Failed" in str(task.status) or "Error" in str(task.status):
                        any_error = True
                    if task.status in (TaskStatus.DOWNLOADING, TaskStatus.CONNECTING, TaskStatus.SOLVING_SESSION, TaskStatus.IN_QUEUE):
                        any_downloading = True

            batch_status = BatchStatus.STANDBY
            if all_completed:
                if any(t.status == TaskStatus.UNPACKING for t in [next((t for t in tasks if t.tree_item == batch_item.child(k)), None) for k in range(batch_item.childCount()) if next((t for t in tasks if t.tree_item == batch_item.child(k)), None)]):
                    batch_status = BatchStatus.EXTRACTING
                else:
                    batch_status = BatchStatus.COMPLETED
            elif any_error:
                batch_status = BatchStatus.HAS_FAILURES
            elif any_downloading:
                batch_status = BatchStatus.ACTIVE

            prog = (total_dl / total_size * 100) if total_size > 0 else 0
            prog_str = f"{prog:.1f}%"
            speed_str = f"{total_speed:.2f} MB/s" if total_speed > 0 else "-"

            folder_name = batch_item.data(0, Qt.ItemDataRole.UserRole) or batch_item.text(0)
            batch_item.setText(0, folder_name)
            size_str = format_size_progress(total_dl, total_size) if total_size > 0 else "-"

            elapsed_str = self.format_time(total_elapsed) if total_elapsed > 0 else "-"

            eta_str = "-"
            remaining_batch_bytes = max(0, total_size - total_dl)
            if any_downloading and remaining_batch_bytes > 0:
                if total_speed > 0:
                    eta_seconds = remaining_batch_bytes / (total_speed * 1024 * 1024)
                    eta_str = self.format_time(eta_seconds)
                elif global_speed > 0:
                    eta_seconds = remaining_batch_bytes / (global_speed * 1024 * 1024)
                    eta_str = f"~{self.format_time(eta_seconds)}"

            batch_item.setText(2, str(batch_status))
            status_color = getattr(batch_status, 'color', '#ffffff')
            batch_item.setForeground(2, QBrush(QColor(status_color)))
            batch_item.setToolTip(2, "")
            batch_item.setText(3, prog_str)
            batch_item.setText(4, speed_str)
            batch_item.setText(5, elapsed_str)
            batch_item.setText(6, eta_str)
            batch_item.setText(7, size_str)

            if send_notification_callback:
                if batch_status in (BatchStatus.COMPLETED, TaskStatus.EXTRACTED) and folder_name not in notified_batches:
                    notified_batches.add(folder_name)
                    send_notification_callback("Batch Finished", f"Batch '{folder_name}' is {str(batch_status).lower()}!", QSystemTrayIcon.MessageIcon.Information)
                elif batch_status == BatchStatus.HAS_FAILURES and (folder_name + "_err") not in notified_batches:
                    notified_batches.add(folder_name + "_err")
                    send_notification_callback("Batch Error", f"Batch '{folder_name}' has tasks with errors.", QSystemTrayIcon.MessageIcon.Warning)

        return folder_estimated_sizes
