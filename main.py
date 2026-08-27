"""Flet entry point for mobile builds (flet debug / flet build).

This file exists at the project root so Flet CLI can find it without
needing --module-name. It delegates to the mobile app entry point.
"""

from lgtvtools.flet_ui.app_mobile import main

if __name__ == "__main__":
    main()
