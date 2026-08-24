"""External tool launchers for desktop platforms.

Provides functions to launch external applications like VLC,
gnome-network-displays, and system utilities.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass

from lgtvtools.system.platform import Platform, detect_platform

LOGGER = logging.getLogger(__name__)


@dataclass
class LaunchResult:
    """Result of a launch operation."""

    ok: bool
    message: str


def which(command: str) -> str | None:
    """Check if a command is available (bundled or PATH)."""
    from lgtvtools.system.bundled import which as bundled_which

    return bundled_which(command)


def launch_external(command: str, args: list[str] | None = None) -> LaunchResult:
    """Launch an external application.

    Args:
        command: The command/application to launch.
        args: Optional list of arguments.

    Returns:
        LaunchResult indicating success or failure.
    """
    from lgtvtools.system.bundled import which as bundled_which

    path = bundled_which(command)
    if not path:
        return LaunchResult(False, f"{command} is not installed")

    try:
        subprocess.Popen(
            [path, *(args or [])],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        LOGGER.info("Launched %s %s", command, " ".join(args or []))
        return LaunchResult(True, f"{command} launched")
    except Exception as exc:
        LOGGER.exception("Failed launching %s", command)
        return LaunchResult(False, str(exc))


def open_file_with_default_app(path: str) -> LaunchResult:
    """Open a file with the system default application.

    Args:
        path: Path to the file to open.

    Returns:
        LaunchResult indicating success or failure.
    """
    from pathlib import Path

    current = detect_platform()

    try:
        if current == Platform.MACOS:
            subprocess.Popen(
                ["open", path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif current == Platform.WINDOWS:
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            opener = shutil.which("xdg-open")
            if not opener:
                return LaunchResult(False, "xdg-open is not installed")
            subprocess.Popen(
                [opener, path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        return LaunchResult(True, f"Opened {Path(path).name}")
    except Exception as exc:
        LOGGER.exception("Failed opening %s", path)
        return LaunchResult(False, str(exc))


def open_url_in_browser(url: str) -> LaunchResult:
    """Open a URL in the default browser.

    Args:
        url: URL to open.

    Returns:
        LaunchResult indicating success or failure.
    """
    current = detect_platform()

    try:
        if current == Platform.MACOS:
            subprocess.Popen(
                ["open", url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif current == Platform.WINDOWS:
            os.startfile(url)  # type: ignore[attr-defined]
        else:
            opener = shutil.which("xdg-open")
            if not opener:
                return LaunchResult(False, "xdg-open is not installed")
            subprocess.Popen(
                [opener, url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        return LaunchResult(True, "Opened URL")
    except Exception as exc:
        LOGGER.exception("Failed opening URL %s", url)
        return LaunchResult(False, str(exc))


def start_screen_mirror_native(device_ip: str = "", device_name: str = "") -> LaunchResult:
    """Start screen mirroring using the platform-appropriate native method.

    - macOS: Opens System Settings > Displays (AirPlay)
    - Windows: Opens Connect panel (built-in Miracast)
    - Linux: Launches gnome-network-displays or miraclecast

    Args:
        device_ip: IP of the target device (for hints).
        device_name: Name of the target device (for hints).

    Returns:
        LaunchResult indicating success or failure.
    """
    current = detect_platform()

    if current == Platform.MACOS:
        try:
            subprocess.Popen(
                ["open", "x-apple.systempreferences:com.apple.Displays-Settings.extension"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            hint = f" Select '{device_name}' from the AirPlay list." if device_name else ""
            return LaunchResult(True, f"Opened macOS Display Settings (AirPlay).{hint}")
        except Exception as exc:
            LOGGER.exception("Failed to open Display Settings")
            return LaunchResult(False, str(exc))

    if current == Platform.WINDOWS:
        try:
            subprocess.Popen(
                ["explorer.exe", "ms-settings-connectabledevices:devicediscovery"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            hint = f" Select '{device_name}' from the list." if device_name else ""
            return LaunchResult(True, f"Opened Windows Connect panel.{hint}")
        except Exception:
            pass

        try:
            subprocess.Popen(
                ["explorer.exe", "ms-settings:connecteddevices"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return LaunchResult(True, "Opened Windows Connected Devices settings")
        except Exception as exc:
            LOGGER.exception("Failed to open Windows settings")
            return LaunchResult(False, str(exc))

    # Linux: try gnome-network-displays, then miraclecast
    result = launch_external("gnome-network-displays")
    if result.ok:
        return result

    result = launch_external("miraclecast")
    if result.ok:
        return result

    miracle_wifi = shutil.which("miracle-wifid")
    if miracle_wifi:
        return launch_external("miracle-wifid")

    return LaunchResult(
        False,
        "No mirroring backend available.\nInstall gnome-network-displays or miraclecast.",
    )


def launch_vlc(file_path: str | None = None) -> LaunchResult:
    """Launch VLC media player.

    Args:
        file_path: Optional file to open.

    Returns:
        LaunchResult indicating success or failure.
    """
    args = [file_path] if file_path else []
    return launch_external("vlc", args)


def launch_gnome_network_displays() -> LaunchResult:
    """Launch GNOME Network Displays.

    Returns:
        LaunchResult indicating success or failure.
    """
    return launch_external("gnome-network-displays")
