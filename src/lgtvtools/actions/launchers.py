from __future__ import annotations

import logging
import subprocess

LOGGER = logging.getLogger(__name__)


def open_app(command: str, args: list[str] | None = None) -> tuple[bool, str]:
    from lgtvtools.system.bundled import which as bundled_which

    path = bundled_which(command)
    if not path:
        return False, f"{command} is not installed"
    try:
        subprocess.Popen([path, *(args or [])], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        LOGGER.info("Launched %s", command)
        return True, f"{command} opened"
    except Exception as exc:
        LOGGER.exception("Failed to launch %s", command)
        return False, str(exc)

