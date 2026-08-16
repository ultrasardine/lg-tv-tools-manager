#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${ROOT_DIR}/.build"
PKG_ROOT="${BUILD_DIR}/pkgroot"
PKG_NAME="lg-tv-tools"
VERSION="0.2.0"
ARCH="all"
OUT_DEB="${BUILD_DIR}/${PKG_NAME}_${VERSION}_${ARCH}.deb"

rm -rf "${BUILD_DIR}"
mkdir -p \
  "${PKG_ROOT}/DEBIAN" \
  "${PKG_ROOT}/usr/lib/python3/dist-packages" \
  "${PKG_ROOT}/usr/bin" \
  "${PKG_ROOT}/usr/share/applications" \
  "${PKG_ROOT}/usr/share/icons/hicolor/scalable/apps"

cp -r "${ROOT_DIR}/src/lgtvtools" "${PKG_ROOT}/usr/lib/python3/dist-packages/"
find "${PKG_ROOT}/usr/lib/python3/dist-packages/lgtvtools" -type d -name '__pycache__' -prune -exec rm -rf {} +
cp "${ROOT_DIR}/src/lgtvtools/resources/icons/app.svg" "${PKG_ROOT}/usr/share/icons/hicolor/scalable/apps/lg-tv-tools.svg"

cat > "${PKG_ROOT}/usr/bin/lg-tv-tools" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec python3 -m lgtvtools.app
EOF
chmod 0755 "${PKG_ROOT}/usr/bin/lg-tv-tools"

cat > "${PKG_ROOT}/usr/share/applications/lg-tv-tools.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=LG TV Tools
Comment=Discover LG TVs and launch casting workflows
Exec=lg-tv-tools
Icon=lg-tv-tools
Terminal=false
Categories=Utility;Network;AudioVideo;
StartupNotify=true
EOF

cat > "${PKG_ROOT}/DEBIAN/control" <<EOF
Package: ${PKG_NAME}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Maintainer: Reynaldo  Rodriguez (Reyam) <noreply@users.noreply.github.com>
Depends: python3, python3-pyqt6
Description: Description: LG webOS discovery and DLNA media casting utility for Linux desktops
 LG TV Tools discovers LG TVs on the local network and provides a GUI for
 media casting, desktop mirroring launchers, diagnostics, and KDE integration.
EOF

chmod 0755 "${PKG_ROOT}/DEBIAN"
dpkg-deb --root-owner-group --build "${PKG_ROOT}" "${OUT_DEB}"

echo "Built ${OUT_DEB}"
