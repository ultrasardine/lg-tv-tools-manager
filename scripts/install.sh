#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_ID="lg-tv-tools"
INSTALL_DIR="${HOME}/.local/share/${APP_ID}"
BIN_DIR="${HOME}/.local/bin"
DESKTOP_DIR="${HOME}/.local/share/applications"
ICON_DIR="${INSTALL_DIR}/icons"
LOG_DIR="${INSTALL_DIR}/logs"

mkdir -p "${ICON_DIR}" "${LOG_DIR}" "${BIN_DIR}" "${DESKTOP_DIR}"

cp "${ROOT_DIR}/src/lgtvtools/resources/icons/app.svg" "${ICON_DIR}/app.svg"

cat > "${BIN_DIR}/${APP_ID}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="${ROOT_DIR}/src:\${PYTHONPATH:-}"
exec python3 -m lgtvtools.app
EOF
chmod +x "${BIN_DIR}/${APP_ID}"

cat > "${DESKTOP_DIR}/${APP_ID}.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=LG TV Tools
Comment=Discover LG TVs and launch casting workflows
Exec=${BIN_DIR}/${APP_ID}
Icon=${ICON_DIR}/app.svg
Terminal=false
Categories=Utility;Network;AudioVideo;
StartupNotify=true
EOF

if command -v kbuildsycoca6 >/dev/null 2>&1; then
  kbuildsycoca6 >/dev/null 2>&1 || true
elif command -v kbuildsycoca5 >/dev/null 2>&1; then
  kbuildsycoca5 >/dev/null 2>&1 || true
fi

echo "Installed user integration for ${APP_ID}"
echo "Launcher: ${BIN_DIR}/${APP_ID}"
echo "Desktop file: ${DESKTOP_DIR}/${APP_ID}.desktop"
echo "Icon: ${ICON_DIR}/app.svg"
