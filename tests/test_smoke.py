"""Smoke tests for module imports and basic functionality."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def test_package_version() -> None:
    """Test that the package version is accessible."""
    import lgtvtools

    assert lgtvtools.__version__ == "0.3.0"


def test_core_imports() -> None:
    """Test that core module imports work."""
    from lgtvtools.core import LGTVDevice, WebOSResult, Runtime, discover_lg_tvs

    assert LGTVDevice is not None
    assert WebOSResult is not None
    assert Runtime is not None
    assert callable(discover_lg_tvs)


def test_core_models() -> None:
    """Test core model imports."""
    from lgtvtools.core.models import (
        LGTVDevice,
        WebOSResult,
        UPnPResult,
        UPnPStatus,
        MirrorState,
        CaptureSource,
        CaptureConfig,
        MirrorResult,
        Capability,
        AppState,
    )

    # Test LGTVDevice
    device = LGTVDevice(
        usn="test-usn",
        name="Test TV",
        ip="192.168.1.100",
        location="http://192.168.1.100:1234/",
    )
    assert device.display_name() == "Test TV - 192.168.1.100"
    assert device.ip == "192.168.1.100"

    # Test WebOSResult
    result = WebOSResult(ok=True, message="Success")
    assert result.ok
    assert result.message == "Success"

    # Test UPnPStatus
    assert UPnPStatus.SUCCESS.value == "success"

    # Test MirrorState
    assert MirrorState.IDLE.value == "idle"
    assert MirrorState.STREAMING.value == "streaming"

    # Test CaptureSource
    source = CaptureSource(id="1", name="Screen 1", kind="screen")
    assert source.kind == "screen"

    # Test CaptureConfig
    config = CaptureConfig()
    assert config.framerate == 30
    assert config.max_resolution == (1920, 1080)

    # Test AppState
    state = AppState()
    assert state.devices == []
    assert state.selected_device is None
    assert not state.is_scanning


def test_core_runtime() -> None:
    """Test runtime detection."""
    from lgtvtools.core.runtime import Runtime, RuntimeEnvironment

    runtime = Runtime.detect()
    assert runtime is not None
    assert runtime.environment in RuntimeEnvironment
    assert isinstance(runtime.is_desktop, bool)
    assert isinstance(runtime.is_mobile, bool)
    assert isinstance(runtime.supported_features, list)


def test_core_discovery_imports() -> None:
    """Test discovery module imports."""
    from lgtvtools.core.discovery import discover_lg_tvs, discover_lg_tvs_ssdp
    from lgtvtools.core.discovery.ssdp import discover_lg_tvs as ssdp_discover
    from lgtvtools.core.discovery.upnp import cast_media_to_device, UPnPService

    assert callable(discover_lg_tvs)
    assert callable(discover_lg_tvs_ssdp)
    assert callable(ssdp_discover)
    assert callable(cast_media_to_device)
    assert UPnPService is not None


def test_core_webos_imports() -> None:
    """Test WebOS client imports."""
    from lgtvtools.core.webos import (
        WebOSClient,
        connect_to_tv,
        SSAP_LAUNCH,
        SSAP_TOAST,
        APP_BROWSER,
    )

    assert WebOSClient is not None
    assert callable(connect_to_tv)
    assert SSAP_LAUNCH == "ssap://system.launcher/launch"
    assert SSAP_TOAST == "ssap://system.notifications/createToast"
    assert APP_BROWSER == "com.webos.app.browser"


def test_desktop_imports() -> None:
    """Test desktop module imports."""
    from lgtvtools.desktop import launch_external, MediaShareServer

    assert callable(launch_external)
    assert MediaShareServer is not None


def test_desktop_launchers() -> None:
    """Test desktop launcher functions."""
    from lgtvtools.desktop.actions.launchers import (
        which,
        launch_external,
        open_file_with_default_app,
        open_url_in_browser,
        LaunchResult,
    )

    assert callable(which)
    assert callable(launch_external)
    assert callable(open_file_with_default_app)
    assert callable(open_url_in_browser)

    # Test LaunchResult
    result = LaunchResult(ok=True, message="Success")
    assert result.ok
    assert result.message == "Success"


def test_desktop_media_share() -> None:
    """Test media share server."""
    from lgtvtools.desktop.actions.media_share import MediaShareServer

    server = MediaShareServer()
    assert not server.is_running
    assert server.port == 0
    server.close()


def test_flet_ui_imports() -> None:
    """Test Flet UI module imports."""
    from lgtvtools.flet_ui import AppTheme
    from lgtvtools.flet_ui.theme import AppColors, Styles
    from lgtvtools.flet_ui.state import StateManager, UIState

    assert AppTheme is not None
    assert AppColors.BACKGROUND == "#111319"
    assert Styles is not None
    assert StateManager is not None
    assert UIState is not None


def test_flet_state_manager() -> None:
    """Test Flet state manager."""
    from lgtvtools.flet_ui.state import StateManager
    from lgtvtools.core.models import LGTVDevice

    manager = StateManager()
    assert manager.state is not None
    assert not manager.has_selected_device()

    # Test device selection
    device = LGTVDevice(
        usn="test",
        name="Test TV",
        ip="192.168.1.100",
        location="http://192.168.1.100/",
    )
    manager.set_devices([device])
    assert len(manager.state.devices) == 1

    manager.set_selected_device(device)
    assert manager.has_selected_device()
    assert manager.get_selected_device_name() == "Test TV - 192.168.1.100"

    # Test logging
    manager.log("Test message")
    assert "Test message" in manager.state.log_messages


def test_legacy_imports() -> None:
    """Test that legacy imports still work (with optional dependencies)."""
    from lgtvtools.discovery import ssdp
    from lgtvtools.discovery.models import LGTVDevice

    assert callable(ssdp.discover_lg_tvs)
    assert LGTVDevice is not None

    # UPnP should always work
    from lgtvtools.discovery import upnp
    assert callable(upnp.cast_media_to_device)


def test_legacy_ui_import() -> None:
    """Test legacy UI module import (requires PyQt6)."""
    try:
        from lgtvtools.ui import main_window

        assert hasattr(main_window, "MainWindow")
    except ImportError:
        # PyQt6 not installed, skip test
        pass
