import sys
import os
import time
import logging
from logging.handlers import RotatingFileHandler

from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, QTimer

from ui.main_window import MainWindow
from core.settings import OLD_EXE_CLEANUP_MARKER_SUFFIX

is_debug_mode = any(arg.lower() in ("-debug", "--debug") for arg in sys.argv)

base_dir = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
log_dir = os.path.join(base_dir, "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "silverspoon.log")
handlers = [
    RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8')
]

if is_debug_mode:
    handlers.append(logging.StreamHandler(sys.stdout))

logging.basicConfig(
    level=logging.DEBUG if is_debug_mode else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=handlers
)

# Mute noisy 3rd-party loggers unless in debug mode
if not is_debug_mode:
    for noisy_logger_name in ("selenium", "filelock", "urllib3", "uc", "WDM"):
        logging.getLogger(noisy_logger_name).setLevel(logging.WARNING)

logger = logging.getLogger("pyqt_downloader")

def main():
    # Set explicit AppUserModelID on Windows so taskbar does not group with other forks
    if sys.platform == "win32":
        try:
            import ctypes
            app_id = "churma16.silverspoon.reforged.ui"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception as e:
            logger.warning(f"Could not set AppUserModelID: {e}")

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
                logger.info(f"Cleaned up old executable: {old_path}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup old executable: {cleanup_error}")

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
    
    app.aboutToQuit.connect(logging.shutdown)
    
    exit_code = app.exec()
    logging.shutdown()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
