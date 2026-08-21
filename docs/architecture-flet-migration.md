# Flet Migration Architecture

## Overview

This document describes the hybrid architecture for migrating LG TV Tools from PyQt6 to Flet, supporting both desktop (full features) and mobile (remote-control subset) builds from a shared codebase.

## Package Structure

```
src/lgtvtools/
├── __init__.py              # Package root
├── core/                    # SHARED: Platform-agnostic core
│   ├── __init__.py
│   ├── models.py            # All data models (LGTVDevice, CaptureSource, etc.)
│   ├── discovery/           # TV discovery (SSDP + mDNS abstraction)
│   │   ├── __init__.py
│   │   ├── ssdp.py          # SSDP implementation
│   │   ├── mdns.py          # mDNS abstraction (desktop: zeroconf, mobile: native)
│   │   └── upnp.py          # UPnP/DLNA control
│   ├── webos/               # WebOS WebSocket client (async)
│   │   ├── __init__.py
│   │   └── client.py        # Async SSAP client
│   └── runtime.py           # Runtime feature detection
│
├── desktop/                 # DESKTOP-ONLY: Full feature set
│   ├── __init__.py
│   ├── mirror/              # Screen mirroring (ffmpeg, HLS)
│   │   ├── __init__.py
│   │   ├── capture.py       # ffmpeg pipeline
│   │   ├── hls_server.py    # HLS HTTP server
│   │   ├── session.py       # Mirror session orchestrator
│   │   ├── sources.py       # Screen/window enumeration
│   │   └── worker.py        # Background thread wrapper
│   ├── actions/             # Desktop-only actions
│   │   ├── __init__.py
│   │   ├── launchers.py     # External tool launchers
│   │   ├── media_share.py   # Local HTTP media server
│   │   └── file_ops.py      # File dialogs, clipboard
│   └── capabilities.py      # Desktop dependency detection
│
├── flet_ui/                 # SHARED: Flet UI components
│   ├── __init__.py
│   ├── app.py               # Flet app entry point
│   ├── theme.py             # Flet theme definitions
│   ├── components/          # Reusable UI components
│   │   ├── __init__.py
│   │   ├── device_list.py   # TV list component
│   │   ├── action_panel.py  # Action buttons panel
│   │   ├── diagnostics.py   # Diagnostics panel (desktop)
│   │   └── dialogs.py       # Common dialogs
│   ├── views/               # Screen views
│   │   ├── __init__.py
│   │   ├── main_view.py     # Main application view
│   │   ├── remote_view.py   # TV remote control view
│   │   └── settings_view.py # Settings view
│   └── state.py             # Application state management
│
├── mobile/                  # MOBILE-ONLY: Adaptations
│   ├── __init__.py
│   ├── discovery.py         # Mobile mDNS wrapper (platform channels)
│   └── permissions.py       # Mobile permission handling
│
├── system/                  # SHARED: System utilities
│   ├── __init__.py
│   ├── paths.py             # Cross-platform path resolution
│   ├── platform.py          # Platform detection (extended for mobile)
│   └── logging_config.py    # Logging setup
│
└── legacy/                  # DEPRECATED: Old PyQt6 code (to be removed)
    ├── ui/                  # Old PyQt6 UI
    └── app_qt.py            # Old PyQt6 entry point
```

## Feature Matrix

| Feature | Desktop | Mobile | Implementation |
|---------|---------|--------|----------------|
| TV Discovery (SSDP) | ✅ | ✅ | `core/discovery/ssdp.py` |
| TV Discovery (mDNS) | ✅ | ⚠️ | Desktop: zeroconf, Mobile: native |
| WebOS Pairing | ✅ | ✅ | `core/webos/client.py` |
| Cast URL | ✅ | ✅ | `core/webos/client.py` |
| UPnP Media Cast | ✅ | ⚠️ | `core/discovery/upnp.py` |
| Screen Mirror | ✅ | ❌ | `desktop/mirror/` |
| Local Media Share | ✅ | ❌ | `desktop/actions/media_share.py` |
| External Tools | ✅ | ❌ | `desktop/actions/launchers.py` |
| File Picker | ✅ | ⚠️ | Flet FilePicker (limited mobile) |
| TV Remote | ✅ | ✅ | `flet_ui/views/remote_view.py` |

