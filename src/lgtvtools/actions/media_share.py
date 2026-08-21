from __future__ import annotations

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

import netifaces

LOGGER = logging.getLogger(__name__)


class _ReuseTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


class MediaShareServer:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._server: _ReuseTCPServer | None = None
        self._thread: threading.Thread | None = None
        self._root = Path(tempfile.mkdtemp(prefix="lg-tv-tools-share-"))
        self.port = 0

    def _get_host_ip(self) -> str:
        """Detects the host's LAN IPv4 address (cross-platform)."""
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

    def _ensure_server(self) -> None:
        if self._server:
            return
        handler = functools.partial(SimpleHTTPRequestHandler, directory=str(self._root))
        self._server = _ReuseTCPServer(("0.0.0.0", 0), handler)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        LOGGER.info("Media share server started on port %s", self.port)

    def publish(self, path: str) -> str:
        source = Path(path)
        self._ensure_server()
        target = self._root / source.name
        if target.exists() or target.is_symlink():
            target.unlink()
        try:
            os.symlink(source, target)
        except OSError:
            shutil.copy2(source, target)
        return f"http://{self._get_host_ip()}:{self.port}/{source.name}"

    def close(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._root.exists():
            shutil.rmtree(self._root, ignore_errors=True)
