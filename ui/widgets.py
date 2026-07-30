from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame, QTreeWidget, QAbstractItemView
from PyQt6.QtGui import QPainter, QPainterPath, QColor, QLinearGradient, QPen
from PyQt6.QtCore import Qt, pyqtSignal

class SessionStatsWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame#SessionStatsWidget {
                background-color: #191e2a;
                border-radius: 6px;
            }
            QLabel {
                color: #b0c3d2;
                font-size: 11px;
            }
        """)
        self.setObjectName("SessionStatsWidget")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(24)

        self.dl_label = QLabel("Session Downloaded: <b style='color:#2ecc71;'>0.0 MB</b>")
        layout.addWidget(self.dl_label)

        self.active_label = QLabel("Active: <b style='color:#3498db;'>0</b>")
        layout.addWidget(self.active_label)

        self.completed_label = QLabel("Completed: <b style='color:#2ecc71;'>0</b>")
        layout.addWidget(self.completed_label)

        self.error_label = QLabel("Errors: <b style='color:#e74c3c;'>0</b>")
        layout.addWidget(self.error_label)

        layout.addStretch()

    def update_stats(self, session_bytes, active_count, completed_count, error_count):
        if session_bytes >= 1024 * 1024 * 1024:
            dl_str = f"{session_bytes / (1024 * 1024 * 1024):.2f} GB"
        else:
            dl_str = f"{session_bytes / (1024 * 1024):.1f} MB"

        self.dl_label.setText(f"Session Downloaded: <b style='color:#2ecc71;'>{dl_str}</b>")
        self.active_label.setText(f"Active: <b style='color:#3498db;'>{active_count}</b>")
        self.completed_label.setText(f"Completed: <b style='color:#2ecc71;'>{completed_count}</b>")
        self.error_label.setText(f"Errors: <b style='color:#e74c3c;'>{error_count}</b>")


class SpeedGraphWidget(QWidget):
    def __init__(self, parent=None, max_points=60):
        super().__init__(parent)
        self.max_points = max_points
        self.speed_history = [0.0] * max_points
        self.setMinimumHeight(60)
        self.setMaximumHeight(80)

    def add_data_point(self, speed_mbps):
        self.speed_history.append(float(speed_mbps))
        if len(self.speed_history) > self.max_points:
            self.speed_history.pop(0)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Draw card container
        painter.setBrush(QColor(25, 30, 42))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, w, h, 6, 6)

        if not self.speed_history or w <= 0 or h <= 0:
            return

        max_val = max(max(self.speed_history), 1.0)
        num_points = len(self.speed_history)
        x_step = w / max(num_points - 1, 1)

        path = QPainterPath()
        fill_path = QPainterPath()

        fill_path.moveTo(0, h)

        for i, val in enumerate(self.speed_history):
            x = i * x_step
            usable_h = h - 18
            y = h - 5 - (val / max_val * usable_h)
            if i == 0:
                path.moveTo(x, y)
                fill_path.lineTo(x, y)
            else:
                path.lineTo(x, y)
                fill_path.lineTo(x, y)

        fill_path.lineTo((num_points - 1) * x_step, h)
        fill_path.closeSubpath()

        # Fill with gradient
        gradient = QLinearGradient(0, 0, 0, h)
        gradient.setColorAt(0.0, QColor(46, 204, 113, 110))
        gradient.setColorAt(1.0, QColor(46, 204, 113, 0))
        painter.fillPath(fill_path, gradient)

        # Draw line
        painter.setPen(QPen(QColor(46, 204, 113), 2))
        painter.drawPath(path)

        # Draw label
        painter.setPen(QColor(180, 195, 210))
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        painter.drawText(w - 140, 16, f"Peak: {max_val:.2f} MB/s")


class ReorderableTreeWidget(QTreeWidget):
    order_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

    def dragMoveEvent(self, event):
        target_item = self.itemAt(event.position().toPoint())
        # If target item is a child task (has a parent), prevent dropping directly onto it as a parent container
        if target_item and target_item.parent() is not None:
            if self.dropIndicatorPosition() == QAbstractItemView.DropIndicatorPosition.OnItem:
                event.ignore()
                return
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        super().dropEvent(event)
        self.normalize_structure()
        self.order_changed.emit()

    def normalize_structure(self):
        items_to_move = []
        for top_index in range(self.topLevelItemCount()):
            top_item = self.topLevelItem(top_index)
            self._flatten_nested_items(top_item, items_to_move)

        for item, target_parent in items_to_move:
            current_parent = item.parent()
            if current_parent:
                current_parent.removeChild(item)
            if target_parent is None:
                self.addTopLevelItem(item)
            else:
                target_parent.addChild(item)

    def _flatten_nested_items(self, item, items_to_move):
        for child_index in range(item.childCount()):
            child_item = item.child(child_index)
            # If a child item has sub-children, it is a batch folder dropped inside another item
            if child_item.childCount() > 0:
                items_to_move.append((child_item, None))
            elif item.parent() is not None:
                # If child_item is nested deeper than level 1, move it up to top level parent
                items_to_move.append((child_item, item.parent()))
            self._flatten_nested_items(child_item, items_to_move)


