# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

# Automatically locate 7z.exe and 7z.dll from local directory or standard installation path
binaries = []
for binary_filename in ['7z.exe', '7z.dll']:
    if os.path.exists(binary_filename):
        binaries.append((binary_filename, '.'))
    else:
        system_7z_path = os.path.join(r'C:\Program Files\7-Zip', binary_filename)
        if os.path.exists(system_7z_path):
            binaries.append((system_7z_path, '.'))
        else:
            system_7z_x86_path = os.path.join(r'C:\Program Files (x86)\7-Zip', binary_filename)
            if os.path.exists(system_7z_x86_path):
                binaries.append((system_7z_x86_path, '.'))

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
