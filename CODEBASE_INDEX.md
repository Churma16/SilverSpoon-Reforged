# SilverSpoon - Codebase Index & Architecture Overview

## Overview
SilverSpoon (formerly FitGirlDownloader) is a Python-based bulk downloader application designed to bypass Cloudflare anti-bot protections on file-hosting services (primarily `fuckingfast.co`). It supports multi-threaded download management, automatic extraction via 7-Zip, persistent task queues, grouped batch folders, rate limiting, and automated application updating.

---

## File Map & Module Hierarchy

| File / Resource | Module / Role | Primary Responsibilities |
|---|---|---|
| `pyqt_downloader.py` | PyQt6 GUI Application | Main graphical user interface, task tree rendering, context menus, download worker management, automatic archive extraction, settings & queue state persistence. |
| `downloader.py` | CLI Application | Command-line download runner featuring `GlobalRateLimiter` and `DownloadManager` for headless or server environments. |
| `update_logic.py` | Auto-Updater Subsystem | Background update checker thread (`UpdateCheckerThread`), version comparison, and release asset downloader dialog (`UpdateDownloaderDialog`). |
| `build_exe.bat` | Build Script | PyInstaller packaging script bundling application logic, icon, and 7-Zip binaries into a standalone Windows executable. |
| `requirements.txt` | Dependency File | Defines core runtime dependencies (`cloudscraper`, `PyQt6`). |
| `7z.exe` / `7z.dll` | External Binaries | Bundled Windows 7-Zip executable and dynamic library used for auto-extracting archives. |

---

## Core Classes & Architecture Details

### 1. GUI Subsystem (`pyqt_downloader.py`)
- **`MainWindow`** (`QMainWindow`):
  - Primary UI controller managing layout, menu actions, settings dialog, task queue, system tray icon (`QSystemTrayIcon`), desktop notifications, and application life cycle.
  - Implements tree widget views with parent batch nodes and child task items.
  - Controls threading via `QThreadPool` and worker instances.
- **`SpeedGraphWidget`** (`QWidget`):
  - Real-time custom-painted bandwidth chart (`QPainter`) rendering network traffic history with smooth gradients and peak speed tracking.
- **`DownloadWorker`** (`QRunnable`, `QObject`):
  - Handles individual file download streams using `cloudscraper`.
  - Performs direct link extraction by executing HTMX POST request simulation (`/f/{id}/go`).
  - Supports HTTP Range headers for resuming partial downloads.
- **`ExtractWorker`** (`QRunnable`, `QObject`):
  - Invokes 7-Zip binary (`7z.exe` on Windows or system `/usr/bin/7z`) to extract `.rar` / `.7z` / `.zip` archives.
- **`GlobalRateLimiter`**:
  - Token-bucket algorithm enforcing bandwidth caps across concurrent download threads.

### 2. CLI Subsystem (`downloader.py`)
- **`DownloadManager`**:
  - Orchestrates batch link reading from text files, direct URL resolution via `cloudscraper`, and multi-threaded file downloading via `concurrent.futures.ThreadPoolExecutor`.
- **`GlobalRateLimiter`**:
  - CLI implementation of thread-safe token bucket rate limiting.

### 3. Update Subsystem (`update_logic.py`)
- **`version_key(version)` & `is_newer_version(latest, current)`**:
  - Semantic version parser handling major, minor, patch, and release suffix comparisons.
- **`UpdateCheckerThread`** (`QThread`):
  - Fetches GitHub releases API (`api.github.com/repos/{repo}/releases/latest`) to check for available updates while respecting daily check throttling.
- **`UpdateDownloaderDialog`** (`QDialog`):
  - Displays a modal progress bar while downloading the updated release package in a background thread.

---

## Data & Configuration Structures

- **`queue_state.json`**:
  - Automatically saved state containing task tree hierarchy, batch folder associations, file sizes, downloaded bytes, status (`Completed`, `Paused`, `Error`), and physical file paths.
- **`settings.json`**:
  - User configuration storing preferences such as default download folder, max concurrent workers, auto-extraction options, rate limiters, and `last_update_check` timestamp.

---

## Key Workflows

1. **Direct Link Extraction**:
   `Link` -> `Parse File ID` -> `GET Link Page` -> `POST /f/{id}/go (Hx-Request)` -> `Extract Hx-Redirect Header` -> `Direct Download URL`.
2. **Download & Resuming**:
   `Direct URL` -> `HEAD Request (Content-Length)` -> `Check local file size` -> `Set HTTP Range header if partial` -> `Stream chunks & pass through RateLimiter`.
3. **Auto-Extraction**:
   `Download Finished` -> `Check if Extract Enabled` -> `Locate 7z engine` -> `Execute extraction subprocess` -> `Clean up or report status`.
