from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

LOGGER = logging.getLogger(__name__)


@dataclass
class CommandResult:
    ok: bool
    message: str


def which(command: str) -> str | None:
    return shutil.which(command)


def launch(command: str, args: list[str] | None = None) -> CommandResult:
    path = shutil.which(command)
    if not path:
        return CommandResult(False, f"{command} no está instalado")
    try:
        subprocess.Popen([path, *(args or [])], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        LOGGER.info("Launched %s %s", command, " ".join(args or []))
        return CommandResult(True, f"{command} iniciado")
    except Exception as exc:
        LOGGER.exception("Failed launching %s", command)
        return CommandResult(False, str(exc))


def open_file_with_default_app(path: str) -> CommandResult:
    opener = shutil.which("xdg-open")
    if not opener:
        return CommandResult(False, "xdg-open no está instalado")
    try:
        subprocess.Popen([opener, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return CommandResult(True, f"Abierto {Path(path).name}")
    except Exception as exc:
        LOGGER.exception("Failed opening %s", path)
        return CommandResult(False, str(exc))
