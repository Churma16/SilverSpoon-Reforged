import os
import sys
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QFormLayout, QSpinBox, QDialogButtonBox,
    QFileDialog, QMessageBox, QTextEdit
)
from PyQt6.QtCore import Qt

class ChangelogDialog(QDialog):
    def __init__(self, base_dir, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Changelog - SilverSpoon")
        self.resize(650, 500)
        
        layout = QVBoxLayout(self)
        
        changelog_path = os.path.join(base_dir, "CHANGELOG.md")
        content = ""
        if os.path.exists(changelog_path):
            try:
                with open(changelog_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                content = f"Failed to load CHANGELOG.md:\n{e}"
        else:
            content = "CHANGELOG.md file not found."
            
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setMarkdown(content)
        layout.addWidget(text_edit)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)


class LogViewerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Debug Logs - SilverSpoon")
        self.resize(750, 500)
        
        layout = QVBoxLayout(self)
        
        log_path = os.path.expanduser("~/.silverspoon.log")
        content = ""
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                content = f"Failed to load log file:\n{e}"
        else:
            content = "Log file is empty or does not exist."
            
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlainText(content)
        # Scroll to bottom
        self.text_edit.moveCursor(self.text_edit.textCursor().MoveOperation.End)
        layout.addWidget(self.text_edit)
        
        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.reload_logs)
        btn_layout.addWidget(refresh_btn)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(self.reject)
        btn_layout.addWidget(btn_box)
        
        layout.addLayout(btn_layout)

    def reload_logs(self):
        log_path = os.path.expanduser("~/.silverspoon.log")
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    self.text_edit.setPlainText(f.read())
                self.text_edit.moveCursor(self.text_edit.textCursor().MoveOperation.End)
            except Exception as e:
                self.text_edit.setPlainText(f"Failed to reload log file:\n{e}")



class WarningDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to SilverSpoon Reforged!")
        self.setMinimumWidth(500)
        self.settings = settings
        
        layout = QVBoxLayout(self)
        
        # Shortcuts Section
        shortcuts_label = QLabel("<b>Keyboard Shortcuts:</b>")
        layout.addWidget(shortcuts_label)
        
        shortcuts_text = (
            "<ul>"
            "<li><b>[S] or [Space]</b>: Start / Resume selected downloads</li>"
            "<li><b>[P] or [Space]</b>: Pause selected downloads</li>"
            "<li><b>[C]</b>: Cancel selected downloads</li>"
            "<li><b>[R]</b>: Retry failed downloads</li>"
            "<li><b>[F]</b>: Force Redownload selected tasks</li>"
            "<li><b>[Delete] or [Backspace]</b>: Delete selected tasks</li>"
            "</ul>"
        )
        shortcuts_display = QLabel(shortcuts_text)
        shortcuts_display.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(shortcuts_display)
        
        # Warning Section
        warning_label = QLabel("<b>[warn] VPN USERS WARNING [warn]</b>")
        warning_label.setStyleSheet("color: red; font-size: 14px;")
        warning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(warning_label)
        
        warning_text = QLabel(
            "Cloudflare will aggressively block known VPN IPs. If your downloads are "
            "failing or getting stuck, and you have tried to <i>Force Redownload</i> but "
            "it keeps failing, <b>TURN OFF YOUR VPN</b>."
        )
        warning_text.setWordWrap(True)
        warning_text.setStyleSheet("color: black; font-weight: bold; padding: 10px; background-color: #ffffff; border-radius: 5px;")
        layout.addWidget(warning_text)
        
        # Don't show again checkbox
        self.dont_show_checkbox = QCheckBox("Don't show this again")
        layout.addWidget(self.dont_show_checkbox)
        
        # OK Button
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn_box.accepted.connect(self.accept)
        layout.addWidget(btn_box)

    def accept(self):
        if self.dont_show_checkbox.isChecked():
            self.settings["show_warning_dialog"] = False
        super().accept()

