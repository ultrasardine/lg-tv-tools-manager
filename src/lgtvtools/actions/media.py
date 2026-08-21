from __future__ import annotations

import logging
from pathlib import Path

LOGGER = logging.getLogger(__name__)


def summarize_media(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return "File not found"
    return f"{p.name} ({p.stat().st_size} bytes)"
