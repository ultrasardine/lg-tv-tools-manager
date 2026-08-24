"""Local HTTP media server for sharing files to TVs.

Provides a simple HTTP server that serves media files from a temporary
directory, allowing TVs to access local media via HTTP URLs.
"""

from __future__ import annotations

import contextlib
import functools
import logging
import os
import shutil
import socket
import socketserver
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler
from pathlib import Path

LOGGER = logging.getLogger(__name__)


def _get_host_ip() -> str:
    """Detect the host's LAN IPv4 address (cross-platform).

    Tries multiple methods to find the best LAN IP:
    1. netifaces (if available) - finds IP on the default gateway interface
    2. Socket connect trick - connects to external address to find outbound IP

    Returns:
        The detected LAN IP or "127.0.0.1" if detection fails.
    """
    # Method 1: Use netifaces to find the default gateway interface IP
    try:
        import netifaces
        gateways = netifaces.gateways()
        default_gw = gateways.get("default", {}).get(netifaces.AF_INET)
        if default_gw:
            iface = default_gw[1]
            addrs = netifaces.ifaddresses(iface)
            ipv4_addrs = addrs.get(netifaces.AF_INET, [])
            if ipv4_addrs:
                ip = ipv4_addrs[0].get("addr", "")
                if ip and not ip.startswith("127."):
                    return ip
    except ImportError:
        LOGGER.debug("netifaces not available")
    except Exception:
        LOGGER.debug("netifaces gateway lookup failed", exc_info=True)

    # Method 2: Connect to an external address to determine outbound IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        LOGGER.debug("Socket connect trick failed", exc_info=True)

    return "127.0.0.1"


class _ReuseTCPServer(socketserver.TCPServer):
    """TCP server that allows address reuse."""

    allow_reuse_address = True


class MediaShareServer:
    """HTTP server for sharing local media files.

    Creates a temporary directory and serves files from it via HTTP.
    Files are symlinked (or copied) to the temp directory when published.

    Usage:
        server = MediaShareServer()
        url = server.publish("/path/to/video.mp4")
        # URL like "http://192.168.1.100:8080/video.mp4"
        # ... TV can now access the file via URL ...
        server.close()  # Clean up when done
    """

    def __init__(self) -> None:
        """Initialize the media share server."""
        self._lock = threading.Lock()
        self._server: _ReuseTCPServer | None = None
        self._thread: threading.Thread | None = None
        self._root = Path(tempfile.mkdtemp(prefix="lg-tv-tools-share-"))
        self.port = 0
        self._host_ip = ""

    @property
    def host_ip(self) -> str:
        """Get the host IP address."""
        if not self._host_ip:
            self._host_ip = _get_host_ip()
        return self._host_ip

    @property
    def base_url(self) -> str:
        """Get the base URL of the server."""
        if not self._server:
            return ""
        return f"http://{self.host_ip}:{self.port}"

    @property
    def is_running(self) -> bool:
        """Check if the server is running."""
        return self._server is not None

    def _ensure_server(self) -> None:
        """Start the server if not already running."""
        if self._server:
            return

        with self._lock:
            if self._server:
                return

            handler = functools.partial(
                SimpleHTTPRequestHandler,
                directory=str(self._root),
            )
            self._server = _ReuseTCPServer(("0.0.0.0", 0), handler)
            self.port = self._server.server_address[1]
            self._host_ip = _get_host_ip()

            self._thread = threading.Thread(
                target=self._server.serve_forever,
                daemon=True,
                name="MediaShareServer",
            )
            self._thread.start()

            LOGGER.info(
                "Media share server started on %s:%s",
                self._host_ip,
                self.port,
            )

    def publish(self, path: str) -> str:
        """Publish a file and return its HTTP URL.

        Creates a symlink (or copy) of the file in the temp directory
        and returns a URL that the TV can use to access it.

        Args:
            path: Path to the file to publish.

        Returns:
            HTTP URL to access the file.
        """
        source = Path(path)
        self._ensure_server()

        target = self._root / source.name

        # Remove existing file/symlink if present
        if target.exists() or target.is_symlink():
            target.unlink()

        # Try symlink first, fall back to copy
        try:
            os.symlink(source.resolve(), target)
        except OSError:
            LOGGER.debug("Symlink failed, copying file instead")
            shutil.copy2(source, target)

        url = f"{self.base_url}/{source.name}"
        LOGGER.info("Published: %s -> %s", source.name, url)
        return url

    def unpublish(self, filename: str) -> bool:
        """Remove a published file.

        Args:
            filename: Name of the file to remove.

        Returns:
            True if the file was removed, False otherwise.
        """
        target = self._root / filename
        if target.exists() or target.is_symlink():
            target.unlink()
            LOGGER.info("Unpublished: %s", filename)
            return True
        return False

    def list_published(self) -> list[str]:
        """List all published files.

        Returns:
            List of published file names.
        """
        if not self._root.exists():
            return []
        return [f.name for f in self._root.iterdir() if f.is_file() or f.is_symlink()]

    def close(self) -> None:
        """Stop the server and clean up resources."""
        with self._lock:
            if self._server:
                LOGGER.info("Stopping media share server")
                self._server.shutdown()
                self._server.server_close()
                self._server = None

            if self._root.exists():
                shutil.rmtree(self._root, ignore_errors=True)
                LOGGER.debug("Cleaned up temp directory: %s", self._root)

    def __del__(self) -> None:
        """Ensure cleanup on deletion."""
        with contextlib.suppress(Exception):
            self.close()
