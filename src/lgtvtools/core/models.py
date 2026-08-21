"""Shared data models for LG TV Tools.

This module contains all data models used across desktop and mobile builds.
Models are framework-agnostic dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


# =============================================================================
# Device Models
# =============================================================================


@dataclass
class LGTVDevice:
    """Represents a discovered LG TV on the network.

    Attributes:
        usn: Unique service name (SSDP identifier).
        name: Display name of the TV.
        ip: IP address of the TV.
        location: Primary UPnP location URL.
        model: TV model identifier (e.g., "OLED55C1").
        server: Server header from UPnP response.
        friendly_name: User-configured name from UPnP description.
        services: List of available UPnP service types.
        locations: Set of all discovered location URLs.
        discovery_source: How this device was discovered ("ssdp", "mdns", "both").
    """

    usn: str
    name: str
    ip: str
    location: str
    model: str = ""
    server: str = ""
    friendly_name: str = ""
    services: list[str] = field(default_factory=list)
    locations: set[str] = field(default_factory=set)
    discovery_source: str = "unknown"

    def __post_init__(self) -> None:
        if self.location and not self.locations:
            self.locations.add(self.location)

    def display_name(self) -> str:
        """Return a human-readable display name for the TV."""
        parts = [self.name.strip() or "LG TV"]
        if self.model:
            parts.append(self.model)
        if self.ip:
            parts.append(self.ip)
        return " - ".join(parts)

    def __hash__(self) -> int:
        return hash(self.ip or self.usn)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LGTVDevice):
            return NotImplemented
        return self.ip == other.ip


# =============================================================================
# WebOS Models
# =============================================================================


@dataclass
class WebOSResult:
    """Result of a webOS operation.

    Attributes:
        ok: True if the operation succeeded.
        message: Human-readable result or error message.
        payload: Response payload from the TV (if any).
    """

    ok: bool
    message: str
    payload: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# UPnP Models
# =============================================================================


class UPnPStatus(Enum):
    """Status of a UPnP operation."""

    SUCCESS = "success"
    NO_AV_TRANSPORT = "no_av_transport"
    CONNECTION_ERROR = "connection_error"
    SOAP_ERROR = "soap_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class UPnPResult:
    """Result of a UPnP/DLNA operation.

    Attributes:
        ok: True if the operation succeeded.
        status: Detailed status enum.
        message: Human-readable message.
    """

    ok: bool
    status: UPnPStatus
    message: str = ""


# =============================================================================
# Mirror Models (shared definitions, desktop-only implementation)
# =============================================================================


class MirrorState(Enum):
    """States of a mirror session.

    Valid state transitions:
    - IDLE -> STARTING (when start() is called)
    - STARTING -> STREAMING (when first segment is ready)
    - STARTING -> ERROR (on startup failure)
    - STREAMING -> STOPPING (when stop() is called)
    - STREAMING -> ERROR (on runtime failure)
    - STOPPING -> IDLE (after cleanup completes)
    - ERROR -> IDLE (after error handling/cleanup)
    """

    IDLE = "idle"
    STARTING = "starting"
    STREAMING = "streaming"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class CaptureSource:
    """A capturable screen or window.

    Attributes:
        id: Platform-specific identifier for ffmpeg input.
        name: Human-readable label for display.
        kind: Type of capture source ("screen" or "window").
        resolution: Optional tuple of (width, height) in pixels.
    """

    id: str
    name: str
    kind: Literal["screen", "window"]
    resolution: tuple[int, int] | None = None


@dataclass
class CaptureConfig:
    """Configuration for the capture pipeline.

    Attributes:
        framerate: Target capture frame rate (default: 30 fps).
        max_resolution: Maximum output resolution (default: 1920x1080).
        segment_duration: HLS segment duration in seconds (default: 2).
        max_segments: Maximum segments in HLS playlist (default: 5).
        video_bitrate: Target video bitrate (default: "4M").
        h264_profile: H.264 profile (default: "main").
    """

    framerate: int = 30
    max_resolution: tuple[int, int] = (1920, 1080)
    segment_duration: int = 2
    max_segments: int = 5
    video_bitrate: str = "4M"
    h264_profile: str = "main"


@dataclass
class MirrorResult:
    """Result of a mirror session operation.

    Attributes:
        ok: True if the operation succeeded.
        message: Human-readable description.
        state: Current state of the mirror session.
        player_url: URL to the player page (on successful start).
    """

    ok: bool
    message: str
    state: MirrorState = MirrorState.IDLE
    player_url: str = ""


@dataclass
class EncoderInfo:
    """Detected hardware encoder information.

    Attributes:
        name: Encoder name for ffmpeg.
        is_hardware: True if hardware-accelerated.
        platform: Platform where detected.
    """

    name: str
    is_hardware: bool
    platform: str


# =============================================================================
# Capability Models
# =============================================================================


@dataclass
class Capability:
    """A system capability or dependency.

    Attributes:
        name: Name of the capability (e.g., "ffmpeg", "vlc").
        installed: True if the capability is available.
        hint: Installation hint for the user.
        required_for: Features that require this capability.
    """

    name: str
    installed: bool
    hint: str = ""
    required_for: list[str] = field(default_factory=list)


# =============================================================================
# Application State
# =============================================================================


@dataclass
class AppState:
    """Application state container.

    This is used by the Flet UI for state management.

    Attributes:
        devices: List of discovered TVs.
        selected_device: Currently selected TV.
        is_scanning: True if scanning is in progress.
        is_connecting: True if WebOS connection is in progress.
        is_mirroring: True if mirroring is active.
        connection_status: Current status message.
        last_error: Last error message (if any).
        capabilities: Detected system capabilities (desktop only).
        share_url: Last media share URL.
    """

    devices: list[LGTVDevice] = field(default_factory=list)
    selected_device: LGTVDevice | None = None
    is_scanning: bool = False
    is_connecting: bool = False
    is_mirroring: bool = False
    connection_status: str = "Ready"
    last_error: str | None = None
    capabilities: list[Capability] | None = None
    share_url: str = ""
