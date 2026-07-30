from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QPainterPath, QColor, QLinearGradient, QPen
from PyQt6.QtCore import Qt

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
