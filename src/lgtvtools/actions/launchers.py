from __future__ import annotations

import logging
import shutil
import subprocess

LOGGER = logging.getLogger(__name__)


def open_app(command: str, args: list[str] | None = None) -> tuple[bool, str]:
    path = shutil.which(command)
    if not path:
        return False, f"{command} no está instalado"
    try:
        subprocess.Popen([path, *(args or [])], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        LOGGER.info("Launched %s", command)
        return True, f"{command} abierto"
    except Exception as exc:
        LOGGER.exception("Failed to launch %s", command)
        return False, str(exc)

