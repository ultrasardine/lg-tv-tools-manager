"""LG webOS TV WebSocket (SSAP) client.

Handles pairing, client-key persistence, and command execution
via the Simple Service Access Protocol over WebSocket.
"""

from __future__ import annotations

import contextlib
import json
import logging
import ssl
import time
from dataclasses import dataclass, field
from typing import Any

import websockets.sync.client as ws_client

from ..system.paths import data_dir

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

# Well-known webOS app IDs
APP_BROWSER = "com.webos.app.browser"
APP_MEDIA_PLAYER = "com.webos.app.mediadiscovery"


@dataclass
class WebOSResult:
    """Result of a webOS command."""

    ok: bool
    message: str
    payload: dict[str, Any] = field(default_factory=dict)


class WebOSClient:
    """Synchronous WebSocket client for LG webOS TVs.

    Usage:
        client = WebOSClient("192.168.1.100")
        result = client.connect()  # May show pairing prompt on TV
        if result.ok:
            client.launch_browser("https://youtube.com/watch?v=...")
            client.disconnect()
    """

    def __init__(self, ip: str, port: int = 3000, use_ssl: bool = False) -> None:
        self.ip = ip
        self.port = port
        self.use_ssl = use_ssl
        self._ws: Any = None
        self._msg_id = 0
        self._client_key: str | None = None
        self._keys_file = data_dir() / "webos_keys.json"
        self._load_key()

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
            with contextlib.suppress(Exception):
                keys = json.loads(self._keys_file.read_text())
        if self._client_key:
            keys[self.ip] = self._client_key
            self._keys_file.parent.mkdir(parents=True, exist_ok=True)
            self._keys_file.write_text(json.dumps(keys, indent=2))
            LOGGER.debug("Saved webOS client key for %s", self.ip)

    def _next_id(self) -> str:
        self._msg_id += 1
        return f"msg_{self._msg_id}"

    @property
    def is_connected(self) -> bool:
        return self._ws is not None

    def connect(self, timeout: float = 30.0) -> WebOSResult:
        """Connect and register with the TV.

        On first connection, the TV will display a pairing prompt.
        The user must accept it within the timeout period.
        Subsequent connections use the stored client key (no prompt).

        Returns a WebOSResult indicating success or failure.
        """
        scheme = "wss" if self.use_ssl else "ws"
        uri = f"{scheme}://{self.ip}:{self.port}"

        try:
            if self.use_ssl:
                ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE
                self._ws = ws_client.connect(
                    uri,
                    ssl=ssl_ctx,
                    open_timeout=5,
                    close_timeout=3,
                    additional_headers={"Origin": "null"},
                )
            else:
                self._ws = ws_client.connect(
                    uri,
                    open_timeout=5,
                    close_timeout=3,
                    additional_headers={"Origin": "null"},
                )
        except Exception as exc:
            LOGGER.warning("WebSocket connection to %s failed: %s", uri, exc)
            return WebOSResult(False, f"Cannot connect to TV at {self.ip}:{self.port}")

        # Send registration
        return self._register(timeout)

    def _register(self, timeout: float) -> WebOSResult:
        """Send registration payload and wait for pairing response."""
        payload = dict(_REGISTRATION_PAYLOAD)
        if self._client_key:
            payload["client-key"] = self._client_key

        register_msg = json.dumps({
            "type": "register",
            "id": "register_0",
            "payload": payload,
        })

        try:
            self._ws.send(register_msg)
        except Exception as exc:
            self.disconnect()
            return WebOSResult(False, f"Failed to send registration: {exc}")

        # Wait for registration response
        # The TV may send multiple messages (prompt displayed, then registered)
        deadline = time.time() + timeout
        while time.time() < deadline:
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            try:
                self._ws.timeout = min(remaining, 2.0)
                raw = self._ws.recv()
                msg = json.loads(raw)
            except TimeoutError:
                continue
            except Exception as exc:
                error_str = str(exc)
                # Handle webOS standby ("Try Again Later (EWS)")
                if "1008" in error_str or "Try Again Later" in error_str:
                    self.disconnect()
                    return WebOSResult(
                        False,
                        "TV appears to be in standby. Turn it on and try again.",
                    )
                self.disconnect()
                return WebOSResult(False, f"Error during registration: {exc}")

            msg_type = msg.get("type", "")
            msg_payload = msg.get("payload", {})

            if msg_type == "registered":
                # Success - save the client key
                new_key = msg_payload.get("client-key", "")
                if new_key:
                    self._client_key = new_key
                    self._save_key()
                LOGGER.info("Registered with TV at %s", self.ip)
                return WebOSResult(True, "Paired with TV", msg_payload)

            if (
                msg_type == "response"
                and msg.get("id") == "register_0"
                and msg_payload.get("pairingType") == "PROMPT"
            ):
                LOGGER.info("Pairing prompt displayed on TV at %s", self.ip)
                continue  # Wait for user to accept

            if msg_type == "error":
                error_msg = msg_payload.get("message", msg.get("error", "Unknown error"))
                self.disconnect()
                return WebOSResult(False, f"TV rejected pairing: {error_msg}")

        self.disconnect()
        return WebOSResult(
            False,
            "Pairing timed out. Please accept the prompt on your TV.",
        )

    def disconnect(self) -> None:
        """Close the WebSocket connection."""
        if self._ws:
            with contextlib.suppress(Exception):
                self._ws.close()
            self._ws = None

    def _send_command(self, uri: str, payload: dict[str, Any] | None = None) -> WebOSResult:
        """Send an SSAP command and return the response."""
        if not self._ws:
            return WebOSResult(False, "Not connected to TV")

        msg_id = self._next_id()
        message: dict[str, Any] = {
            "type": "request",
            "id": msg_id,
            "uri": uri,
        }
        if payload:
            message["payload"] = payload

        try:
            self._ws.send(json.dumps(message))
        except Exception as exc:
            return WebOSResult(False, f"Send failed: {exc}")

        # Wait for response with matching ID
        deadline = time.time() + 10.0
        while time.time() < deadline:
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            try:
                self._ws.timeout = min(remaining, 2.0)
                raw = self._ws.recv()
                msg = json.loads(raw)
            except TimeoutError:
                continue
            except Exception as exc:
                return WebOSResult(False, f"Receive failed: {exc}")

            if msg.get("id") == msg_id:
                resp_type = msg.get("type", "")
                resp_payload = msg.get("payload", {})
                if resp_type == "response":
                    return WebOSResult(True, "OK", resp_payload)
                elif resp_type == "error":
                    error_msg = resp_payload.get("message", msg.get("error", "Command failed"))
                    return WebOSResult(False, error_msg, resp_payload)

        return WebOSResult(False, "Command timed out")

    def launch_browser(self, url: str) -> WebOSResult:
        """Open a URL in the TV's built-in web browser."""
        return self._send_command(SSAP_LAUNCH, {
            "id": APP_BROWSER,
            "params": {"target": url},
        })

    def open_media_url(self, url: str, title: str = "LG TV Tools") -> WebOSResult:
        """Open a media URL in the TV's media player.

        Works best with direct video/audio URLs (mp4, m3u8, etc).
        For web pages, use launch_browser() instead.
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
            return self.launch_browser(url)

        result = self._send_command(SSAP_MEDIA_PLAY, {
            "mediaUrl": url,
            "mediaType": media_type,
            "title": title,
        })

        # Fall back to browser if media player fails
        if not result.ok:
            LOGGER.debug("Media viewer failed (%s), falling back to browser", result.message)
            return self.launch_browser(url)
        return result

    def show_toast(self, message: str) -> WebOSResult:
        """Display a toast notification on the TV."""
        return self._send_command(SSAP_TOAST, {"message": message})

    def get_volume(self) -> WebOSResult:
        """Get the current volume level (useful for testing connectivity)."""
        return self._send_command(SSAP_VOLUME_GET)

    def is_paired(self) -> bool:
        """Check if we have a stored client key for this TV."""
        return self._client_key is not None


def connect_to_tv(ip: str, timeout: float = 30.0) -> tuple[WebOSClient, WebOSResult]:
    """Convenience function to create a client and connect.

    Returns the client and the connection result.
    Tries SSL (port 3001) first as most modern LG TVs require it,
    then falls back to plain WebSocket (port 3000).
    """
    # Try SSL first (port 3001) - required by most modern webOS TVs
    client = WebOSClient(ip, port=3001, use_ssl=True)
    result = client.connect(timeout=timeout)
    if result.ok:
        return client, result

    # Check for standby/EWS error
    if "Try Again Later" in result.message or "EWS" in result.message:
        return client, WebOSResult(
            False,
            f"TV at {ip} appears to be in standby. "
            f"Please turn on the TV and try again.",
        )

    LOGGER.debug("SSL WS failed for %s, trying plain on 3000", ip)
    client = WebOSClient(ip, port=3000, use_ssl=False)
    result = client.connect(timeout=timeout)
    if not result.ok and ("Try Again Later" in result.message or "EWS" in result.message):
        return client, WebOSResult(
            False,
            f"TV at {ip} appears to be in standby. "
            f"Please turn on the TV and try again.",
        )
    return client, result
