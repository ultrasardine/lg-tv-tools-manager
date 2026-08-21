"""Async LG webOS TV WebSocket (SSAP) client.

Handles pairing, client-key persistence, and command execution
via the Simple Service Access Protocol over WebSocket.

This is the async version designed for use with Flet applications.
"""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
from typing import Any

import websockets
from websockets.asyncio.client import ClientConnection

from lgtvtools.core.models import WebOSResult
from lgtvtools.system.paths import data_dir

LOGGER = logging.getLogger(__name__)

# The registration manifest required by LG webOS TVs.
# This is the standard manifest used by all third-party LG TV control apps.
_REGISTRATION_PAYLOAD: dict[str, Any] = {
    "forcePairing": False,
    "pairingType": "PROMPT",
    "manifest": {
        "manifestVersion": 1,
        "appVersion": "1.1",
        "signed": {
            "created": "20140509",
            "appId": "com.lge.test",
            "vendorId": "com.lge",
            "localizedAppNames": {
                "": "LG TV Tools",
                "ko-KR": "리모컨 앱",
                "zxx-XX": "ЛГ Rэмotэ AПП",
            },
            "localizedVendorNames": {"": "LG Electronics"},
            "permissions": [
                "TEST_SECURE",
                "CONTROL_INPUT_TEXT",
                "CONTROL_MOUSE_AND_KEYBOARD",
                "READ_INSTALLED_APPS",
                "READ_LGE_SDX",
                "READ_NOTIFICATIONS",
                "SEARCH",
                "WRITE_SETTINGS",
                "WRITE_NOTIFICATION_ALERT",
                "CONTROL_POWER",
                "READ_CURRENT_CHANNEL",
                "READ_RUNNING_APPS",
                "READ_UPDATE_INFO",
                "UPDATE_FROM_REMOTE_APP",
                "READ_LGE_TV_INPUT_EVENTS",
                "READ_TV_CURRENT_TIME",
            ],
            "serial": "2f930e2d2cfe083771f68e4fe7bb07",
        },
        "permissions": [
            "LAUNCH",
            "LAUNCH_WEBAPP",
            "APP_TO_APP",
            "CLOSE",
            "TEST_OPEN",
            "TEST_PROTECTED",
            "CONTROL_AUDIO",
            "CONTROL_DISPLAY",
            "CONTROL_INPUT_JOYSTICK",
            "CONTROL_INPUT_MEDIA_RECORDING",
            "CONTROL_INPUT_MEDIA_PLAYBACK",
            "CONTROL_INPUT_TV",
            "CONTROL_POWER",
            "READ_APP_STATUS",
            "READ_CURRENT_CHANNEL",
            "READ_INPUT_DEVICE_LIST",
            "READ_NETWORK_STATE",
            "READ_RUNNING_APPS",
            "READ_TV_CHANNEL_LIST",
            "WRITE_NOTIFICATION_TOAST",
            "READ_POWER_STATE",
            "READ_COUNTRY_INFO",
        ],
        "signatures": [
            {
                "signatureVersion": 1,
                "signature": (
                    "eyJhbGdvcml0aG0iOiJSU0EtU0hBMjU2Iiwia2V5SWQiOiJ0ZXN0LXNpZ25pbm"
                    "ctY2VydCIsInNpZ25hdHVyZVZlcnNpb24iOjF9.hrVRgjCwXVvE2OOSpDZ58hR+59"
                    "aFNwYDyjQgKk3auukd7pcegmE2CzPCa0bJ0ZsRAcKkCTJrWo5iDzNhMBWRyaMOv5"
                    "zWSrthlf7G128qvIlpMT0YNY+n/FaOHE73uLrS/g7swl3/qH/BGFG2Hu4RlL48eb"
                    "3lLKqTt2xKHdCs6Cd4RMfJPYnzgvI4BNrFUKsjkcu+WD4OO2A27Pq1n50cMchmca"
                    "XadJhGrOqH5YmHdOCj5NSHzJYrsW0HPlpuAx/ECMeIZYDh6RMqaFM2DXzdKX9Nmm"
                    "yqzJ3o/0lkk/N97gfVRLW5hA29yeAwaCViZNCP8iC9aO0q9fQojoa7NQnAtw=="
                ),
            }
        ],
    },
}

