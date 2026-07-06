#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${ROOT_DIR}/src:${PYTHONPATH:-}"

python3 - <<'PY'
import lgtvtools
from lgtvtools.discovery import ssdp, upnp
from lgtvtools.ui import main_window

assert lgtvtools.__version__ == "0.2.0"
assert callable(ssdp.discover_lg_tvs)
assert callable(upnp.cast_media_to_device)
assert hasattr(main_window, "MainWindow")
print("smoke ok")
PY
