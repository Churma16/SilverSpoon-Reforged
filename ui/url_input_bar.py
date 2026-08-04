from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal
from ui.widgets import SpeedGraphWidget

class UrlInputBarWidget(QWidget):
    add_links_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)
        
        # Row 1: Label + Paste Button + Global Speed
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Paste Links or HTML Block Here:"))
        
        paste_btn = QPushButton("Paste from Clipboard")
        paste_btn.setStyleSheet("""
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
        paste_btn.clicked.connect(self.paste_from_clipboard)
        header_layout.addWidget(paste_btn)
        
        header_layout.addStretch()
        
        self.global_speed_label = QLabel("Global Speed: 0.00 MB/s")
        self.global_speed_label.setStyleSheet("font-weight: bold; color: #2ecc71;")
        header_layout.addWidget(self.global_speed_label, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        main_layout.addLayout(header_layout)
        
        # Row 2: Full-width Speed Graph Strip
        self.speed_graph = SpeedGraphWidget(self)
        self.speed_graph.setFixedHeight(45)
        main_layout.addWidget(self.speed_graph)
        
        # Row 3: Text Input Area
        self.text_links = QTextEdit()
        self.text_links.setPlaceholderText(
            "Paste page URLs, direct file-host links, or raw HTML code here..."
        )
        self.text_links.setMaximumHeight(80)
        main_layout.addWidget(self.text_links)
        
        # Row 4: Add Links Button
        add_btn = QPushButton("Add Links to Queue")
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: #ffffff;
                font-weight: bold;
                padding: 6px 12px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #2ecc71; }
            QPushButton:pressed { background-color: #1e8449; }
        """)
        add_btn.clicked.connect(self.add_links_requested.emit)
        main_layout.addWidget(add_btn)

    def paste_from_clipboard(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            current_text = self.text_links.toPlainText()
            if current_text.strip():
                self.text_links.setText(current_text + "\n" + text)
            else:
                self.text_links.setText(text)

    def toPlainText(self):
        return self.text_links.toPlainText()

    def clear(self):
        self.text_links.clear()

    def update_speed(self, speed_str):
        self.global_speed_label.setText(f"Global Speed: {speed_str}")
