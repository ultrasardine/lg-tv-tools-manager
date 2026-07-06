#!/usr/bin/env bash
set -euo pipefail

APP_ID="lg-tv-tools"
rm -f "${HOME}/.local/bin/${APP_ID}"
rm -f "${HOME}/.local/share/applications/${APP_ID}.desktop"
rm -rf "${HOME}/.local/share/${APP_ID}"

if command -v kbuildsycoca6 >/dev/null 2>&1; then
  kbuildsycoca6 >/dev/null 2>&1 || true
elif command -v kbuildsycoca5 >/dev/null 2>&1; then
  kbuildsycoca5 >/dev/null 2>&1 || true
fi

echo "Removed user integration for ${APP_ID}"
