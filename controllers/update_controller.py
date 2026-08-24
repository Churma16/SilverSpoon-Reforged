import os
import sys
import shutil
import logging
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QLabel, QTextEdit,
    QDialogButtonBox, QMessageBox
)

from update_logic import (
    UpdateCheckerThread, UpdateDownloaderDialog,
    extract_and_verify_update, perform_exe_replacement, launch_restart_script
)
from core.settings import (
    CURRENT_VERSION, GITHUB_REPO, get_settings_path,
    save_settings, load_settings, OLD_EXE_CLEANUP_MARKER_SUFFIX
)
from core.history import save_history

logger = logging.getLogger(__name__)


class UpdateController(QObject):
    """Controller responsible for application update checks, user prompts, and binary replacement."""

    update_available_signal = pyqtSignal(str, str, str)
    update_check_completed = pyqtSignal(float)

    def __init__(self, parent_widget=None, get_tasks_callback=None, get_settings_callback=None):
        super().__init__(parent_widget)
        self.parent_widget = parent_widget
        self.get_tasks_callback = get_tasks_callback
        self.get_settings_callback = get_settings_callback
        self.update_checker = None
        self.manual_checker = None

    def start_auto_check_if_enabled(self):
        """Starts auto-check thread if running frozen executable on Windows and enabled in settings."""
        settings = self._get_settings()
        if sys.platform == "win32" and hasattr(sys, 'frozen') and settings.get("auto_check_updates", False):
            self.update_checker = UpdateCheckerThread(CURRENT_VERSION, GITHUB_REPO, get_settings_path())
            self.update_checker.update_available.connect(self.prompt_update)
            self.update_checker.check_finished.connect(self.update_last_check_time)
            self.update_checker.start()

    def check_for_updates_manually(self):
        """Manually triggers an update check with user feedback."""
        self.manual_checker = UpdateCheckerThread(CURRENT_VERSION, GITHUB_REPO, get_settings_path(), force=True)
        self.manual_checker.update_available.connect(self.prompt_update)
        self.manual_checker.check_finished.connect(self.update_last_check_time)
        self.manual_checker.no_update_found.connect(
            lambda: QMessageBox.information(
                self.parent_widget,
                "Up to date",
                "You are already using the latest version of SilverSpoon!"
            )
        )
        self.manual_checker.error_checking.connect(
            lambda err: QMessageBox.warning(
                self.parent_widget,
                "Update Check Failed",
                f"Could not check for updates:\n{err}"
            )
        )
        self.manual_checker.start()

    def update_last_check_time(self, timestamp: float):
        """Saves the last check timestamp into settings."""
        settings = self._get_settings()
        settings["last_update_check"] = timestamp
        save_settings(settings)
        self.update_check_completed.emit(timestamp)

    def prompt_update(self, version: str, changelog: str, download_url: str):
        """Displays modal dialog offering the user to download and apply the update."""
        current_exe_dir = os.path.dirname(sys.executable)
        test_file = os.path.join(current_exe_dir, ".update_test_permission")
        try:
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write("test")
            os.remove(test_file)
        except PermissionError:
            QMessageBox.warning(
                self.parent_widget,
                "Update Available (Admin Required)",
                f"Version {version} is available!\n\n"
                f"However, SilverSpoon is located in a protected folder:\n{current_exe_dir}\n\n"
                "Please run SilverSpoon as Administrator to update automatically, or move it to a normal folder like Downloads or Desktop."
            )
            return
        except Exception:
            pass

        dialog = QDialog(self.parent_widget)
        dialog.setWindowTitle(f"Update Available: {version}")
        dialog.setMinimumWidth(500)

        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"<b>A new version ({version}) is available!</b>"))

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setMarkdown(changelog)
        layout.addWidget(text_edit)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No)
        yes_button = btn_box.button(QDialogButtonBox.StandardButton.Yes)
        if yes_button:
            yes_button.setText("Download and Restart")
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout.addWidget(btn_box)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.execute_update(download_url)

    def execute_update(self, download_url: str):
        """Downloads, unpacks, replaces executable, and launches restart script."""
        dl_dialog = UpdateDownloaderDialog(download_url, self.parent_widget)
        if dl_dialog.exec() == QDialog.DialogCode.Accepted:
            zip_path = dl_dialog.temp_zip
            try:
                extract_dir, new_exe_path = extract_and_verify_update(zip_path)
                current_exe = sys.executable
                current_exe_name = os.path.basename(current_exe)

                if not current_exe_name.lower().startswith("silverspoon"):
                    msg_box = QMessageBox(self.parent_widget)
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
                        clipboard = QApplication.clipboard()
                        if clipboard:
                            clipboard.setText(extract_dir)
                        QMessageBox.information(self.parent_widget, "Copied", "Directory path copied to clipboard.")
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
                    self.parent_widget,
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

                # Persist tasks history and settings before restarting
                tasks = self._get_tasks()
                settings = self._get_settings()
                if tasks is not None:
                    save_history(tasks)
                if settings is not None:
                    save_settings(settings)

                launch_restart_script(current_exe, old_exe_path, cleanup_marker)

                QApplication.quit()
                sys.exit(0)

            except Exception as e:
                logger.error(f"Update failure: {e}", exc_info=True)
                QMessageBox.critical(self.parent_widget, "Update Failed", f"Failed to apply the update:\n{str(e)}")

    def _get_settings(self):
        if self.get_settings_callback:
            return self.get_settings_callback()
        return load_settings()

    def _get_tasks(self):
        if self.get_tasks_callback:
            return self.get_tasks_callback()
        return []
