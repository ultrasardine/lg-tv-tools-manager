"""Unit tests for the sources module.

Tests cover the parsing logic for platform-specific ffmpeg output
and the main enumerate_sources() function.
"""

from __future__ import annotations

import shutil
from unittest import mock

from lgtvtools.mirror.models import CaptureSource
from lgtvtools.mirror.sources import (
    _is_screen_device,
    _parse_avfoundation_output,
    _parse_xrandr_output,
    enumerate_sources,
)
from lgtvtools.system.platform import Platform


class TestIsScreenDevice:
    """Tests for the _is_screen_device helper function."""

    def test_capture_screen_is_screen(self) -> None:
        assert _is_screen_device("Capture screen 0") is True

    def test_display_is_screen(self) -> None:
        assert _is_screen_device("Display 1") is True

    def test_screen_is_screen(self) -> None:
        assert _is_screen_device("Screen") is True

    def test_facetime_camera_is_not_screen(self) -> None:
        assert _is_screen_device("FaceTime HD Camera") is False

    def test_webcam_is_not_screen(self) -> None:
        assert _is_screen_device("USB Webcam") is False

    def test_isight_is_not_screen(self) -> None:
        assert _is_screen_device("Built-in iSight") is False


class TestParseAvfoundationOutput:
    """Tests for parsing ffmpeg avfoundation device list output."""

    def test_parse_single_screen(self) -> None:
        output = """[AVFoundation indev @ 0x7f8b1a] AVFoundation video devices:
[AVFoundation indev @ 0x7f8b1a] [0] FaceTime HD Camera
[AVFoundation indev @ 0x7f8b1a] [1] Capture screen 0
[AVFoundation indev @ 0x7f8b1a] AVFoundation audio devices:
[AVFoundation indev @ 0x7f8b1a] [0] MacBook Pro Microphone"""

        sources = _parse_avfoundation_output(output)

        assert len(sources) == 1
        assert sources[0].id == "1"
        assert sources[0].name == "Capture screen 0"
        assert sources[0].kind == "screen"
        assert sources[0].resolution is None

    def test_parse_multiple_screens(self) -> None:
        output = """[AVFoundation indev @ 0x7f8b1a] AVFoundation video devices:
[AVFoundation indev @ 0x7f8b1a] [0] FaceTime HD Camera
[AVFoundation indev @ 0x7f8b1a] [1] Capture screen 0
[AVFoundation indev @ 0x7f8b1a] [2] Capture screen 1
[AVFoundation indev @ 0x7f8b1a] [3] Capture screen 2
[AVFoundation indev @ 0x7f8b1a] AVFoundation audio devices:
[AVFoundation indev @ 0x7f8b1a] [0] MacBook Pro Microphone"""

        sources = _parse_avfoundation_output(output)

        assert len(sources) == 3
        assert sources[0].id == "1"
        assert sources[0].name == "Capture screen 0"
        assert sources[1].id == "2"
        assert sources[1].name == "Capture screen 1"
        assert sources[2].id == "3"
        assert sources[2].name == "Capture screen 2"

    def test_parse_skips_cameras(self) -> None:
        output = """[AVFoundation indev @ 0x7f8b1a] AVFoundation video devices:
[AVFoundation indev @ 0x7f8b1a] [0] FaceTime HD Camera
[AVFoundation indev @ 0x7f8b1a] [1] USB Webcam
[AVFoundation indev @ 0x7f8b1a] [2] Capture screen 0
[AVFoundation indev @ 0x7f8b1a] AVFoundation audio devices:
[AVFoundation indev @ 0x7f8b1a] [0] MacBook Pro Microphone"""

        sources = _parse_avfoundation_output(output)

        assert len(sources) == 1
        assert sources[0].id == "2"
        assert sources[0].name == "Capture screen 0"

    def test_parse_empty_output(self) -> None:
        sources = _parse_avfoundation_output("")
        assert sources == []

    def test_parse_no_video_devices(self) -> None:
        output = """[AVFoundation indev @ 0x7f8b1a] AVFoundation audio devices:
[AVFoundation indev @ 0x7f8b1a] [0] MacBook Pro Microphone"""

        sources = _parse_avfoundation_output(output)
        assert sources == []

    def test_parse_ignores_audio_section(self) -> None:
        output = """[AVFoundation indev @ 0x7f8b1a] AVFoundation video devices:
[AVFoundation indev @ 0x7f8b1a] [0] Capture screen 0
[AVFoundation indev @ 0x7f8b1a] AVFoundation audio devices:
[AVFoundation indev @ 0x7f8b1a] [0] Display Audio
[AVFoundation indev @ 0x7f8b1a] [1] Screen Audio"""

        sources = _parse_avfoundation_output(output)

        # Should only have the one video device, not the audio devices
        assert len(sources) == 1
        assert sources[0].name == "Capture screen 0"


