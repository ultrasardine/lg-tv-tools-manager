from __future__ import annotations

from pathlib import Path


def kde_applications_dir() -> Path:
    return Path.home() / ".local" / "share" / "applications"