# SSAP endpoint URIs
SSAP_LAUNCH = "ssap://system.launcher/launch"
SSAP_OPEN_URL = "ssap://system.launcher/open"
SSAP_TOAST = "ssap://system.notifications/createToast"
SSAP_GET_APPS = "ssap://com.webos.applicationManager/listLaunchPoints"
SSAP_MEDIA_PLAY = "ssap://media.viewer/open"
SSAP_VOLUME_GET = "ssap://audio/getVolume"
SSAP_VOLUME_SET = "ssap://audio/setVolume"
SSAP_MUTE = "ssap://audio/setMute"
SSAP_POWER_OFF = "ssap://system/turnOff"
SSAP_INPUT_POINTER = "ssap://com.webos.service.networkinput/getPointerInputSocket"
SSAP_INPUT_TEXT = "ssap://com.webos.service.ime/insertText"

# Additional remote control URIs
SSAP_PLAY = "ssap://media.controls/play"
SSAP_PAUSE = "ssap://media.controls/pause"
SSAP_STOP = "ssap://media.controls/stop"
SSAP_REWIND = "ssap://media.controls/rewind"
SSAP_FAST_FORWARD = "ssap://media.controls/fastForward"
SSAP_CHANNEL_UP = "ssap://tv/channelUp"
SSAP_CHANNEL_DOWN = "ssap://tv/channelDown"

# Well-known webOS app IDs
APP_BROWSER = "com.webos.app.browser"
APP_MEDIA_PLAYER = "com.webos.app.mediadiscovery"
APP_YOUTUBE = "youtube.leanback.v4"
APP_NETFLIX = "netflix"
APP_AMAZON_PRIME = "amazon"
APP_DISNEY_PLUS = "com.disney.disneyplus-prod"
APP_SETTINGS = "com.webos.app.settings"
APP_HOME = "com.webos.app.home"


