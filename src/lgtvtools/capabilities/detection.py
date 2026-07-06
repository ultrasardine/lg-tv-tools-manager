from __future__ import annotations

from dataclasses import dataclass
import subprocess
import shutil


@dataclass
class Capability:
    name: str
    installed: bool
    path: str | None = None
    hint: str = ""


KNOWN = {
    "gnome-network-displays": "sudo apt install gnome-network-displays",
    "vlc": "sudo apt install vlc",
    "ffmpeg": "sudo apt install ffmpeg",
    "rygel": "sudo apt install rygel",
    "pulseaudio": "sudo apt install pulseaudio",
    "pipewire": "sudo apt install pipewire",
    "miraclecast": "Install MiracleCast (legacy) or miracle-wifid (modern builds).",
}


def detect_capabilities() -> list[Capability]:
    result: list[Capability] = []
    for name, hint in KNOWN.items():
        if name == "miraclecast":
            path = shutil.which("miraclecast") or shutil.which("miracle-wifid")
        else:
            path = shutil.which(name)
        result.append(Capability(name=name, installed=bool(path), path=path, hint=hint))
    return result


def installed_names() -> set[str]:
    return {cap.name for cap in detect_capabilities() if cap.installed}


def run_if_available(command: str, args: list[str] | None = None) -> subprocess.Popen | None:
    path = shutil.which(command)
    if not path:
        return None
    return subprocess.Popen([path, *(args or [])])
