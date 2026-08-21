"""Flet application entry point.

This module provides the main entry point for the Flet-based
LG TV Tools application.
"""

from __future__ import annotations

import logging

import flet as ft

from lgtvtools.flet_ui.state import StateManager
from lgtvtools.flet_ui.theme import AppTheme
from lgtvtools.flet_ui.views.main_view import MainView
from lgtvtools.system.logging_config import setup_logging
from lgtvtools.system.paths import data_dir

LOGGER = logging.getLogger(__name__)


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
