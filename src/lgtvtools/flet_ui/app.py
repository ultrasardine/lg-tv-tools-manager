"""Flet application entry point.

This module provides the main entry point for the Flet-based
LG TV Tools application.
"""

from __future__ import annotations

import logging
import re
import shutil
import sys
from pathlib import Path

import flet as ft

from lgtvtools.flet_ui.state import StateManager
from lgtvtools.flet_ui.theme import AppTheme
from lgtvtools.flet_ui.views.main_view import MainView
from lgtvtools.system.logging_config import setup_logging
from lgtvtools.system.paths import data_dir

LOGGER = logging.getLogger(__name__)


def _cleanup_flet_client_cache() -> None:
    """Work around a Flet bug on Windows where pathlib.Path.rename() fails.

    On Windows, Path.rename() raises FileExistsError if the destination
    already exists.  Flet's ``ensure_client_cached`` downloads the desktop
    client into a temp directory with a random suffix and then renames it
    to the canonical path.  If the canonical path is already present from
    a previous run, the rename crashes the app.

    This function removes leftover temp directories so the rename succeeds,
    or — if the final directory already exists — removes the temps since
    they are redundant.
    """
    if sys.platform != "win32":
        return

    flet_client_dir = Path.home() / ".flet" / "client"
    if not flet_client_dir.exists():
        return

    # Pattern: flet-desktop-full-<version>.<random_suffix>
    temp_pattern = re.compile(r"^(flet-desktop(?:-full)?-[\d.]+)\.[A-Za-z0-9]{6,}$")

    for entry in flet_client_dir.iterdir():
        if not entry.is_dir():
            continue
        match = temp_pattern.match(entry.name)
        if not match:
            continue

        canonical = flet_client_dir / match.group(1)
        try:
            if canonical.exists():
                # Final cache exists; temp is redundant — remove it
                shutil.rmtree(entry, ignore_errors=True)
                LOGGER.debug("Removed redundant Flet temp cache: %s", entry)
            else:
                # Final cache missing; rename the temp to canonical
                entry.rename(canonical)
                LOGGER.debug("Renamed Flet temp cache %s -> %s", entry, canonical)
        except OSError:
            # Last resort: nuke the temp so Flet can do a clean download
            shutil.rmtree(entry, ignore_errors=True)
            LOGGER.debug("Cleaned broken Flet temp cache: %s", entry)


def _main(page: ft.Page) -> None:
    """Main function called by Flet.

    Args:
        page: The Flet page to build.
    """
    # Setup logging
    setup_logging()
    LOGGER.info("Starting LG TV Tools (Flet)")

    # Ensure data directory exists
    data_dir().mkdir(parents=True, exist_ok=True)

    # Configure page
    page.title = "LG TV Tools"
    page.window.width = 1200
    page.window.height = 760
    page.window.min_width = 800
    page.window.min_height = 500

    # Apply theme
    AppTheme.apply_to_page(page)

    # Create state manager
    state_manager = StateManager()

    # Log runtime info
    runtime = state_manager.runtime
    LOGGER.info("Runtime: %s", runtime)
    state_manager.log(f"Platform: {runtime.environment.value}")

    if runtime.is_desktop:
        if runtime.can_mirror:
            state_manager.log("Screen mirroring: available")
        else:
            state_manager.log("Screen mirroring: ffmpeg not found")

    # Create main view
    main_view = MainView(page, state_manager)

    # Rebuild UI on state change
    def on_state_change() -> None:
        page.controls.clear()
        page.add(main_view.build())
        page.update()

    state_manager.on_change(on_state_change)

    # Setup cleanup on close
    async def on_close(e: ft.ControlEvent) -> None:
        LOGGER.info("Application closing, cleaning up...")
        main_view.cleanup()
        await state_manager.cleanup()

    page.on_close = on_close

    # Add main view to page
    page.add(main_view.build())

    # Start initial network scan
    page.run_task(main_view.scan_network)


def run_app() -> None:
    """Run the Flet application."""
    _cleanup_flet_client_cache()
    ft.app(target=_main)


def run_app_web(port: int = 8550) -> None:
    """Run the Flet application as a web server.

    Args:
        port: Port to run the web server on.
    """
    ft.app(target=_main, view=ft.AppView.WEB_BROWSER, port=port)


def main() -> None:
    """Main entry point."""
    run_app()


if __name__ == "__main__":
    main()
