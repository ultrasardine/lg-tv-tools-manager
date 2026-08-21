"""Application state management for the Flet UI.

Provides a reactive state container that triggers UI updates
when state changes. Uses callbacks to notify the UI layer.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from lgtvtools.core.models import AppState, Capability, LGTVDevice
from lgtvtools.core.runtime import Runtime
from lgtvtools.core.webos import WebOSClient

LOGGER = logging.getLogger(__name__)


@dataclass
class UIState(AppState):
    """Extended application state with UI-specific fields.

    Inherits from AppState and adds fields for UI management.
    """

    # UI state
    current_view: str = "main"
    show_remote: bool = False
    show_settings: bool = False

    # WebOS connection
    webos_client: WebOSClient | None = None

    # Logs
    log_messages: list[str] = field(default_factory=list)
    max_log_messages: int = 100


class StateManager:
    """Manages application state and notifies listeners of changes.

    Usage:
        state_manager = StateManager()
        state_manager.on_change(lambda: page.update())

        # Update state (triggers listener)
        state_manager.set_scanning(True)
        state_manager.set_devices(discovered_devices)
    """

    def __init__(self) -> None:
        """Initialize the state manager."""
        self._state = UIState()
        self._listeners: list[Callable[[], None]] = []
        self._runtime = Runtime.detect()
        self._lock = asyncio.Lock()

    @property
    def state(self) -> UIState:
        """Get the current state (read-only access)."""
        return self._state

    @property
    def runtime(self) -> Runtime:
        """Get the runtime information."""
        return self._runtime

    def on_change(self, callback: Callable[[], None]) -> None:
        """Register a callback to be called when state changes.

        Args:
            callback: Function to call on state change.
        """
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[], None]) -> None:
        """Remove a previously registered callback.

        Args:
            callback: The callback to remove.
        """
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify(self) -> None:
        """Notify all listeners of a state change."""
        for listener in self._listeners:
            try:
                listener()
            except Exception:
                LOGGER.exception("Error in state change listener")

    # =========================================================================
    # State Setters
    # =========================================================================

    def set_scanning(self, scanning: bool) -> None:
        """Set the scanning state."""
        self._state.is_scanning = scanning
        self._notify()

    def set_connecting(self, connecting: bool) -> None:
        """Set the connecting state."""
        self._state.is_connecting = connecting
        self._notify()

    def set_mirroring(self, mirroring: bool) -> None:
        """Set the mirroring state."""
        self._state.is_mirroring = mirroring
        self._notify()

    def set_devices(self, devices: list[LGTVDevice]) -> None:
        """Set the discovered devices."""
        self._state.devices = devices
        self._notify()

    def set_selected_device(self, device: LGTVDevice | None) -> None:
        """Set the currently selected device."""
        self._state.selected_device = device
        self._notify()

    def set_connection_status(self, status: str) -> None:
        """Set the connection status message."""
        self._state.connection_status = status
        self._notify()

    def set_error(self, error: str | None) -> None:
        """Set the last error message."""
        self._state.last_error = error
        self._notify()

    def set_capabilities(self, capabilities: list[Capability]) -> None:
        """Set the detected capabilities."""
        self._state.capabilities = capabilities
        self._notify()

    def set_share_url(self, url: str) -> None:
        """Set the last media share URL."""
        self._state.share_url = url
        self._notify()

    def set_webos_client(self, client: WebOSClient | None) -> None:
        """Set the WebOS client."""
        self._state.webos_client = client
        self._notify()

    def set_current_view(self, view: str) -> None:
        """Set the current view name."""
        self._state.current_view = view
        self._notify()

    def set_show_remote(self, show: bool) -> None:
        """Set whether to show the remote control view."""
        self._state.show_remote = show
        self._notify()

    # =========================================================================
    # Logging
    # =========================================================================

    def log(self, message: str) -> None:
        """Add a log message to the state."""
        self._state.log_messages.append(message)
        # Trim old messages
        if len(self._state.log_messages) > self._state.max_log_messages:
            self._state.log_messages = self._state.log_messages[-self._state.max_log_messages:]
        self._notify()

    def clear_logs(self) -> None:
        """Clear all log messages."""
        self._state.log_messages.clear()
        self._notify()

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    def has_selected_device(self) -> bool:
        """Check if a device is selected."""
        return self._state.selected_device is not None

    def is_connected(self) -> bool:
        """Check if connected to a TV."""
        return self._state.webos_client is not None and self._state.webos_client.is_connected

    def get_selected_device_name(self) -> str:
        """Get the display name of the selected device."""
        if self._state.selected_device:
            return self._state.selected_device.display_name()
        return "No TV selected"

    def get_selected_device_ip(self) -> str | None:
        """Get the IP of the selected device."""
        if self._state.selected_device:
            return self._state.selected_device.ip
        return None

    async def cleanup(self) -> None:
        """Clean up resources (disconnect WebOS client, etc.)."""
        if self._state.webos_client:
            try:
                await self._state.webos_client.disconnect()
            except Exception:
                LOGGER.exception("Error disconnecting WebOS client")
            self._state.webos_client = None
