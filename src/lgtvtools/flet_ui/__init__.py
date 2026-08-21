"""Flet UI module for LG TV Tools.

This module provides the cross-platform Flet-based user interface
that works on desktop (full features) and mobile (remote-control subset).
"""

from __future__ import annotations

__all__ = [
    "main",
    "AppTheme",
]

from lgtvtools.flet_ui.theme import AppTheme


def main() -> None:
    """Entry point for the Flet application."""
    from lgtvtools.flet_ui.app import run_app
    run_app()
