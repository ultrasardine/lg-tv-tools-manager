"""WebOS WebSocket client module.

This module provides both async and sync clients for LG webOS TV control
via the Simple Service Access Protocol (SSAP) over WebSocket.

The async client is the primary implementation for Flet applications.
The sync client is provided for backwards compatibility and testing.
"""

from __future__ import annotations

from lgtvtools.core.webos.client import (
    WebOSClient,
    connect_to_tv,
    SSAP_LAUNCH,
    SSAP_OPEN_URL,
    SSAP_TOAST,
    SSAP_GET_APPS,
    SSAP_MEDIA_PLAY,
    SSAP_VOLUME_GET,
    SSAP_VOLUME_SET,
    SSAP_MUTE,
    SSAP_POWER_OFF,
    SSAP_INPUT_POINTER,
    SSAP_INPUT_TEXT,
    APP_BROWSER,
    APP_MEDIA_PLAYER,
)

__all__ = [
    "WebOSClient",
    "connect_to_tv",
    # SSAP URIs
    "SSAP_LAUNCH",
    "SSAP_OPEN_URL",
    "SSAP_TOAST",
    "SSAP_GET_APPS",
    "SSAP_MEDIA_PLAY",
    "SSAP_VOLUME_GET",
    "SSAP_VOLUME_SET",
    "SSAP_MUTE",
    "SSAP_POWER_OFF",
    "SSAP_INPUT_POINTER",
    "SSAP_INPUT_TEXT",
    # App IDs
    "APP_BROWSER",
    "APP_MEDIA_PLAYER",
]