class SettingsDialog(QDialog):
    def __init__(self, current_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(400)
        
        self.current_settings = current_settings
        
        layout = QFormLayout(self)
        
        # Save Directory
        dir_layout = QHBoxLayout()
        default_dir = self.current_settings.get("default_save_dir", os.path.join(os.path.expanduser("~"), "Downloads"))
        self.dir_input = QLineEdit(default_dir)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_dir)
        dir_layout.addWidget(self.dir_input)
        dir_layout.addWidget(browse_btn)
        layout.addRow("Default Save Directory:", dir_layout)
        
        # Max Workers
        self.workers_spinbox = QSpinBox()
        self.workers_spinbox.setRange(1, 10)
        self.workers_spinbox.setValue(self.current_settings.get("max_workers", 3))
        layout.addRow("Max Concurrent Downloads:", self.workers_spinbox)

        # Speed Limit
        self.speed_limit_spinbox = QSpinBox()
        self.speed_limit_spinbox.setRange(0, 999999)
        self.speed_limit_spinbox.setSuffix(" KB/s (0 = unlimited)")
        self.speed_limit_spinbox.setValue(self.current_settings.get("download_speed_limit", 0))
        layout.addRow("Global Speed Limit (Total):", self.speed_limit_spinbox)
        
        # Extract Option
        self.extract_checkbox = QCheckBox()
        self.extract_checkbox.setChecked(self.current_settings.get("extract_after_download", False))
        layout.addRow("Extract after download by default:", self.extract_checkbox)
        
        # Skip Delete Confirmation Option
        self.skip_delete_checkbox = QCheckBox()
        self.skip_delete_checkbox.setChecked(self.current_settings.get("skip_delete_confirmation", False))
        layout.addRow("Skip delete confirmation:", self.skip_delete_checkbox)
        
        # Desktop Notifications Option
        self.notifications_checkbox = QCheckBox()
        self.notifications_checkbox.setChecked(self.current_settings.get("enable_notifications", True))
        layout.addRow("Enable Desktop Notifications:", self.notifications_checkbox)

        # Minimize to System Tray Option
        self.minimize_tray_checkbox = QCheckBox()
        self.minimize_tray_checkbox.setChecked(self.current_settings.get("minimize_to_tray", False))
        layout.addRow("Minimize to System Tray on Close:", self.minimize_tray_checkbox)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.reset_btn = button_box.addButton("Reset Defaults", QDialogButtonBox.ButtonRole.ResetRole)
        self.reset_btn.clicked.connect(self.reset_to_defaults)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)

    def browse_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Save Directory", self.dir_input.text())
        if folder:
            self.dir_input.setText(os.path.abspath(folder))

    def reset_to_defaults(self):
        reply = QMessageBox.question(
            self, 'Confirm Reset', 
            "Are you sure you want to reset all settings to their default values? (Includes showing warnings and UI sizes)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if sys.platform == "win32":
                default_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            else:
                default_dir = os.path.abspath(".")
            
            self.dir_input.setText(default_dir)
            self.workers_spinbox.setValue(3)
            self.speed_limit_spinbox.setValue(0)
            self.extract_checkbox.setChecked(False)
            self.skip_delete_checkbox.setChecked(False)
            self.notifications_checkbox.setChecked(True)
            self.minimize_tray_checkbox.setChecked(False)
            
            # Reset background invisible settings as well
            self.current_settings["column_widths"] = {}
            self.current_settings["show_warning_dialog"] = True

    def get_updated_settings(self):
        return {
            "default_save_dir": self.dir_input.text(),
            "max_workers": self.workers_spinbox.value(),
            "download_speed_limit": self.speed_limit_spinbox.value(),
            "extract_after_download": self.extract_checkbox.isChecked(),
            "skip_delete_confirmation": self.skip_delete_checkbox.isChecked(),
            "enable_notifications": self.notifications_checkbox.isChecked(),
            "minimize_to_tray": self.minimize_tray_checkbox.isChecked(),
            "column_widths": self.current_settings.get("column_widths", {}),
            "show_warning_dialog": self.current_settings.get("show_warning_dialog", True),
            "last_update_check": self.current_settings.get("last_update_check", 0.0)
        }
