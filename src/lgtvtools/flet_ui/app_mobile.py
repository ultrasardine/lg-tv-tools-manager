"""Mobile-optimized Flet application entry point.

This module provides a mobile-specific entry point that:
- Uses a simplified vertical layout
- Hides desktop-only features
- Optimizes for touch interactions
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


def _mobile_main(page: ft.Page) -> None:
    """Mobile-optimized main function.

    Args:
        page: The Flet page to build.
    """
    # Setup logging
    setup_logging()
    LOGGER.info("Starting LG TV Remote (Mobile)")

    # Ensure data directory exists
    data_dir().mkdir(parents=True, exist_ok=True)

    # Configure page for mobile
    page.title = "LG TV Remote"

    # Apply theme
    AppTheme.apply_to_page(page)

    # Mobile-specific settings
    page.padding = 8

    # Create state manager
    state_manager = StateManager()

    # Log runtime info
    runtime = state_manager.runtime
    LOGGER.info("Runtime: %s", runtime)
    state_manager.log(f"Platform: {runtime.environment.value}")

    # Create main view
    main_view = MainView(page, state_manager)

    # Rebuild UI on state change
    def on_state_change() -> None:
        page.controls.clear()
        page.add(main_view.build())
        page.update()

    state_manager.on_state_change = on_state_change

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


def run_mobile_app() -> None:
    """Run the mobile Flet application."""
    from lgtvtools.flet_ui.app import _cleanup_flet_client_cache

    _cleanup_flet_client_cache()
    ft.app(target=_mobile_main)


def main() -> None:
    """Main entry point for mobile."""
    run_mobile_app()


if __name__ == "__main__":
    main()
