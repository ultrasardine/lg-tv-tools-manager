"""Action panel component with TV control buttons."""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from lgtvtools.core.runtime import Runtime
from lgtvtools.flet_ui.theme import AppColors


def ActionButton(
    label: str,
    icon: str,
    on_click: Callable[[], None] | None = None,
    disabled: bool = False,
    primary: bool = False,
    tooltip: str | None = None,
) -> ft.Container:
    """Create a styled action button with icon and label.

    Args:
        label: Button text.
        icon: Flet icon name.
        on_click: Click callback.
        disabled: Whether button is disabled.
        primary: Whether to use primary color.
        tooltip: Tooltip text.

    Returns:
        A Container with the styled button.
    """
    bgcolor = AppColors.PRIMARY if primary else AppColors.SURFACE_VARIANT
    if disabled:
        bgcolor = AppColors.SURFACE

    return ft.Container(
        content=ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        icon,
                        size=18,
                        color=AppColors.TEXT_PRIMARY if not disabled else AppColors.TEXT_DISABLED,
                    ),
                    ft.Text(
                        label,
                        size=14,
                        color=AppColors.TEXT_PRIMARY if not disabled else AppColors.TEXT_DISABLED,
                    ),
                ],
                spacing=8,
                tight=True,
            ),
            bgcolor=bgcolor,
            on_click=lambda _: on_click() if on_click else None,
            disabled=disabled,
            tooltip=tooltip,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding(left=16, right=16, top=12, bottom=12),
            ),
        ),
        margin=ft.Margin(bottom=8),
    )


def ActionPanel(
    runtime: Runtime,
    has_selection: bool = False,
    is_mirroring: bool = False,
    on_pair: Callable[[], None] | None = None,
    on_mirror: Callable[[], None] | None = None,
    on_cast_url: Callable[[], None] | None = None,
    on_send_video: Callable[[], None] | None = None,
    on_send_image: Callable[[], None] | None = None,
    on_send_music: Callable[[], None] | None = None,
    on_show_remote: Callable[[], None] | None = None,
    on_open_vlc: Callable[[], None] | None = None,
    on_open_gnd: Callable[[], None] | None = None,
    status_text: str = "Ready",
    selected_tv_name: str = "No TV selected",
) -> ft.Container:
    """Create action panel with TV control buttons.

    Displays different buttons based on runtime capabilities:
    - Desktop: Full set (Pair, Mirror, Cast, Media, Tools)
    - Mobile: Subset (Pair, Cast, Remote)

    Args:
        runtime: Runtime detection instance.
        has_selection: Whether a TV is selected.
        is_mirroring: Whether currently mirroring.
        on_pair: Pair button callback.
        on_mirror: Mirror button callback.
        on_cast_url: Cast URL button callback.
        on_send_video: Send video callback.
        on_send_image: Send image callback.
        on_send_music: Send music callback.
        on_show_remote: Show remote callback.
        on_open_vlc: Open VLC callback.
        on_open_gnd: Open GND callback.
        status_text: Status text to display.
        selected_tv_name: Name of selected TV.

    Returns:
        A Container with the action panel UI.
    """
    buttons: list[ft.Control] = []

    # Pair button (always available)
    buttons.append(
        ActionButton(
            label="Pair TV",
            icon=ft.Icons.LINK,
            on_click=on_pair,
            disabled=not has_selection,
            primary=True,
            tooltip="Connect and pair with the selected TV",
        )
    )

    # Remote control button (always available)
    buttons.append(
        ActionButton(
            label="Remote",
            icon=ft.Icons.SETTINGS_REMOTE,
            on_click=on_show_remote,
            disabled=not has_selection,
            tooltip="Open TV remote control",
        )
    )

    # Cast URL button (always available)
    buttons.append(
        ActionButton(
            label="Cast URL",
            icon=ft.Icons.LINK,
            on_click=on_cast_url,
            disabled=not has_selection,
            tooltip="Open a URL on the TV browser",
        )
    )

    # Desktop-only features
    if runtime.is_desktop:
        # Mirror button (desktop only, requires ffmpeg)
        if runtime.can_mirror:
            mirror_label = "Stop Mirror" if is_mirroring else "Mirror"
            buttons.append(
                ActionButton(
                    label=mirror_label,
                    icon=ft.Icons.SCREEN_SHARE if not is_mirroring else ft.Icons.STOP_SCREEN_SHARE,
                    on_click=on_mirror,
                    disabled=not has_selection,
                    tooltip="Mirror your screen to the TV",
                )
            )

        # Media buttons (desktop only)
        buttons.append(
            ActionButton(
                label="Video",
                icon=ft.Icons.VIDEO_FILE,
                on_click=on_send_video,
                disabled=not has_selection,
                tooltip="Send a video file to the TV",
            )
        )

        buttons.append(
            ActionButton(
                label="Image",
                icon=ft.Icons.IMAGE,
                on_click=on_send_image,
                disabled=not has_selection,
                tooltip="Send an image file to the TV",
            )
        )

        buttons.append(
            ActionButton(
                label="Music",
                icon=ft.Icons.MUSIC_NOTE,
                on_click=on_send_music,
                disabled=not has_selection,
                tooltip="Send a music file to the TV",
            )
        )

        # External tool buttons (desktop only)
        if runtime.has_vlc:
            buttons.append(
                ActionButton(
                    label="Open VLC",
                    icon=ft.Icons.PLAY_CIRCLE,
                    on_click=on_open_vlc,
                    tooltip="Open VLC media player",
                )
            )

        if runtime.is_linux:
            buttons.append(
                ActionButton(
                    label="Open GND",
                    icon=ft.Icons.CAST,
                    on_click=on_open_gnd,
                    tooltip="Open GNOME Network Displays",
                )
            )

    # Status section
    status_section = ft.Container(
        content=ft.Column(
            controls=[
                ft.Divider(height=1, color=AppColors.BORDER),
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                f"TV: {selected_tv_name}",
                                size=12,
                                color=AppColors.TEXT_SECONDARY,
                                max_lines=2,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            ft.Text(
                                status_text,
                                size=14,
                                color=AppColors.TEXT_PRIMARY,
                                weight=ft.FontWeight.W_500,
                            ),
                        ],
                        spacing=4,
                    ),
                    padding=ft.Padding(top=8, bottom=8),
                ),
            ],
            spacing=8,
        ),
        margin=ft.Margin(top=8),
    )

    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Text(
                    "Actions",
                    size=16,
                    weight=ft.FontWeight.W_500,
                    color=AppColors.TEXT_PRIMARY,
                ),
                ft.Container(height=8),
                *buttons,
                status_section,
            ],
            scroll=ft.ScrollMode.AUTO,
        ),
        bgcolor=AppColors.SURFACE,
        border_radius=8,
        padding=16,
        expand=True,
    )
