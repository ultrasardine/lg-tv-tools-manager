from __future__ import annotations

import functools
import logging
import os
import shutil
import socketserver
import tempfile
import threading
import socket
import struct
import fcntl
from http.server import SimpleHTTPRequestHandler
from pathlib import Path

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

    def _get_default_interface(self) -> str | None:
        """Reads /proc/net/route to find the default gateway interface."""
        try:
            with open("/proc/net/route", "r") as f:
                for line in f.readlines()[1:]:
                    fields = line.strip().split()
                    if fields[1] == '00000000':
                        return fields[0]
        except Exception:
            pass
        return None

    def _get_ip_for_interface(self, ifname: str) -> str | None:
        """Uses ioctl to get the IPv4 address of an interface."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            ifreq = struct.pack('16sH2x4s8x', ifname.encode('utf-8'), socket.AF_INET, b'\x00' * 4)
            res = fcntl.ioctl(s.fileno(), 0x8915, ifreq)
            ip = struct.unpack('16sH2x4s8x', res)[2]
            return socket.inet_ntoa(ip)
        except Exception:
            return None

    def _get_host_ip(self) -> str:
        """Detects the host's LAN IPv4 address using local routing table."""
        ifname = self._get_default_interface()
        if ifname:
            ip = self._get_ip_for_interface(ifname)
            if ip:
                return ip
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
