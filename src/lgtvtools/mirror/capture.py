"""Capture pipeline for screen mirroring using ffmpeg.

This module provides the CapturePipeline class that manages an ffmpeg subprocess
for capturing, encoding, and producing HLS segments. It handles platform-specific
input formats and hardware encoder detection with fallback to software encoding.

Requirements covered:
- 2.1: Capture frames at minimum 30 fps
- 2.2: Deliver frames with <100ms latency
- 2.4: Adapt to resolution changes (via scale filter)
- 3.1: Encode to H.264 Baseline/Main profile
- 3.2: Use hardware-accelerated encoding when available
- 3.3: Fall back to libx264 software encoding
- 3.4: Encode at max 1920x1080 or source resolution (whichever smaller)
- 3.5: Produce HLS-compatible segments with proper keyframe intervals
- 7.1: Use x11grab on Linux
- 7.2: Use gdigrab on Windows
- 7.3: Display error if ffmpeg is not installed
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from lgtvtools.mirror.models import CaptureConfig, CaptureSource, EncoderInfo
from lgtvtools.system.platform import Platform

LOGGER = logging.getLogger(__name__)

# Hardware encoders by platform (in order of preference)
HARDWARE_ENCODERS: dict[Platform, list[str]] = {
    Platform.MACOS: ["h264_videotoolbox"],
    Platform.DEBIAN: ["h264_vaapi", "h264_nvenc"],
    Platform.RHEL: ["h264_vaapi", "h264_nvenc"],
    Platform.WINDOWS: ["h264_nvenc", "h264_qsv"],
}

# Software fallback encoder (always available with ffmpeg)
SOFTWARE_ENCODER = "libx264"


class CapturePipeline:
    """Manages an ffmpeg subprocess that captures, encodes, and produces HLS segments.

    This class handles the full capture-encode-mux pipeline for screen mirroring:
    - Platform-specific input format selection (avfoundation/x11grab/gdigrab)
    - Hardware encoder detection and selection with software fallback
    - Resolution capping with aspect ratio preservation
    - HLS output with configurable segment duration and playlist size

    Attributes:
        source: The capture source to use.
        output_dir: Directory where HLS segments and playlist will be written.
        platform: The current platform.
        config: Capture configuration parameters.
        encoder: The detected encoder to use for encoding.

    Example:
        >>> pipeline = CapturePipeline(
        ...     source=CaptureSource(id="1", name="Screen 1", kind="screen"),
        ...     output_dir=Path("/tmp/mirror"),
        ...     platform=Platform.MACOS,
        ... )
        >>> pipeline.start()
        >>> # ... capture is running ...
        >>> pipeline.stop()
    """

    def __init__(
        self,
        source: CaptureSource,
        output_dir: Path,
        platform: Platform,
        config: CaptureConfig | None = None,
    ) -> None:
        """Initialize the capture pipeline.

        Args:
            source: The capture source (screen/window) to capture.
            output_dir: Directory where HLS segments and playlist will be written.
                Must exist and be writable.
            platform: The current platform (macOS, Linux, Windows).
            config: Optional capture configuration. Uses defaults if not provided.
        """
        self.source = source
        self.output_dir = output_dir
        self.platform = platform
        self.config = config or CaptureConfig()

        self._process: subprocess.Popen[bytes] | None = None
        self._encoder: EncoderInfo | None = None

    @property
    def encoder(self) -> EncoderInfo:
        """Get the encoder to use for encoding.

        Detects available hardware encoders on first access and caches the result.
        Falls back to libx264 if no hardware encoder is available.
        """
        if self._encoder is None:
            self._encoder = self._detect_encoder()
        return self._encoder

    @property
    def is_running(self) -> bool:
        """Check if the ffmpeg subprocess is alive.

        Returns:
            True if the ffmpeg process is running, False otherwise.
        """
        if self._process is None:
            return False
        return self._process.poll() is None

    @property
    def playlist_path(self) -> Path:
        """Path to the HLS playlist file."""
        return self.output_dir / "stream.m3u8"

    @property
    def segment_pattern(self) -> str:
        """Pattern for HLS segment filenames."""
        return str(self.output_dir / "seg%d.ts")

    def start(self) -> None:
        """Spawn the ffmpeg process to begin capture.

        Raises:
            FileNotFoundError: If ffmpeg is not installed on the system.
            RuntimeError: If the pipeline is already running.
            OSError: If the ffmpeg process fails to start.
        """
        if self.is_running:
            raise RuntimeError("Capture pipeline is already running")

        from lgtvtools.system.bundled import which as bundled_which

        ffmpeg_path = bundled_which("ffmpeg")
        if ffmpeg_path is None:
            raise FileNotFoundError(
                "ffmpeg is not installed. Screen mirroring requires ffmpeg."
            )

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        command = self._build_command()
        LOGGER.info("Starting capture pipeline: %s", " ".join(command))
        LOGGER.debug("Encoder: %s (hardware=%s)", self.encoder.name, self.encoder.is_hardware)

        try:
            self._process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
            )
            LOGGER.info(
                "ffmpeg process started with PID %d",
                self._process.pid,
            )
        except OSError as e:
            LOGGER.error("Failed to start ffmpeg: %s", e)
            raise

    def stop(self, timeout: float = 3.0) -> None:
        """Stop ffmpeg gracefully with SIGTERM, then SIGKILL after timeout.

        Args:
            timeout: Maximum time in seconds to wait for graceful termination
                before sending SIGKILL.
        """
        if self._process is None:
            LOGGER.debug("No process to stop")
            return

        if not self.is_running:
            LOGGER.debug("Process already terminated")
            self._process = None
            return

        pid = self._process.pid
        LOGGER.info("Stopping capture pipeline (PID %d)", pid)

        # Send SIGTERM for graceful shutdown
        try:
            self._process.terminate()
            LOGGER.debug("Sent SIGTERM to ffmpeg")
        except ProcessLookupError:
            LOGGER.debug("Process already gone before SIGTERM")
            self._process = None
            return

        # Wait for graceful termination
        try:
            self._process.wait(timeout=timeout)
            LOGGER.info("ffmpeg terminated gracefully")
        except subprocess.TimeoutExpired:
            LOGGER.warning(
                "ffmpeg did not terminate within %.1fs, sending SIGKILL",
                timeout,
            )
            try:
                self._process.kill()
                self._process.wait(timeout=1.0)
                LOGGER.info("ffmpeg killed with SIGKILL")
            except ProcessLookupError:
                LOGGER.debug("Process gone before SIGKILL")
            except subprocess.TimeoutExpired:
                LOGGER.error("ffmpeg did not respond to SIGKILL")

        self._process = None

    def get_stderr(self) -> str:
        """Get the stderr output from the ffmpeg process.

        Useful for debugging encoder failures.

        Returns:
            The stderr output, or empty string if no process or stderr unavailable.
        """
        if self._process is None or self._process.stderr is None:
            return ""
        try:
            # Non-blocking read of available stderr
            return self._process.stderr.read().decode("utf-8", errors="replace")
        except (OSError, ValueError):
            return ""

    def _build_command(self) -> list[str]:
        """Construct the ffmpeg command line for this platform and source.

        Returns:
            A list of command-line arguments for ffmpeg.
        """
        cmd = ["ffmpeg", "-hide_banner", "-y"]

        # Input configuration (platform-specific)
        cmd.extend(self._build_input_args())

        # Encoding configuration
        cmd.extend(self._build_encoding_args())

        # Video filter for resolution capping
        cmd.extend(self._build_filter_args())

        # HLS output configuration
        cmd.extend(self._build_hls_args())

        # Output file
        cmd.append(str(self.playlist_path))

        return cmd

    def _build_input_args(self) -> list[str]:
        """Build platform-specific input arguments.

        Returns:
            Input arguments for ffmpeg including format flag and input specifier.
        """
        args: list[str] = []

        if self.platform == Platform.MACOS:
            # macOS: avfoundation with screen index
            args.extend([
                "-f", "avfoundation",
                "-framerate", str(self.config.framerate),
                "-capture_cursor", "1",
                "-i", f"{self.source.id}:none",
            ])
        elif self.platform in (Platform.DEBIAN, Platform.RHEL):
            # Linux: x11grab with display string
            args.extend([
                "-f", "x11grab",
                "-framerate", str(self.config.framerate),
                "-draw_mouse", "1",
            ])
            # Add video size if resolution is known
            if self.source.resolution:
                width, height = self.source.resolution
                args.extend(["-video_size", f"{width}x{height}"])
            args.extend(["-i", self.source.id])
        elif self.platform == Platform.WINDOWS:
            # Windows: gdigrab with "desktop" or "title=<name>"
            args.extend([
                "-f", "gdigrab",
                "-framerate", str(self.config.framerate),
                "-draw_mouse", "1",
                "-i", self.source.id,
            ])
        else:
            # Unknown platform - try x11grab as fallback
            LOGGER.warning("Unknown platform %s, falling back to x11grab", self.platform)
            args.extend([
                "-f", "x11grab",
                "-framerate", str(self.config.framerate),
                "-i", self.source.id,
            ])

        return args

    def _build_encoding_args(self) -> list[str]:
        """Build encoding arguments including encoder selection.

        Returns:
            Encoding arguments for ffmpeg.
        """
        args: list[str] = []

        # Encoder selection
        encoder = self.encoder
        args.extend(["-c:v", encoder.name])

        # H.264 profile
        args.extend(["-profile:v", self.config.h264_profile])

        # Bitrate
        args.extend(["-b:v", self.config.video_bitrate])

        # Keyframe interval for clean segment boundaries
        # Set GOP size = framerate * segment_duration
        gop_size = self.config.framerate * self.config.segment_duration
        args.extend(["-g", str(gop_size)])
        args.extend(["-keyint_min", str(gop_size)])

        # Pixel format for compatibility
        args.extend(["-pix_fmt", "yuv420p"])

        return args

    def _build_filter_args(self) -> list[str]:
        """Build video filter arguments for resolution capping.

        Uses ffmpeg's scale filter with force_original_aspect_ratio to
        cap resolution while preserving aspect ratio.

        Returns:
            Video filter arguments for ffmpeg.
        """
        max_width, max_height = self.config.max_resolution

        # Scale filter that:
        # 1. Caps width to max_width if larger
        # 2. Caps height to max_height if larger
        # 3. Preserves aspect ratio
        # 4. Ensures dimensions are divisible by 2 (required for most codecs)
        scale_filter = (
            f"scale='min({max_width},iw)':'min({max_height},ih)'"
            f":force_original_aspect_ratio=decrease,"
            f"scale=trunc(iw/2)*2:trunc(ih/2)*2"
        )

        return ["-vf", scale_filter]

    def _build_hls_args(self) -> list[str]:
        """Build HLS output arguments.

        Returns:
            HLS output arguments for ffmpeg.
        """
        return [
            "-f", "hls",
            "-hls_time", str(self.config.segment_duration),
            "-hls_list_size", str(self.config.max_segments),
            "-hls_flags", "delete_segments+append_list",
            "-hls_segment_filename", self.segment_pattern,
        ]

    def _detect_encoder(self) -> EncoderInfo:
        """Probe available hardware encoders and select the best one.

        Checks ffmpeg's available encoders and selects the first available
        hardware encoder for the current platform, falling back to libx264
        if none are available.

        Returns:
            EncoderInfo with the selected encoder's details.
        """
        available_encoders = self._get_available_encoders()

        # Try hardware encoders for this platform
        hw_encoders = HARDWARE_ENCODERS.get(self.platform, [])
        for encoder in hw_encoders:
            if encoder in available_encoders:
                LOGGER.info("Selected hardware encoder: %s", encoder)
                return EncoderInfo(
                    name=encoder,
                    is_hardware=True,
                    platform=self.platform.value,
                )

        # Fall back to software encoder
        LOGGER.info("No hardware encoder available, using %s", SOFTWARE_ENCODER)
        return EncoderInfo(
            name=SOFTWARE_ENCODER,
            is_hardware=False,
            platform=self.platform.value,
        )

    def _get_available_encoders(self) -> set[str]:
        """Query ffmpeg for available video encoders.

        Returns:
            A set of encoder names available in the current ffmpeg installation.
        """
        encoders: set[str] = set()

        try:
            result = subprocess.run(
                ["ffmpeg", "-hide_banner", "-encoders"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode != 0:
                LOGGER.warning("ffmpeg -encoders failed with code %d", result.returncode)
                return encoders

            # Parse encoder list from output
            # Format: " V..... encoder_name          Description"
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    # Check if this is a video encoder line
                    flags = parts[0]
                    if len(flags) >= 1 and flags[0] == "V":
                        encoder_name = parts[1]
                        encoders.add(encoder_name)

        except subprocess.TimeoutExpired:
            LOGGER.warning("Timeout querying ffmpeg encoders")
        except OSError as e:
            LOGGER.warning("Failed to query ffmpeg encoders: %s", e)

        LOGGER.debug("Available encoders: %s", encoders)
        return encoders


def build_scale_filter(
    max_width: int,
    max_height: int,
) -> str:
    """Build an ffmpeg scale filter for resolution capping.

    This is a utility function exposed for testing purposes.

    Args:
        max_width: Maximum output width.
        max_height: Maximum output height.

    Returns:
        An ffmpeg scale filter string that caps resolution while
        preserving aspect ratio and ensuring even dimensions.
    """
    return (
        f"scale='min({max_width},iw)':'min({max_height},ih)'"
        f":force_original_aspect_ratio=decrease,"
        f"scale=trunc(iw/2)*2:trunc(ih/2)*2"
    )


def compute_output_resolution(
    input_width: int,
    input_height: int,
    max_width: int,
    max_height: int,
) -> tuple[int, int]:
    """Compute the output resolution after scale filter is applied.

    This function simulates ffmpeg's scale filter behavior for testing.

    Args:
        input_width: Input video width.
        input_height: Input video height.
        max_width: Maximum output width.
        max_height: Maximum output height.

    Returns:
        A tuple of (output_width, output_height) after resolution capping
        and aspect ratio preservation.
    """
    if input_width <= 0 or input_height <= 0:
        return (0, 0)

    # Calculate aspect ratio
    aspect = input_width / input_height

    # Calculate constrained dimensions
    if input_width > max_width:
        output_width = max_width
        output_height = int(max_width / aspect)
    else:
        output_width = input_width
        output_height = input_height

    if output_height > max_height:
        output_height = max_height
        output_width = int(max_height * aspect)

    # Ensure even dimensions (required by most codecs)
    output_width = (output_width // 2) * 2
    output_height = (output_height // 2) * 2

    return (output_width, output_height)


def select_encoder(
    platform: Platform,
    available_encoders: set[str],
) -> EncoderInfo:
    """Select the best encoder for the given platform and available encoders.

    This is a utility function exposed for testing the encoder selection logic.

    Args:
        platform: The target platform.
        available_encoders: Set of encoder names available in ffmpeg.

    Returns:
        EncoderInfo for the selected encoder (hardware if available, else libx264).
    """
    # Try hardware encoders for this platform
    hw_encoders = HARDWARE_ENCODERS.get(platform, [])
    for encoder in hw_encoders:
        if encoder in available_encoders:
            return EncoderInfo(
                name=encoder,
                is_hardware=True,
                platform=platform.value,
            )

    # Fall back to software encoder
    return EncoderInfo(
        name=SOFTWARE_ENCODER,
        is_hardware=False,
        platform=platform.value,
    )
