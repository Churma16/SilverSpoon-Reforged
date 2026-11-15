# SilverSpoon Reforged

> **Credits:** A heavily refactored and updated fork of [SilverSpoon](https://github.com/billysams21/SilverSpoon) by [billysams21](https://github.com/billysams21).
>
> **Supported Hosts:** Currently supports `fuckingfast.co`. More file hosts might come later.

A bulk downloader that grabs direct links and downloads multi-part files concurrently, with pause and resume support. Built to handle host verification and fast multi-threaded downloads without manual hassle.

## Features

> Some features listed below may look familiar.

### Fork-Exclusive Features & Improvements

* **SeleniumBase UC & Auto Turnstile Solver:** Solves Cloudflare Turnstile in the background to grab direct download links automatically.
* **Live Worker & Settings Sync:** Change max concurrent workers and app settings on the fly without stopping active tasks.
* **Smart Auto-Scaling Units:** Progress metrics and file sizes scale automatically across KB, MB, and GB for individual files and batch totals.
* **Clear Task Lifecycle & Statuses:** Clear status transitions (`Solving Session...`, `Connecting...`, `Downloading`) backed by clean logging.
* **Web Page Link Extractor:** Paste any webpage URL and SilverSpoon scans the HTML to extract supported host links for you.
* **Global Rate Limiting:** Cap overall download speeds to keep your internet connection usable while downloading.
* **Real-Time Bandwidth Graph:** Live speed graph showing current bandwidth and peak speeds.
* **Session Stats Bar:** Tracks total data downloaded, active jobs, and completed tasks at a glance.
* **Drag-and-Drop Queue Reordering:** Rearrange download tasks and batch folders directly in the list.
* **System Tray & Notifications:** Minimizes to the system tray and alerts you when downloads or extractions finish.
* **In-App Changelog Viewer:** View recent update notes right inside the app.
* **Auto-Shutdown:** Automatically shut down or sleep your computer once the entire queue finishes.

### Base Original Features

* **Auto-Updater (Windows):** Checks for and applies updates automatically without manual zip downloads.
* **Built-in Archive Extraction:** Unpacks multi-part archives automatically via 7-Zip (Windows) or `p7zip` (Linux/macOS).
* **Persistent Queue & History:** Saves task progress, queues, and folder trees across restarts so you never lose your place.
* **Batch Folder Grouping:** Groups related parts into collapsible folders with collective progress, speed, and ETA.
* **Saved Preferences:** Keeps your download directory, worker count, and extraction settings between runs.
* **Clipboard & TXT Import:** Paste link lists straight from your clipboard or load a `.txt` file via the menu.
* **Live Speed & ETAs:** Real-time speed calculations and time-remaining estimates per file and per batch.
* **Keyboard Shortcuts & Context Menus:** Resizable columns, right-click menus, and hotkeys (`Space` to pause/resume, `Delete` to remove).
* **File Management & Redownload:** Delete tasks with or without local files, or force-restart corrupted parts from scratch.
* **Hover Diagnostics:** Hover over failed tasks to see error details and copy logs in one click.
* **Multi-threaded Downloads:** Download multiple parts at once (default: 3 workers) with HTTP Range pause/resume support.
* **GUI and CLI:** Desktop UI in PyQt6, plus a standalone CLI script (`downloader.py`) for terminal setups.

## Requirements

* **Python**: 3.10 or newer (tested up to 3.13)
* **GUI**: PyQt6 (`>= 6.11.0`)
* **Automation**: `seleniumbase` (UC Mode) & `cloudscraper` (`>= 1.2.71`)
* **Archive Extraction**: 7-Zip (`7z.exe`/`7z.dll` on Windows, `/usr/bin/7z` / `p7zip` on Unix)
* **Build Tool**: PyInstaller (only needed if building `.exe` binaries)
* **Tested On**: Windows 11

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Churma16/SilverSpoon-Reforged.git
   cd SilverSpoon-Reforged
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Desktop GUI
Run the app:
```bash
python pyqt_downloader.py
```
*(Or launch `SilverSpoon.exe` directly if using the pre-built release).*

![App Screenshot 1](assets/screenshot1.png)

1. Pick a download directory with **Browse...** (or save a default under `File -> Settings`).
2. Paste links into the input box (one per line), or load a file via `File -> Import Links from File...`.
![App Screenshot 2](assets/screenshot2.png)
3. Click **Add Links to Queue** and confirm the batch folder name.
4. Select the files you want with **Select All** or check individual boxes.
5. (Optional) Check **Extract after download** to automatically unpack archives when they finish.
6. Hit the green **Start / Resume** button to begin downloading.
![App Screenshot 3](assets/screenshot3.png)
7. Pause, resume, or manage items whenever you need with the toolbar buttons.

### Command Line
For headless or terminal runs:
1. Put your URLs in `link.txt` (one per line).
2. Run:
   ```bash
   python downloader.py link.txt
   ```
*(Files download into the current working directory).*

## Project Structure

* `core/` - Download management, rate limiting, session persistence, and extractor logic.
  * `core/extractors/` - Host-specific extractors.
* `ui/` - PyQt6 interface, dialogs, and custom widgets (speed graph, trees).
* `utils/` - Size formatting, unit converters, and string helpers.
* `assets/` - Screenshots and icons.
* `.github/` - Workflows for releases, version tags, and health checks.

## Contributing

Pull requests are welcome. Check out [CONTRIBUTING.md](CONTRIBUTING.md) for branch rules (`dev` branch) and local setup before submitting changes.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for full release history and notes.

## Legal Disclaimer

This project is for educational, research, and personal bandwidth management only. The developers do not host, index, or distribute copyrighted content, and do not condone copyright infringement. You are responsible for following applicable laws and host terms of service.
