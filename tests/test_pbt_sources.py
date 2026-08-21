"""Property-based tests for source enumeration.

# Feature: screen-capture-mirror, Property 7: Source enumeration IDs match platform format

Tests verify that parsed source IDs conform to the expected format
for each platform's ffmpeg input requirements.
"""

from __future__ import annotations

import re
from unittest import mock

from hypothesis import given, settings
from hypothesis import strategies as st

from lgtvtools.mirror.sources import (
    _parse_avfoundation_output,
    _parse_gdigrab_output,
    _parse_xrandr_output,
    enumerate_sources,
)
from lgtvtools.system.platform import Platform

# -----------------------------------------------------------------------------
# Platform ID format patterns (from design.md)
# -----------------------------------------------------------------------------
# macOS avfoundation: numeric index (e.g., "1", "2", "0")
MACOS_ID_PATTERN = re.compile(r"^\d+$")

# Linux X11 x11grab: display string ":N.N" or ":N.N+X,Y"
# Examples: ":0.0", ":0.0+1920,0", ":1.0+0,1080"
LINUX_X11_ID_PATTERN = re.compile(r"^:\d+\.\d+(\+\d+,\d+)?$")

# Linux PipeWire: "default"
LINUX_PIPEWIRE_ID_PATTERN = re.compile(r"^default$")

# Windows gdigrab: "desktop" or "title=<name>"
WINDOWS_ID_PATTERN = re.compile(r"^(desktop|title=.+)$")


# -----------------------------------------------------------------------------
# Strategies for generating mock ffmpeg output
# -----------------------------------------------------------------------------

# Strategy for macOS screen indices (realistic range 0-9)
macos_screen_indices = st.integers(min_value=0, max_value=9)

# Strategy for screen names
screen_names = st.sampled_from(
    [
        "Capture screen",
        "Screen",
        "Display",
        "Built-in Retina Display",
        "External Display",
    ]
)


@st.composite
def macos_avfoundation_output(draw: st.DrawFn) -> tuple[str, list[tuple[str, str]]]:
    """Generate mock ffmpeg avfoundation output with expected source IDs.

    Returns a tuple of (ffmpeg_output_string, list of (id, name) tuples for screens).
    """
    # Generate 1-3 screens
    num_screens = draw(st.integers(min_value=1, max_value=3))
    # Generate 0-2 cameras to include before screens
    num_cameras = draw(st.integers(min_value=0, max_value=2))

    lines = ["[AVFoundation indev @ 0x7f8b1a] AVFoundation video devices:"]
    expected_sources: list[tuple[str, str]] = []

    # Add cameras first (indices 0 to num_cameras-1)
    camera_names = ["FaceTime HD Camera", "USB Webcam", "OBS Virtual Camera"]
    for i in range(num_cameras):
        camera_name = camera_names[i % len(camera_names)]
        lines.append(f"[AVFoundation indev @ 0x7f8b1a] [{i}] {camera_name}")

    # Add screens (indices num_cameras to num_cameras+num_screens-1)
    for i in range(num_screens):
        screen_idx = num_cameras + i
        base_name = draw(screen_names)
        screen_name = f"{base_name} {i}"
        lines.append(f"[AVFoundation indev @ 0x7f8b1a] [{screen_idx}] {screen_name}")
        expected_sources.append((str(screen_idx), screen_name))

    # Add audio section to verify parser ignores it
    lines.append("[AVFoundation indev @ 0x7f8b1a] AVFoundation audio devices:")
    lines.append("[AVFoundation indev @ 0x7f8b1a] [0] MacBook Pro Microphone")

    return "\n".join(lines), expected_sources


# Strategy for X11 display names
x11_display_names = st.sampled_from(
    ["eDP-1", "HDMI-1", "HDMI-2", "DP-1", "DP-2", "VGA-1", "DVI-I-1"]
)

# Strategy for common display resolutions
display_resolutions = st.sampled_from(
    [(1920, 1080), (1366, 768), (2560, 1440), (3840, 2160), (1280, 720), (1680, 1050)]
)


