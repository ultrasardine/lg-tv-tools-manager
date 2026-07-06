#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEB_PATH="${ROOT_DIR}/.build/lg-tv-tools_0.2.0_all.deb"
KEYID="88228B125455C0B7644DB1A9320D6B571195D41C"

if ! command -v gpg >/dev/null 2>&1; then
  echo "gpg is not installed"
  exit 1
fi

if [[ ! -f "${DEB_PATH}" ]]; then
  echo "Missing package: ${DEB_PATH}"
  exit 1
fi

gpg --batch --yes --pinentry-mode loopback --local-user "${KEYID}" --armor --detach-sign "${DEB_PATH}"
echo "Signed ${DEB_PATH}"
