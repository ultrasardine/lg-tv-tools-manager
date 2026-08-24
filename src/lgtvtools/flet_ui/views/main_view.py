"""Main application view."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import flet as ft

from lgtvtools.core.discovery import discover_lg_tvs
from lgtvtools.core.models import LGTVDevice
from lgtvtools.core.webos import connect_to_tv
from lgtvtools.flet_ui.components.action_panel import ActionPanel
from lgtvtools.flet_ui.components.device_list import DeviceList
from lgtvtools.flet_ui.components.dialogs import show_error_dialog, show_url_input_dialog
from lgtvtools.flet_ui.components.remote_control import RemoteControl
from lgtvtools.flet_ui.state import StateManager
from lgtvtools.flet_ui.theme import AppColors

if TYPE_CHECKING:
    from lgtvtools.desktop.desktop_actions import DesktopActions

LOGGER = logging.getLogger(__name__)


class MainView:
    """Main application view controller.

    Manages the main UI logic and state interactions.
    Not a Flet control itself - instead provides a build() method
    that returns the current UI based on state.

    Layout (desktop):
    +----------------+----------------+----------------+
    |   Device List  |    Actions     |  Diagnostics   |
    +----------------+----------------+----------------+

    Layout (mobile):
    +--------------------------------+
    |         Device List            |
    +--------------------------------+
    |          Actions               |
    +--------------------------------+
    """

    def __init__(self, page: ft.Page, state_manager: StateManager) -> None:
        """Initialize the main view.

        Args:
            page: The Flet page.
            state_manager: Application state manager.
        """
        self.page = page
        self.state_manager = state_manager
        self._desktop_actions: DesktopActions | None = None

        # Initialize desktop actions if on desktop
        if state_manager.runtime.is_desktop:
            from lgtvtools.desktop.desktop_actions import DesktopActions
            self._desktop_actions = DesktopActions(page, state_manager)

    async def scan_network(self) -> None:
        """Scan for LG TVs on the network."""
        self.state_manager.set_scanning(True)
        self.state_manager.set_connection_status("Scanning for TVs...")
        self.state_manager.log("Scanning for TVs...")

        try:
            # Run discovery in thread pool to avoid blocking
            devices = await asyncio.to_thread(discover_lg_tvs, 5.0)
            self.state_manager.set_devices(devices)
            self.state_manager.log(f"Found {len(devices)} TV(s)")

            if devices:
                # Auto-select first device if none selected
                if not self.state_manager.state.selected_device:
                    self.state_manager.set_selected_device(devices[0])
                self.state_manager.set_connection_status(f"{len(devices)} TV(s) found")
            else:
                self.state_manager.set_connection_status("No TVs found")
        except Exception as e:
            LOGGER.exception("Discovery failed")
            self.state_manager.set_error(str(e))
            self.state_manager.log(f"Discovery error: {e}")
            self.state_manager.set_connection_status("Scan failed")
        finally:
            self.state_manager.set_scanning(False)

    def on_device_select(self, device: LGTVDevice) -> None:
        """Handle device selection."""
        self.state_manager.set_selected_device(device)
        self.state_manager.log(f"Selected: {device.display_name()}")
        self.state_manager.set_connection_status("TV ready")

    async def pair_tv(self) -> None:
        """Pair with the selected TV."""
        device = self.state_manager.state.selected_device
        if not device:
            return

        self.state_manager.set_connecting(True)
        self.state_manager.set_connection_status("Connecting...")
        self.state_manager.log(f"Pairing with {device.display_name()}...")

        try:
            client, result = await connect_to_tv(device.ip, timeout=30.0)

            if result.ok:
                self.state_manager.set_webos_client(client)
                self.state_manager.set_connection_status("Paired")
                self.state_manager.log("Paired successfully")

                # Show toast on TV
                await client.show_toast("LG TV Tools connected!")
            else:
                self.state_manager.set_error(result.message)
                self.state_manager.log(f"Pairing failed: {result.message}")
                self.state_manager.set_connection_status("Pairing failed")
                await show_error_dialog(self.page, "Pairing Failed", result.message)
        except Exception as e:
            LOGGER.exception("Pairing failed")
            self.state_manager.set_error(str(e))
            self.state_manager.log(f"Pairing error: {e}")
            self.state_manager.set_connection_status("Error")
            await show_error_dialog(self.page, "Error", str(e))
        finally:
            self.state_manager.set_connecting(False)

    async def cast_url(self) -> None:
        """Cast a URL to the TV."""
        device = self.state_manager.state.selected_device
        if not device:
            return

        async def on_submit(url: str) -> None:
            self.state_manager.log(f"Casting URL: {url}")
            self.state_manager.set_connection_status("Casting...")

            try:
                # Connect if not already
                client = self.state_manager.state.webos_client
                if not client or not client.is_connected:
                    client, result = await connect_to_tv(device.ip, timeout=15.0)
                    if not result.ok:
                        await show_error_dialog(self.page, "Connection Failed", result.message)
                        return
                    self.state_manager.set_webos_client(client)

                result = await client.launch_browser(url)
                if result.ok:
                    self.state_manager.log(f"Casted: {url}")
                    self.state_manager.set_connection_status("Casting")
                else:
                    self.state_manager.log(f"Cast failed: {result.message}")
                    await show_error_dialog(self.page, "Cast Failed", result.message)
            except Exception as e:
                LOGGER.exception("Cast failed")
                self.state_manager.log(f"Cast error: {e}")
                await show_error_dialog(self.page, "Error", str(e))

        await show_url_input_dialog(
            self.page,
            title=f"Cast to {device.name}",
            hint="Enter URL (e.g., youtube.com/watch?v=...)",
            on_submit=on_submit,
        )

    async def start_mirror(self) -> None:
        """Start or stop screen mirroring."""
        if not self._desktop_actions:
            return

        # Use native mirroring
        await self._desktop_actions.start_native_mirror()

    def show_remote(self) -> None:
        """Show the remote control overlay."""
        self.state_manager.set_show_remote(True)

    def hide_remote(self) -> None:
        """Hide the remote control overlay."""
        self.state_manager.set_show_remote(False)

    async def remote_action(self, action: str) -> None:
        """Execute a remote control action."""
        client = self.state_manager.state.webos_client
        if not client:
            # Try to connect first
            device = self.state_manager.state.selected_device
            if device:
                client, result = await connect_to_tv(device.ip, timeout=15.0)
                if result.ok:
                    self.state_manager.set_webos_client(client)
                else:
                    self.state_manager.log(f"Connection failed: {result.message}")
                    return

        if not client:
            self.state_manager.log("Not connected to TV")
            return

        try:
            result = None
            if action == "power":
                result = await client.power_off()
            elif action == "volume_up":
                result = await client.volume_up()
            elif action == "volume_down":
                result = await client.volume_down()
            elif action == "mute":
                result = await client.toggle_mute()
            elif action == "channel_up":
                result = await client.channel_up()
            elif action == "channel_down":
                result = await client.channel_down()
            elif action == "play":
                result = await client.play()
            elif action == "pause":
                result = await client.pause()
            elif action == "stop":
                result = await client.stop()
            elif action == "rewind":
                result = await client.rewind()
            elif action == "forward":
                result = await client.fast_forward()
            elif action == "home" or action == "back":
                result = await client.launch_app("com.webos.app.home")

            if result and not result.ok:
                self.state_manager.log(f"Remote action failed: {result.message}")
        except Exception as e:
            LOGGER.exception("Remote action failed")
            self.state_manager.log(f"Remote error: {e}")

    def _build_device_list(self) -> ft.Control:
        """Build the device list component."""
        state = self.state_manager.state
        return DeviceList(
            devices=state.devices,
            selected_device=state.selected_device,
            on_select=self.on_device_select,
            on_refresh=lambda: self.page.run_task(self.scan_network),
            is_scanning=state.is_scanning,
        )

    def _build_action_panel(self) -> ft.Control:
        """Build the action panel component."""
        state = self.state_manager.state
        runtime = self.state_manager.runtime

        return ActionPanel(
            runtime=runtime,
            has_selection=state.selected_device is not None,
            is_mirroring=state.is_mirroring,
            on_pair=lambda: self.page.run_task(self.pair_tv),
            on_cast_url=lambda: self.page.run_task(self.cast_url),
            on_show_remote=self.show_remote,
            # Desktop-only callbacks
            on_mirror=lambda: self.page.run_task(self.start_mirror) if self._desktop_actions else None,
            on_send_video=lambda: self.page.run_task(self._desktop_actions.send_video) if self._desktop_actions else None,
            on_send_image=lambda: self.page.run_task(self._desktop_actions.send_image) if self._desktop_actions else None,
            on_send_music=lambda: self.page.run_task(self._desktop_actions.send_music) if self._desktop_actions else None,
            on_open_vlc=lambda: self.page.run_task(self._desktop_actions.open_vlc) if self._desktop_actions else None,
            on_open_gnd=lambda: self.page.run_task(self._desktop_actions.open_gnome_network_displays) if self._desktop_actions else None,
            status_text=state.connection_status,
            selected_tv_name=self.state_manager.get_selected_device_name(),
        )

    def _build_diagnostics_panel(self) -> ft.Control:
        """Build the diagnostics panel (desktop only)."""
        state = self.state_manager.state
        runtime = self.state_manager.runtime

        # Capabilities section
        cap_items: list[ft.Control] = []
        if state.capabilities:
            for cap in state.capabilities:
                status_icon = ft.Icons.CHECK_CIRCLE if cap.installed else ft.Icons.CANCEL
                status_color = AppColors.SUCCESS if cap.installed else AppColors.TEXT_DISABLED
                cap_items.append(
                    ft.Row(
                        controls=[
                            ft.Icon(status_icon, size=14, color=status_color),
                            ft.Text(cap.name, size=12, color=AppColors.TEXT_PRIMARY),
                        ],
                        spacing=8,
                    )
                )
        else:
            # Generate capabilities from runtime
            for cap in runtime.get_capabilities_report():
                status_icon = ft.Icons.CHECK_CIRCLE if cap.installed else ft.Icons.CANCEL
                status_color = AppColors.SUCCESS if cap.installed else AppColors.TEXT_DISABLED
                cap_items.append(
                    ft.Row(
                        controls=[
                            ft.Icon(status_icon, size=14, color=status_color),
                            ft.Text(cap.name, size=12, color=AppColors.TEXT_PRIMARY),
                        ],
                        spacing=8,
                    )
                )

        # Log section
        log_text = "\n".join(state.log_messages[-20:]) if state.log_messages else "No logs yet"

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Diagnostics",
                        size=16,
                        weight=ft.FontWeight.W_500,
                        color=AppColors.TEXT_PRIMARY,
                    ),
                    ft.Container(height=8),
                    ft.Text("Dependencies", size=12, color=AppColors.TEXT_SECONDARY),
                    ft.Container(
                        content=ft.Column(controls=cap_items, spacing=4),
                        bgcolor=AppColors.SURFACE_VARIANT,
                        border_radius=8,
                        padding=12,
                    ),
                    ft.Container(height=16),
                    ft.Text("Logs", size=12, color=AppColors.TEXT_SECONDARY),
                    ft.Container(
                        content=ft.Text(
                            log_text,
                            size=11,
                            color=AppColors.TEXT_SECONDARY,
                            selectable=True,
                        ),
                        bgcolor=AppColors.SURFACE_VARIANT,
                        border_radius=8,
                        padding=12,
                        expand=True,
                    ),
                ],
                scroll=ft.ScrollMode.AUTO,
            ),
            bgcolor=AppColors.SURFACE,
            border_radius=8,
            padding=16,
            expand=True,
        )

    def _build_remote_overlay(self) -> ft.Control | None:
        """Build the remote control overlay if visible."""
        if not self.state_manager.state.show_remote:
            return None

        return ft.Container(
            content=ft.Stack(
                controls=[
                    # Semi-transparent backdrop
                    ft.Container(
                        bgcolor="#00000080",
                        expand=True,
                        on_click=lambda _: self.hide_remote(),
                    ),
                    # Remote control centered
                    ft.Container(
                        content=RemoteControl(
                            on_power=lambda: self.page.run_task(lambda: self.remote_action("power")),
                            on_volume_up=lambda: self.page.run_task(lambda: self.remote_action("volume_up")),
                            on_volume_down=lambda: self.page.run_task(lambda: self.remote_action("volume_down")),
                            on_mute=lambda: self.page.run_task(lambda: self.remote_action("mute")),
                            on_channel_up=lambda: self.page.run_task(lambda: self.remote_action("channel_up")),
                            on_channel_down=lambda: self.page.run_task(lambda: self.remote_action("channel_down")),
                            on_play=lambda: self.page.run_task(lambda: self.remote_action("play")),
                            on_pause=lambda: self.page.run_task(lambda: self.remote_action("pause")),
                            on_stop=lambda: self.page.run_task(lambda: self.remote_action("stop")),
                            on_rewind=lambda: self.page.run_task(lambda: self.remote_action("rewind")),
                            on_forward=lambda: self.page.run_task(lambda: self.remote_action("forward")),
                            on_home=lambda: self.page.run_task(lambda: self.remote_action("home")),
                            on_back=lambda: self.page.run_task(lambda: self.remote_action("back")),
                            on_close=self.hide_remote,
                        ),
                        alignment=ft.Alignment(0, 0),
                    ),
                ],
            ),
            expand=True,
        )

    def build(self) -> ft.Control:
        """Build the main view UI."""
        runtime = self.state_manager.runtime

        # Build main content based on platform
        if runtime.is_desktop:
            # Desktop: 3-column layout
            main_content = ft.Row(
                controls=[
                    ft.Container(
                        content=self._build_device_list(),
                        expand=1,
                        padding=8,
                    ),
                    ft.Container(
                        content=self._build_action_panel(),
                        expand=1,
                        padding=8,
                    ),
                    ft.Container(
                        content=self._build_diagnostics_panel(),
                        expand=1,
                        padding=8,
                    ),
                ],
                expand=True,
            )
        else:
            # Mobile: vertical layout
            main_content = ft.Column(
                controls=[
                    ft.Container(
                        content=self._build_device_list(),
                        expand=2,
                        padding=8,
                    ),
                    ft.Container(
                        content=self._build_action_panel(),
                        expand=1,
                        padding=8,
                    ),
                ],
                expand=True,
            )

        # Build with optional overlay
        remote_overlay = self._build_remote_overlay()

        if remote_overlay:
            return ft.Stack(
                controls=[
                    main_content,
                    remote_overlay,
                ],
                expand=True,
            )

        return main_content

    def cleanup(self) -> None:
        """Clean up resources."""
        if self._desktop_actions:
            self._desktop_actions.cleanup()
