"""MirrorSession orchestrator for the screen mirroring lifecycle.

This module provides the MirrorSession class that coordinates the full
mirror pipeline: starting the HLS server, spawning the ffmpeg capture
pipeline, waiting for the first segment, and launching the TV browser.

Requirements covered:
- 5.1: Send stream URL to TV browser when first segment is ready
- 5.2: Construct URL using host LAN IP and HLS server port
- 5.3: Stop pipeline if TV browser launch fails
- 6.1: Toggle session on/off with single button
- 6.2: Release resources within 3 seconds on stop
- 6.3: Delete temporary segment files on stop
- 6.6: Graceful shutdown on application exit
- 8.1: Stop session on encoder crash with error message
- 8.2: Continue serving if TV disconnects (with log warning)
- 8.3: Error if no LAN network interface found
- 8.4: Log errors at WARNING or ERROR level
"""

from __future__ import annotations

import logging
import shutil
import tempfile
import threading
import time
from pathlib import Path

from lgtvtools.mirror.capture import CapturePipeline
from lgtvtools.mirror.hls_server import HLSServer
from lgtvtools.mirror.models import (
    CaptureConfig,
    CaptureSource,
    MirrorResult,
    MirrorState,
)
from lgtvtools.system.platform import detect_platform
from lgtvtools.webos.client import WebOSClient, connect_to_tv

LOGGER = logging.getLogger(__name__)

# Timeout for waiting for the first HLS segment (seconds)
FIRST_SEGMENT_TIMEOUT = 10.0

# Interval for checking segment availability (seconds)
SEGMENT_CHECK_INTERVAL = 0.2

# Timeout for connecting to the TV (seconds)
TV_CONNECT_TIMEOUT = 15.0


