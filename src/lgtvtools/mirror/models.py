"""Data models for the screen mirroring feature.

This module defines the core data structures used throughout the mirror package:
- MirrorState: Enum representing the states of a mirror session
- CaptureSource: Dataclass for a capturable screen or window
- CaptureConfig: Dataclass with configuration for the capture pipeline
- MirrorResult: Dataclass for results of mirror session operations
- EncoderInfo: Dataclass for detected hardware encoder information
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


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
    STARTING = "starting"  # ffmpeg spawning, waiting for first segment
    STREAMING = "streaming"  # Active stream, TV playing
    STOPPING = "stopping"  # Graceful shutdown in progress
    ERROR = "error"


@dataclass
class CaptureSource:
    """A capturable screen or window.

    Attributes:
        id: Platform-specific identifier for ffmpeg input.
            - macOS: numeric index (e.g., "1", "2")
            - Linux (X11): display string (e.g., ":0.0", ":0.0+1920,0")
            - Windows: "desktop" or "title=<window_name>"
        name: Human-readable label for display in the picker.
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
        max_resolution: Maximum output resolution as (width, height).
            Source will be scaled down if larger, preserving aspect ratio
            (default: 1920x1080).
        segment_duration: Duration of each HLS segment in seconds (default: 2).
        max_segments: Maximum number of segments in the HLS playlist sliding
            window (default: 5).
        video_bitrate: Target video bitrate as ffmpeg string (default: "4M").
        h264_profile: H.264 profile for encoding (default: "main").
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
        ok: True if the operation succeeded, False otherwise.
        message: Human-readable description of the result or error.
        state: Current state of the mirror session after the operation.
        player_url: URL to the player page (only set on successful start).
    """

    ok: bool
    message: str
    state: MirrorState = MirrorState.IDLE
    player_url: str = ""


@dataclass
class EncoderInfo:
    """Detected hardware encoder availability.

    Attributes:
        name: The encoder name as recognized by ffmpeg
            (e.g., "h264_videotoolbox", "libx264").
        is_hardware: True if this is a hardware-accelerated encoder.
        platform: The platform where this encoder was detected
            (e.g., "macOS", "Linux", "Windows").
    """

    name: str
    is_hardware: bool
    platform: str
