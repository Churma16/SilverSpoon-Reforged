import os
import sys
import time
import re
import logging
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QLineEdit, QMessageBox, QInputDialog, QFileDialog,
    QMenu, QSystemTrayIcon, QAbstractItemView, QHeaderView
)
from PyQt6.QtGui import QAction, QDesktopServices, QIcon
from PyQt6.QtCore import Qt, QTimer, QUrl, QEvent
from curl_cffi import requests as cffi_requests

from core.settings import (
    load_settings, save_settings, CURRENT_VERSION, GITHUB_REPO
)
from core.download_task import DownloadTask
from core.types import TaskStatus
from services.system_service import SystemService
from controllers.download_controller import DownloadController
from controllers.update_controller import UpdateController
from ui.tree_adapter import TaskTreeAdapter
from ui.action_bar import ActionBarWidget
from ui.directory_bar import DirectoryBarWidget
from ui.url_input_bar import UrlInputBarWidget
from ui.menus import setup_menu_bar
from ui.dialogs import (
    WarningDialog, SettingsDialog, ChangelogDialog,
    LogViewerDialog, PrivacyPolicyDialog, TermsOfServiceDialog
)
from ui.widgets import SessionStatsWidget, ReorderableTreeWidget

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main Application Window for SilverSpoon Reforged Bulk Downloader."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SilverSpoon Reforged - UI (PyQt6)")
        self.resize(1000, 650)

        # Asset base path resolution (frozen exe vs local source)
        if hasattr(sys, '_MEIPASS'):
            self.base_dir = sys._MEIPASS
        else:
            self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        icon_path = os.path.join(self.base_dir, 'SilverSpoon.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.settings = load_settings()

        # Initialize Controllers & Services
        self.download_controller = DownloadController(self.base_dir, self.settings, self)
        self.update_controller = UpdateController(
            parent_widget=self,
            get_tasks_callback=lambda: self.download_controller.tasks,
            get_settings_callback=lambda: self.settings
        )

        self.setup_system_tray()
        self.setup_ui()

        # Initialize Tree Adapter (View Presenter)
        self.tree_adapter = TaskTreeAdapter(self.tree, lambda: self.download_controller.tasks)

        # Load initial persistent history into UI
        initial_tasks = self.download_controller.load_initial_history()
        for task in initial_tasks:
            if task.status in (TaskStatus.UNPACKING, "Extracting..."):
                task.status = TaskStatus.FINISHED
            self.tree_adapter.add_task_item(task)

        # Show warning dialog on startup if enabled
        if self.settings.get("show_warning_dialog", True):
            QTimer.singleShot(100, self.show_warning_dialog)

        # Start Update Checker in background if configured
        self.update_controller.start_auto_check_if_enabled()

        # Start download manager loop
        self.download_controller.start_download_manager(
            auto_extract_enabled_check=lambda: (
                hasattr(self, 'action_bar') and
                hasattr(self.action_bar, 'extract_checkbox') and
                self.action_bar.extract_checkbox.isChecked()
            )
        )

        # UI Refresh Timer (500ms heartbeat)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(500)

    # ---------------------------------------------------------
    # System Tray & Notification Management
    # ---------------------------------------------------------
    def setup_system_tray(self):
        icon_path = os.path.join(self.base_dir, 'SilverSpoon.ico')
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("SilverSpoon Reforged Bulk Downloader")

        tray_menu = QMenu(self)
        show_action = QAction("Show / Hide Window", self)
        show_action.triggered.connect(self.toggle_visibility)
        tray_menu.addAction(show_action)

        pause_action = QAction("Pause All Downloads", self)
        pause_action.triggered.connect(self.download_controller.pause_all)
        tray_menu.addAction(pause_action)

        resume_action = QAction("Resume All Downloads", self)
        resume_action.triggered.connect(self.download_controller.resume_all)
        tray_menu.addAction(resume_action)

        tray_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.force_quit)
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def send_notification(self, title: str, message: str, icon_type: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information):
        if self.settings.get("enable_notifications", True) and hasattr(self, 'tray_icon') and QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon.showMessage(title, message, icon_type, 3000)

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.activateWindow()

    def on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_visibility()

    def force_quit(self):
        self.download_controller.stop_download_manager()
        if hasattr(self, 'tray_icon'):
            self.tray_icon.hide()
        self.download_controller.trigger_history_save()
        save_settings(self.settings)
        logging.shutdown()
        QApplication.quit()

    def closeEvent(self, event):
        if self.settings.get("minimize_to_tray", False) and hasattr(self, 'tray_icon') and self.tray_icon.isVisible():
            self.hide()
            self.send_notification("SilverSpoon", "SilverSpoon is running in the background system tray.")
            event.ignore()
            return

        # Save tasks history
        self.download_controller.trigger_history_save()

        # Save tree column widths
        col_widths = {}
        for i in range(self.tree.columnCount()):
            col_widths[str(i)] = self.tree.columnWidth(i)
        self.settings["column_widths"] = col_widths
        save_settings(self.settings)

        # Stop background services
        self.download_controller.stop_download_manager()

        logging.shutdown()
        event.accept()

    # ---------------------------------------------------------
    # UI Setup & Layout
    # ---------------------------------------------------------
    def setup_ui(self):
        setup_menu_bar(self)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # 1. Directory Bar
        default_dir = self.settings.get("default_save_dir", os.path.join(os.path.expanduser("~"), "Downloads"))
        self.dir_bar = DirectoryBarWidget(default_dir, self)
        self.dir_input = self.dir_bar.dir_input
        main_layout.addWidget(self.dir_bar)

        # 2. Input Section
        self.url_bar = UrlInputBarWidget(self)
        self.url_bar.add_links_requested.connect(self.add_links)
        self.global_speed_label = self.url_bar.global_speed_label
        self.text_links = self.url_bar.text_links
        self.speed_graph = self.url_bar.speed_graph
        main_layout.addWidget(self.url_bar)

        # 3. Tree View Section
        self.tree = ReorderableTreeWidget()
        self.tree.order_changed.connect(self.sync_tasks_order_from_tree)
        self.tree.setColumnCount(8)
        self.tree.setHeaderLabels(["Filename / Folder", "Sel", "Status", "Progress", "Speed", "Elapsed", "ETA", "Size"])

        header = self.tree.header()
        for i in range(8):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)

        col_widths = self.settings.get("column_widths", {})
        default_widths = {0: 300, 1: 40, 2: 90, 3: 70, 4: 80, 5: 65, 6: 65, 7: 140}
        for col, width in default_widths.items():
            saved_w = col_widths.get(str(col), width)
            self.tree.setColumnWidth(col, int(saved_w))

        self.tree.header().moveSection(1, 0)
        self.tree.header().moveSection(7, 2)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_tree_context_menu)
        self.tree.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.tree.installEventFilter(self)
        main_layout.addWidget(self.tree, stretch=1)

        # 4. Action Section
        self.action_bar = ActionBarWidget(self.settings, self)
        self.action_bar.select_all_clicked.connect(self.toggle_select_all)
        self.action_bar.start_clicked.connect(self.start_downloads)
        self.action_bar.pause_clicked.connect(self.pause_selected)
        self.action_bar.cancel_clicked.connect(self.cancel_selected)
        self.action_bar.retry_clicked.connect(self.retry_selected)
        self.action_bar.force_redownload_clicked.connect(self.force_redownload_selected)
        self.action_bar.copy_log_clicked.connect(self.copy_selected_error_log)
        self.action_bar.delete_clicked.connect(self.delete_selected)
        self.action_bar.clear_completed_clicked.connect(self.clear_finished)
        self.action_bar.extract_changed.connect(lambda val: self.save_setting_key("extract_after_download", val))
        self.action_bar.shutdown_changed.connect(lambda val: self.save_setting_key("auto_shutdown_on_completion", val))
        self.action_bar.shutdown_action_changed.connect(lambda val: self.save_setting_key("auto_shutdown_action", val))
        main_layout.addWidget(self.action_bar)

        # 5. Session Statistics Section
        self.session_stats_widget = SessionStatsWidget(self)
        main_layout.addWidget(self.session_stats_widget)

    # ---------------------------------------------------------
    # Tree Events & Context Menu
    # ---------------------------------------------------------
    def show_tree_context_menu(self, position):
        item = self.tree.itemAt(position)
        tasks = self.download_controller.tasks
        if item and not any(t.tree_item and t.tree_item.checkState(1) == Qt.CheckState.Checked for t in tasks):
            if not item.isSelected():
                self.tree.clearSelection()
            self.tree.setCurrentItem(item)
            item.setSelected(True)

        menu = QMenu(self)
        menu.addAction("[S] Start / Resume", self.start_downloads)
        menu.addAction("[P] Pause", self.pause_selected)
        menu.addAction("[C] Cancel", self.cancel_selected)
        menu.addSeparator()
        menu.addAction("[R] Retry", self.retry_selected)
        menu.addAction("[F] Force Redownload", self.force_redownload_selected)
        menu.addAction("[E] Re-extract Archive", self.reextract_selected)
        menu.addAction("Copy Error Details", self.copy_selected_error_log)
        menu.addSeparator()
        menu.addAction("Delete", self.delete_selected)
        menu.exec(self.tree.viewport().mapToGlobal(position))

    def sync_tasks_order_from_tree(self):
        reordered_tasks = self.tree_adapter.get_reordered_tasks()
        self.download_controller.sync_tasks_order(reordered_tasks)

    def toggle_select_all(self):
        self.tree_adapter.toggle_select_all()

    def get_selected_tasks(self):
        return self.tree_adapter.get_selected_tasks()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_selected()
        elif event.key() == Qt.Key.Key_F:
            self.force_redownload_selected()
        else:
            super().keyPressEvent(event)

    def eventFilter(self, source, event):
        if source == self.tree and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                self.delete_selected()
                return True
            if event.key() == Qt.Key.Key_F:
                self.force_redownload_selected()
                return True
            if event.key() == Qt.Key.Key_S:
                self.start_downloads()
                return True
            if event.key() == Qt.Key.Key_P:
                self.pause_selected()
                return True
            if event.key() == Qt.Key.Key_Space:
                selected = self.get_selected_tasks()
                if selected:
                    if selected[0].status in (TaskStatus.DOWNLOADING, TaskStatus.CONNECTING):
                        self.pause_selected()
                    else:
                        self.start_downloads()
                return True
            if event.key() == Qt.Key.Key_C:
                self.cancel_selected()
                return True
            if event.key() == Qt.Key.Key_R:
                self.retry_selected()
                return True
        return super().eventFilter(source, event)

    # ---------------------------------------------------------
    # Task Actions & Link Addition
    # ---------------------------------------------------------
    def browse_dir(self):
        selected_dir = QFileDialog.getExistingDirectory(self, "Select Save Directory", self.dir_input.text())
        if selected_dir:
            self.dir_input.setText(selected_dir)
            self.save_setting_key("default_save_dir", selected_dir)

    def paste_from_clipboard(self):
        clipboard = QApplication.clipboard()
        if clipboard:
            text = clipboard.text()
            if text:
                current_text = self.text_links.toPlainText()
                if current_text.strip():
                    self.text_links.setText(current_text + "\n" + text)
                else:
                    self.text_links.setText(text)

    def add_links(self):
        text = self.text_links.toPlainText().strip()
        if not text:
            return

        cleaned_lines = []
        for line in text.splitlines():
            line_str = line.strip()
            line_str = re.sub(r'^[-\*\d\.]+\s+', '', line_str)
            cleaned_lines.append(line_str)
        sanitized_text = "\n".join(cleaned_lines)

        extracted_urls = re.findall(r'https?://[^\s"<>\']+', sanitized_text)
        ff_links = [u.rstrip('"\';>,') for u in extracted_urls if "fuckingfast.co" in u]
        web_urls = [u.rstrip('"\';>,') for u in extracted_urls if "fuckingfast.co" not in u]

        if not ff_links and web_urls:
            target_url = web_urls[0]
            try:
                scraper = cffi_requests.Session(impersonate="chrome")
                res = scraper.get(target_url, timeout=15)
                if res.status_code == 200:
                    page_ff_urls = re.findall(r'https?://fuckingfast\.co/[^\s"<>\']+', res.text)
                    ff_links = list(dict.fromkeys([u.rstrip('"\';>,') for u in page_ff_urls]))
            except Exception as e:
                QMessageBox.critical(self, "Link Extractor Error", f"Failed to extract webpage links:\n{e}")
                return

        cleaned_links = list(dict.fromkeys(ff_links))
        if not cleaned_links:
            QMessageBox.warning(self, "No Valid Links", "No fuckingfast.co links were found directly or on the specified web page.")
            return

        save_dir = os.path.abspath(self.dir_input.text())
        suggested_folder = ""
        first_link = cleaned_links[0]
        first_filename = first_link.split('#')[-1] if '#' in first_link else first_link.split('/')[-1].split('#')[0]
        match = re.search(r'(.*?)(\.part\d+\.rar|\.rar)$', first_filename, re.IGNORECASE)
        if match:
            suggested_folder = match.group(1).strip('._-')
        else:
            suggested_folder = first_filename.rsplit('.', 1)[0]

        folder_name, ok = QInputDialog.getText(
            self,
            "Batch Folder Name",
            "Enter a folder name for these files:\n(This groups related multi-part archive files together)",
            QLineEdit.EchoMode.Normal,
            suggested_folder
        )

        if not ok or not folder_name.strip():
            return

        folder_name = folder_name.strip()
        new_tasks = []
        for link in cleaned_links:
            task = DownloadTask(link, save_dir, folder_name)
            new_tasks.append(task)
            self.download_controller.add_task(task)
            self.tree_adapter.add_task_item(task)

        self.text_links.clear()

    def start_downloads(self):
        selected_tasks = self.get_selected_tasks()
        self.download_controller.start_downloads(selected_tasks if selected_tasks else None)

    def pause_selected(self):
        selected_tasks = self.get_selected_tasks()
        if selected_tasks:
            self.download_controller.pause_tasks(selected_tasks)

    def cancel_selected(self):
        selected_tasks = self.get_selected_tasks()
        if selected_tasks:
            self.download_controller.cancel_tasks(selected_tasks)

    def retry_selected(self):
        selected_tasks = self.get_selected_tasks()
        if selected_tasks:
            self.download_controller.retry_tasks(selected_tasks)

    def force_redownload_selected(self):
        tasks_to_redownload = self.get_selected_tasks()
        if not tasks_to_redownload:
            QMessageBox.information(self, "No Selection", "Select one or more tasks to force redownload.")
            return

        completed_or_downloaded = [
            t for t in tasks_to_redownload
            if t.status in (TaskStatus.FINISHED, TaskStatus.EXTRACTED) or t.progress > 0
        ]

        if completed_or_downloaded:
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setWindowTitle("Confirm Force Redownload")
            msg_box.setText(
                f"You have selected {len(tasks_to_redownload)} task(s), including {len(completed_or_downloaded)} completed/partially downloaded file(s).\n\n"
                "Force redownloading will permanently DELETE existing files from disk and restart downloading from 0%."
            )
            msg_box.addButton("Redownload All Selected", QMessageBox.ButtonRole.AcceptRole)
            btn_failed_only = msg_box.addButton("Redownload Failed Tasks Only", QMessageBox.ButtonRole.ActionRole)
            btn_cancel = msg_box.addButton(QMessageBox.StandardButton.Cancel)

            msg_box.exec()
            clicked_btn = msg_box.clickedButton()

            if clicked_btn == btn_cancel:
                return
            elif clicked_btn == btn_failed_only:
                tasks_to_redownload = [
                    t for t in tasks_to_redownload
                    if t.status in (TaskStatus.FAILED, TaskStatus.EXTRACT_ERROR) or "Error" in str(t.status) or "Failed" in str(t.status)
                ]
                if not tasks_to_redownload:
                    QMessageBox.information(self, "No Failed Tasks", "None of the selected tasks were in a failed state.")
                    return

        redownloaded, skipped, failed = self.download_controller.force_redownload_tasks(tasks_to_redownload)
        if skipped or failed or redownloaded == 0:
            QMessageBox.information(
                self,
                "Force Redownload",
                f"Queued: {redownloaded}\nSkipped active tasks: {skipped}\nFailed: {failed}"
            )

    def reextract_selected(self):
        selected_tasks = self.get_selected_tasks()
        if not selected_tasks:
            QMessageBox.information(self, "No Selection", "Select a task or batch folder to re-extract.")
            return

        target_folders = set(t.folder_name for t in selected_tasks)
        reextracted_count = self.download_controller.reextract_folders(target_folders)
        if reextracted_count > 0:
            QMessageBox.information(self, "Re-extracting", f"Triggered re-extraction for {reextracted_count} batch folder(s).")

    def delete_selected(self):
        tasks_to_delete = self.get_selected_tasks()
        if not tasks_to_delete:
            return

        delete_files = False
        if not self.settings.get("skip_delete_confirmation", False):
            dialog = SettingsDialog(self.settings, self) if False else None
            # Standard delete confirmation box
            from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QCheckBox
            dialog = QDialog(self)
            dialog.setWindowTitle("Confirm Delete")
            layout = QVBoxLayout(dialog)
            layout.addWidget(QLabel(f"Are you sure you want to delete {len(tasks_to_delete)} selected task(s)?"))
            file_checkbox = QCheckBox("Also delete downloaded files from disk")
            layout.addWidget(file_checkbox)
            dont_ask_checkbox = QCheckBox("Don't ask again")
            layout.addWidget(dont_ask_checkbox)

            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No)
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                delete_files = file_checkbox.isChecked()
                if dont_ask_checkbox.isChecked():
                    self.save_setting_key("skip_delete_confirmation", True)
            else:
                return

        for task in list(tasks_to_delete):
            self.tree_adapter.remove_task_item(task)
        self.download_controller.delete_tasks(tasks_to_delete, delete_files_from_disk=delete_files)

    def clear_finished(self):
        removed_tasks = self.download_controller.clear_finished_tasks()
        for task in removed_tasks:
            self.tree_adapter.remove_task_item(task)

    def copy_selected_error_log(self):
        for task in self.get_selected_tasks():
            if "Error" in str(task.status) or "Failed" in str(task.status):
                self.copy_error_log(task)
                return
        QMessageBox.information(self, "No Error Selected", "Select a failed task first, then copy its error details.")

    def copy_error_log(self, task: DownloadTask):
        log_path = os.path.join(self.base_dir, "logs", "silverspoon.log")
        if not os.path.exists(log_path):
            QMessageBox.information(self, "No Log", "No error log found.")
            return

        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                logs = f.readlines()

            keywords = [task.link, task.file_id, task.filename]
            matching_logs = [line for line in logs if any(keyword and keyword in line for keyword in keywords)]
            relevant_logs = "".join(matching_logs[-20:] if matching_logs else logs[-20:])

            if not relevant_logs.strip():
                QMessageBox.information(self, "Log Empty", "The error log is empty.")
                return

            clipboard = QApplication.clipboard()
            if clipboard:
                log_label = "Matching log lines" if matching_logs else "Recent log lines"
                clipboard.setText(f"Task File: {task.filename}\nTask Link: {task.link}\nStatus: {task.status}\n\n{log_label}:\n{relevant_logs}")
                QMessageBox.information(self, "Log Copied", "Relevant error logs have been copied to your clipboard.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not read log file: {e}")

    # ---------------------------------------------------------
    # Dialogs & Helpers
    # ---------------------------------------------------------
    def open_settings_dialog(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() == SettingsDialog.DialogCode.Accepted:
            self.settings = dialog.get_updated_settings()
            save_settings(self.settings)
            self.download_controller.max_workers = self.settings.get("max_workers", 3)
            self.download_controller.download_manager.max_workers = self.settings.get("max_workers", 3)
            self.download_controller.download_manager.settings = self.settings

    def manual_update_check(self):
        self.update_controller.check_for_updates_manually()

    def import_links_from_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Import Links", "", "Text Files (*.txt);;All Files (*)")
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    current_text = self.text_links.toPlainText()
                    if current_text.strip():
                        self.text_links.setText(current_text + "\n" + content)
                    else:
                        self.text_links.setText(content)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to read file:\n{e}")

    def open_github_link(self):
        QDesktopServices.openUrl(QUrl(f"https://github.com/{GITHUB_REPO}"))

    def open_contact_link(self):
        QDesktopServices.openUrl(QUrl(f"https://github.com/{GITHUB_REPO}/issues"))

    def show_contributing_dialog(self):
        QMessageBox.information(
            self, "Contributing Guide",
            "<h3>Contributing to SilverSpoon</h3>"
            "<p>We welcome contributions! Please see the <b>CONTRIBUTING.md</b> file in the repository for full details.</p>"
            "<p><b>Quick Rules:</b></p>"
            "<ul>"
            "<li>Always work on the <code>dev</code> branch.</li>"
            "<li>Carefully test your changes before submitting a PR.</li>"
            "<li>Report bugs via the GitHub Issues tab.</li>"
            "</ul>"
        )

    def show_changelog_dialog(self):
        dialog = ChangelogDialog(self.base_dir, self)
        dialog.exec()

    def show_log_viewer_dialog(self):
        dialog = LogViewerDialog(self)
        dialog.exec()

    def show_about_dialog(self):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("About SilverSpoon Reforged")
        msg_box.setText(
            f"<h3>SilverSpoon Reforged {CURRENT_VERSION}</h3>"
            "<p>A simple, fast bulk downloader for FuckingFast links.</p>"
            "<p>This is a forked version based on the original work by <b>billysams21</b>.</p>"
            "<p>Select your links, paste them in, and hit Add!</p>"
            "<p>Licensed under the GNU GPLv3.</p>"
        )
        changelog_btn = msg_box.addButton("View Full Changelog", QMessageBox.ButtonRole.ActionRole)
        msg_box.addButton(QMessageBox.StandardButton.Ok)

        msg_box.exec()
        if msg_box.clickedButton() == changelog_btn:
            self.show_changelog_dialog()

    def show_privacy_policy_dialog(self):
        dialog = PrivacyPolicyDialog(self)
        dialog.exec()

    def show_terms_of_service_dialog(self):
        dialog = TermsOfServiceDialog(self)
        dialog.exec()

    def show_warning_dialog(self):
        dialog = WarningDialog(self.settings, self)
        dialog.exec()
        save_settings(self.settings)

    def show_warning_dialog_manual(self):
        dialog = WarningDialog(self.settings, self)
        dialog.dont_show_checkbox.setChecked(not self.settings.get("show_warning_dialog", True))
        dialog.exec()

    def save_setting_key(self, key: str, value):
        self.settings[key] = value
        save_settings(self.settings)

    # ---------------------------------------------------------
    # UI Heartbeat & Auto-Shutdown
    # ---------------------------------------------------------
    def update_ui(self):
        tasks = self.download_controller.tasks
        global_speed = sum(getattr(task, 'speed', 0.0) for task in tasks if task.status == TaskStatus.DOWNLOADING)

        folder_estimated_sizes = self.tree_adapter.update_tree_display(
            global_speed=global_speed,
            notified_batches=self.download_controller.notified_batches,
            send_notification_callback=self.send_notification
        )

        active_tasks = [t for t in tasks if t.status in (TaskStatus.DOWNLOADING, TaskStatus.CONNECTING, TaskStatus.SOLVING_SESSION)]
        pending_tasks = [t for t in tasks if t.status == TaskStatus.IN_QUEUE]
        active_count = len(active_tasks)
        pending_count = len(pending_tasks)

        total_remaining = 0
        for t in active_tasks + pending_tasks:
            if t.total_bytes > 0:
                total_remaining += max(0, t.total_bytes - t.downloaded_bytes)
            else:
                fn = getattr(t, 'folder_name', 'Default')
                total_remaining += folder_estimated_sizes.get(fn, 0)

        if global_speed > 0 and total_remaining > 0:
            queue_eta_seconds = total_remaining / (global_speed * 1024 * 1024)
            queue_eta_str = TaskTreeAdapter.format_time(queue_eta_seconds)
            self.global_speed_label.setText(f"Global Speed: {global_speed:.2f} MB/s | Total Queue ETA: {queue_eta_str} ({active_count} active, {pending_count} pending)")
        elif active_count > 0 or pending_count > 0:
            self.global_speed_label.setText(f"Global Speed: {global_speed:.2f} MB/s | ({active_count} active, {pending_count} pending)")
        else:
            self.global_speed_label.setText(f"Global Speed: {global_speed:.2f} MB/s")

        if hasattr(self, 'speed_graph'):
            self.speed_graph.add_data_point(global_speed)

        # Contextually enable/disable action buttons via ActionBarWidget
        selected_tasks = self.get_selected_tasks()
        if hasattr(self, 'action_bar'):
            self.action_bar.update_states(tasks, selected_tasks)

        # Update Session Statistics Panel
        if hasattr(self, 'session_stats_widget'):
            completed_count = sum(1 for t in tasks if t.status in (TaskStatus.FINISHED, TaskStatus.EXTRACTED))
            error_count = sum(1 for t in tasks if "Error" in str(t.status) or "Failed" in str(t.status))
            self.session_stats_widget.update_stats(
                self.download_controller.session_downloaded_bytes,
                active_count,
                completed_count,
                error_count
            )

        # Check Auto-Shutdown Trigger
        if hasattr(self, 'action_bar') and self.action_bar.shutdown_checkbox.isChecked() and tasks and not getattr(self, 'shutdown_dialog_active', False):
            active_statuses = (
                TaskStatus.DOWNLOADING, 
                TaskStatus.CONNECTING, 
                TaskStatus.SOLVING_SESSION, 
                TaskStatus.IN_QUEUE, 
                TaskStatus.UNPACKING
            )
            has_active_or_queued = any(t.status in active_statuses for t in tasks)
            has_paused = any(t.status in (TaskStatus.PAUSING, TaskStatus.PAUSED) for t in tasks)
            
            if self.download_controller.is_downloading and not has_active_or_queued:
                self.download_controller.is_downloading = False
                if not has_paused:
                    self.trigger_auto_shutdown()

    def trigger_auto_shutdown(self):
        action = self.settings.get("auto_shutdown_action", "Shutdown")
        self.shutdown_dialog_active = True
        self.action_bar.shutdown_checkbox.setChecked(False)
        self.save_setting_key("auto_shutdown_on_completion", False)

        countdown = 60
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setWindowTitle(f"Auto-{action} Triggered")
        msg_box.setText(f"All downloads and extractions completed.\n\nSystem will {action.lower()} in {countdown} seconds.")
        msg_box.addButton(f"Cancel {action}", QMessageBox.ButtonRole.RejectRole)

        timer = QTimer(self)

        def update_timer():
            nonlocal countdown
            countdown -= 1
            if countdown <= 0:
                timer.stop()
                msg_box.accept()
                SystemService.execute_power_action(action)
            else:
                msg_box.setText(f"All downloads and extractions completed.\n\nSystem will {action.lower()} in {countdown} seconds.")

        timer.timeout.connect(update_timer)
        timer.start(1000)

        msg_box.exec()
        timer.stop()
        self.shutdown_dialog_active = False
