# LG TV Tools

[![CI](https://github.com/ultrasardine/lg-tv-tools-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/ultrasardine/lg-tv-tools-manager/actions/workflows/ci.yml)
[![Release](https://github.com/ultrasardine/lg-tv-tools-manager/actions/workflows/release.yml/badge.svg)](https://github.com/ultrasardine/lg-tv-tools-manager/actions/workflows/release.yml)
[![GitHub release](https://img.shields.io/github/v/release/ultrasardine/lg-tv-tools-manager)](https://github.com/ultrasardine/lg-tv-tools-manager/releases/latest)

LG TV Tools is a cross-platform application for discovering and controlling LG televisions on your local network. Built with Flet for desktop and mobile support, it provides screen mirroring, URL casting, media handoff, and direct TV remote control.

**Version: 0.3.0**

## Downloads

Pre-built executables are available for each platform:

| Platform | Download |
|----------|----------|
| Windows | [lg-tv-tools-windows-x64.zip](https://github.com/ultrasardine/lg-tv-tools-manager/releases/latest/download/lg-tv-tools-windows-x64.zip) |
| macOS (Apple Silicon) | [lg-tv-tools-macos-arm64.tar.gz](https://github.com/ultrasardine/lg-tv-tools-manager/releases/latest/download/lg-tv-tools-macos-arm64.tar.gz) |
| Linux | [lg-tv-tools-linux-x64.tar.gz](https://github.com/ultrasardine/lg-tv-tools-manager/releases/latest/download/lg-tv-tools-linux-x64.tar.gz) |

Or install via pip/uv (see [Installation](#installation) below).

## Author

- Author: Reynaldo Rodríguez
- User: reyam
- Portfolio: [Reynaldo8509](https://github.com/Reynaldo8509)

## Architecture

The application uses a hybrid architecture with three layers:

- **Shared Core** (`lgtvtools.core`) - Platform-agnostic discovery, WebOS client, and data models
- **Desktop Features** (`lgtvtools.desktop`) - Full feature set including file operations, external tool launching, and media sharing
- **Flet UI** (`lgtvtools.flet_ui`) - Cross-platform UI with adaptive layouts for desktop and mobile

For detailed architecture documentation, see [docs/architecture-flet-migration.md](docs/architecture-flet-migration.md).

## Features

### All Platforms
- Automatic SSDP/DLNA + mDNS/Bonjour discovery (dual-protocol)
- WebOS WebSocket pairing and direct TV control
- Remote control interface (volume, channels, media playback, power)
- Cast URLs to the TV (YouTube via native app, media via native player, others via browser)
- Diagnostic logging

### Desktop (macOS, Linux, Windows)
- Full Flet desktop interface
- Media file handoff (video, image, music) via webOS or UPnP/DLNA
- In-app screen mirroring via ffmpeg capture and HLS streaming
- Platform-aware native mirroring (AirPlay, Miracast, gnome-network-displays)
- VLC launcher integration
- Installed-dependency detection
- KDE launcher integration via `.desktop` (Linux)

### Mobile (iOS, Android)
- Simplified touch-optimized interface
- TV discovery and selection
- Remote control with touch-friendly buttons
- URL casting

## Installation

### Quick Start

```bash
# Install with uv (recommended)
uv sync

# Run the desktop app
uv run lg-tv-tools

# Run the mobile/remote-only app
uv run lg-tv-remote
```

### Optional Dependencies

For full desktop functionality:

```bash
# Install with desktop extras (netifaces, zeroconf for enhanced discovery)
uv sync --extra desktop
```

For legacy PyQt6 interface:

```bash
# Install with Qt extras
uv sync --extra qt

# Run legacy PyQt6 app
uv run lg-tv-tools-qt
```

## Entry Points

| Command | Description |
|---------|-------------|
| `lg-tv-tools` | Desktop Flet application (full features) |
| `lg-tv-remote` | Mobile Flet application (remote control subset) |
| `lg-tv-tools-qt` | Legacy PyQt6 application |

## Requirements

### Core
- Python 3.10 or newer
- flet >= 0.27
- websockets >= 16.1.1

### Optional (Desktop Extras)
- netifaces >= 0.11.0 (enhanced network interface detection)
- zeroconf >= 0.150.0 (mDNS/Bonjour discovery)

### Optional (Legacy Qt)
- PyQt6 >= 6.6

## Detected Dependencies

The application checks for platform-relevant tools at runtime:

- `ffmpeg` (all platforms - required for in-app screen mirroring)
  - **Windows**: bundled with the release build, no install needed
  - **macOS**: `brew install ffmpeg`
  - **Linux**: `sudo apt install ffmpeg` or `sudo dnf install ffmpeg`
- `VLC` (all platforms - optional, for media playback)
  - **Windows**: `winget install VideoLAN.VLC`
  - **macOS**: `brew install --cask vlc`
  - **Linux**: `sudo apt install vlc` or `sudo dnf install vlc`
- `gnome-network-displays` (Linux only - Miracast streaming)
- `rygel` (Linux only - UPnP/DLNA media server)
- `pulseaudio` / `pipewire` (Linux only - audio subsystem)
- `miraclecast` (Linux only - Miracast alternative)

If any applicable dependency is missing, the UI shows a platform-appropriate installation hint.

## Development

### Run the App

```bash
# Desktop Flet app
make run
# or: uv run lg-tv-tools

# Mobile/remote app
make run-mobile
# or: uv run lg-tv-remote

# Legacy PyQt6 app (requires qt extras)
make run-qt
# or: uv run lg-tv-tools-qt
```

### Mobile Testing (iOS/Android)

```bash
# Debug on a connected iOS device (live reload)
make run-ios
# or: flet debug --device-id ios

# Build iOS IPA for distribution
make build-ios
# or: flet build ipa --ios-team-id YOUR_TEAM_ID
```

The `main.py` at the project root serves as the Flet CLI entry point for mobile builds, delegating to the mobile-optimized app.

Prerequisites for iOS:
- Xcode 15+ installed
- CocoaPods (`brew install cocoapods`)
- Developer Mode enabled on iPhone (Settings > Privacy & Security > Developer Mode)
- SSL fix: `curl -L -o /tmp/manifest.json https://github.com/flet-dev/python-build/releases/download/20260730/manifest.json`

### Environment Setup

```bash
make sync              # Sync base dependencies
make sync-desktop      # Sync with desktop extras (netifaces, zeroconf)
make sync-qt           # Sync with Qt extras for legacy PyQt6
make sync-all          # Sync with all optional extras
```

### Quality Gates

```bash
make lint          # Ruff lint check
make format        # Format with ruff
make typecheck     # mypy static analysis
make test          # Run tests
make check         # All quality gates
```

### Testing

```bash
make test              # Run tests (quiet output)
make test-verbose      # Verbose test output
make test-cov          # Tests with coverage report
```

## KDE Integration (Linux)

Install the user-level launcher:

```bash
bash scripts/install.sh
```

Remove the user-level launcher:

```bash
bash scripts/uninstall.sh
```

The installer places:
- A wrapper in `~/.local/bin/lg-tv-tools`
- A `.desktop` file in `~/.local/share/applications/lg-tv-tools.desktop`
- An icon in `~/.local/share/lg-tv-tools/icons/app.svg`

## Logging

Runtime logs are written to:

```text
~/.local/share/lg-tv-tools/logs/lg-tv-tools.log
```

## WebOS TV Control

The app communicates directly with LG webOS TVs via the SSAP WebSocket protocol (port 3001, SSL):

1. **Pair TV** - One-time pairing: the TV shows a prompt, you accept, and the client key is stored locally for future use.
2. **Cast URL** - Smart URL casting: YouTube links open in the native YouTube app, media URLs (mp4, m3u8, etc.) play in the TV's native media viewer, and other URLs open in the TV browser as fallback.
3. **Remote Control** - Volume, mute, channel, media playback, and power controls.
4. **Media playback** - Sends video/audio/image URLs to the TV's native media player.

The TV must be powered on (not standby) for WebSocket commands to work. Pairing keys are stored in `~/.local/share/lg-tv-tools/webos_keys.json`.

## Media Flow (Desktop)

When a file is selected, the app:

1. Publishes the file via a temporary local HTTP URL
2. Tries to send through UPnP/AVTransport (if the TV exposes DLNA services)
3. Falls back to the webOS WebSocket API to open the URL in the TV's media player or browser
4. Falls back to VLC or the system default application when direct TV playback is unavailable

The temporary URL is only useful if the LG TV can reach the host on the local network.

## Screen Mirroring (Desktop)

### In-App HLS Streaming

Built-in screen mirroring that captures your display using ffmpeg and streams to the TV's webOS browser via HLS:

1. Click "Mirror Screen" in the main window
2. Select a capture source (display, window, or application)
3. The app starts an ffmpeg capture pipeline encoding to H.264/HLS
4. A local HTTP server serves the HLS stream
5. The TV's browser opens an HTML player with hls.js

**Requirements:**
- `ffmpeg` must be installed with screen capture support
- Hardware encoding (VideoToolbox on macOS, VAAPI/NVENC on Linux) is used when available
- The TV must be able to reach the host's HTTP server (default port 8765)

### Platform-Native Mirroring

For native protocols, the app opens the system's mirroring interface:

- **macOS**: Opens System Settings > Displays for AirPlay targets
- **Windows**: Opens the Connect/Cast panel (built-in Miracast)
- **Linux**: Launches `gnome-network-displays` or `miraclecast`

## TV Discovery

The app discovers LG TVs using two protocols in parallel:

**SSDP (UPnP)** - Sends M-SEARCH packets to multicast group 239.255.255.250:1900 with different search targets. Devices are confirmed as LG through header pre-check and XML device-description validation.

**mDNS/Bonjour** - Browses for `_airplay._tcp` and `_raop._tcp` services. Filters for LG devices by service name and TXT record properties. This protocol works reliably on networks where SSDP multicast is blocked.

Results from both protocols are merged and deduplicated by IP address.

### Troubleshooting Discovery

If discovery fails, check:
- Firewall rules: UDP port 1900 (SSDP) and port 5353 (mDNS) must be allowed
- Network isolation: some routers block multicast between wireless clients
- VPN/Docker: multiple network interfaces can route multicast to the wrong subnet
- TV settings: ensure AirPlay/Screen Share is enabled on the LG TV

Set `LGTVTOOLS_STRICT_MANUFACTURER_FILTER=1` to only accept devices whose XML manufacturer field contains "LG" (SSDP only).

## Packaging

### Debian Package

```bash
bash scripts/build_deb.sh
```

### macOS App Bundle

```bash
make build-macos
```

### Release Validation

```bash
make release-check   # lint + format + typecheck + test + smoke
```

## Limitations

- In-app HLS mirroring requires ffmpeg with screen capture support
- Native mirroring depends on platform backend (AirPlay, Miracast, gnome-network-displays)
- WebOS commands require the TV to be powered on (not standby)
- UPnP/DLNA behavior varies between LG models and firmware versions
- Mobile builds have limited features (remote control only, no file operations)

## Security / Networking Relevance

This project demonstrates practical cross-platform development and network-service troubleshooting around **SSDP, UPnP, AVTransport, DLNA, mDNS/Bonjour and local-network discovery**. It complements the SOC portfolio by showing hands-on work with network protocols, service discovery, diagnostics and cross-platform integration.
