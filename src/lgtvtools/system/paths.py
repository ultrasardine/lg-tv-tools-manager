from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "LG TV Tools"
APP_ID = "lg-tv-tools"


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def data_dir() -> Path:
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / APP_ID


def config_dir() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / APP_ID


def log_dir() -> Path:
    return data_dir() / "logs"


def icon_path() -> Path:
    return data_dir() / "icons" / "app.svg"


def desktop_entry_path() -> Path:
    return data_dir() / "applications" / f"{APP_ID}.desktop"


def user_bin_dir() -> Path:
    return Path.home() / ".local" / "bin"
