# SilverSpoon Reforged (previously FitGirlDownloader)

> **Acknowledgments:** This project is a heavily refactored and enhanced fork of the original [SilverSpoon](https://github.com/billysams21/SilverSpoon) by [billysams21](https://github.com/billysams21).

> **Note:** Currently, this tool ONLY supports `fuckingfast.co` links (often used by FitGirl Repacks). Support for other hosts may be added in the future.

A Python-based bulk downloader designed to bypass Cloudflare protections on file-hosting sites like *fuckingfast.co*. It automates the process of extracting direct download links and supports concurrent downloading with pause and resume capabilities.

## Features

* **Auto Web Scraper:** Don't want to copy links manually? Paste a website URL (like a FitGirl repacks page) and SilverSpoon will automatically scan the raw HTML and extract all `fuckingfast.co` links for you!
* **Global Rate Limiting & Throttling:** Features a powerful thread-safe token bucket rate limiter to cap your global download speeds without stalling active connections.
* **Real-Time Speed Graph:** Includes a custom-painted `SpeedGraphWidget` rendering your historical network bandwidth curves with smooth gradients and peak tracking.
* **System Tray & Notifications:** Keep SilverSpoon running in the background with a system tray icon and receive desktop notifications when your batches finish downloading or extracting.
* **Auto-Updater:** (Windows only) Automatically checks for, downloads, and applies new updates so you are always on the latest version without manual `.zip` downloads.
* **Cross-Platform Extraction:** Built-in auto-extraction support for Windows (bundled `7z`), as well as Linux and macOS (via `/usr/bin/7z` / `p7zip`).
* **Cloudflare Bypass:** Uses `cloudscraper` to mimic a real browser and bypass anti-bot challenges.
* **Persistent Download History:** Automatically saves your task queue, progress, and folder groupings across sessions. Close the app anytime without losing your place!
* **Grouped Batch Folders:** Downloads are neatly organized into collapsible dropdown trees, showing aggregated progress, speed, and ETA for entire batches.
* **Smart Folder Grouping & Batching:** Automatically suggests a unified folder name for a batch of links, perfectly grouping main game parts and messy optional files together.
* **Persistent Settings:** Your preferences (save directory, concurrent workers, extraction options) are saved and remembered for your next session.
* **Import Links & Clipboard:** Easily load bulk link lists from `.txt` files directly via the File menu, or use the "Paste from Clipboard" button for styled-free pasting.
* **Live Speed & ETAs:** Features a real-time global download speed tracker and Calculates Estimated Time Remaining (ETA) for both individual files and total batch completions.
* **Customizable UI & Shortcuts:** Interactive, resizable columns that save their state, plus right-click context menus and handy keyboard shortcuts (e.g., `Space` to pause/resume, `Delete` to remove tasks).
* **File Management:** Safely delete tasks and optionally remove their associated physical files from your disk, or use "Force Redownload" to wipe and restart a corrupted file.
* **Error Diagnostics:** Hover over failed tasks for detailed tooltips, and easily copy error logs for quick troubleshooting.
* **Direct Link Extraction:** Automatically simulates the internal HTMX POST requests and scrapes raw HTML to fetch the real `.rar` direct links.
* **Multi-threading:** Downloads multiple parts concurrently (default 3 workers, customizable in Settings) to maximize bandwidth.
* **Pause, Resume & Retry:** Safely pause your downloads, recover from network drops, or quickly retry errored links using HTTP `Range` headers.
* **Graphical Interface:** Includes a clean, modern GUI built with PyQt6.
* **Command Line Interface:** Also includes a lightweight CLI script for server environments or automation.

## Requirements

* Python 3.10+
* Dependencies listed in `requirements.txt`

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
2. Open the game link and click the provider you want to use (for now it's FuckingFast).
![FitGirl 1](assets/fitgirl1.png)
3. Copy the links you want to download.
![FitGirl 2](assets/fitgirl2.png)
4. Paste your `fuckingfast.co` links into the top text box (one per line) or use `File -> Import Links from File...`.
![App Screenshot 2](assets/screenshot2.png)
5. Click **Add Links to Queue**. A prompt will appear allowing you to confirm the Batch Folder name so all main and optional files go to the exact same place.
6. Click **Select All** (or check individual boxes) for the files you want to download.
7. (Optional) Check the **Extract after download** checkbox if you want files extracted automatically using the built-in 7-Zip engine.
8. Click the green **Start / Resume** button to begin downloading.
![App Screenshot 3](assets/screenshot3.png)
9. Use the **Pause** and **Start / Resume** buttons to manage your selected downloads at any time.

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
  * `core/extractors/` - Provider-specific link scrapers (e.g., FuckingFast).
* `ui/` - PyQt6 user interface components, main window, dialogs, and custom widgets (e.g., speed graph).
* `utils/` - Helper functions for byte size formatting, unit conversions, and text utilities.
* `assets/` - Documentation screenshots and icon resources.
* `.github/` - GitHub Actions workflows for automated versioning and release publishing.


## Contributing

We welcome contributions! If you'd like to help improve SilverSpoon, please see our [Contributing Guide](CONTRIBUTING.md) for instructions on how to set up your environment, follow our branching strategy (`dev` branch), and submit Pull Requests.


## Changelog

Detailed release notes and history of changes can be found in the [CHANGELOG.md](CHANGELOG.md) file.

## Disclaimer

This tool is provided for educational and automation purposes only. The author is not responsible for the content downloaded using this tool. Please respect the terms of service of the file-hosting providers.
