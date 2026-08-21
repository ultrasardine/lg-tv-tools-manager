#!/usr/bin/env bash
# Build a macOS .app bundle using PyInstaller.
# Requires: pyinstaller (installed via uv pip install pyinstaller)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="LG TV Tools"
PKG_NAME="lg-tv-tools"
VERSION="0.2.0"
BUILD_DIR="${ROOT_DIR}/.build/macos"
DIST_DIR="${BUILD_DIR}/dist"
ICON_SRC="${ROOT_DIR}/src/lgtvtools/resources/icons/app.svg"

# Check platform
if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "Error: macOS build must run on macOS"
    exit 1
fi

# Ensure PyInstaller is available
if ! uv run python3 -c "import PyInstaller" 2>/dev/null; then
    echo "Installing PyInstaller..."
    uv pip install pyinstaller
fi

rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"

# Convert SVG to icns if possible (requires rsvg-convert + iconutil)
ICON_FLAG=""
if command -v rsvg-convert &>/dev/null && command -v iconutil &>/dev/null; then
    ICONSET_DIR="${BUILD_DIR}/${PKG_NAME}.iconset"
    mkdir -p "${ICONSET_DIR}"
    for SIZE in 16 32 64 128 256 512; do
        rsvg-convert -w "${SIZE}" -h "${SIZE}" "${ICON_SRC}" -o "${ICONSET_DIR}/icon_${SIZE}x${SIZE}.png"
        DOUBLE=$((SIZE * 2))
        rsvg-convert -w "${DOUBLE}" -h "${DOUBLE}" "${ICON_SRC}" -o "${ICONSET_DIR}/icon_${SIZE}x${SIZE}@2x.png"
    done
    iconutil -c icns "${ICONSET_DIR}" -o "${BUILD_DIR}/${PKG_NAME}.icns"
    ICON_FLAG="--icon=${BUILD_DIR}/${PKG_NAME}.icns"
    echo "Generated .icns icon"
fi

# Build the .app bundle
uv run pyinstaller \
    --name "${APP_NAME}" \
    --windowed \
    --onedir \
    --distpath "${DIST_DIR}" \
    --workpath "${BUILD_DIR}/work" \
    --specpath "${BUILD_DIR}" \
    --add-data "${ROOT_DIR}/src/lgtvtools/resources:lgtvtools/resources" \
    ${ICON_FLAG} \
    --noconfirm \
    "${ROOT_DIR}/src/lgtvtools/app.py"

# Create a compressed DMG if hdiutil is available
APP_PATH="${DIST_DIR}/${APP_NAME}.app"
if [[ -d "${APP_PATH}" ]]; then
    DMG_PATH="${ROOT_DIR}/.build/${PKG_NAME}-${VERSION}-macos.dmg"
    if command -v hdiutil &>/dev/null; then
        hdiutil create -volname "${APP_NAME}" \
            -srcfolder "${DIST_DIR}" \
            -ov -format UDZO \
            "${DMG_PATH}"
        echo "Built: ${DMG_PATH}"
    else
        echo "Built: ${APP_PATH}"
    fi
else
    echo "Error: .app bundle not found after build"
    exit 1
fi