class TestParseXrandrOutput:
    """Tests for parsing xrandr output for X11 displays."""

    def test_parse_single_display(self) -> None:
        output = """Screen 0: minimum 8 x 8, current 1920 x 1080, maximum 32767 x 32767
eDP-1 connected primary 1920x1080+0+0 (normal left inverted right x axis y axis) 309mm x 174mm
   1920x1080     60.00*+  59.97
   1680x1050     59.95
DP-1 disconnected (normal left inverted right x axis y axis)"""

        with mock.patch(
            "lgtvtools.mirror.sources._get_display_env", return_value=":0.0"
        ):
            sources = _parse_xrandr_output(output)

        assert len(sources) == 1
        assert sources[0].id == ":0.0"
        assert sources[0].name == "eDP-1 (1920x1080)"
        assert sources[0].kind == "screen"
        assert sources[0].resolution == (1920, 1080)

    def test_parse_multiple_displays(self) -> None:
        output = """Screen 0: minimum 8 x 8, current 3840 x 1080, maximum 32767 x 32767
eDP-1 connected primary 1920x1080+0+0 (normal left inverted right x axis y axis) 309mm x 174mm
   1920x1080     60.00*+
HDMI-1 connected 1920x1080+1920+0 (normal left inverted right x axis y axis) 527mm x 296mm
   1920x1080     60.00*+  50.00
DP-1 disconnected (normal left inverted right x axis y axis)"""

        with mock.patch(
            "lgtvtools.mirror.sources._get_display_env", return_value=":0.0"
        ):
            sources = _parse_xrandr_output(output)

        assert len(sources) == 2
        # Primary display at origin
        assert sources[0].id == ":0.0"
        assert sources[0].name == "eDP-1 (1920x1080)"
        # Secondary display with offset
        assert sources[1].id == ":0.0+1920,0"
        assert sources[1].name == "HDMI-1 (1920x1080)"

    def test_parse_display_without_primary(self) -> None:
        output = """Screen 0: minimum 8 x 8, current 1920 x 1080, maximum 32767 x 32767
HDMI-1 connected 1920x1080+0+0 (normal left inverted right x axis y axis) 527mm x 296mm
   1920x1080     60.00*+"""

        with mock.patch(
            "lgtvtools.mirror.sources._get_display_env", return_value=":0.0"
        ):
            sources = _parse_xrandr_output(output)

        assert len(sources) == 1
        assert sources[0].id == ":0.0"
        assert sources[0].name == "HDMI-1 (1920x1080)"

    def test_parse_empty_output(self) -> None:
        with mock.patch(
            "lgtvtools.mirror.sources._get_display_env", return_value=":0.0"
        ):
            sources = _parse_xrandr_output("")
        assert sources == []

    def test_parse_no_connected_displays(self) -> None:
        output = """Screen 0: minimum 8 x 8, current 1920 x 1080, maximum 32767 x 32767
eDP-1 disconnected (normal left inverted right x axis y axis)
HDMI-1 disconnected (normal left inverted right x axis y axis)"""

        with mock.patch(
            "lgtvtools.mirror.sources._get_display_env", return_value=":0.0"
        ):
            sources = _parse_xrandr_output(output)
        assert sources == []


class TestEnumerateSources:
    """Tests for the main enumerate_sources function."""

    def test_returns_empty_when_ffmpeg_not_found(self) -> None:
        with mock.patch.object(shutil, "which", return_value=None):
            sources = enumerate_sources(Platform.MACOS)
        assert sources == []

    def test_returns_empty_for_unknown_platform(self) -> None:
        with mock.patch.object(shutil, "which", return_value="/usr/bin/ffmpeg"):
            sources = enumerate_sources(Platform.UNKNOWN)
        assert sources == []

    def test_macos_calls_enumerate_macos_sources(self) -> None:
        expected = [CaptureSource(id="1", name="Capture screen 0", kind="screen")]
        with (
            mock.patch.object(shutil, "which", return_value="/usr/bin/ffmpeg"),
            mock.patch(
                "lgtvtools.mirror.sources._enumerate_macos_sources",
                return_value=expected,
            ),
        ):
            sources = enumerate_sources(Platform.MACOS)
        assert sources == expected

    def test_debian_calls_enumerate_linux_sources(self) -> None:
        expected = [CaptureSource(id=":0.0", name="eDP-1 (1920x1080)", kind="screen")]
        with (
            mock.patch.object(shutil, "which", return_value="/usr/bin/ffmpeg"),
            mock.patch(
                "lgtvtools.mirror.sources._enumerate_linux_sources",
                return_value=expected,
            ),
        ):
            sources = enumerate_sources(Platform.DEBIAN)
        assert sources == expected

    def test_rhel_calls_enumerate_linux_sources(self) -> None:
        expected = [CaptureSource(id=":0.0", name="eDP-1 (1920x1080)", kind="screen")]
        with (
            mock.patch.object(shutil, "which", return_value="/usr/bin/ffmpeg"),
            mock.patch(
                "lgtvtools.mirror.sources._enumerate_linux_sources",
                return_value=expected,
            ),
        ):
            sources = enumerate_sources(Platform.RHEL)
        assert sources == expected

    def test_windows_calls_enumerate_windows_sources(self) -> None:
        expected = [CaptureSource(id="desktop", name="Entire Desktop", kind="screen")]
        with (
            mock.patch.object(shutil, "which", return_value="/usr/bin/ffmpeg"),
            mock.patch(
                "lgtvtools.mirror.sources._enumerate_windows_sources",
                return_value=expected,
            ),
        ):
            sources = enumerate_sources(Platform.WINDOWS)
        assert sources == expected
