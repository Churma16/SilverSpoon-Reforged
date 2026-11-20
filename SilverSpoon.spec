# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

# Automatically locate 7z.exe and 7z.dll from local directory or standard installation path
missing_binaries = []
binaries = []
for binary_filename in ['7z.exe', '7z.dll']:
    found_path = None
    for candidate_path in [
        binary_filename,
        os.path.join(r'C:\Program Files\7-Zip', binary_filename),
        os.path.join(r'C:\Program Files (x86)\7-Zip', binary_filename),
    ]:
        if os.path.exists(candidate_path):
            found_path = candidate_path
            break
    if found_path:
        binaries.append((found_path, '.'))
    else:
        missing_binaries.append(binary_filename)

if missing_binaries:
    raise SystemExit(
        f"[ERROR] Required 7-Zip binaries missing from build environment: {', '.join(missing_binaries)}. "
        f"Please install 7-Zip or place 7z.exe and 7z.dll in the project root."
    )

data_files = [
    ('SilverSpoon.ico', '.'),
    ('SilverSpoon.png', '.'),
    ('VERSION', '.')
]

a = Analysis(
    ['pyqt_downloader.py'],
    pathex=[],
    binaries=binaries,
    datas=data_files,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SilverSpoon',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['SilverSpoon.ico'],
)
