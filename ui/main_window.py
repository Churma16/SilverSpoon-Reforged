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

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QTreeWidget,
    QTreeWidgetItem, QHeaderView, QFileDialog, QAbstractItemView,
    QCheckBox, QDialog, QDialogButtonBox, QMessageBox, QInputDialog,
    QMenu, QSystemTrayIcon
)
from PyQt6.QtGui import QAction, QDesktopServices, QIcon
from PyQt6.QtCore import Qt, QTimer, QUrl, QEvent, QMetaObject, Q_ARG

import cloudscraper
from update_logic import UpdateCheckerThread, UpdateDownloaderDialog

from core.rate_limiter import GlobalRateLimiter
from core.settings import load_settings, save_settings, get_settings_path, CURRENT_VERSION, GITHUB_REPO, OLD_EXE_CLEANUP_MARKER_SUFFIX
from core.history import load_history, save_history
from core.download_task import DownloadTask
from core.extractors.fuckingfast import FuckingFastExtractor
from ui.dialogs import WarningDialog, SettingsDialog
from ui.widgets import SpeedGraphWidget
from utils.formatters import format_error_message

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
        self.scraper = cloudscraper.create_scraper(browser='chrome')
        self.extractor = FuckingFastExtractor(self.scraper)
        self.is_all_selected = False
        self.extracted_folders = set()
        self.notified_batches = set()
        
        self.setup_system_tray()
        self.setup_ui()
        self.load_tasks_from_history()
        
        # Show warning dialog if not disabled
        if self.settings.get("show_warning_dialog", True):
            QTimer.singleShot(100, self.show_warning_dialog)
            
        # Start Update Checker
        if sys.platform == "win32" and hasattr(sys, 'frozen'):
            self.update_checker = UpdateCheckerThread(CURRENT_VERSION, GITHUB_REPO, get_settings_path())
            self.update_checker.update_available.connect(self.prompt_update)
            self.update_checker.check_finished.connect(self.update_last_check_time)
            self.update_checker.start()
            
        # Start Background Download Manager
        self.manager_thread = threading.Thread(target=self.download_manager, daemon=True)
        self.manager_thread.start()
        
        # UI Updater Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(500) # update every 500ms

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
            if task.status in ("Downloading", "Pending", "Starting..."):
                task.pause_flag = True
                task.status = "Paused"

    def resume_all(self):
        for task in self.tasks:
            if task.status in ("Paused", "Queued", "Error", "Cancelled"):
                task.status = "Pending"
                task.pause_flag = False

    def force_quit(self):
        if hasattr(self, 'tray_icon'):
            self.tray_icon.hide()
        save_history(self.tasks)
        save_settings(self.settings)
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
        
        if hasattr(self, 'tray_icon'):
            self.tray_icon.hide()
            
        event.accept()

    def setup_ui(self):
        # Menu Bar Setup
        menu_bar = self.menuBar()
        
        # File Menu
        file_menu = menu_bar.addMenu("&File")
        
        import_action = QAction("&Import Links from File...", self)
        import_action.triggered.connect(self.import_links_from_file)
        file_menu.addAction(import_action)
        
        settings_action = QAction("&Settings", self)
        settings_action.triggered.connect(self.open_settings_dialog)
        file_menu.addAction(settings_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("&Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Help Menu
        help_menu = menu_bar.addMenu("&Help")
        
        github_action = QAction("&GitHub Repository", self)
        github_action.triggered.connect(self.open_github_link)
        help_menu.addAction(github_action)
        
        contact_action = QAction("&Contact Us", self)
        contact_action.triggered.connect(self.open_contact_link)
        help_menu.addAction(contact_action)
        
        contributing_action = QAction("C&ontributing Guide", self)
        contributing_action.triggered.connect(self.show_contributing_dialog)
        help_menu.addAction(contributing_action)
        
        help_menu.addSeparator()
        
        welcome_action = QAction("&Welcome", self)
        welcome_action.triggered.connect(self.show_warning_dialog_manual)
        help_menu.addAction(welcome_action)
        
        check_update_action = QAction("Check for &Updates...", self)
        check_update_action.triggered.connect(self.manual_update_check)
        help_menu.addAction(check_update_action)

        about_menu = menu_bar.addMenu("&About")
        
        about_action = QAction("&About SilverSpoon Reforged", self)
        about_action.triggered.connect(self.show_about_dialog)
        about_menu.addAction(about_action)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # 1. Directory Section
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("Base Save Directory:"))
        default_dir = self.settings.get("default_save_dir", os.path.join(os.path.expanduser("~"), "Downloads"))
        self.dir_input = QLineEdit(default_dir)
        dir_layout.addWidget(self.dir_input)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_dir)
        dir_layout.addWidget(browse_btn)
        main_layout.addLayout(dir_layout)
        
        # 2. Links & Global Stats Section
        stats_layout = QHBoxLayout()
        stats_layout.addWidget(QLabel("Paste Links or HTML Block Here:"))
        
        paste_btn = QPushButton("Paste from Clipboard")
        paste_btn.clicked.connect(self.paste_from_clipboard)
        stats_layout.addWidget(paste_btn)
        
        stats_layout.addStretch()
        self.global_speed_label = QLabel("Global Speed: 0.00 MB/s")
        self.global_speed_label.setStyleSheet("font-weight: bold; color: #2ecc71;")
        stats_layout.addWidget(self.global_speed_label)
        main_layout.addLayout(stats_layout)

        # Traffic / Speed Graph
        self.speed_graph = SpeedGraphWidget(self)
        main_layout.addWidget(self.speed_graph)
        
        self.text_links = QTextEdit()
        self.text_links.setAcceptRichText(False)
        self.text_links.setMaximumHeight(80)
        main_layout.addWidget(self.text_links)
        
        add_btn = QPushButton("Add Links to Queue")
        add_btn.setStyleSheet("background-color: #2e55cc; color: white; font-weight: bold; padding: 6px;")
        add_btn.clicked.connect(self.add_links)
        main_layout.addWidget(add_btn)
        
        # 3. Table/Tree Section
        self.tree = QTreeWidget()
        self.tree.setColumnCount(7)
        self.tree.setHeaderLabels(["Filename / Folder", "Sel", "Status", "Progress", "Speed", "ETA", "Size"])
        
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.tree.setColumnWidth(1, 40)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.tree.header().setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        self.tree.header().setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
        self.tree.header().setSectionResizeMode(6, QHeaderView.ResizeMode.Interactive)
        
        # Load saved column widths if available
        saved_widths = self.settings.get("column_widths", {})
        if saved_widths:
            for i in range(self.tree.columnCount()):
                width = saved_widths.get(str(i))
                if width:
                    self.tree.setColumnWidth(i, width)
        else:
            self.tree.setColumnWidth(0, 300)
            self.tree.setColumnWidth(2, 100)
            self.tree.setColumnWidth(3, 80)
            self.tree.setColumnWidth(4, 80)
            self.tree.setColumnWidth(5, 80)
            self.tree.setColumnWidth(6, 120)
        
        self.tree.header().moveSection(1, 0)
        
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
        main_layout.addWidget(self.tree)
        
        # 4. Action Section
        action_layout = QHBoxLayout()
        
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.toggle_select_all)
        action_layout.addWidget(self.select_all_btn)
        
        self.start_btn = QPushButton("Start / Resume")
        self.start_btn.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; padding: 6px;")
        self.start_btn.clicked.connect(self.start_downloads)
        action_layout.addWidget(self.start_btn)
        
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold; padding: 6px;")
        self.pause_btn.clicked.connect(self.pause_selected)
        action_layout.addWidget(self.pause_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; padding: 6px;")
        self.cancel_btn.clicked.connect(self.cancel_selected)
        action_layout.addWidget(self.cancel_btn)
        
        self.retry_btn = QPushButton("Retry")
        self.retry_btn.setStyleSheet("background-color: #9b59b6; color: white; font-weight: bold; padding: 6px;")
        self.retry_btn.clicked.connect(self.retry_selected)
        action_layout.addWidget(self.retry_btn)

        self.force_redownload_btn = QPushButton("Force Redownload")
        self.force_redownload_btn.setStyleSheet("background-color: #300101; color: white; font-weight: bold; padding: 6px;")
        self.force_redownload_btn.clicked.connect(self.force_redownload_selected)
        action_layout.addWidget(self.force_redownload_btn)

        self.copy_log_btn = QPushButton("Copy Error Details")
        self.copy_log_btn.setStyleSheet("background-color: #555; color: white; font-weight: bold; padding: 6px;")
        self.copy_log_btn.clicked.connect(self.copy_selected_error_log)
        action_layout.addWidget(self.copy_log_btn)
        
        self.delete_btn = QPushButton("[delete] Delete")
        self.delete_btn.setStyleSheet("background-color: #34495e; color: white; font-weight: bold; padding: 6px;")
        self.delete_btn.clicked.connect(self.delete_selected)
        action_layout.addWidget(self.delete_btn)
        
        action_layout.addStretch()
        
        self.extract_checkbox = QCheckBox("Extract after download")
        self.extract_checkbox.setChecked(self.settings.get("extract_after_download", False))
        action_layout.addWidget(self.extract_checkbox)
        
        clear_btn = QPushButton("Clear Completed")
        clear_btn.clicked.connect(self.clear_finished)
        action_layout.addWidget(clear_btn)
        
        main_layout.addLayout(action_layout)

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
                    if selected[0].status in ("Downloading", "Starting..."):
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
        menu.addAction("Copy Error Details", self.copy_selected_error_log)
        menu.addSeparator()
        menu.addAction("Delete", self.delete_selected)
        menu.exec(self.tree.viewport().mapToGlobal(position))

    def get_or_create_batch_item(self, folder_name):
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item.text(0) == folder_name:
                return item
                
        batch_item = QTreeWidgetItem(self.tree)
        batch_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        batch_item.setText(0, folder_name)
        batch_item.setCheckState(1, Qt.CheckState.Unchecked)
        batch_item.setExpanded(True)
        return batch_item

    def trigger_history_save(self):
        if not hasattr(self, '_history_save_timer'):
            self._history_save_timer = QTimer()
            self._history_save_timer.setSingleShot(True)
            self._history_save_timer.timeout.connect(lambda: save_history(self.tasks))
        
        QMetaObject.invokeMethod(self._history_save_timer, "start", Qt.ConnectionType.QueuedConnection, Q_ARG(int, 500))

    def add_task_to_ui(self, task):
        batch_item = self.get_or_create_batch_item(task.folder_name)
        
        child_item = QTreeWidgetItem(batch_item)
        child_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        
        child_item.setText(0, task.filename)
        
        check_state = Qt.CheckState.Checked if task.is_selected else Qt.CheckState.Unchecked
        child_item.setCheckState(1, check_state)
        
        child_item.setText(2, task.status)
        child_item.setText(3, "0%")
        child_item.setText(4, "-")
        child_item.setText(5, "-")
        child_item.setText(6, "-")
        
        task.tree_item = child_item
        
        if task not in self.tasks:
            self.tasks.append(task)
            self.trigger_history_save()

    def copy_selected_error_log(self):
        for task in self.get_selected_tasks():
            if "Error" in task.status:
                self.copy_error_log(task)
                return
        QMessageBox.information(self, "No Error Selected", "Select a failed task first, then copy its error details.")

    def copy_error_log(self, task):
        log_path = os.path.expanduser("~/.silverspoon.log")
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
            
            if task.status == "Extracted":
                self.extracted_folders.add(task.folder_name)
            elif task.status == "Extracting...":
                task.status = "Completed"

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
        QDesktopServices.openUrl(QUrl("https://github.com/billysams21/SilverSpoon"))
        
    def open_contact_link(self):
        QDesktopServices.openUrl(QUrl("https://github.com/billysams21/SilverSpoon/issues"))

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

    def show_about_dialog(self):
        QMessageBox.about(self, "About SilverSpoon Reforged",
            "<h3>SilverSpoon Reforged v1.3.0</h3>"
            "<p>A simple, fast bulk downloader for FuckingFast links developed by billysams21.</p>"
            "<p>Select your links, paste them in, and hit Add!</p>"
            "<p>Licensed under the GNU GPLv3.</p>"
            "<hr>"
            "<h4>Changelog (v1.3.0 - Short):</h4>"
            "<ul>"
            "<li><b>New:</b> Built-in auto-updater for Windows executables.</li>"
            "<li><b>New:</b> VPN warning dialog to help with Cloudflare blocking.</li>"
            "<li><b>New:</b> Default save directory smartly falls back to user Downloads folder.</li>"
            "<li><b>New:</b> Reset Settings to Defaults button.</li>"
            "<li><b>New:</b> Toggle pause/resume with the Spacebar.</li>"
            "<li><b>Fix:</b> Better directory creation error handling during downloads.</li>"
            "</ul>"
            "<hr>"
            "<h4>Changelog (v1.2.1 - Short):</h4>"
            "<ul>"
            "<li><b>New:</b> Right-click context menu and keyboard shortcuts.</li>"
            "<li><b>New:</b> Force Redownload action.</li>"
            "<li><b>New:</b> Hover error tooltips and 'Copy Error Details' log extraction.</li>"
            "<li><b>New:</b> Extraction support for Linux and macOS.</li>"
            "</ul>"
            "<p><i>See CHANGELOG.md for full details.</i></p>"
        )

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
            extract_dir = os.path.join(tempfile.gettempdir(), f"silverspoon_extract_{int(time.time())}")
            
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                    
                new_exe_path = None
                for root, _, files in os.walk(extract_dir):
                    for file in files:
                        if file.lower() == "silverspoon.exe":
                            new_exe_path = os.path.join(root, file)
                            break
                            
                if not new_exe_path:
                    raise Exception("Could not find SilverSpoon.exe inside the downloaded zip.")
                    
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
                
                if os.path.exists(old_exe_path):
                    try:
                        os.remove(old_exe_path)
                    except Exception:
                        pass
                
                os.rename(current_exe, old_exe_path)
                
                copy_success = False
                for _ in range(10):
                    try:
                        shutil.copy2(new_exe_path, current_exe)
                        copy_success = True
                        break
                    except PermissionError:
                        time.sleep(0.5)
                        
                if not copy_success:
                    os.rename(old_exe_path, current_exe)
                    raise Exception("Could not copy the new executable. It might be locked by your Antivirus.")
                
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
                
                bat_path = os.path.join(tempfile.gettempdir(), f"silverspoon_restart_{int(time.time())}.bat")
                with open(bat_path, 'w') as bat:
                    bat.write('@echo off\n')
                    bat.write('set PYINSTALLER_RESET_ENVIRONMENT=1\n')
                    bat.write('set _MEIPASS=\n')
                    bat.write('set _MEIPASS2=\n')
                    bat.write('ping 127.0.0.1 -n 4 > nul\n')
                    bat.write(f'start "" /wait "{current_exe}"\n')
                    bat.write('if errorlevel 1 goto cleanup\n')
                    bat.write(f'if exist "{cleanup_marker}" del /f /q "{old_exe_path}" > nul 2>&1\n')
                    bat.write(f'if not exist "{old_exe_path}" if exist "{cleanup_marker}" del /q "{cleanup_marker}" > nul 2>&1\n')
                    bat.write(':cleanup\n')
                    bat.write(f'del "%~f0"\n')
                
                CREATE_NO_WINDOW = 0x08000000
                subprocess.Popen(
                    [bat_path],
                    creationflags=CREATE_NO_WINDOW,
                    close_fds=True
                )
                
                QApplication.quit()
                sys.exit(0)
                
            except Exception as e:
                QMessageBox.critical(self, "Update Failed", f"Failed to apply the update:\n{str(e)}")

    def open_settings_dialog(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self.settings = dialog.get_updated_settings()
            save_settings(self.settings)
            
            self.max_workers = self.settings.get("max_workers", 3)
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
            
        extracted_urls = re.findall(r'https?://[^\s"<>\']+', text)
        
        ff_links = [u.rstrip('"\';>,') for u in extracted_urls if "fuckingfast.co" in u]
        web_urls = [u.rstrip('"\';>,') for u in extracted_urls if "fuckingfast.co" not in u]
        
        if not ff_links and web_urls:
            target_url = web_urls[0]
            try:
                scraper = cloudscraper.create_scraper(browser='chrome')
                res = scraper.get(target_url, timeout=15)
                if res.status_code == 200:
                    page_ff_urls = re.findall(r'https?://fuckingfast\.co/[^\s"<>\']+', res.text)
                    ff_links = list(dict.fromkeys([u.rstrip('"\';>,') for u in page_ff_urls]))
            except Exception as e:
                QMessageBox.critical(self, "Scraper Error", f"Failed to scrape webpage links:\n{e}")
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
            "Enter a folder name for these files:\n(This groups main game and optional files together)",
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
            if task.status in ("Queued", "Cancelled", "Error", "Paused"):
                task.status = "Pending"
                task.error_message = ""
                task.cancel_flag = False
                task.pause_flag = False

    def pause_selected(self):
        for task in self.get_selected_tasks():
            if task.status in ("Downloading", "Pending", "Starting..."):
                task.pause_flag = True
                task.status = "Pausing..." if task.status == "Downloading" else "Paused"

    def cancel_selected(self):
        for task in self.get_selected_tasks():
            if task.status in ("Downloading", "Pending", "Paused", "Starting...", "Queued"):
                task.cancel_flag = True
                task.pause_flag = False
                task.status = "Cancelled"

    def retry_selected(self):
        for task in self.get_selected_tasks():
            if "Error" in task.status:
                task.status = "Pending"
                task.error_message = ""
                task.cancel_flag = False
                task.pause_flag = False

    def force_redownload_selected(self):
        tasks_to_redownload = self.get_selected_tasks()
        if not tasks_to_redownload:
            QMessageBox.information(self, "No Selection", "Select one or more tasks to force redownload.")
            return

        active_statuses = {"Downloading", "Pending", "Starting...", "Pausing...", "Extracting..."}
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
                task.status = "Error"
                task.error_message = f"Could not delete existing file before redownload. {format_error_message(e)}"
                continue

            task.cancel_flag = False
            task.pause_flag = False
            task.progress = 0.0
            task.speed = 0.0
            task.downloaded_bytes = 0
            task.total_bytes = 0
            task.error_message = ""
            task.status = "Pending"
            self.extracted_folders.discard(task.folder_name)
            redownloaded += 1

        if skipped or failed or redownloaded == 0:
            QMessageBox.information(
                self,
                "Force Redownload",
                f"Queued: {redownloaded}\nSkipped active tasks: {skipped}\nFailed: {failed}"
            )

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
            task.status = "Cancelled"
            
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
        to_remove = [t for t in self.tasks if t.status in ("Completed", "Extracted", "Cancelled")]
        
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

    def format_eta(self, seconds):
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
        global_speed = sum(getattr(task, 'speed', 0.0) for task in self.tasks if task.status == "Downloading")
        
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
            prog_str = f"{task.progress:.1f}%" if task.status not in ("Extracted", "Extracting...", "Extract Error") else "-"
            speed_str = f"{task.speed:.2f} MB/s" if task.status == "Downloading" else "-"
            size_mb = task.total_bytes / (1024*1024)
            dl_mb = task.downloaded_bytes / (1024*1024)
            size_str = f"{dl_mb:.1f} / {size_mb:.1f} MB" if task.total_bytes > 0 else "-"
            
            eta_str = "-"
            if task.status == "Downloading":
                remaining_bytes = max(0, task.total_bytes - task.downloaded_bytes)
                cumulative_remaining_bytes += remaining_bytes
                if task.speed > 0 and task.total_bytes > 0:
                    eta_seconds = remaining_bytes / (task.speed * 1024 * 1024)
                    eta_str = self.format_eta(eta_seconds)
                task.tree_item.setToolTip(5, "")
            elif task.status in ("Pending", "Queued", "Starting..."):
                fn = getattr(task, 'folder_name', 'Default')
                if task.total_bytes > 0:
                    task_rem = max(0, task.total_bytes - task.downloaded_bytes)
                else:
                    task_rem = folder_estimated_sizes.get(fn, 0)
                    
                cumulative_remaining_bytes += task_rem
                eta_str = "-"
                task.tree_item.setToolTip(5, "Waiting in queue")
            elif task.status in ("Completed", "Extracted", "Extracting..."):
                eta_str = "-"
                task.tree_item.setToolTip(5, "")
            
            task.tree_item.setText(2, task.status)
            if "Error" in task.status and task.error_message:
                import textwrap
                wrapped_text = "\n".join(textwrap.wrap(task.error_message, width=60))
                task.tree_item.setToolTip(2, wrapped_text)
            else:
                task.tree_item.setToolTip(2, "")
            task.tree_item.setText(3, prog_str)
            task.tree_item.setText(4, speed_str)
            task.tree_item.setText(5, eta_str)
            task.tree_item.setText(6, size_str)
            
        active_tasks = [t for t in self.tasks if t.status in ("Downloading", "Starting...")]
        pending_tasks = [t for t in self.tasks if t.status in ("Pending", "Queued")]
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
            queue_eta_str = self.format_eta(queue_eta_seconds)
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
                    
                    if task.status not in ("Completed", "Extracted"):
                        all_completed = False
                    if "Error" in task.status:
                        any_error = True
                    if task.status in ("Downloading", "Starting...", "Pending"):
                        any_downloading = True
                        
            batch_status = "Queued"
            if all_completed:
                if any(t.status == "Extracting..." for t in [next((t for t in self.tasks if t.tree_item == batch_item.child(k)), None) for k in range(batch_item.childCount()) if next((t for t in self.tasks if t.tree_item == batch_item.child(k)), None)]):
                    batch_status = "Extracting..."
                else:
                    batch_status = "Completed"
            elif any_error:
                batch_status = "Contains Errors"
            elif any_downloading:
                batch_status = "Active"
                
            prog = (total_dl / total_size * 100) if total_size > 0 else 0
            prog_str = f"{prog:.1f}%"
            speed_str = f"{total_speed:.2f} MB/s" if total_speed > 0 else "-"
            size_mb = total_size / (1024*1024)
            dl_mb = total_dl / (1024*1024)
            size_str = f"{dl_mb:.1f} / {size_mb:.1f} MB" if total_size > 0 else "-"
            
            eta_str = "-"
            remaining_batch_bytes = max(0, total_size - total_dl)
            if any_downloading and remaining_batch_bytes > 0:
                if total_speed > 0:
                    eta_seconds = remaining_batch_bytes / (total_speed * 1024 * 1024)
                    eta_str = self.format_eta(eta_seconds)
                elif global_speed > 0:
                    eta_seconds = remaining_batch_bytes / (global_speed * 1024 * 1024)
                    eta_str = f"~{self.format_eta(eta_seconds)}"
            
            batch_item.setText(2, batch_status)
            batch_item.setToolTip(2, "")
            batch_item.setText(3, prog_str)
            batch_item.setText(4, speed_str)
            batch_item.setText(5, eta_str)
            batch_item.setText(6, size_str)

            folder_name = batch_item.text(0)
            if batch_status in ("Completed", "Extracted") and folder_name not in self.notified_batches:
                self.notified_batches.add(folder_name)
                self.send_notification("Batch Finished", f"Batch '{folder_name}' is {batch_status.lower()}!")
            elif batch_status == "Contains Errors" and (folder_name + "_err") not in self.notified_batches:
                self.notified_batches.add(folder_name + "_err")
                self.send_notification("Batch Error", f"Batch '{folder_name}' has tasks with errors.", QSystemTrayIcon.MessageIcon.Warning)

    def download_manager(self):
        while True:
            active = sum(1 for t in self.tasks if t.status in ("Downloading", "Starting..."))
            if active < self.max_workers:
                for task in self.tasks:
                    if task.status == "Pending":
                        task.status = "Starting..."
                        threading.Thread(target=self.download_worker, args=(task,), daemon=True).start()
                        active += 1
                        if active >= self.max_workers:
                            break
            
            if self.extract_checkbox.isChecked():
                self.check_extraction()
                
            time.sleep(1)
            
    def check_extraction(self):
        folders = {}
        for task in self.tasks:
            if task.folder_name not in folders:
                folders[task.folder_name] = []
            folders[task.folder_name].append(task)
            
        for folder_name, tasks_in_folder in folders.items():
            if folder_name in self.extracted_folders:
                continue
                
            valid_extraction_statuses = {"Completed", "Extracted", "Extracting..."}
            if tasks_in_folder and all(t.status in valid_extraction_statuses for t in tasks_in_folder):
                if all(t.status == "Extracted" for t in tasks_in_folder):
                    self.extracted_folders.add(folder_name)
                    continue
                    
                if any(t.status == "Extracting..." for t in tasks_in_folder):
                    continue
                    
                self.extracted_folders.add(folder_name)
                threading.Thread(target=self.extract_folder, args=(tasks_in_folder,), daemon=True).start()

    def extract_folder(self, tasks_in_folder):
        save_dir = tasks_in_folder[0].save_dir
        folder_name = tasks_in_folder[0].folder_name
        
        for t in tasks_in_folder:
            t.status = "Extracting..."
            
        try:
            files = os.listdir(save_dir)
            files.sort()
            
            first_vol = None
            for f in files:
                if re.search(r'\.part0*1\.rar$', f, re.IGNORECASE) or \
                   re.search(r'\.001$', f) or \
                   (f.lower().endswith('.rar') and not re.search(r'\.part\d+\.rar$', f, re.IGNORECASE)):
                    first_vol = os.path.join(save_dir, f)
                    break
                    
            if not first_vol and files:
                first_vol = os.path.join(save_dir, files[0])
                
            if not first_vol:
                for t in tasks_in_folder:
                    t.status = "Extract Error (No File)"
                    t.error_message = f"No archive file was found in {save_dir}."
                if folder_name in self.extracted_folders:
                    self.extracted_folders.remove(folder_name)
                return
                
            cmd = None
            if sys.platform == 'win32':
                if hasattr(sys, '_MEIPASS'):
                    bundled_7z = os.path.join(sys._MEIPASS, '7z.exe')
                else:
                    bundled_7z = os.path.normpath(os.path.join(self.base_dir, '7z.exe'))
                installed_7z = r"C:\Program Files\7-Zip\7z.exe"
                installed_winrar = r"C:\Program Files\WinRAR\WinRAR.exe"
                if os.path.exists(installed_7z):
                    cmd = [installed_7z, 'x', first_vol, f'-o{save_dir}', '-y']
                elif os.path.exists(installed_winrar):
                    cmd = [installed_winrar, 'x', '-y', first_vol, f'{save_dir}\\']
                elif os.path.exists(bundled_7z):
                    cmd = [bundled_7z, 'x', first_vol, f'-o{save_dir}', '-y']
            else:
                if shutil.which('7z'):
                    cmd = ['7z', 'x', first_vol, f'-o{save_dir}', '-y']
                elif shutil.which('unrar'):
                    cmd = ['unrar', 'x', first_vol, f'{save_dir}/', '-y']
                
            if not cmd:
                for t in tasks_in_folder:
                    t.status = "Extract Error (No extractor found)"
                    t.error_message = "No supported extractor was found. Install 7-Zip or WinRAR, then retry extraction."
                if folder_name in self.extracted_folders:
                    self.extracted_folders.remove(folder_name)
                return
                
            creationflags = 0x08000000 if sys.platform == 'win32' else 0
            subprocess.run(
                cmd,
                check=True,
                creationflags=creationflags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL
            )
            
            for t in tasks_in_folder:
                t.status = "Extracted"
                t.error_message = ""
            self.trigger_history_save()
                
        except subprocess.CalledProcessError as e:
            logging.error(f"Extraction error (subprocess): {e}", exc_info=True)
            for t in tasks_in_folder:
                t.status = "Extract Error (Corrupt?)"
                t.error_message = f"Extractor failed with exit code {e.returncode}. The archive may be corrupt, incomplete, or password-protected."
            if folder_name in self.extracted_folders:
                self.extracted_folders.remove(folder_name)
            self.trigger_history_save()
        except Exception as e:
            logging.error(f"Extraction error: {e}", exc_info=True)
            for t in tasks_in_folder:
                t.status = "Extract Error"
                t.error_message = f"Extraction failed: {format_error_message(e)}"
            if folder_name in self.extracted_folders:
                self.extracted_folders.remove(folder_name)
            self.trigger_history_save()

    def get_direct_link(self, task):
        direct_link, err_msg = self.extractor.extract_direct_url(task.link, task.file_id)
        if not direct_link:
            task.error_message = err_msg or "Could not get the direct download link. The link may be expired or blocked."
            return None
        return direct_link

    def download_worker(self, task):
        dl_url = self.get_direct_link(task)
        if not dl_url:
            if not task.cancel_flag and not task.pause_flag:
                task.status = "Error"
                if not task.error_message:
                    task.error_message = "Could not get the direct download link."
            return
            
        if task.cancel_flag:
            task.status = "Cancelled"
            return
            
        if task.pause_flag:
            task.status = "Paused"
            return

        task.status = "Downloading"
        task.error_message = ""
        
        try:
            if not os.path.exists(task.save_dir):
                try:
                    os.makedirs(task.save_dir, exist_ok=True)
                except Exception as e:
                    task.status = "Error"
                    task.error_message = f"Failed to create save directory '{task.save_dir}'. {format_error_message(e)}"
                    self.trigger_history_save()
                    return
                
            initial_size = 0
            if os.path.exists(task.filepath):
                initial_size = os.path.getsize(task.filepath)
                
            head_req = self.scraper.head(dl_url)
            total_size = int(head_req.headers.get('content-length', 0))
            task.total_bytes = total_size
            
            if initial_size > 0 and initial_size == total_size:
                task.downloaded_bytes = total_size
                task.progress = 100
                task.status = "Completed"
                task.error_message = ""
                return
                
            resume_header = {}
            mode = 'wb'
            if initial_size > 0:
                resume_header = {'Range': f'bytes={initial_size}-'}
                mode = 'ab'
                
            with self.scraper.get(dl_url, stream=True, headers=resume_header) as r:
                if r.status_code not in (200, 206):
                    task.status = "Error"
                    task.error_message = f"Download request failed. Server returned HTTP {r.status_code}."
                    if r.status_code in (403, 503):
                        preview = r.text[:500] if hasattr(r, 'text') else "No text body"
                        logging.error(f"Download 403/503 for {dl_url}. Body preview: {preview}")
                    return
                    
                if r.status_code == 200 and initial_size > 0:
                    mode = 'wb'
                    initial_size = 0
                    
                task.downloaded_bytes = initial_size
                if total_size == 0 and 'content-length' in r.headers:
                    task.total_bytes = int(r.headers['content-length']) + initial_size
                elif total_size == 0:
                    task.total_bytes = 0
                    
                start_time = time.time()
                last_time = start_time
                bytes_since_last = 0
                
                with open(task.filepath, mode) as f:
                    for chunk in r.iter_content(chunk_size=8192*8):
                        if task.pause_flag:
                            task.status = "Paused"
                            task.speed = 0
                            return
                        if task.cancel_flag:
                            task.status = "Cancelled"
                            task.speed = 0
                            return
                            
                        if chunk:
                            f.write(chunk)
                            size = len(chunk)
                            task.downloaded_bytes += size
                            bytes_since_last += size
                            
                            now = time.time()
                            if now - last_time > 0.5:
                                task.speed = (bytes_since_last / (now - last_time)) / (1024*1024)
                                if task.total_bytes > 0:
                                    task.progress = (task.downloaded_bytes / task.total_bytes) * 100
                                last_time = now
                                bytes_since_last = 0
                                
                            self.rate_limiter.consume(size, self.settings.get("download_speed_limit", 0))
                
                task.progress = 100
                task.speed = 0
                task.status = "Completed"
                task.error_message = ""
                self.trigger_history_save()
                
        except Exception as e:
            logging.error(f"Download worker error for task {task.link}: {e}", exc_info=True)
            if not task.cancel_flag and not task.pause_flag:
                task.status = "Error"
                task.error_message = f"Download failed. {format_error_message(e)}"
                self.trigger_history_save()
