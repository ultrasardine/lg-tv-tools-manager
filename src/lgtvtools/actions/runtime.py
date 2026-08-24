from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..system.platform import Platform, detect_platform

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
        return CommandResult(False, f"{command} is not installed")
    try:
        subprocess.Popen([path, *(args or [])], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        LOGGER.info("Launched %s %s", command, " ".join(args or []))
        return CommandResult(True, f"{command} launched")
    except Exception as exc:
        LOGGER.exception("Failed launching %s", command)
        return CommandResult(False, str(exc))


def open_file_with_default_app(path: str) -> CommandResult:
    """Open a file with the system default application (cross-platform)."""
    current = detect_platform()
    try:
        if current == Platform.MACOS:
            subprocess.Popen(["open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif current == Platform.WINDOWS:
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            opener = shutil.which("xdg-open")
            if not opener:
                return CommandResult(False, "xdg-open is not installed")
            subprocess.Popen([opener, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return CommandResult(True, f"Opened {Path(path).name}")
    except Exception as exc:
        LOGGER.exception("Failed opening %s", path)
        return CommandResult(False, str(exc))


def open_url(url: str) -> CommandResult:
    """Open a URL in the default browser (cross-platform)."""
    current = detect_platform()
    try:
        if current == Platform.MACOS:
            subprocess.Popen(["open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif current == Platform.WINDOWS:
            os.startfile(url)  # type: ignore[attr-defined]
        else:
            opener = shutil.which("xdg-open")
            if not opener:
                return CommandResult(False, "xdg-open is not installed")
            subprocess.Popen([opener, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return CommandResult(True, "Opened URL")
    except Exception as exc:
        LOGGER.exception("Failed opening URL %s", url)
        return CommandResult(False, str(exc))


def start_screen_mirror(device_ip: str = "", device_name: str = "") -> CommandResult:
    """Start screen mirroring using the platform-appropriate method.

    - macOS: Opens System Settings > Displays (AirPlay) for the user to select the TV
    - Windows: Opens Connect panel (built-in Miracast)
    - Linux: Launches gnome-network-displays or miraclecast
    """
    current = detect_platform()

    if current == Platform.MACOS:
        # Open System Settings to AirPlay/Displays pane
        # The user can select their TV from the AirPlay display list
        try:
            subprocess.Popen(
                ["open", "x-apple.systempreferences:com.apple.Displays-Settings.extension"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            hint = f" Select '{device_name}' from the AirPlay list." if device_name else ""
            return CommandResult(True, f"Opened macOS Display Settings (AirPlay).{hint}")
        except Exception as exc:
            LOGGER.exception("Failed to open Display Settings")
            return CommandResult(False, str(exc))

    if current == Platform.WINDOWS:
        # Open the Windows Connect panel for Miracast
        try:
            subprocess.Popen(
                ["explorer.exe", "ms-settings-connectabledevices:devicediscovery"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            hint = f" Select '{device_name}' from the list." if device_name else ""
            return CommandResult(True, f"Opened Windows Connect panel.{hint}")
        except Exception:
            pass
        # Fallback: open Connected Devices settings
        try:
            subprocess.Popen(
                ["explorer.exe", "ms-settings:connecteddevices"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return CommandResult(True, "Opened Windows Connected Devices settings")
        except Exception as exc:
            LOGGER.exception("Failed to open Windows settings")
            return CommandResult(False, str(exc))

    # Linux: try gnome-network-displays, then miraclecast
    result = launch("gnome-network-displays")
    if result.ok:
        return result
    result = launch("miraclecast")
    if result.ok:
        return result
    miracle_wifi = shutil.which("miracle-wifid")
    if miracle_wifi:
        return launch("miracle-wifid")
    return CommandResult(
        False,
        "No mirroring backend available.\n"
        "Install gnome-network-displays or miraclecast.",
    )


def start_screen_cast() -> CommandResult:
    """Start screen casting using the platform-appropriate method.

    - macOS: Opens System Settings > Displays (AirPlay)
    - Windows: Opens Connect/Cast panel
    - Linux: Launches gnome-network-displays or miraclecast
    """
    current = detect_platform()

    if current == Platform.MACOS:
        # AirPlay handles both mirroring and casting on macOS
        try:
            subprocess.Popen(
                ["open", "x-apple.systempreferences:com.apple.Displays-Settings.extension"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return CommandResult(True, "Opened macOS Display Settings (AirPlay)")
        except Exception as exc:
            LOGGER.exception("Failed to open Display Settings")
            return CommandResult(False, str(exc))

    if current == Platform.WINDOWS:
        # Open Windows Cast panel
        try:
            subprocess.Popen(
                ["explorer.exe", "ms-settings-connectabledevices:devicediscovery"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return CommandResult(True, "Opened Windows Cast panel")
        except Exception:
            pass
        try:
            subprocess.Popen(
                ["explorer.exe", "ms-settings:connecteddevices"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return CommandResult(True, "Opened Windows Connected Devices")
        except Exception as exc:
            LOGGER.exception("Failed to open Windows settings")
            return CommandResult(False, str(exc))

    # Linux: try gnome-network-displays, then miraclecast
    result = launch("gnome-network-displays")
    if result.ok:
        return result
    result = launch("miraclecast")
    if result.ok:
        return result
    miracle_wifi = shutil.which("miracle-wifid")
    if miracle_wifi:
        return launch("miracle-wifid")
    return CommandResult(
        False,
        "No casting backend available.\n"
        "Install gnome-network-displays or miraclecast.",
    )
