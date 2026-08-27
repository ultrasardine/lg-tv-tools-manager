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

# Authenticate when a token is available (CI) to avoid API rate limits.
# Use a plain string rather than an array for bash 3.2 (macOS) compatibility
# under `set -u`.
AUTH_HEADER=""
if [ -n "${GITHUB_TOKEN:-}" ]; then
    AUTH_HEADER="Authorization: Bearer ${GITHUB_TOKEN}"
fi

if [ -n "$AUTH_HEADER" ]; then
    RELEASE_JSON=$(curl -sL -H "$AUTH_HEADER" -H "Accept: application/vnd.github+json" "$RELEASE_URL")
else
    RELEASE_JSON=$(curl -sL -H "Accept: application/vnd.github+json" "$RELEASE_URL")
fi
TAG=$(echo "$RELEASE_JSON" | grep -o '"tag_name": *"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$TAG" ]; then
    echo "ERROR: Could not resolve latest ffmpeg-static release tag." >&2
    echo "GitHub API response (first 20 lines):" >&2
    echo "$RELEASE_JSON" | head -20 >&2
    exit 1
fi
echo "Latest version: $TAG"

BASE_URL="https://github.com/${REPO}/releases/download/${TAG}"

# Download ffmpeg (--fail makes curl exit non-zero on HTTP errors like 404)
echo "Downloading ${ASSET_FFMPEG}..."
curl -fsSL -o "$OUTPUT_DIR/ffmpeg" "${BASE_URL}/${ASSET_FFMPEG}"
chmod +x "$OUTPUT_DIR/ffmpeg"
echo "Installed: $OUTPUT_DIR/ffmpeg"

# Download ffprobe
echo "Downloading ${ASSET_FFPROBE}..."
curl -fsSL -o "$OUTPUT_DIR/ffprobe" "${BASE_URL}/${ASSET_FFPROBE}"
chmod +x "$OUTPUT_DIR/ffprobe"
echo "Installed: $OUTPUT_DIR/ffprobe"

# Verify
echo "Verification: $("$OUTPUT_DIR/ffmpeg" -version | head -1)"
echo "Done. ffmpeg is ready for bundling in $OUTPUT_DIR"
