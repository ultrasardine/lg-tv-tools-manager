"""Device list component for displaying discovered LG TVs."""

from __future__ import annotations

from typing import Callable

import flet as ft

from lgtvtools.core.models import LGTVDevice
from lgtvtools.flet_ui.theme import AppColors


def create_device_tile(
    device: LGTVDevice,
    selected_device: LGTVDevice | None,
    on_select: Callable[[LGTVDevice], None] | None,
) -> ft.Container:
    """Create a list tile for a device."""
    is_selected = selected_device and selected_device.ip == device.ip

    # Discovery source indicator
    source_icon = ft.Icon(
        ft.Icons.WIFI if device.discovery_source == "ssdp" else ft.Icons.BLUETOOTH,
        size=14,
        color=AppColors.TEXT_SECONDARY,
        tooltip=f"Discovered via {device.discovery_source.upper()}",
    )

    # Model info if available
    subtitle_parts = [device.ip]
    if device.model:
        subtitle_parts.append(device.model)

    def on_click(e: ft.ControlEvent) -> None:
        if on_select:
            on_select(device)

    return ft.Container(
        content=ft.ListTile(
            leading=ft.Icon(
                ft.Icons.TV,
                color=AppColors.PRIMARY if is_selected else AppColors.TEXT_SECONDARY,
            ),
            title=ft.Text(
                device.name or "LG TV",
                color=AppColors.TEXT_PRIMARY,
                weight=ft.FontWeight.W_500 if is_selected else ft.FontWeight.NORMAL,
            ),
            subtitle=ft.Row(
                controls=[
                    ft.Text(
                        " - ".join(subtitle_parts),
                        size=12,
                        color=AppColors.TEXT_SECONDARY,
                    ),
                    source_icon,
                ],
                spacing=8,
            ),
            trailing=ft.Icon(
                ft.Icons.CHECK_CIRCLE,
                color=AppColors.SUCCESS,
                visible=is_selected,
            ),
            on_click=on_click,
        ),
        bgcolor=AppColors.SURFACE_VARIANT if is_selected else AppColors.SURFACE,
        border_radius=8,
        margin=ft.Margin(bottom=8),
        animate=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT),
    )


def create_empty_state() -> ft.Container:
    """Create the empty state view when no devices are found."""
    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Icon(
                    ft.Icons.TV_OFF,
                    size=48,
                    color=AppColors.TEXT_DISABLED,
                ),
                ft.Text(
                    "No TVs found",
                    size=16,
                    color=AppColors.TEXT_SECONDARY,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    "Make sure your LG TV is on and connected to the same network",
                    size=12,
                    color=AppColors.TEXT_DISABLED,
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        ),
        padding=32,
        alignment=ft.Alignment(0, 0),
    )


def create_scanning_indicator() -> ft.Container:
    """Create the scanning in progress indicator."""
    return ft.Container(
        content=ft.Row(
            controls=[
                ft.ProgressRing(
                    width=16,
                    height=16,
                    stroke_width=2,
                    color=AppColors.PRIMARY,
                ),
                ft.Text(
                    "Scanning for TVs...",
                    size=14,
                    color=AppColors.TEXT_SECONDARY,
                ),
            ],
            spacing=12,
        ),
        padding=16,
    )


def DeviceList(
    devices: list[LGTVDevice],
    selected_device: LGTVDevice | None = None,
    on_select: Callable[[LGTVDevice], None] | None = None,
    on_refresh: Callable[[], None] | None = None,
    is_scanning: bool = False,
) -> ft.Container:
    """Create a device list component displaying discovered LG TVs.

    Shows TV name, IP address, and discovery source indicator.
    Supports selection with visual feedback.

    Args:
        devices: List of discovered TV devices.
        selected_device: Currently selected device (if any).
        on_select: Callback when a device is selected.
        on_refresh: Callback when refresh button is clicked.
        is_scanning: Whether a scan is in progress.

    Returns:
        A Container with the device list UI.
    """
    # Header with title and refresh button
    header = ft.Container(
        content=ft.Row(
            controls=[
                ft.Text(
                    "LG TVs",
                    size=16,
                    weight=ft.FontWeight.W_500,
                    color=AppColors.TEXT_PRIMARY,
                ),
                ft.IconButton(
                    icon=ft.Icons.REFRESH,
                    icon_color=AppColors.TEXT_SECONDARY,
                    tooltip="Scan for TVs",
                    on_click=lambda e: on_refresh() if on_refresh else None,
                    disabled=is_scanning,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        padding=ft.Padding(left=16, right=8, top=8, bottom=8),
    )

    # Content area
    if is_scanning and not devices:
        content = create_scanning_indicator()
    elif not devices:
        content = create_empty_state()
    else:
        device_tiles = [create_device_tile(d, selected_device, on_select) for d in devices]
        content = ft.Column(
            controls=device_tiles,
            scroll=ft.ScrollMode.AUTO,
            spacing=0,
        )

    # Scanning indicator at top if scanning with devices
    if is_scanning and devices:
        content = ft.Column(
            controls=[
                create_scanning_indicator(),
                content,
            ],
            spacing=0,
        )

    return ft.Container(
        content=ft.Column(
            controls=[header, content],
            spacing=0,
            expand=True,
        ),
        bgcolor=AppColors.SURFACE,
        border_radius=8,
        expand=True,
    )
