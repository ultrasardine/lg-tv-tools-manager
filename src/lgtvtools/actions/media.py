from __future__ import annotations

from pathlib import Path
import logging

LOGGER = logging.getLogger(__name__)


def summarize_media(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return "Archivo no encontrado"
    return f"{p.name} ({p.stat().st_size} bytes)"
