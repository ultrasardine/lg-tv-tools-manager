#!/usr/bin/env bash
# Build an RPM package for RHEL/Alma Linux/Fedora.
# Requires: rpmbuild (rpm-build package)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PKG_NAME="lg-tv-tools"
VERSION="0.2.0"
RELEASE="1"
BUILD_DIR="${ROOT_DIR}/.build/rpm"
SPEC_FILE="${BUILD_DIR}/SPECS/${PKG_NAME}.spec"

# Check for rpmbuild
if ! command -v rpmbuild &>/dev/null; then
    echo "Error: rpmbuild not found. Install with: sudo dnf install rpm-build"
    exit 1
fi

# Set up RPM build tree
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"/{SPECS,SOURCES,BUILD,RPMS,SRPMS}

# Create tarball source
TAR_DIR="${BUILD_DIR}/SOURCES/${PKG_NAME}-${VERSION}"
mkdir -p "${TAR_DIR}"
cp -r "${ROOT_DIR}/src/lgtvtools" "${TAR_DIR}/"
find "${TAR_DIR}" -type d -name '__pycache__' -prune -exec rm -rf {} +
tar czf "${BUILD_DIR}/SOURCES/${PKG_NAME}-${VERSION}.tar.gz" \
    -C "${BUILD_DIR}/SOURCES" "${PKG_NAME}-${VERSION}"
rm -rf "${TAR_DIR}"

# Generate spec file
cat > "${SPEC_FILE}" <<EOF
Name:           ${PKG_NAME}
Version:        ${VERSION}
Release:        ${RELEASE}%{?dist}
Summary:        LG webOS discovery and DLNA media casting utility

License:        MIT
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

Requires:       python3
Requires:       python3-qt6

%description
LG TV Tools discovers LG TVs on the local network and provides a GUI for
media casting, desktop mirroring launchers, diagnostics, and desktop integration.

%prep
%setup -q

%install
mkdir -p %{buildroot}/usr/lib/python3/dist-packages
cp -r lgtvtools %{buildroot}/usr/lib/python3/dist-packages/

mkdir -p %{buildroot}/usr/bin
cat > %{buildroot}/usr/bin/${PKG_NAME} <<'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
exec python3 -m lgtvtools.app
WRAPPER
chmod 0755 %{buildroot}/usr/bin/${PKG_NAME}

mkdir -p %{buildroot}/usr/share/applications
cat > %{buildroot}/usr/share/applications/${PKG_NAME}.desktop <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=LG TV Tools
Comment=Discover LG TVs and launch casting workflows
Exec=${PKG_NAME}
Icon=${PKG_NAME}
Terminal=false
Categories=Utility;Network;AudioVideo;
StartupNotify=true
DESKTOP

mkdir -p %{buildroot}/usr/share/icons/hicolor/scalable/apps
cp %{_sourcedir}/../../../src/lgtvtools/resources/icons/app.svg \
    %{buildroot}/usr/share/icons/hicolor/scalable/apps/${PKG_NAME}.svg 2>/dev/null || true

%files
/usr/lib/python3/dist-packages/lgtvtools/
/usr/bin/${PKG_NAME}
/usr/share/applications/${PKG_NAME}.desktop
%if 0
/usr/share/icons/hicolor/scalable/apps/${PKG_NAME}.svg
%endif

%changelog
* $(date '+%a %b %d %Y') Reynaldo Rodriguez <noreply@users.noreply.github.com> - ${VERSION}-${RELEASE}
- Multiplatform release
EOF

# Build the RPM
rpmbuild --define "_topdir ${BUILD_DIR}" -bb "${SPEC_FILE}"

RPM_PATH=$(find "${BUILD_DIR}/RPMS" -name "*.rpm" | head -1)
if [[ -n "${RPM_PATH}" ]]; then
    cp "${RPM_PATH}" "${ROOT_DIR}/.build/"
    echo "Built: ${ROOT_DIR}/.build/$(basename "${RPM_PATH}")"
else
    echo "Error: RPM not found after build"
    exit 1
fi
