"""Platform-specific capture source enumeration.

This module provides functions to enumerate available screens and windows
for capture on macOS, Linux, and Windows platforms using ffmpeg or native tools.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess

from lgtvtools.mirror.models import CaptureSource
from lgtvtools.system.platform import Platform

LOGGER = logging.getLogger(__name__)


def enumerate_sources(platform: Platform) -> list[CaptureSource]:
    """List available capture sources for the current platform.

    Uses platform-specific methods to discover capturable screens and windows:
    - macOS: parses `ffmpeg -f avfoundation -list_devices true` output
    - Linux: enumerates X11 displays via xrandr or detects PipeWire/Wayland
    - Windows: parses `ffmpeg -f gdigrab -list_devices true` output

    Args:
        platform: The platform to enumerate sources for.

    Returns:
        A list of CaptureSource objects. Returns an empty list if:
        - ffmpeg is not installed (logs a warning)
        - Platform is unknown/unsupported
        - Enumeration fails for any reason
    """
    from lgtvtools.system.bundled import which as bundled_which

    if not bundled_which("ffmpeg"):
        LOGGER.warning("ffmpeg not found in PATH; cannot enumerate capture sources")
        return []

    if platform == Platform.MACOS:
        return _enumerate_macos_sources()
    elif platform in (Platform.DEBIAN, Platform.RHEL):
        return _enumerate_linux_sources()
    elif platform == Platform.WINDOWS:
        return _enumerate_windows_sources()
    else:
        LOGGER.warning(
            "Unknown platform %s; cannot enumerate capture sources", platform
        )
        return []


def _enumerate_macos_sources() -> list[CaptureSource]:
    """Enumerate capture sources on macOS using ffmpeg avfoundation.

    Parses output from `ffmpeg -f avfoundation -list_devices true -i dummy`
    to extract available video capture devices (screens).

    Returns:
        List of CaptureSource objects for macOS. Source IDs are numeric
        indices suitable for use with `-i "<index>:none"`.
    """
    sources: list[CaptureSource] = []

    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-f",
                "avfoundation",
                "-list_devices",
                "true",
                "-i",
                "dummy",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        # ffmpeg writes device list to stderr and exits with error code
        output = result.stderr
    except subprocess.TimeoutExpired:
        LOGGER.warning("Timeout while enumerating macOS capture sources")
        return sources
    except OSError as e:
        LOGGER.warning("Failed to run ffmpeg for macOS source enumeration: %s", e)
        return sources

    sources.extend(_parse_avfoundation_output(output))
    return sources


def _parse_avfoundation_output(output: str) -> list[CaptureSource]:
    """Parse ffmpeg avfoundation device list output.

    Example ffmpeg output:
        [AVFoundation indev @ ...] AVFoundation video devices:
        [AVFoundation indev @ ...] [0] FaceTime HD Camera
        [AVFoundation indev @ ...] [1] Capture screen 0
        [AVFoundation indev @ ...] [2] Capture screen 1
        [AVFoundation indev @ ...] AVFoundation audio devices:
        ...

    Args:
        output: The stderr output from ffmpeg -list_devices command.

    Returns:
        List of CaptureSource objects for screens found in the output.
    """
    sources: list[CaptureSource] = []

    # Track whether we're in the video devices section
    in_video_section = False

    # Pattern for device lines: [index] Device Name
    device_pattern = re.compile(r"\[(\d+)\]\s+(.+)")

    for line in output.splitlines():
        # Detect section headers
        if "video devices:" in line.lower():
            in_video_section = True
            continue
        if "audio devices:" in line.lower():
            in_video_section = False
            continue

        if not in_video_section:
            continue

        # Extract device info
        match = device_pattern.search(line)
        if match:
            index = match.group(1)
            name = match.group(2).strip()

            # Filter to screen capture devices (skip cameras)
            if _is_screen_device(name):
                sources.append(
                    CaptureSource(
                        id=index,
                        name=name,
                        kind="screen",
                        resolution=None,
                    )
                )

    LOGGER.debug("Found %d macOS screen sources", len(sources))
    return sources


def _is_screen_device(name: str) -> bool:
    """Check if an avfoundation device name indicates a screen capture device.

    Args:
        name: The device name from ffmpeg output.

    Returns:
        True if this appears to be a screen/display device rather than a camera.
    """
    name_lower = name.lower()
    # Screen capture devices typically contain these patterns
    screen_indicators = ("capture screen", "screen", "display")
    # Cameras typically contain these patterns
    camera_indicators = ("camera", "facetime", "webcam", "isight")

    # Explicitly exclude cameras
    for indicator in camera_indicators:
        if indicator in name_lower:
            return False

    # Include known screen patterns
    return any(indicator in name_lower for indicator in screen_indicators)


def _enumerate_linux_sources() -> list[CaptureSource]:
    """Enumerate capture sources on Linux.

    Attempts to enumerate displays using:
    1. xrandr for X11 displays (most common)
    2. PipeWire detection for Wayland
    3. Fallback to primary display if detection fails

    Returns:
        List of CaptureSource objects for Linux. Source IDs follow x11grab
        format (e.g., ":0.0", ":0.0+1920,0") or "default" for PipeWire.
    """
    sources: list[CaptureSource] = []

    # Check for PipeWire/Wayland first
    if _is_pipewire_available():
        sources.append(
            CaptureSource(
                id="default",
                name="PipeWire Screen Capture",
                kind="screen",
                resolution=None,
            )
        )
        LOGGER.debug("Found PipeWire screen capture source")
        return sources

    # Try xrandr for X11 displays
    xrandr_sources = _enumerate_xrandr_sources()
    if xrandr_sources:
        sources.extend(xrandr_sources)
        return sources

    # Fallback: provide default X11 display
    display = _get_display_env()
    if display:
        sources.append(
            CaptureSource(
                id=display,
                name=f"Primary Display ({display})",
                kind="screen",
                resolution=None,
            )
        )
        LOGGER.debug("Using fallback X11 display: %s", display)

    return sources


def _is_pipewire_available() -> bool:
    """Check if PipeWire screen capture is available.

    Returns:
        True if PipeWire appears to be running and available for screen capture.
    """
    # Check if ffmpeg supports pipewire input
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-formats"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if "pipewire" not in result.stdout.lower():
            return False
    except (subprocess.TimeoutExpired, OSError):
        return False

    # Check if pipewire is running
    try:
        pgrep_result = subprocess.run(
            ["pgrep", "-x", "pipewire"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        return pgrep_result.returncode == 0
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        return False


def _enumerate_xrandr_sources() -> list[CaptureSource]:
    """Enumerate X11 displays using xrandr.

    Returns:
        List of CaptureSource objects with x11grab-compatible IDs.
    """
    sources: list[CaptureSource] = []

    if not shutil.which("xrandr"):
        LOGGER.debug("xrandr not found; skipping X11 display enumeration")
        return sources

    try:
        result = subprocess.run(
            ["xrandr", "--query"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode != 0:
            LOGGER.debug("xrandr query failed with code %d", result.returncode)
            return sources
        output = result.stdout
    except subprocess.TimeoutExpired:
        LOGGER.warning("Timeout while running xrandr")
        return sources
    except OSError as e:
        LOGGER.warning("Failed to run xrandr: %s", e)
        return sources

    sources.extend(_parse_xrandr_output(output))
    return sources


def _parse_xrandr_output(output: str) -> list[CaptureSource]:
    """Parse xrandr output to extract connected displays.

    Example xrandr output:
        Screen 0: minimum 8 x 8, current 3840 x 1080, maximum 32767 x 32767
        eDP-1 connected primary 1920x1080+0+0 (normal left...) 309mm x 174mm
           1920x1080     60.00*+  59.97
        HDMI-1 connected 1920x1080+1920+0 (normal left...) 527mm x 296mm
           1920x1080     60.00*+  50.00
        DP-1 disconnected (normal left inverted right x axis y axis)

    Args:
        output: The stdout from xrandr --query.

    Returns:
        List of CaptureSource objects for connected displays.
    """
    sources: list[CaptureSource] = []
    display = _get_display_env()

    # Pattern for connected displays with geometry
    # Example: "eDP-1 connected primary 1920x1080+0+0"
    # or: "HDMI-1 connected 1920x1080+1920+0"
    display_pattern = re.compile(
        r"^(\S+)\s+connected\s+(?:primary\s+)?(\d+)x(\d+)\+(\d+)\+(\d+)"
    )

    for line in output.splitlines():
        match = display_pattern.match(line)
        if match:
            name = match.group(1)
            width = int(match.group(2))
            height = int(match.group(3))
            x_offset = int(match.group(4))
            y_offset = int(match.group(5))

            # Construct x11grab source ID
            # Format: :display.screen+x_offset,y_offset
            if x_offset == 0 and y_offset == 0:
                source_id = display
            else:
                source_id = f"{display}+{x_offset},{y_offset}"

            sources.append(
                CaptureSource(
                    id=source_id,
                    name=f"{name} ({width}x{height})",
                    kind="screen",
                    resolution=(width, height),
                )
            )

    LOGGER.debug("Found %d X11 display sources via xrandr", len(sources))
    return sources


def _get_display_env() -> str:
    """Get the X11 DISPLAY environment variable value.

    Returns:
        The DISPLAY value, defaulting to ":0.0" if not set.
    """
    import os

    display = os.environ.get("DISPLAY", ":0.0")
    # Ensure display has screen number
    if "." not in display:
        display = f"{display}.0"
    return display


def _enumerate_windows_sources() -> list[CaptureSource]:
    """Enumerate capture sources on Windows using ffmpeg gdigrab.

    On Windows, gdigrab supports:
    - "desktop" - captures the entire desktop
    - "title=<window_title>" - captures a specific window by title

    This function always includes the desktop and attempts to enumerate
    visible windows via ffmpeg.

    Returns:
        List of CaptureSource objects for Windows. At minimum, includes
        the "desktop" source.
    """
    sources: list[CaptureSource] = []

    # Always include desktop capture as the primary option
    sources.append(
        CaptureSource(
            id="desktop",
            name="Entire Desktop",
            kind="screen",
            resolution=None,
        )
    )

    # Attempt to enumerate windows via ffmpeg
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-f",
                "gdigrab",
                "-list_devices",
                "true",
                "-i",
                "dummy",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        # Parse any window information from stderr
        window_sources = _parse_gdigrab_output(result.stderr)
        sources.extend(window_sources)
    except subprocess.TimeoutExpired:
        LOGGER.warning("Timeout while enumerating Windows capture sources")
    except OSError as e:
        LOGGER.warning("Failed to run ffmpeg for Windows source enumeration: %s", e)

    LOGGER.debug("Found %d Windows capture sources", len(sources))
    return sources


def _parse_gdigrab_output(output: str) -> list[CaptureSource]:
    """Parse ffmpeg gdigrab output for window information.

    Note: gdigrab doesn't provide a comprehensive window list like avfoundation.
    This function is a placeholder for potential future enhancements using
    Windows-specific APIs.

    Args:
        output: The stderr output from ffmpeg -list_devices command.

    Returns:
        List of additional CaptureSource objects found (currently empty).
    """
    # gdigrab doesn't enumerate windows in the same way as avfoundation
    # Future enhancement: use pywin32 or ctypes to enumerate windows
    # and allow capture via "title=<window_title>"
    _ = output  # Unused for now
    return []
