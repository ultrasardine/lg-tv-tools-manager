"""Desktop-specific functionality for LG TV Tools.

This module contains features that are only available on desktop platforms:
- Screen mirroring (requires ffmpeg)
- External tool launchers (VLC, gnome-network-displays, etc.)
- Local media sharing via HTTP server
- File operations (file picker integration)
"""

from __future__ import annotations

__all__ = [
    "launch_external",
    "MediaShareServer",
    "DesktopActions",
]

from lgtvtools.desktop.actions.launchers import launch_external
from lgtvtools.desktop.actions.media_share import MediaShareServer
from lgtvtools.desktop.desktop_actions import DesktopActions
