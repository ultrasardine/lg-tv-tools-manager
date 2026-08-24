"""Capability detection with platform-aware install hints."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from ..system.platform import Platform, detect_platform


@dataclass
class Capability:
    name: str
    installed: bool
    path: str | None = None
    hint: str = ""


# Per-platform dependency definitions.
# Keys: binary name to look up in PATH.
# Values: dict mapping Platform -> install hint (or None to skip on that platform).

_DEPS: dict[str, dict[Platform, str | None]] = {
    "vlc": {
        Platform.MACOS: "brew install --cask vlc",
        Platform.DEBIAN: "sudo apt install vlc",
        Platform.RHEL: "sudo dnf install vlc",
        Platform.WINDOWS: "winget install VideoLAN.VLC",
    },
    "ffmpeg": {
        Platform.MACOS: "brew install ffmpeg",
        Platform.DEBIAN: "sudo apt install ffmpeg",
        Platform.RHEL: "sudo dnf install ffmpeg",
        Platform.WINDOWS: "winget install Gyan.FFmpeg",
    },
    "gnome-network-displays": {
        Platform.MACOS: None,  # Not available on macOS
        Platform.DEBIAN: "sudo apt install gnome-network-displays",
        Platform.RHEL: "sudo dnf install gnome-network-displays",
        Platform.WINDOWS: None,  # Not available on Windows
    },
    "rygel": {
        Platform.MACOS: None,  # Not available on macOS
        Platform.DEBIAN: "sudo apt install rygel",
        Platform.RHEL: "sudo dnf install rygel",
        Platform.WINDOWS: None,  # Not available on Windows
    },
    "pulseaudio": {
        Platform.MACOS: None,  # macOS uses CoreAudio
        Platform.DEBIAN: "sudo apt install pulseaudio",
        Platform.RHEL: "sudo dnf install pulseaudio",
        Platform.WINDOWS: None,  # Windows uses WASAPI/DirectSound
    },
    "pipewire": {
        Platform.MACOS: None,  # macOS uses CoreAudio
        Platform.DEBIAN: "sudo apt install pipewire",
        Platform.RHEL: "sudo dnf install pipewire",
        Platform.WINDOWS: None,  # Windows uses WASAPI/DirectSound
    },
    "miraclecast": {
        Platform.MACOS: None,  # Not available on macOS
        Platform.DEBIAN: "Install MiracleCast from source or miracle-wifid",
        Platform.RHEL: "Install MiracleCast from source or miracle-wifid",
        Platform.WINDOWS: None,  # Windows has built-in Miracast
    },
}


def detect_capabilities() -> list[Capability]:
    """Detect installed capabilities relevant to the current platform."""
    from lgtvtools.system.bundled import which as bundled_which

    current = detect_platform()
    result: list[Capability] = []

    for name, hints in _DEPS.items():
        # Skip dependencies not applicable to this platform
        hint = hints.get(current, hints.get(Platform.UNKNOWN))
        if hint is None:
            continue

        if name == "miraclecast":
            path = bundled_which("miraclecast") or bundled_which("miracle-wifid")
        else:
            path = bundled_which(name)

        result.append(Capability(name=name, installed=bool(path), path=path, hint=hint))

    return result


def installed_names() -> set[str]:
    """Return names of all detected capabilities that are installed."""
    return {cap.name for cap in detect_capabilities() if cap.installed}


def install_command_summary() -> str:
    """Return a one-liner install command for all missing deps on this platform."""
    current = detect_platform()
    missing = [cap for cap in detect_capabilities() if not cap.installed]

    if not missing:
        return ""

    # Build a grouped install command where possible (apt/dnf/brew/winget)
    if current == Platform.DEBIAN:
        pkg_names = [cap.name for cap in missing if cap.hint.startswith("sudo apt")]
        if pkg_names:
            return f"sudo apt update && sudo apt install {' '.join(pkg_names)}"
    elif current == Platform.RHEL:
        pkg_names = [cap.name for cap in missing if cap.hint.startswith("sudo dnf")]
        if pkg_names:
            return f"sudo dnf install {' '.join(pkg_names)}"
    elif current == Platform.MACOS:
        brew_pkgs = [cap.name for cap in missing if "brew install" in cap.hint and "--cask" not in cap.hint]
        brew_casks = [cap.name for cap in missing if "--cask" in cap.hint]
        parts: list[str] = []
        if brew_pkgs:
            parts.append(f"brew install {' '.join(brew_pkgs)}")
        if brew_casks:
            parts.append(f"brew install --cask {' '.join(brew_casks)}")
        return " && ".join(parts)
    elif current == Platform.WINDOWS:
        winget_ids = [cap.hint.split()[-1] for cap in missing if cap.hint.startswith("winget install")]
        if winget_ids:
            return " && ".join(f"winget install {pkg}" for pkg in winget_ids)

    return ""


def run_if_available(command: str, args: list[str] | None = None) -> subprocess.Popen | None:
    """Run a command if it exists in PATH, otherwise return None."""
    from lgtvtools.system.bundled import which as bundled_which

    path = bundled_which(command)
    if not path:
        return None
    return subprocess.Popen([path, *(args or [])])
