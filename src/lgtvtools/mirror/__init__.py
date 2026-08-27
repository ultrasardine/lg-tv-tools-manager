"""Screen mirroring pipeline for LG TV.

This package provides in-app screen mirroring functionality using ffmpeg
as the capture/encode/mux backend. The captured content is served as an
HLS stream to the TV's webOS browser via an embedded hls.js player.

Architecture:
    - CapturePipeline manages the ffmpeg subprocess
    - HLSServer serves the stream over HTTP
    - MirrorSession orchestrates the full lifecycle

Legacy Qt components (ContentPicker, MirrorWorker) require PyQt6 and are
not imported by default. Import them directly if needed:
    from lgtvtools.mirror.content_picker import ContentPicker
    from lgtvtools.mirror.worker import MirrorWorker

Typical usage:
    from lgtvtools.mirror import MirrorSession, enumerate_sources

    sources = enumerate_sources()
    session = MirrorSession(device_ip="192.168.1.100", source=selected_source)
    result = session.start()
    # ... later ...
    session.stop()
"""

from __future__ import annotations

from .models import CaptureSource, MirrorState
from .session import MirrorSession
from .sources import enumerate_sources

__all__ = [
    "CaptureSource",
    "MirrorSession",
    "MirrorState",
    "enumerate_sources",
]