## Runtime Feature Detection

The `core/runtime.py` module provides runtime detection:

```python
from lgtvtools.core.runtime import Runtime

runtime = Runtime.detect()

if runtime.is_desktop:
    # Full feature set available
    from lgtvtools.desktop.mirror import MirrorSession

if runtime.has_ffmpeg:
    # Screen mirroring available

if runtime.has_zeroconf:
    # mDNS discovery available

if runtime.is_mobile:
    # Limited feature set
    # Use mobile-specific discovery
```

## Async Architecture

Flet works best with async patterns. The migration converts all I/O operations to async:

### WebOS Client (Before - Sync)
```python
class WebOSClient:
    def connect(self, timeout: float = 30.0) -> WebOSResult:
        self._ws = ws_client.connect(uri, ...)
        return self._register(timeout)
```

### WebOS Client (After - Async)
```python
class WebOSClient:
    async def connect(self, timeout: float = 30.0) -> WebOSResult:
        self._ws = await websockets.connect(uri, ...)
        return await self._register(timeout)
```

### UI Integration
```python
async def scan_network(page: ft.Page):
    state.is_scanning = True
    page.update()
    
    devices = await asyncio.to_thread(discover_lg_tvs)
    state.devices = devices
    
    state.is_scanning = False
    page.update()
```

## State Management

Application state is managed through a central `AppState` class:

```python
@dataclass
class AppState:
    devices: list[LGTVDevice] = field(default_factory=list)
    selected_device: LGTVDevice | None = None
    is_scanning: bool = False
    is_mirroring: bool = False
    connection_status: str = "Ready"
    last_error: str | None = None
    
    # Desktop-only state
    capabilities: list[Capability] | None = None
    mirror_worker: MirrorWorker | None = None
```

## Entry Points

### Desktop
```python
# lgtvtools/flet_ui/app.py
def main():
    ft.app(target=desktop_main, assets_dir="assets")

def desktop_main(page: ft.Page):
    page.title = "LG TV Tools"
    runtime = Runtime.detect()
    state = AppState()
    
    if runtime.is_desktop:
        state.capabilities = detect_capabilities()
    
    main_view = MainView(page, state, runtime)
    page.add(main_view)
```

### Mobile
```python
# lgtvtools/flet_ui/app_mobile.py
def main():
    ft.app(target=mobile_main)

def mobile_main(page: ft.Page):
    page.title = "LG TV Remote"
    runtime = Runtime.detect()
    state = AppState()
    
    # Mobile uses simplified view
    main_view = MobileMainView(page, state, runtime)
    page.add(main_view)
```

## Build Targets

### pyproject.toml
```toml
[project]
dependencies = [
    "flet>=0.27",
    "websockets>=16.1.1",
]

[project.optional-dependencies]
desktop = [
    "netifaces>=0.11.0",
    "zeroconf>=0.150.0",
]

[project.scripts]
lg-tv-tools = "lgtvtools.flet_ui.app:main"
lg-tv-tools-qt = "lgtvtools.legacy.app_qt:main"  # Deprecated

[project.gui-scripts]
lg-tv-remote = "lgtvtools.flet_ui.app_mobile:main"
```

## Migration Path

### Phase 1: Core Extraction (Current)
1. Extract platform-agnostic code to `core/`
2. Convert WebOS client to async
3. Create runtime feature detection

### Phase 2: Flet UI (Next)
1. Build shared UI components
2. Implement main view with feature detection
3. Desktop-specific panels (diagnostics, mirror)

### Phase 3: Mobile Adaptation
1. Simplified mobile UI
2. Mobile-specific discovery (if needed)
3. Permission handling

### Phase 4: Cleanup
1. Move PyQt6 code to `legacy/`
2. Update tests
3. Update documentation
