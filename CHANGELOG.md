# Changelog

All notable changes to this project will be documented in this file. See [commit-and-tag-version](https://github.com/absolute-version/commit-and-tag-version) for commit guidelines.

## [1.7.1](https://github.com/Churma16/SilverSpoon-Reforged/compare/v1.7.0...v1.7.1) (2026-07-31)
## [1.7.0](https://github.com/Churma16/SilverSpoon-Reforged/compare/v1.6.0...v1.7.0) (2026-07-30)

### Features

* **updater:** add optional SHA-256 integrity verification step before extracting update archives ([3ec54a1](https://github.com/Churma16/SilverSpoon-Reforged/commit/3ec54a15cff130236332f635cb450c40ab4e7241))

### Bug Fixes

* **core:** safely decode raw binary response previews during 403/503 error logging ([e2653e8](https://github.com/Churma16/SilverSpoon-Reforged/commit/e2653e8ee76758f1299827a611c2b07d776b7f5b))
* **core:** sanitize raw filenames and folder paths with os.path.basename to prevent directory traversal ([ca25cb4](https://github.com/Churma16/SilverSpoon-Reforged/commit/ca25cb4b326030ada6fffd9f7b648ab3f25515f7))
* **extraction:** expand Windows 7-Zip executable lookup to include Program Files (x86) and PATH ([50a929b](https://github.com/Churma16/SilverSpoon-Reforged/commit/50a929b57020d08a03ec33d6d721424f6f3b919b))
* **updater:** add Zip Slip path traversal guard and sanitize batch script paths ([7621924](https://github.com/Churma16/SilverSpoon-Reforged/commit/762192481a15abc203eda67f18523782cd775075))
## [1.6.0](https://github.com/Churma16/SilverSpoon-Reforged/compare/v1.5.0...v1.6.0) (2026-07-30)

### Features

* **core:** add DownloadManager and ExtractionManager classes ([988ccb0](https://github.com/Churma16/SilverSpoon-Reforged/commit/988ccb0b35f846a2fd4cd8d415c8eaf802c411f8))
* **core:** dynamically load version string from VERSION file and update repository target ([672c805](https://github.com/Churma16/SilverSpoon-Reforged/commit/672c805f2869a58938e49c5ddc2bd80f34db0090))
* **ui:** add auto-shutdown on completion feature with 60s countdown timer ([b7121e8](https://github.com/Churma16/SilverSpoon-Reforged/commit/b7121e8e4f2335982f46142e020d9a095c81e205))
* **ui:** add list marker sanitization, re-extraction action, and redownload confirmation dialog ([0e59dc5](https://github.com/Churma16/SilverSpoon-Reforged/commit/0e59dc5b32194ca8c6acdb29e0e2e5d70fb88f12))

### Bug Fixes

* **ui:** restore missing summary popup message box in force_redownload_selected ([9084e62](https://github.com/Churma16/SilverSpoon-Reforged/commit/9084e62a973d56cf470311c3bae0226cda7c4ce6))
## [1.5.0](https://github.com/Churma16/SilverSpoon-Reforged/compare/v1.4.2...v1.5.0) (2026-07-30)

### Features

* **core:** add status color mapping property to TaskStatus and BatchStatus enums ([67f8be4](https://github.com/Churma16/SilverSpoon-Reforged/commit/67f8be4bea4e6d1d2864041fccf8a46883010d60))
* **ui:** add ChangelogDialog to render CHANGELOG.md file dynamically ([d18ff36](https://github.com/Churma16/SilverSpoon-Reforged/commit/d18ff36d549cee54415c27b310c4b443d14a9ce6))
* **ui:** add session stats widget and tree drag-and-drop reordering widget ([4edc7f1](https://github.com/Churma16/SilverSpoon-Reforged/commit/4edc7f1c48e107c33c4b9c6046cf460d995a05a1))
* **ui:** integrate drag-drop task reordering and session statistics tracking in MainWindow ([506d468](https://github.com/Churma16/SilverSpoon-Reforged/commit/506d4680a429d05d96303b4814c4525cd27972fc))
* **ui:** render dynamic status colors in tree items and collapse batch folders by default ([830e169](https://github.com/Churma16/SilverSpoon-Reforged/commit/830e1699f626ec77db195452dc1b1abda7117305))
## [1.4.2](https://github.com/Churma16/SilverSpoon-Reforged/compare/v1.4.1...v1.4.2) (2026-07-30)
## [1.4.1](https://github.com/Churma16/SilverSpoon-Reforged/compare/v1.4.0...v1.4.1) (2026-07-30)
## 1.4.0 (2026-07-30)


### Features

* add Linux/macOS extraction support ([af49e29](https://github.com/Churma16/SilverSpoon-Reforged/commit/af49e29d6d510ad96e0b21a17356268604bfa1a3))
* add status codes ([1de8f90](https://github.com/Churma16/SilverSpoon-Reforged/commit/1de8f902fca7fbf419d5134ef8f2fb134aa27336))
* **core:** add TaskStatus enum and type definitions ([49ce690](https://github.com/Churma16/SilverSpoon-Reforged/commit/49ce690640b97eb95790f78b5c8a12e6db3f73c4))
* **downloader:** add download speed limit setting and throttling mechanism ([98456d2](https://github.com/Churma16/SilverSpoon-Reforged/commit/98456d2cd439c3f5fa6b41b01fbecb804bf9a68f))
* **downloader:** add web page scraping and raw HTML parsing for links ([ac25a2f](https://github.com/Churma16/SilverSpoon-Reforged/commit/ac25a2fd93310cd014fa7c1f6d214193304cea3d))
* **downloader:** implement thread-safe global token bucket rate limiter ([efecee0](https://github.com/Churma16/SilverSpoon-Reforged/commit/efecee0c0d55cedd46709caf54c9b0bf3c5f0fda))
* **downloader:** integrate global rate limiter into GUI download workers ([66486aa](https://github.com/Churma16/SilverSpoon-Reforged/commit/66486aafc8420dfb00ba5c2f204508c95bc5ae91))
* force redownload, context menu, copy log, error hover, keyboard shortcuts ([da43f6c](https://github.com/Churma16/SilverSpoon-Reforged/commit/da43f6c2fe16770392b05555b769bdfa87899893))
* implement auto-updater for Windows executable ([87a584b](https://github.com/Churma16/SilverSpoon-Reforged/commit/87a584b6dd4822fb4cc1aa1ba20a0678a85b344e))
* linux extraction support using p7zip ([d44b68e](https://github.com/Churma16/SilverSpoon-Reforged/commit/d44b68eecd7b98cdaeb58f10df286efe94733784))
* **ui:** add real-time download speed graph widget ([a5f25c8](https://github.com/Churma16/SilverSpoon-Reforged/commit/a5f25c8a3b2bd7921e584743feefb2fc78415d30))
* **ui:** add system tray integration and desktop notifications ([7710980](https://github.com/Churma16/SilverSpoon-Reforged/commit/7710980fe506c8ed3fe1be311c0a6d50ab929dab))
* **ui:** add total queue ETA calculation and estimated batch size calculation ([fcbdaf1](https://github.com/Churma16/SilverSpoon-Reforged/commit/fcbdaf1efeafe9b59aab8e49f5e189929dd9f8fa))
* welcome/warning dialogue, path fixes, reset settings button ([1bbb2e6](https://github.com/Churma16/SilverSpoon-Reforged/commit/1bbb2e69c7db6d07a39fce6e9d756da01b911892))


### Bug Fixes

* code cleaning ([8a701d3](https://github.com/Churma16/SilverSpoon-Reforged/commit/8a701d3b8b73596b059ada9b55c1b711223f1d5e))
* **downloader:** dynamically evaluate speed limit settings during chunk iterations ([6ecb83d](https://github.com/Churma16/SilverSpoon-Reforged/commit/6ecb83d5a4931317e5e73c932c8c0ef258fbc5f9))

# Changelog

All notable changes to this project will be documented in this file.

## [v1.3.0] - 2026-07-17

### New Features
* **Auto-Updater**: Implemented a built-in automatic updater for Windows executables that seamlessly downloads, replaces the binary, and restarts the application.
* **VPN Warning Dialog**: Added a welcome dialog to warn users about aggressive Cloudflare blocking of known VPN IPs, which can cause persistent download failures.
* **Smart Default Save Directory**: The default save location now automatically detects and falls back to the user's "Downloads" folder on Windows (or the current directory otherwise).
* **Reset Settings**: Added a "Reset Defaults" button in the Settings menu to easily revert all configurations (including UI sizes and warning dialog visibility) to their factory defaults.
* **Spacebar Toggle**: You can now conveniently toggle pause and resume for selected downloads using the `Space` key.

### Fixes & Improvements
* **Directory Creation Stability**: Improved error handling when creating save directories during downloads, preventing crashes if the path is invalid or restricted.

## [v1.2.1] - 2026-07-16

### New Features
* **Cross-Platform Extraction**: Added extraction support for Linux and macOS (`/usr/bin/7z` / `p7zip`) alongside Windows (`7-Zip`/`WinRAR`).
* **Context Menu & Keyboard Shortcuts**: Added a right-click context menu to the download table and handy keyboard shortcuts for starting (`S`), pausing (`P`), cancelling (`C`), retrying (`R`), redownloading (`F`), and deleting (`Delete`/`Backspace`) tasks.
* **Force Redownload**: Added a "Force Redownload" button/action to easily delete an existing downloaded file and restart the task from scratch.
* **Error Diagnostics & Logging**: Added descriptive hover tooltips (`HTTP status codes`, timeouts, disconnection reasons) on errored tasks, background error logging (`~/.silverspoon.log`), and a dedicated "Copy Error Details" button for easy troubleshooting.
* **License**: Added the `GNU General Public License v3.0` (`GPLv3`).

## [v1.2.0] - 2026-07-15

### New Features
* **Persistent Download History**: Automatically saves and restores your task queue, progress, and folder groupings across sessions.
* **Grouped Batch Folders**: Replaced the flat table with a collapsible tree view. Downloads are automatically grouped by batch, showing aggregated progress, speed, and ETA for the entire folder.
* **Live Speed & ETAs**: Added a real-time global download speed tracker and estimated time remaining (ETA) for individual files and entire batches.
* **Customizable UI**: Interactive, resizable columns that save their state so your layout is preserved across app restarts.
* **Paste from Clipboard**: Added a dedicated button to paste links safely as unstyled plain text.
* **Task & File Deletion**: Added a "Delete" button and keyboard shortcut support (`Delete`/`Backspace`) to remove tasks, complete with an option to permanently delete associated physical downloaded files.
* **Retry Action**: Added a dedicated "Retry Error" button to quickly restart failed downloads.

### Changes
* **Improved Selection Logic**: Added `Shift/Ctrl+Click` highlighting support and visually moved the selection column to the far left.
* **Extractor Thread Safety**: Fixed race conditions that could cause extraction threads to overlap when multiple batches finish or are loaded from history.
* **UI Polish**: Removed dotted focus boxes when clicking cells for a cleaner, modern look.


## [v1.1.0] - 2026-07-05

### New Features
* **Top Menu Bar**: Added a new top menu bar for easier navigation and quick access to tools.
* **Persistent Settings**: Added a Settings page (`File -> Settings`) with persistent configurations for your Base Save Directory, Max Concurrent Downloads, and Auto-extract preference.
* **Import Links**: You can now import links directly from `.txt` files via the File menu.
* **Batch Folder Prompt**: Automatically groups multi-part archives and optional files into the exact same folder when adding links, keeping your downloads perfectly organized.
* **Help Menu**: Added a Help menu containing quick links to the GitHub Repository, Contact Us (Issues), a Contributing Guide, and an About page.

### Changes
* **Action Buttons**: Consolidated 'Start' and 'Resume' into a single, smarter action button for a cleaner interface.