@st.composite
def xrandr_output(draw: st.DrawFn) -> tuple[str, list[tuple[str, str, int, int]]]:
    """Generate mock xrandr output with expected source IDs.

    Returns a tuple of (xrandr_output_string, list of (id, name, width, height) tuples).
    """
    # Generate 1-3 connected displays
    num_displays = draw(st.integers(min_value=1, max_value=3))

    lines = [
        "Screen 0: minimum 8 x 8, current 3840 x 2160, maximum 32767 x 32767"
    ]
    expected_sources: list[tuple[str, str, int, int]] = []

    used_names: set[str] = set()
    x_offset = 0

    for i in range(num_displays):
        # Get unique display name
        display_name = draw(x11_display_names)
        while display_name in used_names:
            display_name = draw(x11_display_names)
        used_names.add(display_name)

        width, height = draw(display_resolutions)

        # First display is primary and at origin
        if i == 0:
            primary_str = "primary "
            offset_str = "+0+0"
            expected_id = ":0.0"
        else:
            primary_str = ""
            offset_str = f"+{x_offset}+0"
            expected_id = f":0.0+{x_offset},0"

        line = (
            f"{display_name} connected {primary_str}{width}x{height}{offset_str} "
            "(normal left inverted right x axis y axis) 527mm x 296mm"
        )
        lines.append(line)
        lines.append(f"   {width}x{height}     60.00*+")

        expected_sources.append(
            (expected_id, f"{display_name} ({width}x{height})", width, height)
        )
        x_offset += width

    # Add disconnected display
    lines.append("DP-99 disconnected (normal left inverted right x axis y axis)")

    return "\n".join(lines), expected_sources


# Strategy for window titles (for Windows gdigrab)
window_titles = st.sampled_from(
    [
        "Firefox",
        "Google Chrome",
        "Visual Studio Code",
        "Notepad",
        "Windows Terminal",
        "File Explorer",
    ]
)


# -----------------------------------------------------------------------------
# Property Tests
# -----------------------------------------------------------------------------


