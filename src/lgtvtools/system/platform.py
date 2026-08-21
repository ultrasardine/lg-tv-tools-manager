"""Platform detection for multiplatform install hints and dependency lists."""

from __future__ import annotations

import platform
import sys
from enum import Enum
from pathlib import Path


class Platform(Enum):
    """Supported platform families."""

    MACOS = "macos"
    DEBIAN = "debian"  # Ubuntu, Kali, Debian
    RHEL = "rhel"  # Alma Linux, Rocky, RHEL, CentOS Stream, Fedora
    WINDOWS = "windows"  # Windows 10/11
    UNKNOWN = "unknown"


def detect_platform() -> Platform:
    """Identify the current platform family."""
    if sys.platform == "darwin":
        return Platform.MACOS

    if sys.platform == "win32":
        return Platform.WINDOWS

    if sys.platform != "linux":
        return Platform.UNKNOWN

    # Read os-release for distro identification
    os_release = _read_os_release()
    id_value = os_release.get("ID", "").lower()
    id_like = os_release.get("ID_LIKE", "").lower()

    # Debian family: debian, ubuntu, kali, pop, mint, etc.
    debian_ids = {"debian", "ubuntu", "kali", "pop", "linuxmint", "elementary", "zorin"}
    if id_value in debian_ids or "debian" in id_like or "ubuntu" in id_like:
        return Platform.DEBIAN

    # RHEL family: rhel, almalinux, rocky, centos, fedora, etc.
    rhel_ids = {"rhel", "almalinux", "rocky", "centos", "fedora", "ol"}
    if id_value in rhel_ids or "rhel" in id_like or "fedora" in id_like:
        return Platform.RHEL

    return Platform.UNKNOWN


def platform_label() -> str:
    """Return a human-readable label for the current platform."""
    labels = {
        Platform.MACOS: "macOS",
        Platform.DEBIAN: "Debian/Ubuntu",
        Platform.RHEL: "RHEL/Alma Linux",
        Platform.WINDOWS: "Windows",
        Platform.UNKNOWN: platform.system(),
    }
    return labels[detect_platform()]


def _read_os_release() -> dict[str, str]:
    """Parse /etc/os-release into a dict."""
    result: dict[str, str] = {}
    for path in (Path("/etc/os-release"), Path("/usr/lib/os-release")):
        if path.exists():
            for line in path.read_text().splitlines():
                if "=" in line:
                    key, _, value = line.partition("=")
                    result[key.strip()] = value.strip().strip('"')
            break
    return result
