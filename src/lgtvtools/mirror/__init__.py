"""Screen mirroring pipeline for LG TV.

This package provides in-app screen mirroring functionality using ffmpeg
as the capture/encode/mux backend. The captured content is served as an
HLS stream to the TV's webOS browser via an embedded hls.js player.

Architecture:
    - Content is selected via ContentPicker dialog
    - CapturePipeline manages the ffmpeg subprocess
    - HLSServer serves the stream over HTTP
    - MirrorSession orchestrates the full lifecycle
    - MirrorWorker runs the session on a background QThread

Typical usage:
    from lgtvtools.mirror import MirrorSession, enumerate_sources, ContentPicker

    sources = enumerate_sources()
    # Show ContentPicker dialog to user...
    session = MirrorSession(device_ip="192.168.1.100", source=selected_source)
    result = session.start()
    # ... later ...
    session.stop()
"""

from __future__ import annotations

from .content_picker import ContentPicker
from .models import CaptureSource, MirrorState
from .session import MirrorSession
from .sources import enumerate_sources
from .worker import MirrorWorker

__all__ = [
    "CaptureSource",
    "ContentPicker",
    "MirrorSession",
    "MirrorState",
    "MirrorWorker",
    "enumerate_sources",
]
