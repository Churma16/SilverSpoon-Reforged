import os
import qtawesome as qta
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QCheckBox, QComboBox
)
from PyQt6.QtCore import pyqtSignal


class ActionBarWidget(QWidget):
    select_all_clicked = pyqtSignal()
    start_clicked = pyqtSignal()
    pause_clicked = pyqtSignal()
    cancel_clicked = pyqtSignal()
    retry_clicked = pyqtSignal()
    force_redownload_clicked = pyqtSignal()
    copy_log_clicked = pyqtSignal()
    delete_clicked = pyqtSignal()
    clear_completed_clicked = pyqtSignal()
    extract_changed = pyqtSignal(bool)
    shutdown_changed = pyqtSignal(bool)
    shutdown_action_changed = pyqtSignal(str)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setup_ui()

    @staticmethod
    def _make_action_button_style(variant="default"):
        colors = {
            "primary": {"bg": "#27ae60", "hover": "#2ecc71", "press": "#1e8449"},
            "warning": {"bg": "#e67e22", "hover": "#f39c12", "press": "#ca6f1e"},
            "danger": {"bg": "#c0392b", "hover": "#e74c3c", "press": "#a93226"},
            "accent": {"bg": "#8e44ad", "hover": "#9b59b6", "press": "#76388e"},
            "destructive": {"bg": "#922b21", "hover": "#b03a2e", "press": "#7b241c"},
            "neutral": {"bg": "#566573", "hover": "#6b7d8a", "press": "#4a5a68"},
            "default": {"bg": "#2c3e50", "hover": "#34495e", "press": "#1a252f"}
        }
        c = colors.get(variant, colors["default"])
        return f"""
            QPushButton {{
                background-color: {c['bg']};
                color: #ffffff;
                font-weight: bold;
                padding: 6px 12px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {c['hover']};
            }}
            QPushButton:pressed {{
                background-color: {c['press']};
            }}
            QPushButton:disabled {{
                background-color: #333333;
                color: #777777;
                border: 1px solid #444444;
            }}
        """

    def setup_ui(self):
        action_layout = QHBoxLayout(self)
        action_layout.setContentsMargins(0, 0, 0, 0)

        icon_color = "#ffffff"
        icon_size = 14

        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.setIcon(qta.icon("fa5s.check-double", color=icon_color, scale_factor=icon_size / 16))
        self.select_all_btn.setStyleSheet(self._make_action_button_style("default"))
        self.select_all_btn.clicked.connect(self.select_all_clicked.emit)
        action_layout.addWidget(self.select_all_btn)
        
        self.start_btn = QPushButton("Start / Resume")
        self.start_btn.setIcon(qta.icon("fa5s.play", color=icon_color, scale_factor=icon_size / 16))
        self.start_btn.setStyleSheet(self._make_action_button_style("primary"))
        self.start_btn.clicked.connect(self.start_clicked.emit)
        action_layout.addWidget(self.start_btn)
        
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setIcon(qta.icon("fa5s.pause", color=icon_color, scale_factor=icon_size / 16))
        self.pause_btn.setStyleSheet(self._make_action_button_style("neutral"))
        self.pause_btn.clicked.connect(self.pause_clicked.emit)
        action_layout.addWidget(self.pause_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setIcon(qta.icon("fa5s.stop", color=icon_color, scale_factor=icon_size / 16))
        self.cancel_btn.setStyleSheet(self._make_action_button_style("danger"))
        self.cancel_btn.clicked.connect(self.cancel_clicked.emit)
        action_layout.addWidget(self.cancel_btn)
        
        self.retry_btn = QPushButton("Retry")
        self.retry_btn.setIcon(qta.icon("fa5s.redo", color=icon_color, scale_factor=icon_size / 16))
        self.retry_btn.setStyleSheet(self._make_action_button_style("warning"))
        self.retry_btn.clicked.connect(self.retry_clicked.emit)
        action_layout.addWidget(self.retry_btn)

        self.force_redownload_btn = QPushButton("Force Redownload")
        self.force_redownload_btn.setIcon(qta.icon("fa5s.download", color=icon_color, scale_factor=icon_size / 16))
        self.force_redownload_btn.setStyleSheet(self._make_action_button_style("warning"))
        self.force_redownload_btn.clicked.connect(self.force_redownload_clicked.emit)
        action_layout.addWidget(self.force_redownload_btn)

        self.copy_log_btn = QPushButton("Copy Error Details")
        self.copy_log_btn.setIcon(qta.icon("fa5s.copy", color=icon_color, scale_factor=icon_size / 16))
        self.copy_log_btn.setStyleSheet(self._make_action_button_style("neutral"))
        self.copy_log_btn.clicked.connect(self.copy_log_clicked.emit)
        action_layout.addWidget(self.copy_log_btn)
        
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setIcon(qta.icon("fa5s.trash-alt", color=icon_color, scale_factor=icon_size / 16))
        self.delete_btn.setStyleSheet(self._make_action_button_style("danger"))
        self.delete_btn.clicked.connect(self.delete_clicked.emit)
        action_layout.addWidget(self.delete_btn)
        
        action_layout.addStretch()
        
        self.extract_checkbox = QCheckBox("Extract after download")
        self.extract_checkbox.setChecked(self.settings.get("extract_after_download", False))
        self.extract_checkbox.stateChanged.connect(lambda: self.extract_changed.emit(self.extract_checkbox.isChecked()))
        action_layout.addWidget(self.extract_checkbox)

        self.shutdown_checkbox = QCheckBox("Auto-action when done")
        self.shutdown_checkbox.setChecked(self.settings.get("auto_shutdown_on_completion", False))
        self.shutdown_checkbox.stateChanged.connect(lambda: self.shutdown_changed.emit(self.shutdown_checkbox.isChecked()))
        action_layout.addWidget(self.shutdown_checkbox)

        self.shutdown_action_combo = QComboBox()
        self.shutdown_action_combo.addItems(["Shutdown", "Sleep", "Hibernate"])
        self.shutdown_action_combo.setCurrentText(self.settings.get("auto_shutdown_action", "Shutdown"))
        self.shutdown_action_combo.currentTextChanged.connect(self.shutdown_action_changed.emit)
        action_layout.addWidget(self.shutdown_action_combo)
        
        self.clear_btn = QPushButton("Clear Completed")
        self.clear_btn.setIcon(qta.icon("fa5s.broom", color=icon_color, scale_factor=icon_size / 16))
        self.clear_btn.setStyleSheet(self._make_action_button_style("default"))
        self.clear_btn.clicked.connect(self.clear_completed_clicked.emit)
        action_layout.addWidget(self.clear_btn)

    def update_states(self, tasks, selected_tasks):
        has_tasks = len(tasks) > 0
        has_selection = len(selected_tasks) > 0
        
        from core.types import TaskStatus
        any_downloading_or_queued = any(t.status in (TaskStatus.DOWNLOADING, TaskStatus.CONNECTING, TaskStatus.IN_QUEUE) for t in tasks)
        selected_pausable = any(t.status in (TaskStatus.DOWNLOADING, TaskStatus.CONNECTING, TaskStatus.IN_QUEUE) for t in selected_tasks)
        selected_resumable = any(t.status in (TaskStatus.PAUSED, TaskStatus.STANDBY, TaskStatus.FAILED, TaskStatus.CANCELLED) for t in selected_tasks)
        selected_failed = any(t.status in (TaskStatus.FAILED, TaskStatus.EXTRACT_ERROR) or "Error" in str(t.status) or "Failed" in str(t.status) for t in selected_tasks)
        has_completed = any(t.status in (TaskStatus.FINISHED, TaskStatus.EXTRACTED) for t in tasks)

        self.select_all_btn.setEnabled(has_tasks)
        self.start_btn.setEnabled(has_tasks and (selected_resumable or not has_selection))
        self.pause_btn.setEnabled(selected_pausable if has_selection else any_downloading_or_queued)
        self.cancel_btn.setEnabled(has_selection or any_downloading_or_queued)
        self.retry_btn.setEnabled(has_selection)
        self.force_redownload_btn.setEnabled(has_selection)
        self.copy_log_btn.setEnabled(selected_failed if has_selection else any(t.status in (TaskStatus.FAILED, TaskStatus.EXTRACT_ERROR) or "Error" in str(t.status) or "Failed" in str(t.status) for t in tasks))
        self.delete_btn.setEnabled(has_selection)
        self.clear_btn.setEnabled(has_completed)
