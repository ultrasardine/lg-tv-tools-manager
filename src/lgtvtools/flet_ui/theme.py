"""Theme definitions for the Flet UI.

Defines the color scheme, typography, and component styles
for the LG TV Tools application.
"""

from __future__ import annotations

import flet as ft


class AppColors:
    """Application color palette."""

    # Primary colors (dark theme)
    BACKGROUND = "#111319"
    SURFACE = "#1a1d24"
    SURFACE_VARIANT = "#252830"

    # Accent colors
    PRIMARY = "#4a9eff"
    PRIMARY_VARIANT = "#2d7dd2"
    SECONDARY = "#7c4dff"

    # Text colors
    TEXT_PRIMARY = "#e7e7e7"
    TEXT_SECONDARY = "#a0a0a0"
    TEXT_DISABLED = "#606060"

    # Status colors
    SUCCESS = "#4caf50"
    WARNING = "#ff9800"
    ERROR = "#f44336"
    INFO = "#2196f3"

    # Border colors
    BORDER = "#333640"
    BORDER_FOCUS = "#4a9eff"


class AppTheme:
    """Application theme configuration."""

    @staticmethod
    def get_theme() -> ft.Theme:
        """Get the Flet theme configuration."""
        return ft.Theme(
            color_scheme_seed=AppColors.PRIMARY,
            color_scheme=ft.ColorScheme(
                primary=AppColors.PRIMARY,
                secondary=AppColors.SECONDARY,
                surface=AppColors.SURFACE,
                error=AppColors.ERROR,
                on_primary=AppColors.TEXT_PRIMARY,
                on_secondary=AppColors.TEXT_PRIMARY,
                on_surface=AppColors.TEXT_PRIMARY,
                on_error=AppColors.TEXT_PRIMARY,
            ),
            text_theme=ft.TextTheme(
                body_large=ft.TextStyle(color=AppColors.TEXT_PRIMARY),
                body_medium=ft.TextStyle(color=AppColors.TEXT_PRIMARY),
                body_small=ft.TextStyle(color=AppColors.TEXT_SECONDARY),
                title_large=ft.TextStyle(color=AppColors.TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                title_medium=ft.TextStyle(color=AppColors.TEXT_PRIMARY, weight=ft.FontWeight.W_500),
                title_small=ft.TextStyle(color=AppColors.TEXT_SECONDARY),
            ),
        )

    @staticmethod
    def apply_to_page(page: ft.Page) -> None:
        """Apply the theme to a Flet page."""
        page.theme_mode = ft.ThemeMode.DARK
        page.theme = AppTheme.get_theme()
        page.bgcolor = AppColors.BACKGROUND
        page.padding = 0


class Styles:
    """Reusable style definitions for components."""

    @staticmethod
    def card() -> dict:
        """Style for card containers."""
        return {
            "bgcolor": AppColors.SURFACE,
            "border_radius": 8,
            "padding": 16,
        }

    @staticmethod
    def card_header() -> dict:
        """Style for card headers."""
        return {
            "size": 16,
            "weight": ft.FontWeight.W_500,
            "color": AppColors.TEXT_PRIMARY,
        }

    @staticmethod
    def primary_button() -> dict:
        """Style for primary action buttons."""
        return {
            "bgcolor": AppColors.PRIMARY,
            "color": AppColors.TEXT_PRIMARY,
            "style": ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding(left=16, right=16, top=12, bottom=12),
            ),
        }

    @staticmethod
    def secondary_button() -> dict:
        """Style for secondary action buttons."""
        return {
            "bgcolor": AppColors.SURFACE_VARIANT,
            "color": AppColors.TEXT_PRIMARY,
            "style": ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding(left=16, right=16, top=12, bottom=12),
            ),
        }

    @staticmethod
    def icon_button() -> dict:
        """Style for icon buttons."""
        return {
            "icon_color": AppColors.TEXT_PRIMARY,
            "style": ft.ButtonStyle(
                shape=ft.CircleBorder(),
                padding=12,
            ),
        }

    @staticmethod
    def text_field() -> dict:
        """Style for text input fields."""
        return {
            "bgcolor": AppColors.SURFACE_VARIANT,
            "border_color": AppColors.BORDER,
            "focused_border_color": AppColors.BORDER_FOCUS,
            "cursor_color": AppColors.PRIMARY,
            "text_style": ft.TextStyle(color=AppColors.TEXT_PRIMARY),
            "border_radius": 8,
        }

    @staticmethod
    def list_tile() -> dict:
        """Style for list tiles."""
        return {
            "bgcolor": AppColors.SURFACE,
            "shape": ft.RoundedRectangleBorder(radius=8),
        }

    @staticmethod
    def selected_list_tile() -> dict:
        """Style for selected list tiles."""
        return {
            "bgcolor": AppColors.SURFACE_VARIANT,
            "shape": ft.RoundedRectangleBorder(radius=8),
        }
