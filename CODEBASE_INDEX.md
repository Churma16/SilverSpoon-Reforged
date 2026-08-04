# SilverSpoon Reforged - Codebase Index & Architecture Overview

## 1. What is this project?
SilverSpoon Reforged is a Python-based bulk downloader application designed for link extraction and multi-threaded stream downloads from supported file-hosting services. 

*This project is a heavily refactored and enhanced fork of the original [SilverSpoon](https://github.com/billysams21/SilverSpoon) project created by billysams21.*

It supports multi-threaded download management, automatic extraction via 7-Zip, persistent task queues, grouped batch folders, rate limiting, system tray notifications, real-time bandwidth visualization, drag-and-drop queue reordering, auto-shutdown on completion, and automated application updating.

---

## File Map & Module Hierarchy

| File / Folder Path | Module / Role | Primary Responsibilities |
|---|---|---|
| [pyqt_downloader.py](file:///d:/Document/Coding/POS_Furnitur/App/SilverSpoon/pyqt_downloader.py) | GUI Entry Point | Application startup script, old EXE cleanup handling, splash screen display (`QSplashScreen`), and `QApplication` event loop initialization. |
| [downloader.py](file:///d:/Document/Coding/POS_Furnitur/App/SilverSpoon/downloader.py) | CLI Application | Standalone command-line runner featuring `DownloadManager` and `GlobalRateLimiter` for headless environments. |
| [update_logic.py](file:///d:/Document/Coding/POS_Furnitur/App/SilverSpoon/update_logic.py) | Auto-Updater Subsystem | Background update checker thread (`UpdateCheckerThread`), release extraction (`extract_and_verify_update`), EXE replacement (`perform_exe_replacement`), and restart trampoline script (`launch_restart_script`). |
| [core/](file:///d:/Document/Coding/POS_Furnitur/App/SilverSpoon/core/) | Core Logic Package | Business logic for download task models, thread managers, history management, rate limiting, enums, and persistent settings. |
| ├── [core/download_task.py](file:///d:/Document/Coding/POS_Furnitur/App/SilverSpoon/core/download_task.py) | Task Model | `DownloadTask` class encapsulating link, status, byte progress, save directory, tree item binding, and serialization. |
| ├── [core/download_manager.py](file:///d:/Document/Coding/POS_Furnitur/App/SilverSpoon/core/download_manager.py) | Download Orchestrator | `DownloadManager` thread managing worker spawning, active download concurrency, and worker byte streaming. |
| ├── [core/extraction_manager.py](file:///d:/Document/Coding/POS_Furnitur/App/SilverSpoon/core/extraction_manager.py) | Extraction Orchestrator | `ExtractionManager` managing auto-extraction routines, 7z/WinRAR subprocess invocation, and manual re-extraction. |
| ├── [core/rate_limiter.py](file:///d:/Document/Coding/POS_Furnitur/App/SilverSpoon/core/rate_limiter.py) | Bandwidth Limiter | `GlobalRateLimiter` implementing a token-bucket algorithm for global download speed capping. |
| ├── [core/settings.py](file:///d:/Document/Coding/POS_Furnitur/App/SilverSpoon/core/settings.py) | Settings Manager | Configuration I/O helper functions for loading/saving `settings.json`. |
| ├── [core/history.py](file:///d:/Document/Coding/POS_Furnitur/App/SilverSpoon/core/history.py) | History & Queue Persistence | Serialization functions for saving and restoring task states in `queue_state.json`. |
| ├── [core/types.py](file:///d:/Document/Coding/POS_Furnitur/App/SilverSpoon/core/types.py) | Enums & Color Types | `TaskStatus` and `BatchStatus` enums defining status strings and UI display colors. |
| └── [core/extractors/](file:///d:/Document/Coding/POS_Furnitur/App/SilverSpoon/core/extractors/) | Extractor Modules | Host-specific direct link extractors. |
| &nbsp;&nbsp;&nbsp;&nbsp;├── [core/extractors/base.py](file:///d:/Document/Coding/POS_Furnitur/App/SilverSpoon/core/extractors/base.py) | Base Extractor API | Abstract base class defining the link extraction contract. |
| &nbsp;&nbsp;&nbsp;&nbsp;└── [core/extractors/fuckingfast.py](file:///d:/Document/Coding/POS_Furnitur/App/SilverSpoon/core/extractors/fuckingfast.py) | FuckingFast Provider | Simulates HTMX POST requests to resolve direct download links from `fuckingfast.co`. |
| [ui/](file:///d:/Document/Coding/POS_Furnitur/App/SilverSpoon/ui/) | User Interface Package | PyQt6 graphical components, dialogs, custom widgets, and window management. |
| ├── [ui/main_window.py](file:///d:/Document/Coding/POS_Furnitur/App/SilverSpoon/ui/main_window.py) | Main Window Controller | `MainWindow` (`QMainWindow`) orchestrating task tree widgets, worker execution, system tray icon (`QSystemTrayIcon`), desktop notifications, menu bars, auto-shutdown timer, and settings sync. |
| ├── [ui/dialogs.py](file:///d:/Document/Coding/POS_Furnitur/App/SilverSpoon/ui/dialogs.py) | UI Dialogs | `SettingsDialog`, `WarningDialog`, `ChangelogDialog`, batch folder naming prompt, error details popup, and log viewers. |
| └── [ui/widgets.py](file:///d:/Document/Coding/POS_Furnitur/App/SilverSpoon/ui/widgets.py) | Custom Widgets | `SpeedGraphWidget` (bandwidth chart), `SessionStatsWidget` (live metrics bar), and `ReorderableTreeWidget` (drag-and-drop tree reordering). |
| [utils/](file:///d:/Document/Coding/POS_Furnitur/App/SilverSpoon/utils/) | Utilities Package | Shared helper functions and formatting routines. |
| └── [utils/formatters.py](file:///d:/Document/Coding/POS_Furnitur/App/SilverSpoon/utils/formatters.py) | Data Formatters | Helpers for human-readable byte sizes, speed indicators, and ETA formatting. |
| [build_exe.bat](file:///d:/Document/Coding/POS_Furnitur/App/SilverSpoon/build_exe.bat) | Build Script | PyInstaller script packaging application logic, icons, and 7-Zip binaries into a standalone executable. |
| [requirements.txt](file:///d:/Document/Coding/POS_Furnitur/App/SilverSpoon/requirements.txt) | Dependencies | Core runtime Python packages (`cloudscraper`, `PyQt6`). |
| `7z.exe` / `7z.dll` | External Binaries | Bundled 7-Zip engine used for automatic archive extraction on Windows. |

---

## Core Classes & Architecture Details

### 1. GUI Subsystem (`ui/` & `pyqt_downloader.py`)
- **`MainWindow`** (`QMainWindow` in `ui/main_window.py`):
  - Primary UI controller managing layout, menu actions, settings dialog, task queue, system tray icon (`QSystemTrayIcon`), desktop notifications, and application life cycle.
  - Implements `ReorderableTreeWidget` views with drag-and-drop reordering, status color styling, list marker stripping on paste, and auto-shutdown options.
- **`ReorderableTreeWidget`** (`QTreeWidget` in `ui/widgets.py`):
  - Custom tree widget supporting internal drag-and-drop reordering for tasks and batch folders with structure normalization.
- **`SpeedGraphWidget`** (`QWidget` in `ui/widgets.py`):
  - Custom-painted bandwidth graph widget (`QPainter`) rendering historical network speed curves with smooth gradients and peak speed tracking.
- **`SessionStatsWidget`** (`QFrame` in `ui/widgets.py`):
  - Styled card widget rendering live session download totals, active task count, completed task count, and error count.
- **`ChangelogDialog`** (`QDialog` in `ui/dialogs.py`):
  - Markdown viewer dialog displaying full `CHANGELOG.md` contents directly in the app.

### 2. Core Business Logic (`core/`)
- **`DownloadManager`** (`core/download_manager.py`):
  - Manages active download threads, worker assignment, byte streaming, and rate limiting integration.
- **`ExtractionManager`** (`core/extraction_manager.py`):
  - Manages background archive extraction threads, multi-part volume detection, 7z/WinRAR process launching, and manual re-extraction.
- **`DownloadTask`** (`core/download_task.py`):
  - Data model tracking URL, target filepath, batch folder name, status (`Queued`, `Downloading`, `Paused`, `Completed`, `Error`), byte progress, and tree widget reference.
- **`GlobalRateLimiter`** (`core/rate_limiter.py`):
  - Token-bucket algorithm enforcing bandwidth caps across concurrent download threads.
- **`FuckingFastExtractor`** (`core/extractors/fuckingfast.py`):
  - Cloudflare-bypassing link resolver using `cloudscraper` and HTMX header simulation (`HX-Request`, `HX-Target`, `Hx-Redirect`).

### 3. CLI Subsystem (`downloader.py`)
- **`DownloadManager`**:
  - Orchestrates link reading, direct URL extraction, and parallel downloads via `concurrent.futures.ThreadPoolExecutor`.

### 4. Update Subsystem (`update_logic.py`)
- **`version_key(version)` & `is_newer_version(latest, current)`**:
  - Semantic version parser handling major, minor, patch, and pre-release suffix comparisons.
- **`UpdateCheckerThread`** (`QThread`):
  - Asynchronously checks GitHub Releases API (`api.github.com/repos/{repo}/releases/latest`) with daily throttling checks.
- **`UpdateDownloaderDialog`** (`QDialog`):
  - Modal progress bar dialog managing release asset downloading in a background thread.
- **`extract_and_verify_update`, `perform_exe_replacement`, `launch_restart_script`**:
  - Modular update utilities for extracting release zips, performing executable replacement, and executing PyInstaller restart trampoline scripts.

---

## Data & Configuration Structures

- **`queue_state.json`**:
  - Saved task queue state containing batch folder hierarchies, download progress, status, byte counts, and save locations across application restarts.
- **`settings.json`**:
  - Application preferences including base download directory, max concurrent workers, auto-extract settings, auto-shutdown settings, rate limit caps, and `last_update_check` timestamp.
- **`~/.silverspoon.log`**:
  - Runtime exception and error log file generated by `logging.basicConfig`.

---

## Key Workflows

1. **Direct Link Extraction**:
   `Link` -> `FuckingFastExtractor` -> `GET Page (cloudscraper)` -> `POST /f/{id}/go` -> `Read Hx-Redirect Header` -> `Direct URL`.
2. **Download & Resuming**:
   `Direct URL` -> `HEAD Request (Content-Length)` -> `Check local file` -> `Apply HTTP Range header (bytes=N-)` -> `Stream chunks via RateLimiter`.
3. **Auto-Extraction**:
   `Task Downloaded` -> `ExtractionManager` -> `Check Auto-Extract Option` -> `Spawn Subprocess` -> `Execute 7z` -> `Update Status`.
4. **Bandwidth & Session Visualization**:
   `Download Workers Speed` -> `Aggregate Global MB/s` -> `SpeedGraphWidget.add_data_point()` -> `SessionStatsWidget.update_stats()`.
5. **Drag & Drop Task Reordering**:
   `User Drags Task/Batch` -> `ReorderableTreeWidget.dropEvent` -> `normalize_structure()` -> `sync_tasks_order_from_tree()` -> `Save Queue History`.
