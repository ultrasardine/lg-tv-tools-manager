from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def test_imports() -> None:
    import lgtvtools
    from lgtvtools.discovery import ssdp, upnp

    assert lgtvtools.__version__ == "0.2.0"
    assert callable(ssdp.discover_lg_tvs)
    assert callable(upnp.cast_media_to_device)


def test_ui_module_import() -> None:
    from lgtvtools.ui import main_window

    assert hasattr(main_window, "MainWindow")
