"""LG TV Tools - Shared Core Module.

This module contains platform-agnostic code that can be used by both
desktop (full features) and mobile (remote-control subset) builds.

Components:
- models: Data models (LGTVDevice, WebOSResult, etc.)
- discovery: TV discovery protocols (SSDP, mDNS abstraction, UPnP)
- webos: Async WebOS WebSocket client
- runtime: Runtime feature detection
"""

from __future__ import annotations

__all__ = [
    "LGTVDevice",
    "WebOSResult",
    "Runtime",
    "discover_lg_tvs",
]

from lgtvtools.core.models import LGTVDevice, WebOSResult
from lgtvtools.core.runtime import Runtime


# Lazy import for discovery to avoid import errors on mobile
def discover_lg_tvs(timeout: float = 5.0) -> list[LGTVDevice]:
    """Discover LG TVs using available protocols."""
    from lgtvtools.core.discovery import discover_lg_tvs as _discover
    return _discover(timeout)