class WebOSClient:
    """Async WebSocket client for LG webOS TVs.

    This client uses async/await patterns compatible with Flet's event loop.

    Usage:
        async with WebOSClient("192.168.1.100") as client:
            result = await client.connect()  # May show pairing prompt on TV
            if result.ok:
                await client.launch_browser("https://youtube.com/watch?v=...")

    Or manually:
        client = WebOSClient("192.168.1.100")
        result = await client.connect()
        if result.ok:
            await client.launch_browser("https://youtube.com")
        await client.disconnect()
    """

    def __init__(self, ip: str, port: int = 3001, use_ssl: bool = True) -> None:
        """Initialize the WebOS client.

        Args:
            ip: IP address of the LG TV.
            port: WebSocket port (3001 for SSL, 3000 for plain).
            use_ssl: Whether to use SSL/TLS connection.
        """
        self.ip = ip
        self.port = port
        self.use_ssl = use_ssl
        self._ws: ClientConnection | None = None
        self._msg_id = 0
        self._client_key: str | None = None
        self._keys_file = data_dir() / "webos_keys.json"
        self._load_key()

    async def __aenter__(self) -> WebOSClient:
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit - ensures disconnect."""
        await self.disconnect()

    def _load_key(self) -> None:
        """Load stored client key for this TV."""
        if not self._keys_file.exists():
            return
        try:
            keys = json.loads(self._keys_file.read_text())
            self._client_key = keys.get(self.ip)
        except Exception:
            LOGGER.debug("Could not load webOS keys file", exc_info=True)

    def _save_key(self) -> None:
        """Persist client key for this TV."""
        keys: dict[str, str] = {}
        if self._keys_file.exists():
            try:
                keys = json.loads(self._keys_file.read_text())
            except Exception:
                pass
        if self._client_key:
            keys[self.ip] = self._client_key
            self._keys_file.parent.mkdir(parents=True, exist_ok=True)
            self._keys_file.write_text(json.dumps(keys, indent=2))
            LOGGER.debug("Saved webOS client key for %s", self.ip)

    def _next_id(self) -> str:
        """Generate the next message ID."""
        self._msg_id += 1
        return f"msg_{self._msg_id}"

    @property
    def is_connected(self) -> bool:
        """Check if the WebSocket is connected."""
        return self._ws is not None

    @property
    def is_paired(self) -> bool:
        """Check if we have a stored client key for this TV."""
        return self._client_key is not None

    async def connect(self, timeout: float = 30.0) -> WebOSResult:
        """Connect and register with the TV.

        On first connection, the TV will display a pairing prompt.
        The user must accept it within the timeout period.
        Subsequent connections use the stored client key (no prompt).

        Args:
            timeout: Maximum time to wait for pairing acceptance.

        Returns:
            WebOSResult indicating success or failure.
        """
        scheme = "wss" if self.use_ssl else "ws"
        uri = f"{scheme}://{self.ip}:{self.port}"

        try:
            if self.use_ssl:
                ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE
                self._ws = await asyncio.wait_for(
                    websockets.connect(
                        uri,
                        ssl=ssl_ctx,
                        additional_headers={"Origin": "null"},
                    ),
                    timeout=5.0,
                )
            else:
                self._ws = await asyncio.wait_for(
                    websockets.connect(
                        uri,
                        additional_headers={"Origin": "null"},
                    ),
                    timeout=5.0,
                )
        except asyncio.TimeoutError:
            LOGGER.warning("WebSocket connection to %s timed out", uri)
            return WebOSResult(ok=False, message=f"Connection timed out to {self.ip}:{self.port}")
        except Exception as exc:
            LOGGER.warning("WebSocket connection to %s failed: %s", uri, exc)
            return WebOSResult(ok=False, message=f"Cannot connect to TV at {self.ip}:{self.port}")

        # Send registration
        return await self._register(timeout)

    async def _register(self, timeout: float) -> WebOSResult:
        """Send registration payload and wait for pairing response."""
        if not self._ws:
            return WebOSResult(ok=False, message="Not connected")

        payload = dict(_REGISTRATION_PAYLOAD)
        if self._client_key:
            payload["client-key"] = self._client_key

        register_msg = json.dumps({
            "type": "register",
            "id": "register_0",
            "payload": payload,
        })

        try:
            await self._ws.send(register_msg)
        except Exception as exc:
            await self.disconnect()
            return WebOSResult(ok=False, message=f"Failed to send registration: {exc}")

        # Wait for registration response
        # The TV may send multiple messages (prompt displayed, then registered)
        try:
            deadline = asyncio.get_event_loop().time() + timeout
            while asyncio.get_event_loop().time() < deadline:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    break

                try:
                    raw = await asyncio.wait_for(
                        self._ws.recv(),
                        timeout=min(remaining, 2.0),
                    )
                    msg = json.loads(raw)
                except asyncio.TimeoutError:
                    continue
                except Exception as exc:
                    error_str = str(exc)
                    # Handle webOS standby ("Try Again Later (EWS)")
                    if "1008" in error_str or "Try Again Later" in error_str:
                        await self.disconnect()
                        return WebOSResult(
                            ok=False,
                            message="TV appears to be in standby. Turn it on and try again.",
                        )
                    await self.disconnect()
                    return WebOSResult(ok=False, message=f"Error during registration: {exc}")

                msg_type = msg.get("type", "")
                msg_payload = msg.get("payload", {})

                if msg_type == "registered":
                    # Success - save the client key
                    new_key = msg_payload.get("client-key", "")
                    if new_key:
                        self._client_key = new_key
                        self._save_key()
                    LOGGER.info("Registered with TV at %s", self.ip)
                    return WebOSResult(ok=True, message="Paired with TV", payload=msg_payload)

                if msg_type == "response" and msg.get("id") == "register_0":
                    # Check if it's a pairing prompt response
                    if msg_payload.get("pairingType") == "PROMPT":
                        LOGGER.info("Pairing prompt displayed on TV at %s", self.ip)
                        continue  # Wait for user to accept

                if msg_type == "error":
                    error_msg = msg_payload.get("message", msg.get("error", "Unknown error"))
                    await self.disconnect()
                    return WebOSResult(ok=False, message=f"TV rejected pairing: {error_msg}")

        except Exception as exc:
            await self.disconnect()
            return WebOSResult(ok=False, message=f"Registration error: {exc}")

        await self.disconnect()
        return WebOSResult(
            ok=False,
            message="Pairing timed out. Please accept the prompt on your TV.",
        )

    async def disconnect(self) -> None:
        """Close the WebSocket connection."""
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

    async def _send_command(
        self,
        uri: str,
        payload: dict[str, Any] | None = None,
        timeout: float = 10.0,
    ) -> WebOSResult:
        """Send an SSAP command and return the response.

        Args:
            uri: SSAP endpoint URI.
            payload: Optional command payload.
            timeout: Command timeout in seconds.

        Returns:
            WebOSResult with the command response.
        """
        if not self._ws:
            return WebOSResult(ok=False, message="Not connected to TV")

        msg_id = self._next_id()
        message: dict[str, Any] = {
            "type": "request",
            "id": msg_id,
            "uri": uri,
        }
        if payload:
            message["payload"] = payload

        try:
            await self._ws.send(json.dumps(message))
        except Exception as exc:
            return WebOSResult(ok=False, message=f"Send failed: {exc}")

        # Wait for response with matching ID
        try:
            deadline = asyncio.get_event_loop().time() + timeout
            while asyncio.get_event_loop().time() < deadline:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    break

                try:
                    raw = await asyncio.wait_for(
                        self._ws.recv(),
                        timeout=min(remaining, 2.0),
                    )
                    msg = json.loads(raw)
                except asyncio.TimeoutError:
                    continue
                except Exception as exc:
                    return WebOSResult(ok=False, message=f"Receive failed: {exc}")

                if msg.get("id") == msg_id:
                    resp_type = msg.get("type", "")
                    resp_payload = msg.get("payload", {})
                    if resp_type == "response":
                        return WebOSResult(ok=True, message="OK", payload=resp_payload)
                    elif resp_type == "error":
                        error_msg = resp_payload.get("message", msg.get("error", "Command failed"))
                        return WebOSResult(ok=False, message=error_msg, payload=resp_payload)

        except Exception as exc:
            return WebOSResult(ok=False, message=f"Command error: {exc}")

        return WebOSResult(ok=False, message="Command timed out")

    # =========================================================================
    # App Launch Commands
    # =========================================================================

    async def launch_browser(self, url: str) -> WebOSResult:
        """Open a URL in the TV's built-in web browser.

        Args:
            url: URL to open.

        Returns:
            WebOSResult indicating success or failure.
        """
        return await self._send_command(SSAP_LAUNCH, {
            "id": APP_BROWSER,
            "params": {"target": url},
        })

    async def launch_app(self, app_id: str, params: dict[str, Any] | None = None) -> WebOSResult:
        """Launch an app on the TV.

        Args:
            app_id: The webOS app ID.
            params: Optional launch parameters.

        Returns:
            WebOSResult indicating success or failure.
        """
        payload: dict[str, Any] = {"id": app_id}
        if params:
            payload["params"] = params
        return await self._send_command(SSAP_LAUNCH, payload)

    async def open_media_url(self, url: str, title: str = "LG TV Tools") -> WebOSResult:
        """Open a media URL in the TV's media player.

        Works best with direct video/audio URLs (mp4, m3u8, etc).
        For web pages, use launch_browser() instead.

        Args:
            url: Media URL to play.
            title: Display title for the media.

        Returns:
            WebOSResult indicating success or failure.
        """
        # Determine media type from URL
        lower_url = url.lower()
        if any(ext in lower_url for ext in (".mp4", ".mkv", ".avi", ".webm", ".mov", ".m3u8", ".ts")):
            media_type = "video"
        elif any(ext in lower_url for ext in (".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac")):
            media_type = "audio"
        elif any(ext in lower_url for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")):
            media_type = "image"
        else:
            # Default to browser for unknown content types
            return await self.launch_browser(url)

        result = await self._send_command(SSAP_MEDIA_PLAY, {
            "mediaUrl": url,
            "mediaType": media_type,
            "title": title,
        })

        # Fall back to browser if media player fails
        if not result.ok:
            LOGGER.debug("Media viewer failed (%s), falling back to browser", result.message)
            return await self.launch_browser(url)
        return result

    # =========================================================================
    # Notification Commands
    # =========================================================================

    async def show_toast(self, message: str) -> WebOSResult:
        """Display a toast notification on the TV.

        Args:
            message: Message to display.

        Returns:
            WebOSResult indicating success or failure.
        """
        return await self._send_command(SSAP_TOAST, {"message": message})

    # =========================================================================
    # Volume Commands
    # =========================================================================

    async def get_volume(self) -> WebOSResult:
        """Get the current volume level.

        Returns:
            WebOSResult with volume info in payload.
        """
        return await self._send_command(SSAP_VOLUME_GET)

    async def set_volume(self, level: int) -> WebOSResult:
        """Set the volume level.

        Args:
            level: Volume level (0-100).

        Returns:
            WebOSResult indicating success or failure.
        """
        return await self._send_command(SSAP_VOLUME_SET, {"volume": max(0, min(100, level))})

    async def volume_up(self, step: int = 1) -> WebOSResult:
        """Increase volume by a step.

        Args:
            step: Volume increase amount.

        Returns:
            WebOSResult indicating success or failure.
        """
        result = await self.get_volume()
        if not result.ok:
            return result
        current = result.payload.get("volume", 0)
        return await self.set_volume(current + step)

    async def volume_down(self, step: int = 1) -> WebOSResult:
        """Decrease volume by a step.

        Args:
            step: Volume decrease amount.

        Returns:
            WebOSResult indicating success or failure.
        """
        result = await self.get_volume()
        if not result.ok:
            return result
        current = result.payload.get("volume", 0)
        return await self.set_volume(current - step)

    async def set_mute(self, mute: bool) -> WebOSResult:
        """Set mute state.

        Args:
            mute: True to mute, False to unmute.

        Returns:
            WebOSResult indicating success or failure.
        """
        return await self._send_command(SSAP_MUTE, {"mute": mute})

    async def toggle_mute(self) -> WebOSResult:
        """Toggle mute state.

        Returns:
            WebOSResult indicating success or failure.
        """
        result = await self.get_volume()
        if not result.ok:
            return result
        current_mute = result.payload.get("muted", False)
        return await self.set_mute(not current_mute)

    # =========================================================================
    # Power Commands
    # =========================================================================

    async def power_off(self) -> WebOSResult:
        """Turn off the TV.

        Returns:
            WebOSResult indicating success or failure.
        """
        return await self._send_command(SSAP_POWER_OFF)

    # =========================================================================
    # Media Control Commands
    # =========================================================================

    async def play(self) -> WebOSResult:
        """Send play command to current media."""
        return await self._send_command(SSAP_PLAY)

    async def pause(self) -> WebOSResult:
        """Send pause command to current media."""
        return await self._send_command(SSAP_PAUSE)

    async def stop(self) -> WebOSResult:
        """Send stop command to current media."""
        return await self._send_command(SSAP_STOP)

    async def rewind(self) -> WebOSResult:
        """Send rewind command to current media."""
        return await self._send_command(SSAP_REWIND)

    async def fast_forward(self) -> WebOSResult:
        """Send fast forward command to current media."""
        return await self._send_command(SSAP_FAST_FORWARD)

    # =========================================================================
    # Channel Commands
    # =========================================================================

    async def channel_up(self) -> WebOSResult:
        """Go to next channel."""
        return await self._send_command(SSAP_CHANNEL_UP)

    async def channel_down(self) -> WebOSResult:
        """Go to previous channel."""
        return await self._send_command(SSAP_CHANNEL_DOWN)

    # =========================================================================
    # App Information
    # =========================================================================

    async def get_apps(self) -> WebOSResult:
        """Get list of installed apps.

        Returns:
            WebOSResult with apps list in payload.
        """
        return await self._send_command(SSAP_GET_APPS)


async def connect_to_tv(ip: str, timeout: float = 30.0) -> tuple[WebOSClient, WebOSResult]:
    """Convenience function to create a client and connect.

    Tries SSL (port 3001) first as most modern LG TVs require it,
    then falls back to plain WebSocket (port 3000).

    Args:
        ip: IP address of the LG TV.
        timeout: Connection/pairing timeout.

    Returns:
        Tuple of (client, result).
    """
    # Try SSL first (port 3001) - required by most modern webOS TVs
    client = WebOSClient(ip, port=3001, use_ssl=True)
    result = await client.connect(timeout=timeout)

    if result.ok:
        return client, result

    # Check for standby/EWS error
    if "standby" in result.message.lower() or "ews" in result.message.lower():
        return client, WebOSResult(
            ok=False,
            message=f"TV at {ip} appears to be in standby. Please turn on the TV and try again.",
        )

    LOGGER.debug("SSL WS failed for %s, trying plain on 3000", ip)
    client = WebOSClient(ip, port=3000, use_ssl=False)
    result = await client.connect(timeout=timeout)

    if not result.ok and ("standby" in result.message.lower() or "ews" in result.message.lower()):
        return client, WebOSResult(
            ok=False,
            message=f"TV at {ip} appears to be in standby. Please turn on the TV and try again.",
        )

    return client, result
