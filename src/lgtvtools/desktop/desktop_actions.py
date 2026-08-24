"""Desktop-specific actions for the Flet UI.

This module provides desktop-only functionality that integrates with
the Flet UI layer: file picking, media sharing, external tool launching,
and screen mirroring orchestration.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import flet as ft

from lgtvtools.core.discovery.upnp import cast_media_to_device
from lgtvtools.core.webos import connect_to_tv
from lgtvtools.desktop.actions.launchers import (
    launch_external,
    launch_gnome_network_displays,
    launch_vlc,
    start_screen_mirror_native,
)
from lgtvtools.desktop.actions.media_share import MediaShareServer

if TYPE_CHECKING:
    from lgtvtools.flet_ui.state import StateManager

LOGGER = logging.getLogger(__name__)


# File type definitions for the file picker
MEDIA_TYPES = {
    "video": {
        "label": "Video Files",
        "extensions": ["mp4", "mkv", "avi", "webm", "mov", "m4v", "wmv"],
    },
    "image": {
        "label": "Image Files",
        "extensions": ["png", "jpg", "jpeg", "gif", "bmp", "webp"],
    },
    "music": {
        "label": "Audio Files",
        "extensions": ["mp3", "flac", "wav", "ogg", "m4a", "aac"],
    },
}


class DesktopActions:
    """Desktop-specific actions integrated with Flet UI.

    Provides methods for:
    - File picking and media sharing
    - External tool launching (VLC, GNOME Network Displays)
    - Screen mirroring orchestration
    - Clipboard operations

    Usage:
        desktop_actions = DesktopActions(page, state_manager)

        # Connect callbacks to UI buttons
        btn_video.on_click = lambda e: page.run_task(
            desktop_actions.send_video
        )
    """

    def __init__(
        self,
        page: ft.Page,
        state_manager: StateManager,
    ) -> None:
        """Initialize desktop actions.

        Args:
            page: The Flet page.
            state_manager: Application state manager.
        """
        self.page = page
        self.state_manager = state_manager
        self._share_server = MediaShareServer()
        self._file_picker: ft.FilePicker | None = None
        self._pending_media_type: str | None = None

    @property
    def share_server(self) -> MediaShareServer:
        """Get the media share server instance."""
        return self._share_server

    def _ensure_file_picker(self) -> ft.FilePicker:
        """Ensure the file picker is created and added to the page."""
        if self._file_picker is None:
            self._file_picker = ft.FilePicker(
                on_result=self._on_file_picked,
            )
            self.page.overlay.append(self._file_picker)
            self.page.update()
        return self._file_picker

    def _on_file_picked(self, e: ft.FilePickerResultEvent) -> None:
        """Handle file picker result."""
        if not e.files or not self._pending_media_type:
            self._pending_media_type = None
            return

        file_path = e.files[0].path
        if file_path:
            self.page.run_task(
                lambda: self._send_media_file(file_path, self._pending_media_type or "video")
            )
        self._pending_media_type = None

    async def _send_media_file(self, file_path: str, media_type: str) -> None:
        """Send a media file to the TV.

        Args:
            file_path: Path to the media file.
            media_type: Type of media ("video", "image", "music").
        """
        device = self.state_manager.state.selected_device
        if not device:
            return

        filename = Path(file_path).name
        self.state_manager.log(f"Sharing {media_type}: {filename}")
        self.state_manager.set_connection_status("Sharing media...")

        try:
            # Publish the file via HTTP server
            share_url = self._share_server.publish(file_path)
            self.state_manager.set_share_url(share_url)
            self.state_manager.log(f"URL: {share_url}")

            # Try UPnP first
            result = await asyncio.to_thread(
                cast_media_to_device,
                device,
                share_url,
                filename,
            )

            if result.ok:
                self.state_manager.log(f"UPnP cast to {device.display_name()}")
                self.state_manager.set_connection_status("Sent via UPnP")
                return

            self.state_manager.log(f"UPnP: {result.status.value} - {result.message}")

            # Fall back to WebOS API
            self.state_manager.set_connection_status("Trying WebOS...")

            client = self.state_manager.state.webos_client
            if not client or not client.is_connected:
                client, connect_result = await connect_to_tv(device.ip, timeout=15.0)
                if not connect_result.ok:
                    self.state_manager.log(f"Connection failed: {connect_result.message}")
                    self.state_manager.set_connection_status("Connection failed")
                    await self._show_error("Connection Failed", connect_result.message)
                    return
                self.state_manager.set_webos_client(client)

            ws_result = await client.open_media_url(share_url, filename)
            if ws_result.ok:
                self.state_manager.log(f"Sent via WebOS: {filename}")
                self.state_manager.set_connection_status("Sent via WebOS")
            else:
                self.state_manager.log(f"WebOS failed: {ws_result.message}")
                self.state_manager.set_connection_status("Send failed")
                await self._show_error("Media Send Failed", ws_result.message)

        except Exception as e:
            LOGGER.exception("Failed to send media")
            self.state_manager.log(f"Error: {e}")
            self.state_manager.set_connection_status("Error")
            await self._show_error("Error", str(e))

    async def _show_error(self, title: str, message: str) -> None:
        """Show an error dialog."""
        from lgtvtools.flet_ui.components.dialogs import show_error_dialog
        await show_error_dialog(self.page, title, message)

    # =========================================================================
    # Public Methods - Media Actions
    # =========================================================================

    async def send_video(self) -> None:
        """Open file picker and send a video file."""
        await self._pick_and_send_media("video")

    async def send_image(self) -> None:
        """Open file picker and send an image file."""
        await self._pick_and_send_media("image")

    async def send_music(self) -> None:
        """Open file picker and send a music file."""
        await self._pick_and_send_media("music")

    async def _pick_and_send_media(self, media_type: str) -> None:
        """Open file picker for the specified media type.

        Args:
            media_type: Type of media to pick ("video", "image", "music").
        """
        if not self.state_manager.has_selected_device():
            await self._show_error("No TV Selected", "Please select a TV first.")
            return

        type_info = MEDIA_TYPES.get(media_type)
        if not type_info:
            return

        self._pending_media_type = media_type
        picker = self._ensure_file_picker()

        # Create allowed extensions
        allowed_extensions = type_info["extensions"]

        picker.pick_files(
            dialog_title=f"Select {type_info['label'].lower()}",
            allowed_extensions=allowed_extensions,
            allow_multiple=False,
        )

    # =========================================================================
    # Public Methods - External Tools
    # =========================================================================

    async def open_vlc(self) -> None:
        """Launch VLC media player."""
        result = await asyncio.to_thread(launch_vlc)
        self.state_manager.log(result.message)
        if not result.ok:
            await self._show_error("VLC", result.message)

    async def open_gnome_network_displays(self) -> None:
        """Launch GNOME Network Displays."""
        result = await asyncio.to_thread(launch_gnome_network_displays)
        self.state_manager.log(result.message)
        if not result.ok:
            await self._show_error("GNOME Network Displays", result.message)

    async def start_native_mirror(self) -> None:
        """Start native screen mirroring."""
        device = self.state_manager.state.selected_device
        device_name = device.name if device else ""
        device_ip = device.ip if device else ""

        result = await asyncio.to_thread(
            start_screen_mirror_native,
            device_ip,
            device_name,
        )
        self.state_manager.log(result.message)
        if not result.ok:
            await self._show_error("Screen Mirror", result.message)

    async def launch_external_app(self, command: str, args: list[str] | None = None) -> None:
        """Launch an external application.

        Args:
            command: Command to launch.
            args: Optional arguments.
        """
        result = await asyncio.to_thread(launch_external, command, args)
        self.state_manager.log(result.message)
        if not result.ok:
            await self._show_error("Launch Failed", result.message)

    # =========================================================================
    # Public Methods - Clipboard
    # =========================================================================

    async def copy_share_url(self) -> None:
        """Copy the last share URL to clipboard."""
        url = self.state_manager.state.share_url
        if not url:
            url = self._share_server.base_url or "No URL available"

        self.page.set_clipboard(url)
        self.state_manager.log(f"Copied: {url}")

        # Show snackbar
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(f"Copied: {url}"),
            action="OK",
        )
        self.page.snack_bar.open = True
        self.page.update()

    # =========================================================================
    # Cleanup
    # =========================================================================

    def cleanup(self) -> None:
        """Clean up resources."""
        self._share_server.close()
