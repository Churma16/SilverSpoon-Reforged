import sys
import os
import time
import logging

from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, QTimer

from ui.main_window import MainWindow
from core.settings import OLD_EXE_CLEANUP_MARKER_SUFFIX

log_file = os.path.expanduser("~/.silverspoon.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

def main():
    # Perform cleanup of old exe if marker file exists
    if sys.platform == "win32" and hasattr(sys, 'frozen'):
        marker_file = sys.executable + OLD_EXE_CLEANUP_MARKER_SUFFIX
        if os.path.exists(marker_file):
            try:
                with open(marker_file, 'r', encoding='utf-8') as f:
                    old_path = f.read().strip()
                if old_path and os.path.exists(old_path):
                    for _ in range(5):
                        try:
                            os.remove(old_path)
                            break
                        except Exception:
                            time.sleep(1)
                os.remove(marker_file)
            except Exception:
                pass

    app = QApplication(sys.argv)
    
    # Determine base directory for assets
    if hasattr(sys, '_MEIPASS'):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
    # Show splash screen
    splash_pixmap = QPixmap(os.path.join(base_dir, "SilverSpoon.png"))
    
    if not splash_pixmap.isNull():
        if splash_pixmap.width() > 600 or splash_pixmap.height() > 400:
            splash_pixmap = splash_pixmap.scaled(600, 400, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            
    splash = QSplashScreen(splash_pixmap, Qt.WindowType.WindowStaysOnTopHint)
    splash.show()
    
    app.processEvents()
    
    window = MainWindow()
    
    QTimer.singleShot(1000, splash.close)
    QTimer.singleShot(1000, window.show)
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