class MirrorSession:
    """Orchestrates the full mirror lifecycle: server -> capture -> TV launch.

    This class manages the state machine for a mirror session and coordinates
    the HLSServer, CapturePipeline, and WebOSClient components.

    State machine transitions:
    - IDLE -> STARTING (when start() is called)
    - STARTING -> STREAMING (when first segment is ready)
    - STARTING -> ERROR (on startup failure)
    - STREAMING -> STOPPING (when stop() is called)
    - STREAMING -> ERROR (on runtime failure)
    - STOPPING -> IDLE (after cleanup completes)
    - ERROR -> IDLE (after error handling/cleanup)

    Example:
        >>> source = CaptureSource(id="1", name="Screen 1", kind="screen")
        >>> session = MirrorSession(device_ip="192.168.1.100", source=source)
        >>> result = session.start()
        >>> if result.ok:
        ...     print(f"Streaming at {result.player_url}")
        >>> # ... later ...
        >>> session.stop()
    """

    def __init__(
        self,
        device_ip: str,
        source: CaptureSource,
        config: CaptureConfig | None = None,
    ) -> None:
        """Initialize a mirror session.

        Args:
            device_ip: IP address of the target LG TV.
            source: The capture source (screen/window) to mirror.
            config: Optional capture configuration. Uses defaults if not provided.
        """
        self._device_ip = device_ip
        self._source = source
        self._config = config or CaptureConfig()
        self._platform = detect_platform()

        self._state = MirrorState.IDLE
        self._state_lock = threading.Lock()

        self._segments_dir: Path | None = None
        self._hls_server: HLSServer | None = None
        self._pipeline: CapturePipeline | None = None
        self._webos_client: WebOSClient | None = None

        self._player_url: str = ""

    @property
    def state(self) -> MirrorState:
        """Current state of the mirror session."""
        with self._state_lock:
            return self._state

    @property
    def is_active(self) -> bool:
        """Check if the session is actively streaming.

        Returns:
            True if the session is in STARTING or STREAMING state.
        """
        with self._state_lock:
            return self._state in (MirrorState.STARTING, MirrorState.STREAMING)

    @property
    def player_url(self) -> str:
        """URL to the player page (only valid when streaming)."""
        return self._player_url

    def _transition_state(self, new_state: MirrorState) -> bool:
        """Attempt to transition to a new state.

        Validates that the transition is valid according to the state machine.

        Args:
            new_state: The target state to transition to.

        Returns:
            True if the transition was valid and performed, False otherwise.
        """
        valid_transitions: dict[MirrorState, set[MirrorState]] = {
            MirrorState.IDLE: {MirrorState.STARTING},
            MirrorState.STARTING: {MirrorState.STREAMING, MirrorState.ERROR},
            MirrorState.STREAMING: {MirrorState.STOPPING, MirrorState.ERROR},
            MirrorState.STOPPING: {MirrorState.IDLE},
            MirrorState.ERROR: {MirrorState.IDLE},
        }

        with self._state_lock:
            allowed = valid_transitions.get(self._state, set())
            if new_state in allowed:
                LOGGER.debug(
                    "State transition: %s -> %s",
                    self._state.value,
                    new_state.value,
                )
                self._state = new_state
                return True
            else:
                LOGGER.warning(
                    "Invalid state transition attempted: %s -> %s",
                    self._state.value,
                    new_state.value,
                )
                return False

    def start(self) -> MirrorResult:
        """Start the mirror pipeline.

        Coordinates the startup sequence:
        1. Check ffmpeg availability
        2. Check network availability
        3. Create temp directory for segments
        4. Start HLS server
        5. Start capture pipeline
        6. Wait for first segment (10s timeout)
        7. Connect to TV and launch browser with player URL

        Returns:
            MirrorResult indicating success or failure, with player URL on success.
        """
        # Validate state transition
        if not self._transition_state(MirrorState.STARTING):
            return MirrorResult(
                ok=False,
                message="Cannot start session: already active or in error state",
                state=self.state,
            )

        try:
            # Pre-flight checks
            result = self._check_prerequisites()
            if not result.ok:
                self._handle_startup_error(result.message)
                return result

            # Create temp directory for HLS segments
            self._segments_dir = Path(tempfile.mkdtemp(prefix="lgtvtools-mirror-"))
            LOGGER.info("Created segments directory: %s", self._segments_dir)

            # Start HLS server
            self._hls_server = HLSServer(self._segments_dir)
            self._hls_server.start()
            host_ip = self._hls_server.get_host_ip()

            # Check for valid LAN IP
            if host_ip == "127.0.0.1":
                self._handle_startup_error("No LAN network interface found")
                return MirrorResult(
                    ok=False,
                    message="No LAN network interface found. "
                    "Please connect to a network with your TV.",
                    state=MirrorState.ERROR,
                )

            # Start capture pipeline
            self._pipeline = CapturePipeline(
                source=self._source,
                output_dir=self._segments_dir,
                platform=self._platform,
                config=self._config,
            )
            self._pipeline.start()

            # Wait for first segment
            if not self._wait_for_first_segment():
                stderr = ""
                if self._pipeline:
                    stderr = self._pipeline.get_stderr()
                self._handle_startup_error(f"Encoding failed to start: {stderr}")
                return MirrorResult(
                    ok=False,
                    message="Encoding failed to start. First segment not produced "
                    f"within {FIRST_SEGMENT_TIMEOUT:.0f} seconds.",
                    state=MirrorState.ERROR,
                )

            # Construct player URL
            self._player_url = self._hls_server.player_url(host_ip)
            LOGGER.info("Player URL ready: %s", self._player_url)

            # Launch TV browser
            result = self._launch_tv_browser()
            if not result.ok:
                self._handle_startup_error(f"TV browser launch failed: {result.message}")
                return result

            # Transition to streaming state
            if not self._transition_state(MirrorState.STREAMING):
                self._handle_startup_error("Failed to transition to streaming state")
                return MirrorResult(
                    ok=False,
                    message="Internal error: invalid state transition",
                    state=self.state,
                )

            LOGGER.info(
                "Mirror session started successfully for %s -> %s",
                self._source.name,
                self._device_ip,
            )

            return MirrorResult(
                ok=True,
                message="Mirror session started",
                state=MirrorState.STREAMING,
                player_url=self._player_url,
            )

        except FileNotFoundError as e:
            # ffmpeg not found (raised by CapturePipeline.start())
            self._handle_startup_error(str(e))
            return MirrorResult(
                ok=False,
                message=str(e),
                state=MirrorState.ERROR,
            )
        except OSError as e:
            # Network or file system error
            self._handle_startup_error(f"OS error during startup: {e}")
            return MirrorResult(
                ok=False,
                message=f"Failed to start mirror session: {e}",
                state=MirrorState.ERROR,
            )
        except Exception as e:
            # Catch-all for unexpected errors
            LOGGER.exception("Unexpected error starting mirror session")
            self._handle_startup_error(f"Unexpected error: {e}")
            return MirrorResult(
                ok=False,
                message=f"Unexpected error: {e}",
                state=MirrorState.ERROR,
            )

    def stop(self) -> None:
        """Stop the mirror session and clean up all resources.

        Performs ordered teardown:
        1. Stop capture pipeline (ffmpeg)
        2. Disconnect WebOS client
        3. Stop HLS server (includes cleanup of segment files)

        This method is safe to call from any state.
        """
        current_state = self.state

        # Handle state transition
        if current_state == MirrorState.STREAMING:
            self._transition_state(MirrorState.STOPPING)
        elif current_state == MirrorState.ERROR:
            # Cleanup from error state
            pass
        elif current_state == MirrorState.STARTING:
            # Abort startup
            self._transition_state(MirrorState.ERROR)
        elif current_state == MirrorState.IDLE:
            # Nothing to stop
            LOGGER.debug("Stop called on idle session, nothing to do")
            return
        elif current_state == MirrorState.STOPPING:
            # Already stopping
            LOGGER.debug("Stop called while already stopping")
            return

        LOGGER.info("Stopping mirror session...")

        # Stop capture pipeline first (ffmpeg)
        if self._pipeline is not None:
            try:
                self._pipeline.stop(timeout=3.0)
                LOGGER.info("Capture pipeline stopped")
            except OSError as e:
                LOGGER.warning("Error stopping capture pipeline: %s", e)
            self._pipeline = None

        # Disconnect WebOS client
        if self._webos_client is not None:
            try:
                self._webos_client.disconnect()
                LOGGER.debug("WebOS client disconnected")
            except OSError as e:
                LOGGER.warning("Error disconnecting WebOS client: %s", e)
            self._webos_client = None

        # Stop HLS server (includes segment cleanup)
        if self._hls_server is not None:
            try:
                self._hls_server.stop()
                LOGGER.info("HLS server stopped")
            except OSError as e:
                LOGGER.warning("Error stopping HLS server: %s", e)
            self._hls_server = None

        # Clear state
        self._segments_dir = None
        self._player_url = ""

        # Transition to idle
        with self._state_lock:
            self._state = MirrorState.IDLE

        LOGGER.info("Mirror session stopped and cleaned up")

    def check_health(self) -> MirrorResult:
        """Check the health of an active streaming session.

        Verifies that ffmpeg is still running and producing segments.
        Should be called periodically from a monitoring thread.

        Returns:
            MirrorResult indicating session health.
        """
        if self.state != MirrorState.STREAMING:
            return MirrorResult(
                ok=False,
                message=f"Session not streaming (state: {self.state.value})",
                state=self.state,
            )

        # Check if ffmpeg is still running
        if self._pipeline is not None and not self._pipeline.is_running:
            stderr = self._pipeline.get_stderr()
            LOGGER.error("ffmpeg process has crashed: %s", stderr[:500] if stderr else "no output")

            # Transition to error and stop
            self._transition_state(MirrorState.ERROR)
            self.stop()

            return MirrorResult(
                ok=False,
                message=f"Encoder crashed: {stderr[:200] if stderr else 'unknown error'}",
                state=MirrorState.ERROR,
            )

        return MirrorResult(
            ok=True,
            message="Session healthy",
            state=MirrorState.STREAMING,
            player_url=self._player_url,
        )

    def _check_prerequisites(self) -> MirrorResult:
        """Check that all prerequisites are met before starting.

        Returns:
            MirrorResult indicating if prerequisites are met.
        """
        # Check ffmpeg availability
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path is None:
            LOGGER.error("ffmpeg not found in PATH")
            return MirrorResult(
                ok=False,
                message="ffmpeg is not installed. Screen mirroring requires ffmpeg.",
                state=MirrorState.ERROR,
            )

        LOGGER.debug("ffmpeg found at: %s", ffmpeg_path)
        return MirrorResult(ok=True, message="Prerequisites met", state=MirrorState.STARTING)

    def _wait_for_first_segment(self) -> bool:
        """Wait for the first HLS segment to be produced.

        Polls the segments directory for .ts files until the timeout.

        Returns:
            True if a segment was found, False if timeout.
        """
        if self._segments_dir is None:
            return False

        deadline = time.time() + FIRST_SEGMENT_TIMEOUT
        segment_pattern = "*.ts"

        while time.time() < deadline:
            # Check if ffmpeg crashed
            if self._pipeline is not None and not self._pipeline.is_running:
                LOGGER.error("ffmpeg exited while waiting for first segment")
                return False

            # Check for .ts files
            segments = list(self._segments_dir.glob(segment_pattern))
            if segments:
                LOGGER.info("First segment produced: %s", segments[0].name)
                return True

            time.sleep(SEGMENT_CHECK_INTERVAL)

        LOGGER.error(
            "Timeout waiting for first segment (%.0fs)", FIRST_SEGMENT_TIMEOUT
        )
        return False

    def _launch_tv_browser(self) -> MirrorResult:
        """Connect to the TV and launch the browser with the player URL.

        Returns:
            MirrorResult indicating success or failure.
        """
        LOGGER.info("Connecting to TV at %s...", self._device_ip)

        try:
            self._webos_client, connect_result = connect_to_tv(
                self._device_ip, timeout=TV_CONNECT_TIMEOUT
            )

            if not connect_result.ok:
                LOGGER.error("Failed to connect to TV: %s", connect_result.message)
                return MirrorResult(
                    ok=False,
                    message=f"Cannot connect to TV: {connect_result.message}",
                    state=MirrorState.ERROR,
                )

            LOGGER.info("Connected to TV, launching browser...")
            launch_result = self._webos_client.launch_browser(self._player_url)

            if not launch_result.ok:
                LOGGER.error("Failed to launch TV browser: %s", launch_result.message)
                return MirrorResult(
                    ok=False,
                    message=f"Failed to launch TV browser: {launch_result.message}",
                    state=MirrorState.ERROR,
                )

            LOGGER.info("TV browser launched with player URL")
            return MirrorResult(
                ok=True,
                message="Browser launched",
                state=MirrorState.STARTING,
            )

        except OSError as e:
            LOGGER.error("Error launching TV browser: %s", e)
            return MirrorResult(
                ok=False,
                message=f"Error connecting to TV: {e}",
                state=MirrorState.ERROR,
            )

    def _handle_startup_error(self, message: str) -> None:
        """Handle an error during startup by transitioning to error state and cleaning up.

        Args:
            message: Error message to log.
        """
        LOGGER.error("Startup error: %s", message)

        # Transition to error state
        with self._state_lock:
            self._state = MirrorState.ERROR

        # Clean up any partially started resources
        self.stop()
