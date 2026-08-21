"""MirrorWorker QThread for background screen mirroring operations.

This module provides the MirrorWorker class that runs the MirrorSession
on a background thread, keeping the PyQt6 UI responsive during capture
and streaming operations.

Requirements covered:
- 6.4: Run capture and encoding on a background thread for UI responsiveness
- 6.5: Emit signals for UI status indicator updates
"""

from __future__ import annotations

import logging
import threading

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from lgtvtools.mirror.models import CaptureConfig, CaptureSource, MirrorState
from lgtvtools.mirror.session import MirrorSession

LOGGER = logging.getLogger(__name__)

# Interval for health check polling (seconds)
HEALTH_CHECK_INTERVAL = 2.0


class MirrorWorker(QThread):
    """Background thread for screen mirroring operations.

    This class wraps MirrorSession in a QThread to keep the UI responsive
    while capture and encoding run. It follows the existing worker patterns
    (DiscoveryWorker, WebOSWorker) in the codebase.

    Signals:
        started: Emitted when the stream is live on the TV.
        stopped: Emitted when the session ends (normal or requested stop).
        error(str): Emitted on failure with an error message.

    Example:
        >>> source = CaptureSource(id="1", name="Screen 1", kind="screen")
        >>> worker = MirrorWorker(device_ip="192.168.1.100", source=source)
        >>> worker.started.connect(on_mirror_started)
        >>> worker.stopped.connect(on_mirror_stopped)
        >>> worker.error.connect(on_mirror_error)
        >>> worker.start()
        >>> # ... later ...
        >>> worker.request_stop()
    """

    started = pyqtSignal()  # Emitted when stream is live on TV
    stopped = pyqtSignal()  # Emitted when session ends
    error = pyqtSignal(str)  # Emitted on failure with message

    def __init__(
        self,
        device_ip: str,
        source: CaptureSource,
        config: CaptureConfig | None = None,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the mirror worker.

        Args:
            device_ip: IP address of the target LG TV.
            source: The capture source (screen/window) to mirror.
            config: Optional capture configuration. Uses defaults if not provided.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._device_ip = device_ip
        self._source = source
        self._config = config

        self._session: MirrorSession | None = None
        self._stop_event = threading.Event()

    @property
    def player_url(self) -> str:
        """URL to the player page (only valid when streaming)."""
        if self._session is not None:
            return self._session.player_url
        return ""

    @property
    def is_active(self) -> bool:
        """Check if the session is actively streaming."""
        if self._session is not None:
            return self._session.is_active
        return False

    def run(self) -> None:
        """Start the mirror session and wait for stop signal.

        This method:
        1. Creates and starts the MirrorSession
        2. Emits `started` signal on success
        3. Monitors session health until stop is requested
        4. Emits `stopped` signal when session ends
        5. Emits `error` signal if startup or runtime fails
        """
        LOGGER.info(
            "MirrorWorker starting for %s -> %s",
            self._source.name,
            self._device_ip,
        )

        try:
            # Create and start the session
            self._session = MirrorSession(
                device_ip=self._device_ip,
                source=self._source,
                config=self._config,
            )

            result = self._session.start()

            if not result.ok:
                LOGGER.error("Mirror session failed to start: %s", result.message)
                self.error.emit(result.message)
                return

            # Session started successfully
            LOGGER.info("Mirror session started, player URL: %s", result.player_url)
            self.started.emit()

            # Monitor session health until stop is requested
            self._monitor_session()

        except Exception as exc:
            LOGGER.exception("Unexpected error in MirrorWorker")
            self.error.emit(str(exc))
        finally:
            self._cleanup()
            self.stopped.emit()
            LOGGER.info("MirrorWorker finished")

    def request_stop(self) -> None:
        """Thread-safe request to stop the session.

        This method can be called from any thread (typically the main UI thread).
        It signals the worker to stop and waits for cleanup.
        """
        LOGGER.info("Stop requested for MirrorWorker")
        self._stop_event.set()

    def _monitor_session(self) -> None:
        """Monitor session health until stop is requested.

        Polls the session health periodically and handles errors.
        Exits when stop_event is set or session encounters an error.
        """
        while not self._stop_event.is_set():
            # Check session health
            if self._session is not None:
                health = self._session.check_health()

                if not health.ok:
                    # Session encountered an error (e.g., ffmpeg crashed)
                    LOGGER.error("Session health check failed: %s", health.message)
                    self.error.emit(health.message)
                    return

                # Session is healthy, continue monitoring
                if health.state != MirrorState.STREAMING:
                    # Session ended for some reason
                    LOGGER.warning(
                        "Session no longer streaming (state: %s)",
                        health.state.value,
                    )
                    return

            # Wait for stop signal or next health check
            if self._stop_event.wait(timeout=HEALTH_CHECK_INTERVAL):
                # Stop was requested
                LOGGER.debug("Stop event received during monitoring")
                break

    def _cleanup(self) -> None:
        """Clean up resources when the worker finishes."""
        if self._session is not None:
            try:
                self._session.stop()
            except OSError as exc:
                LOGGER.warning("Error during session cleanup: %s", exc)
            self._session = None

        # Clear the stop event for potential reuse (though workers are typically
        # single-use)
        self._stop_event.clear()
