# SilverSpoon Reforged

> **Acknowledgments:** This project is a heavily refactored and enhanced fork of the original [SilverSpoon](https://github.com/billysams21/SilverSpoon) by [billysams21](https://github.com/billysams21).

> **Note:** Currently, this tool only supports `fuckingfast.co` links. Support for additional file hosts may be added in future updates.

A Python-based bulk downloader designed for link extraction and multi-threaded file downloads from supported hosters. It automates the process of extracting direct download links and supports concurrent downloading with pause and resume capabilities.

## Features

### Fork-Exclusive Features & Improvements

* **SeleniumBase UC & Auto Turnstile Solver:** Integrated browser session automation using SeleniumBase Undetected ChromeDriver running in headless mode with automated Turnstile token solving and in-browser asynchronous link fetching.
* **Live Worker & Settings Sync:** Dynamic updating of max concurrent download workers and settings without needing to restart active tasks.
* **Smart Auto-Scaling Progress Units:** Progress metrics and file size columns automatically auto-scale between KB, MB, and GB for both individual files and batch totals.
* **Refined Task Lifecycle & Statuses:** Cleaner status transitions (`Solving Session...`, `Connecting...`, `Downloading`) and robust logger integration across core modules.
* **Auto Web Link Extractor:** Don't want to copy links manually? Paste a web page URL and SilverSpoon will automatically scan the raw HTML and extract supported host links for you!
* **Global Rate Limiting & Throttling:** Features a powerful thread-safe token bucket rate limiter to cap your global download speeds without stalling active connections.
* **Real-Time Bandwidth Graph:** Includes a custom-painted `SpeedGraphWidget` rendering historical network bandwidth curves with smooth gradients and peak tracking.
* **Session Metrics & Stats Bar:** Live `SessionStatsWidget` tracking total downloaded bytes, active downloads, completed tasks, and error counts.
* **Interactive Drag-and-Drop Reordering:** Custom `ReorderableTreeWidget` allowing interactive drag-and-drop reordering of tasks and batch folders.
* **System Tray & Desktop Notifications:** Keep SilverSpoon running in the background with system tray integration and desktop notifications when downloads or extractions complete.
* **In-App Changelog Viewer:** Built-in markdown viewer dialog (`ChangelogDialog`) to inspect release notes directly from the GUI.
* **Auto-Shutdown on Completion:** Option to automatically shut down or put the computer to sleep when all queue downloads finish.

### Base Original Features

* **Auto-Updater:** (Windows only) Automatically checks for, downloads, and applies new updates so you are always on the latest version without manual `.zip` downloads.
* **Cross-Platform Auto-Extraction:** Built-in auto-extraction support for Windows (via 7-Zip engine), as well as Linux and macOS (via `/usr/bin/7z` / `p7zip`).
* **Automated Session Management:** Uses `cloudscraper` and browser engines to manage network challenges and resolve direct download links.
* **Persistent Session History:** Automatically saves your task queue, progress, and folder groupings across sessions. Close the app anytime without losing your place!
* **Grouped Batch Folders:** Downloads are neatly organized into collapsible dropdown trees, showing aggregated progress, speed, and ETA for entire batches.
* **Smart Folder Grouping & Batching:** Automatically suggests a unified folder name for a batch of links, grouping related part files together.
* **Persistent Settings:** Your preferences (save directory, concurrent workers, extraction options) are saved and remembered for your next session.
* **Import Links & Clipboard:** Easily load bulk link lists from `.txt` files directly via the File menu, or use the "Paste from Clipboard" button for styled-free pasting.
* **Live Speed & ETAs:** Features a real-time global download speed tracker and calculates Estimated Time Remaining (ETA) for both individual files and total batch completions.
* **Customizable UI & Shortcuts:** Interactive, resizable columns that save their state, plus right-click context menus and handy keyboard shortcuts (e.g., `Space` to pause/resume, `Delete` to remove tasks).
* **File Management:** Safely delete tasks and optionally remove their associated physical files from your disk, or use "Force Redownload" to wipe and restart a corrupted file.
* **Error Diagnostics:** Hover over failed tasks for detailed tooltips, and easily copy error logs for quick troubleshooting.
* **Direct Link Extractor:** Automatically simulates internal HTMX POST requests and parses raw HTML to fetch direct links.
* **Multi-threading:** Downloads multiple parts concurrently (default 3 workers, customizable in Settings) to maximize bandwidth.
* **Pause, Resume & Retry:** Safely pause your downloads, recover from network drops, or quickly retry errored links using HTTP `Range` headers.
* **PyQt6 GUI & Headless CLI:** Clean graphical UI built with PyQt6 along with a lightweight CLI script (`downloader.py`) for headless automation.

## Requirements & Tech Stack

* **Language**: Python 3.10+ (Verified on Python 3.13)
* **GUI Framework**: PyQt6 (`>= 6.11.0`)
* **Session & Browser Automation**: `seleniumbase` (UC Mode) & `cloudscraper` (`>= 1.2.71`)
* **Extraction Engine**: 7-Zip engine (`7z.exe`/`7z.dll` on Windows, `/usr/bin/7z` on Unix)
* **Build Tool**: PyInstaller (for standalone `.exe` executable builds)
* **Verified Environment (This Fork)**: Windows 11 (tested and fully functional on host machine)

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/billysams21/SilverSpoon.git
   cd SilverSpoon
   ```
2. Install the required Python packages (or do it inside virtual environment):
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Using the GUI (Recommended)
Launch the graphical interface (or double-click `SilverSpoon.exe`):
```bash
python pyqt_downloader.py
```

![App Screenshot 1](assets/screenshot1.png)

1. Click **Browse...** to select your base save directory (or set a persistent default in `File -> Settings`).
2. Copy the links you want to download.
3. Paste your links into the top text box (one per line) or use `File -> Import Links from File...`.
![App Screenshot 2](assets/screenshot2.png)
4. Click **Add Links to Queue**. A prompt will appear allowing you to confirm the Batch Folder name so all main and optional files go to the exact same place.
5. Click **Select All** (or check individual boxes) for the files you want to download.
6. (Optional) Check the **Extract after download** checkbox if you want files extracted automatically using the built-in 7-Zip engine.
7. Click the green **Start / Resume** button to begin downloading.
![App Screenshot 3](assets/screenshot3.png)
8. Use the **Pause** and **Start / Resume** buttons to manage your selected downloads at any time.

### Using the CLI
If you prefer the command line:
1. Put your links into `link.txt` (one per line).
2. Run the script:
   ```bash
   python downloader.py link.txt
   ```
*(Files will be downloaded to the current working directory).*

## Project Structure

* `core/` - Core download management, thread-safe rate limiting, session history, and auto-extraction logic.
  * `core/extractors/` - Provider-specific link scrapers.
* `ui/` - PyQt6 user interface components, main window, dialogs, and custom widgets (e.g., speed graph).
* `utils/` - Helper functions for byte size formatting, unit conversions, and text utilities.
* `assets/` - Documentation screenshots and icon resources.
* `.github/` - GitHub Actions workflows for automated versioning and release publishing.


## Contributing

We welcome contributions! If you'd like to help improve SilverSpoon, please see our [Contributing Guide](CONTRIBUTING.md) for instructions on how to set up your environment, follow our branching strategy (`dev` branch), and submit Pull Requests.


## Changelog

Detailed release notes and history of changes can be found in the [CHANGELOG.md](CHANGELOG.md) file.

## Legal Disclaimer

This software is provided strictly for educational, research, and personal bandwidth management purposes. The developers do not host, index, store, or distribute any content or copyrighted files, and do not condone unauthorized copyright infringement. End-users are solely responsible for ensuring their usage complies with all applicable local laws, regulations, and third-party host terms of service.
