import sys
import os
import time
import threading
import re
import subprocess
import logging
import tempfile
import zipfile
import shutil

logger = logging.getLogger(__name__)

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QTreeWidget,
    QTreeWidgetItem, QHeaderView, QFileDialog, QAbstractItemView,
    QCheckBox, QDialog, QDialogButtonBox, QMessageBox, QInputDialog,
    QMenu, QSystemTrayIcon
)
from PyQt6.QtGui import QAction, QDesktopServices, QIcon, QBrush, QColor
from PyQt6.QtCore import Qt, QTimer, QUrl, QEvent, QMetaObject, Q_ARG

from curl_cffi import requests as cffi_requests
from update_logic import (
    UpdateCheckerThread, UpdateDownloaderDialog,
    extract_and_verify_update, perform_exe_replacement, launch_restart_script
)

from core.rate_limiter import GlobalRateLimiter
from core.settings import load_settings, save_settings, get_settings_path, CURRENT_VERSION, GITHUB_REPO, OLD_EXE_CLEANUP_MARKER_SUFFIX
from core.history import load_history, save_history
from core.download_task import DownloadTask
from core.types import TaskStatus, BatchStatus
from core.extractors.fuckingfast import FuckingFastExtractor
from core.download_manager import DownloadManager
from core.extraction_manager import ExtractionManager
from ui.action_bar import ActionBarWidget
from ui.directory_bar import DirectoryBarWidget
from ui.url_input_bar import UrlInputBarWidget
from ui.menus import setup_menu_bar
from ui.dialogs import WarningDialog, SettingsDialog, ChangelogDialog, LogViewerDialog, PrivacyPolicyDialog, TermsOfServiceDialog
from ui.widgets import SpeedGraphWidget, SessionStatsWidget, ReorderableTreeWidget
from utils.formatters import format_error_message, format_bytes, format_size_progress


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SilverSpoon Reforged - UI (PyQt6)")
        self.resize(1000, 650)
        
        # Determine paths to assets (works both locally and within a PyInstaller bundled .exe)
        if hasattr(sys, '_MEIPASS'):
            self.base_dir = sys._MEIPASS
        else:
            self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
        icon_path = os.path.join(self.base_dir, 'SilverSpoon.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.settings = load_settings()
        
        self.tasks = []
        self.max_workers = self.settings.get("max_workers", 3)
        self.rate_limiter = GlobalRateLimiter()
        self.scraper = cffi_requests.Session(impersonate="chrome")
        self.extractor = FuckingFastExtractor(self.scraper)
        self.is_all_selected = False
        self.extracted_folders = set()
        self.notified_batches = set()
        self.session_downloaded_bytes = 0
        self.session_bytes_lock = threading.Lock()
        
        self.setup_system_tray()
        self.setup_ui()
        self.load_tasks_from_history()
        
        # Show warning dialog if not disabled
        if self.settings.get("show_warning_dialog", True):
            QTimer.singleShot(100, self.show_warning_dialog)
            
        # Start Update Checker
        if sys.platform == "win32" and hasattr(sys, 'frozen') and self.settings.get("auto_check_updates", False):
            self.update_checker = UpdateCheckerThread(CURRENT_VERSION, GITHUB_REPO, get_settings_path())
            self.update_checker.update_available.connect(self.prompt_update)
            self.update_checker.check_finished.connect(self.update_last_check_time)
            self.update_checker.start()
            
        self.extraction_manager = ExtractionManager(
            self.tasks,
            self.extracted_folders,
            self.base_dir,
            self.trigger_history_save
        )
        
        self.download_manager = DownloadManager(
            self.tasks,
            self.max_workers,
            self.rate_limiter,
            self.scraper,
            self.extractor,
            self.settings,
            self.add_session_downloaded_bytes,
            self.trigger_history_save
        )
        
        def check_extraction_callback():
            try:
                if hasattr(self, 'action_bar') and hasattr(self.action_bar, 'extract_checkbox') and self.action_bar.extract_checkbox.isChecked():
                    self.extraction_manager.check_extraction()
            except (RuntimeError, AttributeError):
                pass

        self.download_manager.start(check_extraction_callback)
        
        # UI Updater Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(500) # update every 500ms

    def add_session_downloaded_bytes(self, size):
        with self.session_bytes_lock:
            self.session_downloaded_bytes += size


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
        pause_action.triggered.connect(self.pause_all)
        tray_menu.addAction(pause_action)
        
        resume_action = QAction("Resume All Downloads", self)
        resume_action.triggered.connect(self.resume_all)
        tray_menu.addAction(resume_action)
        
        tray_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.force_quit)
        tray_menu.addAction(exit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def send_notification(self, title, message, icon_type=QSystemTrayIcon.MessageIcon.Information):
        if self.settings.get("enable_notifications", True) and hasattr(self, 'tray_icon') and QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon.showMessage(title, message, icon_type, 3000)

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.activateWindow()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_visibility()

    def pause_all(self):
        for task in self.tasks:
            if task.status in (TaskStatus.DOWNLOADING, TaskStatus.IN_QUEUE, TaskStatus.CONNECTING):
                task.pause_flag = True
                task.status = TaskStatus.PAUSED

    def resume_all(self):
        for task in self.tasks:
            if task.status in (TaskStatus.PAUSED, TaskStatus.STANDBY, TaskStatus.FAILED, TaskStatus.CANCELLED):
                task.status = TaskStatus.IN_QUEUE
                task.pause_flag = False

    def force_quit(self):
        if hasattr(self, 'download_manager'):
            self.download_manager.stop()
        if hasattr(self, 'tray_icon'):
            self.tray_icon.hide()
        save_history(self.tasks)
        save_settings(self.settings)
        logging.shutdown()
        QApplication.quit()

    def closeEvent(self, event):
        if self.settings.get("minimize_to_tray", False) and hasattr(self, 'tray_icon') and self.tray_icon.isVisible():
            self.hide()
            self.send_notification("SilverSpoon", "SilverSpoon is running in the background system tray.")
            event.ignore()
            return

        # Save tasks history before closing
        save_history(self.tasks)
        
        # Save column widths
        col_widths = {}
        for i in range(self.tree.columnCount()):
            col_widths[str(i)] = self.tree.columnWidth(i)
        self.settings["column_widths"] = col_widths
        save_settings(self.settings)
        
        # Stop background download loop
        if hasattr(self, 'download_manager'):
            self.download_manager.stop()

        # Shut down the SeleniumBase UC browser driver used by the extractor
        if hasattr(self, 'extractor') and hasattr(self.extractor, 'close'):
            self.extractor.close()
            
        logging.shutdown()
        event.accept()

    def setup_ui(self):
        setup_menu_bar(self)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)
        
        # 1. Directory Section
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
        self.tree.itemClicked.connect(self.handle_item_clicked)
        self.tree.itemSelectionChanged.connect(self.handle_item_selection_changed)
        self.tree.setStyleSheet("""
            QTreeView::indicator { width: 16px; height: 16px; }
            QTreeView::item:selected { outline: none; }
        """)
        main_layout.addWidget(self.tree, stretch=1)
        
        # 4. Action Section
        self.action_bar = ActionBarWidget(self.settings, self)
        self.select_all_btn = self.action_bar.select_all_btn
        self.start_btn = self.action_bar.start_btn
        self.pause_btn = self.action_bar.pause_btn
        self.cancel_btn = self.action_bar.cancel_btn
        self.retry_btn = self.action_bar.retry_btn
        self.force_redownload_btn = self.action_bar.force_redownload_btn
        self.copy_log_btn = self.action_bar.copy_log_btn
        self.delete_btn = self.action_bar.delete_btn
        self.extract_checkbox = self.action_bar.extract_checkbox
        self.shutdown_checkbox = self.action_bar.shutdown_checkbox
        self.shutdown_action_combo = self.action_bar.shutdown_action_combo
        self.clear_btn = self.action_bar.clear_btn

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

    def show_tree_context_menu(self, position):
        item = self.tree.itemAt(position)
        if item and not any(t.tree_item and t.tree_item.checkState(1) == Qt.CheckState.Checked for t in self.tasks):
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

    def get_or_create_batch_item(self, folder_name):
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

    def sync_tasks_order_from_tree(self):
        reordered_task_list = []
        for batch_index in range(self.tree.topLevelItemCount()):
            top_level_batch_item = self.tree.topLevelItem(batch_index)
            current_folder_name = top_level_batch_item.data(0, Qt.ItemDataRole.UserRole) or top_level_batch_item.text(0)
            
            for child_index in range(top_level_batch_item.childCount()):
                child_task_item = top_level_batch_item.child(child_index)
                matching_task = next((task for task in self.tasks if task.tree_item == child_task_item), None)
                if matching_task:
                    if matching_task.folder_name != current_folder_name:
                        matching_task.folder_name = current_folder_name
                    reordered_task_list.append(matching_task)
                    
        for task in self.tasks:
            if task not in reordered_task_list:
                reordered_task_list.append(task)
                
        self.tasks = reordered_task_list
        self.trigger_history_save()

    def trigger_history_save(self):
        if not hasattr(self, '_history_save_timer'):
            self._history_save_timer = QTimer()
            self._history_save_timer.setSingleShot(True)
            self._history_save_timer.timeout.connect(lambda: save_history(self.tasks))
        
        QMetaObject.invokeMethod(self._history_save_timer, "start", Qt.ConnectionType.QueuedConnection, Q_ARG(int, 500))

    def add_task_to_ui(self, task):
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
        
        if task not in self.tasks:
            self.tasks.append(task)
            self.trigger_history_save()

    def copy_selected_error_log(self):
        for task in self.get_selected_tasks():
            if "Error" in str(task.status) or "Failed" in str(task.status):
                self.copy_error_log(task)
                return
        QMessageBox.information(self, "No Error Selected", "Select a failed task first, then copy its error details.")

    def copy_error_log(self, task):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        log_path = os.path.join(base_dir, "logs", "silverspoon.log")
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
            log_label = "Matching log lines" if matching_logs else "Recent log lines"
            clipboard.setText(f"Task File: {task.filename}\nTask Link: {task.link}\nStatus: {task.status}\n\n{log_label}:\n{relevant_logs}")
            QMessageBox.information(self, "Log Copied", "Relevant error logs have been copied to your clipboard.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not read log file: {e}")

    def load_tasks_from_history(self):
        loaded_tasks = load_history()
        for task in loaded_tasks:
            self.add_task_to_ui(task)
            
            if task.status == TaskStatus.EXTRACTED:
                self.extracted_folders.add(task.folder_name)
            elif task.status in (TaskStatus.UNPACKING, "Extracting..."):
                task.status = TaskStatus.FINISHED

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
        QMessageBox.information(self, "Contributing Guide",
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
        save_settings(self.settings)

    def manual_update_check(self):
        self.manual_checker = UpdateCheckerThread(CURRENT_VERSION, GITHUB_REPO, get_settings_path(), force=True)
        self.manual_checker.update_available.connect(self.prompt_update)
        self.manual_checker.check_finished.connect(self.update_last_check_time)
        self.manual_checker.no_update_found.connect(lambda: QMessageBox.information(self, "Up to date", "You are already using the latest version of SilverSpoon!"))
        self.manual_checker.error_checking.connect(lambda err: QMessageBox.warning(self, "Update Check Failed", f"Could not check for updates:\n{err}"))
        self.manual_checker.start()
        
    def update_last_check_time(self, timestamp):
        self.settings["last_update_check"] = timestamp
        save_settings(self.settings)
        self.settings = load_settings()
        
    def prompt_update(self, version, changelog, download_url):
        current_exe_dir = os.path.dirname(sys.executable)
        test_file = os.path.join(current_exe_dir, ".update_test_permission")
        try:
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
        except PermissionError:
            QMessageBox.warning(
                self, "Update Available (Admin Required)",
                f"Version {version} is available!\n\n"
                f"However, SilverSpoon is located in a protected folder:\n{current_exe_dir}\n\n"
                "Please run SilverSpoon as Administrator to update automatically, or move it to a normal folder like Downloads or Desktop."
            )
            return
        except Exception:
            pass
            
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Update Available: {version}")
        dialog.setMinimumWidth(500)
        
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"<b>A new version ({version}) is available!</b>"))
        
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setMarkdown(changelog)
        layout.addWidget(text_edit)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No)
        btn_box.button(QDialogButtonBox.StandardButton.Yes).setText("Download and Restart")
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout.addWidget(btn_box)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.execute_update(download_url)
            
    def execute_update(self, download_url):
        dl_dialog = UpdateDownloaderDialog(download_url, self)
        if dl_dialog.exec() == QDialog.DialogCode.Accepted:
            zip_path = dl_dialog.temp_zip
            try:
                extract_dir, new_exe_path = extract_and_verify_update(zip_path)
                current_exe = sys.executable
                current_exe_name = os.path.basename(current_exe)
                
                if not current_exe_name.lower().startswith("silverspoon"):
                    msg_box = QMessageBox(self)
                    msg_box.setWindowTitle("Update Downloaded (Manual Action Required)")
                    msg_box.setText(
                        f"The update has been downloaded and extracted to:\n{extract_dir}\n\n"
                        "Because you are running SilverSpoon from a differently named executable or script, "
                        "the automatic replacement was aborted to keep you safe."
                    )
                    
                    copy_btn = msg_box.addButton("Copy Directory Path", QMessageBox.ButtonRole.ActionRole)
                    ok_btn = msg_box.addButton(QMessageBox.StandardButton.Ok)
                    msg_box.setDefaultButton(ok_btn)
                    
                    msg_box.exec()
                    
                    if msg_box.clickedButton() == copy_btn:
                        QApplication.clipboard().setText(extract_dir)
                        QMessageBox.information(self, "Copied", "Directory path copied to clipboard.")
                        
                    return
                
                old_exe_path = current_exe + ".old"
                perform_exe_replacement(new_exe_path, current_exe, old_exe_path)
                
                try:
                    shutil.rmtree(extract_dir, ignore_errors=True)
                    if os.path.exists(zip_path):
                        os.remove(zip_path)
                except Exception:
                    pass

                delete_old_exe = QMessageBox.question(
                    self,
                    "Remove Previous Version?",
                    "The previous version is saved as:\n"
                    f"{old_exe_path}\n\n"
                    "Delete this backup after the new version closes normally?\n"
                    "It will be kept if the replacement cannot start.\n"
                    "Choose No to keep it for rollback.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                ) == QMessageBox.StandardButton.Yes
                cleanup_marker = current_exe + OLD_EXE_CLEANUP_MARKER_SUFFIX
                if delete_old_exe:
                    with open(cleanup_marker, "w", encoding="utf-8") as marker:
                        marker.write("Delete the previous executable after a successful restart.\n")
                elif os.path.exists(cleanup_marker):
                    os.remove(cleanup_marker)

                save_history(self.tasks)
                save_settings(self.settings)
                
                launch_restart_script(current_exe, old_exe_path, cleanup_marker)
                
                QApplication.quit()
                sys.exit(0)
                
            except Exception as e:
                QMessageBox.critical(self, "Update Failed", f"Failed to apply the update:\n{str(e)}")


    def open_settings_dialog(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            updated_settings = dialog.get_updated_settings()
            self.settings.update(updated_settings)
            save_settings(self.settings)
            
            self.max_workers = self.settings.get("max_workers", 3)
            if hasattr(self, 'download_manager'):
                self.download_manager.max_workers = self.max_workers
            default_dir = self.settings.get("default_save_dir", os.path.join(os.path.expanduser("~"), "Downloads"))
            self.dir_input.setText(default_dir)
            self.extract_checkbox.setChecked(self.settings.get("extract_after_download", False))

    def browse_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Save Directory", self.dir_input.text())
        if folder:
            self.dir_input.setText(os.path.abspath(folder))

    def paste_from_clipboard(self):
        clipboard = QApplication.clipboard()
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
            
        # Clean leading list markers (e.g. "- https://", "* https://", "1. https://") per line
        cleaned_lines = []
        for line in text.splitlines():
            line_str = line.strip()
            # Strip common list prefixes before searching
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
        
        for link in cleaned_links:
            task = DownloadTask(link, save_dir, folder_name)
            self.add_task_to_ui(task)
            
        self.text_links.clear()

    def toggle_select_all(self):
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
                
        for task in self.tasks:
            task.is_selected = self.is_all_selected

    def handle_item_clicked(self, item, col):
        if col == 1:
            state = item.checkState(1)
            
            if item.parent() is None:
                for i in range(item.childCount()):
                    child = item.child(i)
                    child.setCheckState(1, state)
                    task = next((t for t in self.tasks if t.tree_item == child), None)
                    if task:
                        task.is_selected = (state == Qt.CheckState.Checked)
            else:
                task = next((t for t in self.tasks if t.tree_item == item), None)
                if task:
                    task.is_selected = (state == Qt.CheckState.Checked)
                    
    def handle_item_selection_changed(self):
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
                    task = next((t for t in self.tasks if t.tree_item == child), None)
                    if task:
                        task.is_selected = True
                else:
                    child.setCheckState(1, Qt.CheckState.Unchecked)
                    task = next((t for t in self.tasks if t.tree_item == child), None)
                    if task:
                        task.is_selected = False

    def get_selected_tasks(self):
        checked = [t for t in self.tasks if t.tree_item and t.tree_item.checkState(1) == Qt.CheckState.Checked]
        if checked:
            return checked
            
        selected_items = self.tree.selectedItems()
        selected_tasks = []
        for item in selected_items:
            if item.parent() is None:
                for i in range(item.childCount()):
                    child = item.child(i)
                    task = next((t for t in self.tasks if t.tree_item == child), None)
                    if task and task not in selected_tasks:
                        selected_tasks.append(task)
            else:
                task = next((t for t in self.tasks if t.tree_item == item), None)
                if task and task not in selected_tasks:
                    selected_tasks.append(task)
        return selected_tasks

    def start_downloads(self):
        for task in self.get_selected_tasks():
            if task.status in (TaskStatus.STANDBY, TaskStatus.CANCELLED, TaskStatus.FAILED, TaskStatus.PAUSED, TaskStatus.EXTRACT_ERROR):
                if os.path.exists(task.filepath) and (task.progress >= 100 or (task.total_bytes > 0 and os.path.getsize(task.filepath) >= task.total_bytes)):
                    task.progress = 100.0
                    task.status = TaskStatus.FINISHED
                    task.error_message = ""
                else:
                    task.status = TaskStatus.IN_QUEUE
                    task.error_message = ""
                    task.cancel_flag = False
                    task.pause_flag = False

    def pause_selected(self):
        for task in self.get_selected_tasks():
            if task.status in (TaskStatus.DOWNLOADING, TaskStatus.IN_QUEUE, TaskStatus.CONNECTING):
                task.pause_flag = True
                task.status = TaskStatus.PAUSING if task.status == TaskStatus.DOWNLOADING else TaskStatus.PAUSED

    def cancel_selected(self):
        for task in self.get_selected_tasks():
            if task.status in (TaskStatus.DOWNLOADING, TaskStatus.IN_QUEUE, TaskStatus.PAUSED, TaskStatus.CONNECTING, TaskStatus.STANDBY):
                task.cancel_flag = True
                task.pause_flag = False
                task.status = TaskStatus.CANCELLED

    def retry_selected(self):
        for task in self.get_selected_tasks():
            if "Failed" in str(task.status) or "Error" in str(task.status):
                if os.path.exists(task.filepath) and (task.progress >= 100 or (task.total_bytes > 0 and os.path.getsize(task.filepath) >= task.total_bytes)):
                    task.progress = 100.0
                    task.status = TaskStatus.FINISHED
                    task.error_message = ""
                else:
                    task.status = TaskStatus.IN_QUEUE
                    task.error_message = ""
                    task.cancel_flag = False
                    task.pause_flag = False

    def force_redownload_selected(self):
        tasks_to_redownload = self.get_selected_tasks()
        if not tasks_to_redownload:
            QMessageBox.information(self, "No Selection", "Select one or more tasks to force redownload.")
            return

        active_statuses = {TaskStatus.DOWNLOADING, TaskStatus.IN_QUEUE, TaskStatus.CONNECTING, TaskStatus.PAUSING, TaskStatus.UNPACKING}
        
        # Check if confirmation is needed (e.g. any completed, extracted, or partially downloaded files)
        completed_or_downloaded = [t for t in tasks_to_redownload if t.status in (TaskStatus.FINISHED, TaskStatus.EXTRACTED) or t.progress > 0]
        
        if completed_or_downloaded:
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setWindowTitle("Confirm Force Redownload")
            msg_box.setText(
                f"You have selected {len(tasks_to_redownload)} task(s), including {len(completed_or_downloaded)} completed/partially downloaded file(s).\n\n"
                "Force redownloading will permanently DELETE existing files from disk and restart downloading from 0%."
            )
            btn_all = msg_box.addButton("Redownload All Selected", QMessageBox.ButtonRole.AcceptRole)
            btn_failed_only = msg_box.addButton("Redownload Failed Tasks Only", QMessageBox.ButtonRole.ActionRole)
            btn_cancel = msg_box.addButton(QMessageBox.StandardButton.Cancel)
            
            msg_box.exec()
            clicked_btn = msg_box.clickedButton()
            
            if clicked_btn == btn_cancel:
                return
            elif clicked_btn == btn_failed_only:
                tasks_to_redownload = [t for t in tasks_to_redownload if t.status in (TaskStatus.FAILED, TaskStatus.EXTRACT_ERROR) or "Error" in str(t.status) or "Failed" in str(t.status)]
                if not tasks_to_redownload:
                    QMessageBox.information(self, "No Failed Tasks", "None of the selected tasks were in a failed state.")
                    return

        redownloaded = 0
        skipped = 0
        failed = 0

        for task in tasks_to_redownload:
            if task.status in active_statuses:
                skipped += 1
                continue

            try:
                if os.path.exists(task.filepath):
                    os.remove(task.filepath)
            except Exception as e:
                failed += 1
                task.status = TaskStatus.FAILED
                task.error_message = f"Could not delete existing file before redownload. {format_error_message(e)}"
                continue

            task.cancel_flag = False
            task.pause_flag = False
            task.progress = 0.0
            task.speed = 0.0
            task.downloaded_bytes = 0
            task.total_bytes = 0
            task.error_message = ""
            task.status = TaskStatus.IN_QUEUE
            self.extracted_folders.discard(task.folder_name)
            redownloaded += 1

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
        reextracted_count = 0

        for folder_name in target_folders:
            folder_tasks = [t for t in self.tasks if t.folder_name == folder_name]
            if not folder_tasks:
                continue

            # Remove from extracted tracking so extract_folder runs
            self.extracted_folders.discard(folder_name)
            threading.Thread(target=self.extract_folder, args=(folder_tasks,), daemon=True).start()
            reextracted_count += 1

        if reextracted_count > 0:
            QMessageBox.information(self, "Re-extracting", f"Triggered re-extraction for {reextracted_count} batch folder(s).")

    def delete_selected(self):
        tasks_to_delete = self.get_selected_tasks()
        if not tasks_to_delete:
            return
            
        delete_files = False
        
        if not self.settings.get("skip_delete_confirmation", False):
            dialog = QDialog(self)
            dialog.setWindowTitle("Confirm Delete")
            layout = QVBoxLayout(dialog)
            
            label = QLabel(f"Are you sure you want to delete {len(tasks_to_delete)} selected task(s)?")
            layout.addWidget(label)
            
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
                    self.settings["skip_delete_confirmation"] = True
                    save_settings(self.settings)
            else:
                return
                
        for task in tasks_to_delete:
            task.cancel_flag = True
            task.status = TaskStatus.CANCELLED
            
            if delete_files and os.path.exists(task.filepath):
                try:
                    os.remove(task.filepath)
                except Exception as e:
                    print(f"Failed to delete {task.filepath}: {e}")
                    
            if task.tree_item:
                parent = task.tree_item.parent()
                if parent:
                    parent.removeChild(task.tree_item)
                    if parent.childCount() == 0:
                        idx = self.tree.indexOfTopLevelItem(parent)
                        if idx >= 0:
                            self.tree.takeTopLevelItem(idx)
                            
            if task in self.tasks:
                self.tasks.remove(task)
                
        self.trigger_history_save()
                
    def clear_finished(self):
        to_remove = [t for t in self.tasks if t.status in (TaskStatus.FINISHED, TaskStatus.EXTRACTED, TaskStatus.CANCELLED)]
        
        if not to_remove:
            return
            
        for t in to_remove:
            if t.tree_item:
                parent = t.tree_item.parent()
                if parent:
                    parent.removeChild(t.tree_item)
                    if parent.childCount() == 0:
                        idx = self.tree.indexOfTopLevelItem(parent)
                        if idx >= 0:
                            self.tree.takeTopLevelItem(idx)
            self.tasks.remove(t)
            
        self.trigger_history_save()

    def format_time(self, seconds):
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

    def update_ui(self):
        import time
        global_speed = sum(getattr(task, 'speed', 0.0) for task in self.tasks if task.status == TaskStatus.DOWNLOADING)
        
        folder_estimated_sizes = {}
        folder_tasks_map = {}
        all_known_sizes = [t.total_bytes for t in self.tasks if getattr(t, 'total_bytes', 0) > 0]
        global_avg_size = (sum(all_known_sizes) / len(all_known_sizes)) if all_known_sizes else 0
        
        for task in self.tasks:
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

        cumulative_remaining_bytes = 0
        
        for task in self.tasks:
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
                cumulative_remaining_bytes += remaining_bytes
                if task.speed > 0 and task.total_bytes > 0:
                    eta_seconds = remaining_bytes / (task.speed * 1024 * 1024)
                    eta_str = self.format_time(eta_seconds)
                task.tree_item.setToolTip(6, "")
            elif task.status in (TaskStatus.IN_QUEUE, TaskStatus.STANDBY, TaskStatus.CONNECTING, TaskStatus.SOLVING_SESSION):
                fn = getattr(task, 'folder_name', 'Default')
                if task.total_bytes > 0:
                    task_rem = max(0, task.total_bytes - task.downloaded_bytes)
                else:
                    task_rem = folder_estimated_sizes.get(fn, 0)
                    
                cumulative_remaining_bytes += task_rem
                eta_str = "-"
                task.tree_item.setToolTip(6, "Waiting in queue")
            elif task.status in (TaskStatus.FINISHED, TaskStatus.EXTRACTED, TaskStatus.UNPACKING):
                eta_str = "-"
                task.tree_item.setToolTip(6, "")
            
            task.tree_item.setText(2, str(task.status))
            status_color = getattr(task.status, 'color', '#ffffff')
            task.tree_item.setForeground(2, QBrush(QColor(status_color)))
            if ("Failed" in str(task.status) or "Error" in str(task.status)) and task.error_message:
                import textwrap
                wrapped_text = "\n".join(textwrap.wrap(task.error_message, width=60))
                task.tree_item.setToolTip(2, wrapped_text)
            else:
                task.tree_item.setToolTip(2, "")
            task.tree_item.setText(3, prog_str)
            task.tree_item.setText(4, speed_str)
            task.tree_item.setText(5, elapsed_str)
            task.tree_item.setText(6, eta_str)
            task.tree_item.setText(7, size_str)
            
        active_tasks = [t for t in self.tasks if t.status in (TaskStatus.DOWNLOADING, TaskStatus.CONNECTING, TaskStatus.SOLVING_SESSION)]
        pending_tasks = [t for t in self.tasks if t.status == TaskStatus.IN_QUEUE]
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
            queue_eta_str = self.format_time(queue_eta_seconds)
            self.global_speed_label.setText(f"Global Speed: {global_speed:.2f} MB/s | Total Queue ETA: {queue_eta_str} ({active_count} active, {pending_count} pending)")
        elif active_count > 0 or pending_count > 0:
            self.global_speed_label.setText(f"Global Speed: {global_speed:.2f} MB/s | ({active_count} active, {pending_count} pending)")
        else:
            self.global_speed_label.setText(f"Global Speed: {global_speed:.2f} MB/s")

        if hasattr(self, 'speed_graph'):
            self.speed_graph.add_data_point(global_speed)
            
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
                task = next((t for t in self.tasks if t.tree_item == child), None)
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
                if any(t.status == TaskStatus.UNPACKING for t in [next((t for t in self.tasks if t.tree_item == batch_item.child(k)), None) for k in range(batch_item.childCount()) if next((t for t in self.tasks if t.tree_item == batch_item.child(k)), None)]):
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

            if batch_status in (BatchStatus.COMPLETED, TaskStatus.EXTRACTED) and folder_name not in self.notified_batches:
                self.notified_batches.add(folder_name)
                self.send_notification("Batch Finished", f"Batch '{folder_name}' is {str(batch_status).lower()}!")
            elif batch_status == BatchStatus.HAS_FAILURES and (folder_name + "_err") not in self.notified_batches:
                self.notified_batches.add(folder_name + "_err")
                self.send_notification("Batch Error", f"Batch '{folder_name}' has tasks with errors.", QSystemTrayIcon.MessageIcon.Warning)

        # Contextually enable/disable action buttons via ActionBarWidget
        selected_tasks = self.get_selected_tasks()
        if hasattr(self, 'action_bar'):
            self.action_bar.update_states(self.tasks, selected_tasks)

        # Update Session Statistics Panel
        if hasattr(self, 'session_stats_widget'):
            active_count = sum(1 for t in self.tasks if t.status in (TaskStatus.DOWNLOADING, TaskStatus.CONNECTING, TaskStatus.IN_QUEUE))
            completed_count = sum(1 for t in self.tasks if t.status in (TaskStatus.FINISHED, TaskStatus.EXTRACTED))
            error_count = sum(1 for t in self.tasks if "Error" in str(t.status) or "Failed" in str(t.status))
            self.session_stats_widget.update_stats(self.session_downloaded_bytes, active_count, completed_count, error_count)

        # Check Auto-Shutdown Trigger
        if self.shutdown_checkbox.isChecked() and self.tasks and not getattr(self, 'shutdown_dialog_active', False):
            has_active_or_queued = any(t.status in (TaskStatus.DOWNLOADING, TaskStatus.CONNECTING, TaskStatus.IN_QUEUE, TaskStatus.UNPACKING) for t in self.tasks)
            # Only trigger if downloads were started (or currently active/queued) and have now all finished
            if hasattr(self, 'is_downloading') and self.is_downloading and not has_active_or_queued:
                self.trigger_auto_shutdown()

    def save_setting_key(self, key, value):
        self.settings[key] = value
        save_settings(self.settings)

    def trigger_auto_shutdown(self):
        action = self.settings.get("auto_shutdown_action", "Shutdown")
        self.shutdown_dialog_active = True
        self.shutdown_checkbox.setChecked(False)
        self.save_setting_key("auto_shutdown_on_completion", False)

        countdown = 60
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setWindowTitle(f"Auto-{action} Triggered")
        msg_box.setText(f"All downloads and extractions completed.\n\nSystem will {action.lower()} in {countdown} seconds.")
        cancel_btn = msg_box.addButton(f"Cancel {action}", QMessageBox.ButtonRole.RejectRole)
        
        timer = QTimer(self)
        
        def update_timer():
            nonlocal countdown
            countdown -= 1
            if countdown <= 0:
                timer.stop()
                msg_box.accept()
                self.execute_system_shutdown(action)
            else:
                msg_box.setText(f"All downloads and extractions completed.\n\nSystem will {action.lower()} in {countdown} seconds.")

        timer.timeout.connect(update_timer)
        timer.start(1000)

        msg_box.exec()
        timer.stop()
        self.shutdown_dialog_active = False

    def execute_system_shutdown(self, action="Shutdown"):
        try:
            if sys.platform == "win32":
                if action == "Sleep":
                    os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
                elif action == "Hibernate":
                    os.system("shutdown /h")
                else:
                    os.system("shutdown /s /t 0")
            elif sys.platform == "darwin":
                if action == "Sleep":
                    os.system("pmset sleepnow")
                else:
                    os.system("sudo shutdown -h now")
            else:
                if action == "Sleep":
                    os.system("systemctl suspend")
                elif action == "Hibernate":
                    os.system("systemctl hibernate")
                else:
                    os.system("shutdown -h now")
        except Exception as e:
            logger.error(f"Failed to execute system {action.lower()}: {e}")


