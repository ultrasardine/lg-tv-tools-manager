"""TV remote control component."""

from __future__ import annotations

from typing import Callable

import flet as ft

from lgtvtools.flet_ui.theme import AppColors


def RemoteButton(
    icon: str | None = None,
    label: str | None = None,
    on_click: Callable[[], None] | None = None,
    size: str = "normal",  # "small", "normal", "large"
    circular: bool = True,
) -> ft.Container:
    """Create a single remote control button.

    Args:
        icon: Flet icon name.
        label: Text label (used if no icon).
        on_click: Click callback.
        size: Button size ("small", "normal", "large").
        circular: Whether button is circular.

    Returns:
        A Container with the remote button.
    """
    sizes = {
        "small": (36, 16),
        "normal": (48, 20),
        "large": (64, 28),
    }
    btn_size, icon_size = sizes.get(size, (48, 20))

    if icon:
        return ft.Container(
            content=ft.IconButton(
                icon=icon,
                icon_size=icon_size,
                icon_color=AppColors.TEXT_PRIMARY,
                on_click=lambda e: on_click() if on_click else None,
                style=ft.ButtonStyle(
                    shape=ft.CircleBorder() if circular else ft.RoundedRectangleBorder(radius=8),
                    bgcolor=AppColors.SURFACE_VARIANT,
                    padding=8,
                ),
                width=btn_size,
                height=btn_size,
            ),
        )
    else:
        return ft.Container(
            content=ft.ElevatedButton(
                text=label or "",
                on_click=lambda e: on_click() if on_click else None,
                style=ft.ButtonStyle(
                    shape=ft.CircleBorder() if circular else ft.RoundedRectangleBorder(radius=8),
                    bgcolor=AppColors.SURFACE_VARIANT,
                    padding=8,
                ),
                width=btn_size,
                height=btn_size,
            ),
        )


def RemoteControl(
    on_power: Callable[[], None] | None = None,
    on_volume_up: Callable[[], None] | None = None,
    on_volume_down: Callable[[], None] | None = None,
    on_mute: Callable[[], None] | None = None,
    on_channel_up: Callable[[], None] | None = None,
    on_channel_down: Callable[[], None] | None = None,
    on_play: Callable[[], None] | None = None,
    on_pause: Callable[[], None] | None = None,
    on_stop: Callable[[], None] | None = None,
    on_rewind: Callable[[], None] | None = None,
    on_forward: Callable[[], None] | None = None,
    on_home: Callable[[], None] | None = None,
    on_back: Callable[[], None] | None = None,
    on_close: Callable[[], None] | None = None,
) -> ft.Container:
    """Create a full TV remote control panel.

    Provides:
    - Power button
    - Volume controls
    - Media controls (play/pause, stop, forward, rewind)
    - Channel controls
    - Navigation buttons (home, back)

    Args:
        on_power: Power button callback.
        on_volume_up: Volume up callback.
        on_volume_down: Volume down callback.
        on_mute: Mute callback.
        on_channel_up: Channel up callback.
        on_channel_down: Channel down callback.
        on_play: Play callback.
        on_pause: Pause callback.
        on_stop: Stop callback.
        on_rewind: Rewind callback.
        on_forward: Forward callback.
        on_home: Home callback.
        on_back: Back callback.
        on_close: Close remote callback.

    Returns:
        A Container with the remote control UI.
    """
    # Header with close button
    header = ft.Container(
        content=ft.Row(
            controls=[
                ft.Text(
                    "Remote Control",
                    size=18,
                    weight=ft.FontWeight.W_500,
                    color=AppColors.TEXT_PRIMARY,
                ),
                ft.IconButton(
                    icon=ft.Icons.CLOSE,
                    icon_color=AppColors.TEXT_SECONDARY,
                    on_click=lambda e: on_close() if on_close else None,
                    tooltip="Close remote",
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        padding=ft.Padding(bottom=16),
    )

    # Power button row
    power_row = ft.Row(
        controls=[
            RemoteButton(
                icon=ft.Icons.POWER_SETTINGS_NEW,
                on_click=on_power,
                size="large",
            ),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
    )

    # Volume and channel controls
    vol_channel_row = ft.Row(
        controls=[
            # Volume controls
            ft.Column(
                controls=[
                    ft.Text("VOL", size=10, color=AppColors.TEXT_SECONDARY),
                    RemoteButton(icon=ft.Icons.ADD, on_click=on_volume_up),
                    RemoteButton(icon=ft.Icons.VOLUME_OFF, on_click=on_mute, size="small"),
                    RemoteButton(icon=ft.Icons.REMOVE, on_click=on_volume_down),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
            ),
            ft.Container(width=48),  # Spacer
            # Channel controls
            ft.Column(
                controls=[
                    ft.Text("CH", size=10, color=AppColors.TEXT_SECONDARY),
                    RemoteButton(icon=ft.Icons.KEYBOARD_ARROW_UP, on_click=on_channel_up),
                    ft.Container(height=28),
                    RemoteButton(icon=ft.Icons.KEYBOARD_ARROW_DOWN, on_click=on_channel_down),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
            ),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
    )

    # Media controls
    media_row = ft.Row(
        controls=[
            RemoteButton(icon=ft.Icons.FAST_REWIND, on_click=on_rewind),
            RemoteButton(icon=ft.Icons.PLAY_ARROW, on_click=on_play, size="large"),
            RemoteButton(icon=ft.Icons.PAUSE, on_click=on_pause),
            RemoteButton(icon=ft.Icons.STOP, on_click=on_stop),
            RemoteButton(icon=ft.Icons.FAST_FORWARD, on_click=on_forward),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=8,
    )

    # Navigation buttons (Home, Back)
    nav_row = ft.Row(
        controls=[
            RemoteButton(icon=ft.Icons.HOME, on_click=on_home),
            ft.Container(width=48),
            RemoteButton(icon=ft.Icons.ARROW_BACK, on_click=on_back),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
    )

    return ft.Container(
        content=ft.Column(
            controls=[
                header,
                power_row,
                ft.Container(height=24),
                vol_channel_row,
                ft.Container(height=24),
                ft.Text("Media", size=12, color=AppColors.TEXT_SECONDARY),
                media_row,
                ft.Container(height=16),
                ft.Text("Navigation", size=12, color=AppColors.TEXT_SECONDARY),
                nav_row,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        ),
        bgcolor=AppColors.SURFACE,
        border_radius=12,
        padding=20,
        width=320,
    )
