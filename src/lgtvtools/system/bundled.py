"""Bundled binary resolution for packaged builds.

When the app is distributed as a PyInstaller bundle, external tools like
ffmpeg can be shipped alongside the executable. This module provides a
unified lookup that checks the bundled location first, then falls back
to the system PATH.

Lookup order:
1. PyInstaller bundle directory (sys._MEIPASS / "vendor/bin")
2. Development vendor directory (<project_root>/vendor/bin)
3. System PATH (shutil.which)
"""

from __future__ import annotations

import shutil
import sys
from functools import lru_cache
from pathlib import Path


def _bundled_bin_dirs() -> list[Path]:
    """Return directories where bundled binaries may live, in priority order."""
    dirs: list[Path] = []

    # 1. PyInstaller one-file bundle extracts to sys._MEIPASS
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        dirs.append(Path(meipass) / "vendor" / "bin")

    # 2. Development: vendor/bin relative to project root
    #    (project_root/vendor/bin — useful for local dev testing)
    project_root = Path(__file__).resolve().parents[3]
    dirs.append(project_root / "vendor" / "bin")

    return dirs


@lru_cache(maxsize=32)
def which(command: str) -> str | None:
    """Locate a command binary, checking bundled locations first.

    This is a drop-in replacement for shutil.which() that also searches
    the app's bundled vendor directory.

    Args:
        command: The binary name to find (e.g. "ffmpeg", "vlc").

    Returns:
        Absolute path to the binary, or None if not found.
    """
    # On Windows, add .exe extension if not already present
    candidates = [command]
    if sys.platform == "win32" and not command.endswith(".exe"):
        candidates = [f"{command}.exe", command]

    # Check bundled directories first
    for bin_dir in _bundled_bin_dirs():
        if not bin_dir.is_dir():
            continue
        for name in candidates:
            path = bin_dir / name
            if path.is_file():
                return str(path)

    # Fall back to system PATH
    return shutil.which(command)


def is_bundled() -> bool:
    """Return True if running inside a PyInstaller bundle."""
    return hasattr(sys, "_MEIPASS")


def bundled_vendor_dir() -> Path | None:
    """Return the vendor directory inside the bundle, or None if not bundled."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        vendor = Path(meipass) / "vendor" / "bin"
        if vendor.is_dir():
            return vendor
    return None
