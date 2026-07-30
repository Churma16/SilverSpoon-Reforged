import os
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog
from PyQt6.QtCore import pyqtSignal

class DirectoryBarWidget(QWidget):
    directory_changed = pyqtSignal(str)

    def __init__(self, default_dir, parent=None):
        super().__init__(parent)
        self.default_dir = default_dir
        self.setup_ui()

    def setup_ui(self):
        dir_layout = QHBoxLayout(self)
        dir_layout.setContentsMargins(0, 0, 0, 0)
        
        dir_layout.addWidget(QLabel("Base Save Directory:"))
        self.dir_input = QLineEdit(self.default_dir)
        self.dir_input.textChanged.connect(self.directory_changed.emit)
        dir_layout.addWidget(self.dir_input)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #2c3e50;
                color: #ffffff;
                font-weight: bold;
                padding: 6px 12px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #34495e; }
            QPushButton:pressed { background-color: #1a252f; }
        """)
        browse_btn.clicked.connect(self.browse_dir)
        dir_layout.addWidget(browse_btn)

    def browse_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Save Directory", self.dir_input.text())
        if folder:
            abs_path = os.path.abspath(folder)
            self.dir_input.setText(abs_path)
            self.directory_changed.emit(abs_path)

    def text(self):
        return self.dir_input.text()

    def setText(self, text):
        self.dir_input.setText(text)
