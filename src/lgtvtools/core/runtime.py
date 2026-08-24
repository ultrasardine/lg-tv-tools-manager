"""Runtime feature detection for LG TV Tools.

This module provides runtime detection of available features based on
the current platform and installed dependencies. It enables the hybrid
architecture to adapt behavior for desktop vs mobile environments.
"""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass, field
from enum import Enum
from functools import cached_property
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lgtvtools.core.models import Capability


class RuntimeEnvironment(Enum):
    """Runtime environment classification."""

    DESKTOP_MACOS = "desktop_macos"
    DESKTOP_LINUX = "desktop_linux"
    DESKTOP_WINDOWS = "desktop_windows"
    MOBILE_IOS = "mobile_ios"
    MOBILE_ANDROID = "mobile_android"
    WEB = "web"
    UNKNOWN = "unknown"


@dataclass
class Runtime:
    """Runtime feature detection and capability flags.

    This class detects the current runtime environment and available
    features, enabling the application to adapt its behavior.

    Usage:
        runtime = Runtime.detect()
        if runtime.is_desktop:
            # Enable full feature set
        if runtime.has_ffmpeg:
            # Enable screen mirroring
    """

    environment: RuntimeEnvironment
    _capabilities: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def detect(cls) -> Runtime:
        """Detect the current runtime environment and capabilities.

        Returns:
            Runtime instance with detected environment and capabilities.
        """
        from lgtvtools.system.bundled import which as bundled_which

        env = cls._detect_environment()
        runtime = cls(environment=env)

        # Pre-detect common capabilities
        if runtime.is_desktop:
            runtime._capabilities["ffmpeg"] = bundled_which("ffmpeg") is not None
            runtime._capabilities["vlc"] = bundled_which("vlc") is not None
            runtime._capabilities["xdg_open"] = shutil.which("xdg-open") is not None

            # Check for optional Python packages
            runtime._capabilities["zeroconf"] = cls._check_import("zeroconf")
            runtime._capabilities["netifaces"] = cls._check_import("netifaces")
            runtime._capabilities["pyqt6"] = cls._check_import("PyQt6")

        return runtime

    @staticmethod
    def _detect_environment() -> RuntimeEnvironment:
        """Detect the runtime environment."""
        # Check for Flet mobile markers
        # Flet sets specific environment variables or uses different entry points
        if hasattr(sys, "_MEIPASS"):
            # PyInstaller bundle - could be desktop or mobile
            pass

        # Check platform
        if sys.platform == "darwin":
            # Could be macOS desktop or iOS
            # iOS would typically be detected via Flet's runtime
            try:
                import flet
                if hasattr(flet, "_is_mobile") and flet._is_mobile:  # type: ignore
                    return RuntimeEnvironment.MOBILE_IOS
            except (ImportError, AttributeError):
                pass
            return RuntimeEnvironment.DESKTOP_MACOS

        if sys.platform == "win32":
            return RuntimeEnvironment.DESKTOP_WINDOWS

        if sys.platform == "linux":
            # Check for Android
            # Android would typically be detected via Flet's runtime
            try:
                import flet
                if hasattr(flet, "_is_mobile") and flet._is_mobile:  # type: ignore
                    return RuntimeEnvironment.MOBILE_ANDROID
            except (ImportError, AttributeError):
                pass
            return RuntimeEnvironment.DESKTOP_LINUX

        # Check for web (Flet web target)
        if sys.platform == "emscripten":
            return RuntimeEnvironment.WEB

        return RuntimeEnvironment.UNKNOWN

    @staticmethod
    def _check_import(module_name: str) -> bool:
        """Check if a Python module can be imported."""
        try:
            __import__(module_name)
            return True
        except ImportError:
            return False

    # =========================================================================
    # Environment Properties
    # =========================================================================

    @property
    def is_desktop(self) -> bool:
        """True if running on a desktop platform."""
        return self.environment in (
            RuntimeEnvironment.DESKTOP_MACOS,
            RuntimeEnvironment.DESKTOP_LINUX,
            RuntimeEnvironment.DESKTOP_WINDOWS,
        )

    @property
    def is_mobile(self) -> bool:
        """True if running on a mobile platform."""
        return self.environment in (
            RuntimeEnvironment.MOBILE_IOS,
            RuntimeEnvironment.MOBILE_ANDROID,
        )

    @property
    def is_web(self) -> bool:
        """True if running in a web browser."""
        return self.environment == RuntimeEnvironment.WEB

    @property
    def is_macos(self) -> bool:
        """True if running on macOS."""
        return self.environment == RuntimeEnvironment.DESKTOP_MACOS

    @property
    def is_linux(self) -> bool:
        """True if running on Linux desktop."""
        return self.environment == RuntimeEnvironment.DESKTOP_LINUX

    @property
    def is_windows(self) -> bool:
        """True if running on Windows."""
        return self.environment == RuntimeEnvironment.DESKTOP_WINDOWS

    @property
    def is_ios(self) -> bool:
        """True if running on iOS."""
        return self.environment == RuntimeEnvironment.MOBILE_IOS

    @property
    def is_android(self) -> bool:
        """True if running on Android."""
        return self.environment == RuntimeEnvironment.MOBILE_ANDROID

    # =========================================================================
    # Feature Detection
    # =========================================================================

    @property
    def has_ffmpeg(self) -> bool:
        """True if ffmpeg is available for screen capture."""
        return self._capabilities.get("ffmpeg", False)

    @property
    def has_vlc(self) -> bool:
        """True if VLC is available for media playback."""
        return self._capabilities.get("vlc", False)

    @property
    def has_zeroconf(self) -> bool:
        """True if zeroconf (mDNS) is available."""
        return self._capabilities.get("zeroconf", False)

    @property
    def has_netifaces(self) -> bool:
        """True if netifaces is available for network enumeration."""
        return self._capabilities.get("netifaces", False)

    @property
    def has_pyqt6(self) -> bool:
        """True if PyQt6 is available (legacy UI)."""
        return self._capabilities.get("pyqt6", False)

    # =========================================================================
    # Feature Availability
    # =========================================================================

    @property
    def can_mirror(self) -> bool:
        """True if screen mirroring is possible.

        Requires:
        - Desktop platform
        - ffmpeg installed
        """
        return self.is_desktop and self.has_ffmpeg

    @property
    def can_discover_mdns(self) -> bool:
        """True if mDNS discovery is available.

        Desktop: Requires zeroconf
        Mobile: Uses native APIs (always available on supported platforms)
        """
        if self.is_desktop:
            return self.has_zeroconf
        return self.is_mobile  # Native mDNS on iOS/Android

    @property
    def can_discover_ssdp(self) -> bool:
        """True if SSDP discovery is available.

        Requires UDP socket access. Available on desktop, may require
        permissions on mobile.
        """
        return self.is_desktop or self.is_mobile

    @property
    def can_share_media(self) -> bool:
        """True if local media sharing (HTTP server) is possible.

        Requires desktop platform for reliable background server.
        """
        return self.is_desktop

    @property
    def can_launch_external(self) -> bool:
        """True if external tool launching is possible.

        Desktop only - subprocess access required.
        """
        return self.is_desktop

    @cached_property
    def supported_features(self) -> list[str]:
        """List of supported features in the current runtime."""
        features = ["tv_discovery_ssdp", "webos_pairing", "webos_control", "cast_url"]

        if self.can_discover_mdns:
            features.append("tv_discovery_mdns")

        if self.can_mirror:
            features.append("screen_mirror")

        if self.can_share_media:
            features.append("media_share")

        if self.can_launch_external:
            features.append("external_tools")

        if self.is_desktop:
            features.append("file_picker")
            features.append("clipboard")

        return features

    def check_capability(self, name: str) -> bool:
        """Check if a specific capability is available.

        Args:
            name: Capability name (e.g., "ffmpeg", "zeroconf").

        Returns:
            True if the capability is available.
        """
        if name in self._capabilities:
            return self._capabilities[name]

        # Try to detect on-demand
        if name.startswith("cmd:"):
            from lgtvtools.system.bundled import which as bundled_which

            cmd = name[4:]
            result = bundled_which(cmd) is not None
            self._capabilities[name] = result
            return result

        if name.startswith("pkg:"):
            pkg = name[4:]
            result = self._check_import(pkg)
            self._capabilities[name] = result
            return result

        return False

    def get_capabilities_report(self) -> list[Capability]:
        """Get a full capabilities report.

        Returns:
            List of Capability objects for UI display.
        """
        from lgtvtools.core.models import Capability

        capabilities = []

        if self.is_desktop:
            capabilities.extend([
                Capability(
                    name="ffmpeg",
                    installed=self.has_ffmpeg,
                    hint="Required for screen mirroring. Install via package manager.",
                    required_for=["screen_mirror"],
                ),
                Capability(
                    name="VLC",
                    installed=self.has_vlc,
                    hint="Optional media player. Install via package manager.",
                    required_for=["media_playback"],
                ),
                Capability(
                    name="zeroconf",
                    installed=self.has_zeroconf,
                    hint="Python package for mDNS discovery.",
                    required_for=["tv_discovery_mdns"],
                ),
                Capability(
                    name="netifaces",
                    installed=self.has_netifaces,
                    hint="Python package for network interface enumeration.",
                    required_for=["network_detection"],
                ),
            ])

            # Platform-specific capabilities
            if self.is_linux:
                from lgtvtools.system.bundled import which as bundled_which

                gnd = bundled_which("gnome-network-displays") is not None
                capabilities.append(Capability(
                    name="gnome-network-displays",
                    installed=gnd,
                    hint="For Miracast streaming. Install via package manager.",
                    required_for=["miracast"],
                ))

        return capabilities

    def __repr__(self) -> str:
        return f"Runtime({self.environment.value}, features={self.supported_features})"