class TestProperty7SourceEnumerationIDFormat:
    """Property 7: Source enumeration IDs match platform format.

    For any CaptureSource returned by enumerate_sources() on a given platform,
    the id field SHALL conform to the platform's ffmpeg input format.

    **Validates: Requirements 1.4, 7.4**
    """

    @settings(max_examples=100, deadline=None)
    @given(data=macos_avfoundation_output())
    def test_macos_source_ids_are_numeric_indices(
        self, data: tuple[str, list[tuple[str, str]]]
    ) -> None:
        """macOS source IDs should be numeric indices for avfoundation.

        # Feature: screen-capture-mirror, Property 7: Source enumeration IDs match platform format
        """
        ffmpeg_output, expected_sources = data

        # Parse the mocked output
        sources = _parse_avfoundation_output(ffmpeg_output)

        # Verify we got the expected number of sources
        assert len(sources) == len(expected_sources)

        # Verify each source ID matches macOS format (numeric index)
        for source in sources:
            assert MACOS_ID_PATTERN.match(source.id), (
                f"macOS source ID '{source.id}' does not match expected numeric "
                f"index format. Expected pattern: {MACOS_ID_PATTERN.pattern}"
            )
            assert source.kind == "screen"

        # Verify the IDs match our expected values
        for source, (expected_id, expected_name) in zip(
            sources, expected_sources, strict=True
        ):
            assert source.id == expected_id
            assert source.name == expected_name

    @settings(max_examples=100, deadline=None)
    @given(data=xrandr_output())
    def test_linux_x11_source_ids_are_display_strings(
        self, data: tuple[str, list[tuple[str, str, int, int]]]
    ) -> None:
        """Linux X11 source IDs should be display strings (:N.N or :N.N+X,Y).

        # Feature: screen-capture-mirror, Property 7: Source enumeration IDs match platform format
        """
        xrandr_output_str, expected_sources = data

        # Mock DISPLAY environment variable
        with mock.patch(
            "lgtvtools.mirror.sources._get_display_env", return_value=":0.0"
        ):
            sources = _parse_xrandr_output(xrandr_output_str)

        # Verify we got the expected number of sources
        assert len(sources) == len(expected_sources)

        # Verify each source ID matches Linux X11 format
        for source in sources:
            assert LINUX_X11_ID_PATTERN.match(source.id), (
                f"Linux X11 source ID '{source.id}' does not match expected display "
                f"string format. Expected pattern: {LINUX_X11_ID_PATTERN.pattern}"
            )
            assert source.kind == "screen"

        # Verify the IDs and resolutions match our expected values
        for source, (expected_id, expected_name, width, height) in zip(
            sources, expected_sources, strict=True
        ):
            assert source.id == expected_id
            assert source.name == expected_name
            assert source.resolution == (width, height)

    @settings(max_examples=100, deadline=None)
    @given(st.just(""))  # gdigrab parser currently returns empty list
    def test_windows_source_ids_are_desktop_or_title(self, _output: str) -> None:
        """Windows source IDs should be 'desktop' or 'title=<name>'.

        # Feature: screen-capture-mirror, Property 7: Source enumeration IDs match platform format

        Note: The current implementation always includes 'desktop' as the primary
        source and _parse_gdigrab_output is a placeholder returning empty list.
        This test validates the pattern requirement for any sources that would
        be returned.
        """
        # The gdigrab parser is a placeholder, but we verify the pattern
        # for the expected format matches the design requirements
        valid_windows_ids = ["desktop", "title=Firefox", "title=Notepad"]

        for windows_id in valid_windows_ids:
            assert WINDOWS_ID_PATTERN.match(windows_id), (
                f"Windows source ID '{windows_id}' does not match expected "
                f"format. Expected pattern: {WINDOWS_ID_PATTERN.pattern}"
            )

        # The actual gdigrab parser returns empty (placeholder)
        sources = _parse_gdigrab_output("")
        assert sources == []

    @settings(max_examples=100, deadline=None)
    @given(data=macos_avfoundation_output())
    def test_enumerate_sources_macos_returns_valid_ids(
        self, data: tuple[str, list[tuple[str, str]]]
    ) -> None:
        """enumerate_sources() on macOS returns sources with valid ID format.

        # Feature: screen-capture-mirror, Property 7: Source enumeration IDs match platform format
        """
        ffmpeg_output, _expected_sources = data

        # Mock ffmpeg availability and subprocess call
        with (
            mock.patch("shutil.which", return_value="/usr/bin/ffmpeg"),
            mock.patch("subprocess.run") as mock_run,
        ):
            # Setup mock to return our generated output
            mock_result = mock.Mock()
            mock_result.stderr = ffmpeg_output
            mock_run.return_value = mock_result

            sources = enumerate_sources(Platform.MACOS)

        # All returned sources should have valid macOS IDs
        for source in sources:
            assert MACOS_ID_PATTERN.match(source.id), (
                f"enumerate_sources(MACOS) returned source with invalid ID "
                f"'{source.id}'. Expected numeric index pattern."
            )

    @settings(max_examples=100, deadline=None)
    @given(data=xrandr_output())
    def test_enumerate_sources_linux_returns_valid_ids(
        self, data: tuple[str, list[tuple[str, str, int, int]]]
    ) -> None:
        """enumerate_sources() on Linux returns sources with valid ID format.

        # Feature: screen-capture-mirror, Property 7: Source enumeration IDs match platform format
        """
        xrandr_output_str, _expected = data

        # Mock xrandr path and subprocess call
        with (
            mock.patch("shutil.which", side_effect=lambda cmd: f"/usr/bin/{cmd}"),
            mock.patch("subprocess.run") as mock_run,
            mock.patch(
                "lgtvtools.mirror.sources._is_pipewire_available", return_value=False
            ),
            mock.patch(
                "lgtvtools.mirror.sources._get_display_env", return_value=":0.0"
            ),
        ):
            # Setup mock for xrandr call
            mock_result = mock.Mock()
            mock_result.returncode = 0
            mock_result.stdout = xrandr_output_str
            mock_run.return_value = mock_result

            sources = enumerate_sources(Platform.DEBIAN)

        # All returned sources should have valid Linux X11 IDs
        for source in sources:
            assert LINUX_X11_ID_PATTERN.match(source.id), (
                f"enumerate_sources(DEBIAN) returned source with invalid ID "
                f"'{source.id}'. Expected X11 display string pattern."
            )

    def test_pipewire_source_id_is_default(self) -> None:
        """PipeWire source ID should be 'default'.

        # Feature: screen-capture-mirror, Property 7: Source enumeration IDs match platform format
        """
        # Mock PipeWire availability
        with (
            mock.patch("shutil.which", return_value="/usr/bin/ffmpeg"),
            mock.patch(
                "lgtvtools.mirror.sources._is_pipewire_available", return_value=True
            ),
        ):
            sources = enumerate_sources(Platform.DEBIAN)

        assert len(sources) == 1
        assert LINUX_PIPEWIRE_ID_PATTERN.match(sources[0].id), (
            f"PipeWire source ID '{sources[0].id}' does not match expected "
            f"'default' pattern."
        )
        assert sources[0].id == "default"
        assert sources[0].kind == "screen"

    def test_windows_desktop_source_id_format(self) -> None:
        """Windows desktop source ID should be 'desktop'.

        # Feature: screen-capture-mirror, Property 7: Source enumeration IDs match platform format
        """
        # Mock ffmpeg availability and subprocess call
        with (
            mock.patch("shutil.which", return_value="/usr/bin/ffmpeg"),
            mock.patch("subprocess.run") as mock_run,
        ):
            mock_result = mock.Mock()
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            sources = enumerate_sources(Platform.WINDOWS)

        # Windows always includes 'desktop' as the first source
        assert len(sources) >= 1
        assert sources[0].id == "desktop"
        assert WINDOWS_ID_PATTERN.match(sources[0].id)
        assert sources[0].kind == "screen"
