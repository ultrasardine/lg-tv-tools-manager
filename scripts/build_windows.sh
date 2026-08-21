#!/usr/bin/env bash
# Build a Windows .exe standalone using PyInstaller.
# This script is designed to run on Windows (Git Bash/MSYS2) or cross-build via CI.
# Requires: pyinstaller (installed via uv pip install pyinstaller)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="LG TV Tools"
PKG_NAME="lg-tv-tools"
VERSION="0.2.0"
BUILD_DIR="${ROOT_DIR}/.build/windows"
DIST_DIR="${BUILD_DIR}/dist"

# Ensure PyInstaller is available
if ! uv run python3 -c "import PyInstaller" 2>/dev/null; then
    echo "Installing PyInstaller..."
    uv pip install pyinstaller
fi

rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"

# Convert SVG to ICO if possible (requires ImageMagick)
ICON_FLAG=""
ICON_SRC="${ROOT_DIR}/src/lgtvtools/resources/icons/app.svg"
if command -v magick &>/dev/null; then
    ICO_PATH="${BUILD_DIR}/${PKG_NAME}.ico"
    magick "${ICON_SRC}" -define icon:auto-resize=256,128,64,48,32,16 "${ICO_PATH}"
    ICON_FLAG="--icon=${ICO_PATH}"
    echo "Generated .ico icon"
elif command -v convert &>/dev/null; then
    ICO_PATH="${BUILD_DIR}/${PKG_NAME}.ico"
    convert "${ICON_SRC}" -define icon:auto-resize=256,128,64,48,32,16 "${ICO_PATH}"
    ICON_FLAG="--icon=${ICO_PATH}"
    echo "Generated .ico icon"
fi

# Build the standalone executable
uv run pyinstaller \
    --name "${PKG_NAME}" \
    --windowed \
    --onefile \
    --distpath "${DIST_DIR}" \
    --workpath "${BUILD_DIR}/work" \
    --specpath "${BUILD_DIR}" \
    --add-data "${ROOT_DIR}/src/lgtvtools/resources;lgtvtools/resources" \
    ${ICON_FLAG} \
    --noconfirm \
    "${ROOT_DIR}/src/lgtvtools/app.py"

EXE_PATH="${DIST_DIR}/${PKG_NAME}.exe"
if [[ -f "${EXE_PATH}" ]]; then
    mkdir -p "${ROOT_DIR}/.build"
    cp "${EXE_PATH}" "${ROOT_DIR}/.build/${PKG_NAME}-${VERSION}-windows.exe"
    echo "Built: ${ROOT_DIR}/.build/${PKG_NAME}-${VERSION}-windows.exe"
else
    echo "Error: .exe not found after build"
    exit 1
fi
