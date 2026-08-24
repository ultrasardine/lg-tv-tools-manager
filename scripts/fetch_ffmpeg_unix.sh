#!/usr/bin/env bash
# fetch_ffmpeg_unix.sh
# Downloads static ffmpeg/ffprobe binaries for macOS or Linux.
# Uses eugeneware/ffmpeg-static GitHub releases (static, self-contained).
#
# Usage:
#   bash scripts/fetch_ffmpeg_unix.sh
#   OUTPUT_DIR=vendor/bin bash scripts/fetch_ffmpeg_unix.sh
set -euo pipefail

OUTPUT_DIR="${OUTPUT_DIR:-vendor/bin}"
REPO="eugeneware/ffmpeg-static"

# Detect platform and architecture
OS="$(uname -s)"
ARCH="$(uname -m)"

case "$OS" in
    Darwin) PLATFORM="darwin" ;;
    Linux)  PLATFORM="linux" ;;
    *)      echo "Unsupported OS: $OS"; exit 1 ;;
esac

case "$ARCH" in
    x86_64|amd64)  ARCH_SUFFIX="x64" ;;
    arm64|aarch64) ARCH_SUFFIX="arm64" ;;
    armv7l)        ARCH_SUFFIX="arm" ;;
    *)             echo "Unsupported architecture: $ARCH"; exit 1 ;;
esac

ASSET_FFMPEG="ffmpeg-${PLATFORM}-${ARCH_SUFFIX}"
ASSET_FFPROBE="ffprobe-${PLATFORM}-${ARCH_SUFFIX}"

mkdir -p "$OUTPUT_DIR"

# Check if already present
if [ -x "$OUTPUT_DIR/ffmpeg" ]; then
    echo "ffmpeg already present: $("$OUTPUT_DIR/ffmpeg" -version | head -1)"
    echo "Delete $OUTPUT_DIR/ffmpeg to force re-download."
    exit 0
fi

# Get latest release download URL
echo "Querying GitHub for latest ffmpeg-static release..."
RELEASE_URL="https://api.github.com/repos/${REPO}/releases/latest"
RELEASE_JSON=$(curl -sL "$RELEASE_URL")
TAG=$(echo "$RELEASE_JSON" | grep -o '"tag_name": *"[^"]*"' | head -1 | cut -d'"' -f4)
echo "Latest version: $TAG"

BASE_URL="https://github.com/${REPO}/releases/download/${TAG}"

# Download ffmpeg
echo "Downloading ${ASSET_FFMPEG}..."
curl -sL -o "$OUTPUT_DIR/ffmpeg" "${BASE_URL}/${ASSET_FFMPEG}"
chmod +x "$OUTPUT_DIR/ffmpeg"
echo "Installed: $OUTPUT_DIR/ffmpeg"

# Download ffprobe
echo "Downloading ${ASSET_FFPROBE}..."
curl -sL -o "$OUTPUT_DIR/ffprobe" "${BASE_URL}/${ASSET_FFPROBE}"
chmod +x "$OUTPUT_DIR/ffprobe"
echo "Installed: $OUTPUT_DIR/ffprobe"

# Verify
echo "Verification: $("$OUTPUT_DIR/ffmpeg" -version | head -1)"
echo "Done. ffmpeg is ready for bundling in $OUTPUT_DIR"
