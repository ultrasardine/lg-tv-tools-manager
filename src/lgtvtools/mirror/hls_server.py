"""HTTP server for HLS streaming to the TV browser.

This module provides an HTTP server that serves HLS playlist (.m3u8) files,
video segments (.ts), and an HTML player page with hls.js for playback on
the TV's webOS browser.
"""

from __future__ import annotations

import logging
import os
import shutil
import socket
import socketserver
import threading
from http.server import SimpleHTTPRequestHandler
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

import netifaces

from lgtvtools.mirror.player import generate_player_html

LOGGER = logging.getLogger(__name__)

# Cache durations for different file types
_M3U8_CACHE_CONTROL = "no-cache, no-store, must-revalidate"
_TS_CACHE_CONTROL = "max-age=10"


class _CORSHandler(SimpleHTTPRequestHandler):
    """HTTP request handler with CORS headers and caching for HLS files."""

    def __init__(
        self,
        *args: object,
        directory: str,
        stream_url: str,
        **kwargs: object,
    ) -> None:
        self._stream_url = stream_url
        super().__init__(*args, directory=directory, **kwargs)  # type: ignore[arg-type]

    def end_headers(self) -> None:
        """Add CORS headers to all responses."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.end_headers()

    def do_GET(self) -> None:
        """Handle GET requests with custom caching headers."""
        # Handle player.html specially
        if self.path == "/player.html" or self.path == "/player.html/":
            self._serve_player_html()
            return

        # Call parent to get the file
        f = self.send_head()
        if f:
            try:
                self.copyfile(f, self.wfile)
            finally:
                f.close()

    def send_head(self) -> BytesIO | BinaryIO | None:
        """Send response headers with caching based on file type."""
        path = self.translate_path(self.path)

        # Check if file exists
        if not os.path.exists(path) or os.path.isdir(path):
            return super().send_head()

        # Determine content type and cache control
        if path.endswith(".m3u8"):
            cache_control = _M3U8_CACHE_CONTROL
            content_type = "application/vnd.apple.mpegurl"
        elif path.endswith(".ts"):
            cache_control = _TS_CACHE_CONTROL
            content_type = "video/MP2T"
        else:
            return super().send_head()

        try:
            with open(path, "rb") as f:
                fs = os.fstat(f.fileno())
                content = f.read()
        except OSError:
            self.send_error(404, "File not found")
            return None

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(fs.st_size))
        self.send_header("Cache-Control", cache_control)
        self.end_headers()

        self.wfile.write(content)
        return None

    def _serve_player_html(self) -> None:
        """Serve the dynamically generated player HTML page."""
        html = generate_player_html(self._stream_url)
        encoded = html.encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        self.wfile.write(encoded)

    def log_message(self, format: str, *args: object) -> None:
        """Log HTTP requests at debug level to avoid noise."""
        LOGGER.debug("HLS request: %s", format % args)


class _ReuseTCPServer(socketserver.TCPServer):
    """TCP server that allows address reuse."""

    allow_reuse_address = True


class HLSServer:
    """HTTP server for HLS streaming to the TV browser.

    Serves HLS playlist (.m3u8) and segment (.ts) files from a directory,
    plus a dynamically generated HTML player page with hls.js.

    Example:
        >>> server = HLSServer(Path("/tmp/hls-segments"))
        >>> server.start()
        >>> print(f"Player URL: {server.player_url(server.get_host_ip())}")
        >>> # ... streaming ...
        >>> server.stop()
    """

    def __init__(self, segments_dir: Path) -> None:
        """Initialize the HLS server.

        Args:
            segments_dir: Path to the directory containing HLS segment files.
                This directory will be served via HTTP and cleaned up on stop.
        """
        self._segments_dir = segments_dir
        self._server: _ReuseTCPServer | None = None
        self._thread: threading.Thread | None = None
        self._port: int = 0
        self._lock = threading.Lock()

    def _get_host_ip(self) -> str:
        """Detect the host's LAN IPv4 address (cross-platform).

        Returns:
            The detected LAN IP address, or "127.0.0.1" if no LAN interface found.
        """
        # Method 1: Use netifaces to find the default gateway interface IP
        try:
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

    def get_host_ip(self) -> str:
        """Get the host's LAN IPv4 address.

        Returns:
            The detected LAN IP address, or "127.0.0.1" if no LAN interface found.
        """
        return self._get_host_ip()

    def start(self) -> None:
        """Start serving on 0.0.0.0 with an ephemeral port.

        The server runs in a background daemon thread. Call stop() to terminate.

        Raises:
            OSError: If the server cannot bind to an address.
        """
        with self._lock:
            if self._server is not None:
                LOGGER.warning("HLS server already running on port %s", self._port)
                return

            # Ensure segments directory exists
            self._segments_dir.mkdir(parents=True, exist_ok=True)

            # Determine the stream URL for the player (using placeholder, will be set per-request)
            host_ip = self._get_host_ip()

            # Create handler factory with stream URL
            # We need to defer the full URL construction until we know the port
            def handler_factory(
                *args: object,
                **kwargs: object,
            ) -> _CORSHandler:
                stream_url = f"http://{host_ip}:{self._port}/stream.m3u8"
                return _CORSHandler(
                    *args,
                    directory=str(self._segments_dir),
                    stream_url=stream_url,
                    **kwargs,
                )

            self._server = _ReuseTCPServer(("0.0.0.0", 0), handler_factory)
            self._port = self._server.server_address[1]

            # Update handler factory with actual port
            def updated_handler_factory(
                *args: object,
                **kwargs: object,
            ) -> _CORSHandler:
                stream_url = f"http://{host_ip}:{self._port}/stream.m3u8"
                return _CORSHandler(
                    *args,
                    directory=str(self._segments_dir),
                    stream_url=stream_url,
                    **kwargs,
                )

            # Recreate server with updated handler (now that we know the port)
            self._server.server_close()
            self._server = _ReuseTCPServer(
                ("0.0.0.0", self._port), updated_handler_factory
            )

            self._thread = threading.Thread(
                target=self._server.serve_forever, daemon=True
            )
            self._thread.start()

            LOGGER.info(
                "HLS server started on port %s, serving from %s",
                self._port,
                self._segments_dir,
            )

    def stop(self) -> None:
        """Stop the server and clean up temp segment files.

        Stops the HTTP server, removes all .ts and .m3u8 files from the
        segments directory, and removes the directory itself.
        """
        with self._lock:
            if self._server is not None:
                LOGGER.info("Stopping HLS server on port %s", self._port)
                self._server.shutdown()
                self._server.server_close()
                self._server = None
                self._thread = None

            # Clean up segment files
            self._cleanup_segments()

    def _cleanup_segments(self) -> None:
        """Delete all .ts and .m3u8 files and remove the temp directory."""
        if not self._segments_dir.exists():
            return

        try:
            # Delete all HLS-related files
            for pattern in ("*.ts", "*.m3u8"):
                for file_path in self._segments_dir.glob(pattern):
                    try:
                        file_path.unlink()
                        LOGGER.debug("Deleted segment file: %s", file_path)
                    except OSError as e:
                        LOGGER.warning("Failed to delete %s: %s", file_path, e)

            # Remove the directory if empty
            try:
                shutil.rmtree(self._segments_dir, ignore_errors=True)
                LOGGER.debug("Removed segments directory: %s", self._segments_dir)
            except OSError as e:
                LOGGER.warning(
                    "Failed to remove segments directory %s: %s",
                    self._segments_dir,
                    e,
                )
        except OSError as e:
            LOGGER.error("Error during HLS server cleanup: %s", e)

    @property
    def port(self) -> int:
        """The bound port number.

        Returns:
            The port number the server is bound to, or 0 if not started.
        """
        return self._port

    def player_url(self, host_ip: str) -> str:
        """Construct the full URL to the HTML player page.

        Args:
            host_ip: The host IP address to use in the URL (e.g., "192.168.1.100").

        Returns:
            The full player URL (e.g., "http://192.168.1.100:8080/player.html").
        """
        return f"http://{host_ip}:{self._port}/player.html"

    def stream_url(self, host_ip: str) -> str:
        """Construct the full URL to the HLS playlist.

        Args:
            host_ip: The host IP address to use in the URL (e.g., "192.168.1.100").

        Returns:
            The full stream URL (e.g., "http://192.168.1.100:8080/stream.m3u8").
        """
        return f"http://{host_ip}:{self._port}/stream.m3u8"
