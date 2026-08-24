# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for LG TV Tools.

This spec file configures PyInstaller to build standalone executables
for the Flet-based LG TV Tools application across platforms.

Usage:
    pyinstaller lg-tv-tools.spec

The spec auto-detects the platform and adjusts settings accordingly.
"""

import sys
import os
from pathlib import Path

# Detect platform
IS_WINDOWS = sys.platform == 'win32'
IS_MACOS = sys.platform == 'darwin'
IS_LINUX = sys.platform.startswith('linux')

# Project paths
SPEC_DIR = Path(SPECPATH)
SRC_DIR = SPEC_DIR / 'src'
RESOURCES_DIR = SRC_DIR / 'lgtvtools' / 'resources'

# App metadata
APP_NAME = 'lg-tv-tools'
APP_VERSION = '0.3.0'
APP_BUNDLE_ID = 'com.lgtvtools.app'

# Entry point
ENTRY_POINT = str(SRC_DIR / 'lgtvtools' / 'flet_ui' / 'app.py')

# Data files to include
datas = []

# Include resources directory if it exists
if RESOURCES_DIR.exists():
    if IS_WINDOWS:
        datas.append((str(RESOURCES_DIR), 'lgtvtools/resources'))
    else:
        datas.append((str(RESOURCES_DIR), 'lgtvtools/resources'))

# Include vendored binaries (ffmpeg, etc.) if present
VENDOR_BIN_DIR = SPEC_DIR / 'vendor' / 'bin'
if VENDOR_BIN_DIR.exists():
    datas.append((str(VENDOR_BIN_DIR), 'vendor/bin'))

# Hidden imports that PyInstaller might miss
hiddenimports = [
    # Core modules
    'lgtvtools',
    'lgtvtools.core',
    'lgtvtools.core.models',
    'lgtvtools.core.runtime',
    'lgtvtools.core.discovery',
    'lgtvtools.core.discovery.ssdp',
    'lgtvtools.core.discovery.mdns',
    'lgtvtools.core.discovery.upnp',
    'lgtvtools.core.webos',
    'lgtvtools.core.webos.client',
    # Desktop modules
    'lgtvtools.desktop',
    'lgtvtools.desktop.actions',
    'lgtvtools.desktop.actions.launchers',
    'lgtvtools.desktop.actions.media_share',
    'lgtvtools.desktop.desktop_actions',
    # Flet UI modules
    'lgtvtools.flet_ui',
    'lgtvtools.flet_ui.app',
    'lgtvtools.flet_ui.state',
    'lgtvtools.flet_ui.theme',
    'lgtvtools.flet_ui.components',
    'lgtvtools.flet_ui.components.device_list',
    'lgtvtools.flet_ui.components.action_panel',
    'lgtvtools.flet_ui.components.remote_control',
    'lgtvtools.flet_ui.components.dialogs',
    'lgtvtools.flet_ui.views',
    'lgtvtools.flet_ui.views.main_view',
    # System modules
    'lgtvtools.system',
    'lgtvtools.system.paths',
    'lgtvtools.system.logging_config',
    'lgtvtools.system.platform',
    # Dependencies
    'flet',
    'flet.app',
    'websockets',
    'websockets.client',
    'asyncio',
    'ssl',
    'certifi',
    # Optional dependencies (may not be installed)
    'zeroconf',
    'netifaces',
]

# Excluded modules to reduce size
excludes = [
    # Test frameworks
    'pytest',
    'hypothesis',
    # Dev tools
    'mypy',
    'ruff',
    # Legacy Qt (not needed for Flet build)
    'PyQt6',
    'PyQt5',
    'PySide6',
    'PySide2',
    # Other unnecessary modules
    'tkinter',
    'matplotlib',
    'numpy',
    'pandas',
    'scipy',
]

# Analysis
a = Analysis(
    [ENTRY_POINT],
    pathex=[str(SRC_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

# Remove duplicate/unnecessary files
pyz = PYZ(a.pure)

# Platform-specific executable settings
if IS_MACOS:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=True,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    
    # Create macOS .app bundle
    app = BUNDLE(
        exe,
        name=f'{APP_NAME}.app',
        icon=None,  # Add icon path here if available
        bundle_identifier=APP_BUNDLE_ID,
        info_plist={
            'CFBundleName': 'LG TV Tools',
            'CFBundleDisplayName': 'LG TV Tools',
            'CFBundleVersion': APP_VERSION,
            'CFBundleShortVersionString': APP_VERSION,
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '10.15',
            'NSRequiresAquaSystemAppearance': False,  # Support dark mode
        },
    )

elif IS_WINDOWS:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=APP_NAME,
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
        icon=None,  # Add icon path here if available
    )

else:  # Linux
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=APP_NAME,
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
    )
