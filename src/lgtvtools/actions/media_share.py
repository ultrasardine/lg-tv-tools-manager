from __future__ import annotations

import functools
import logging
import os
import shutil
import socketserver
import tempfile
import threading
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
        return f"http://127.0.0.1:{self.port}/{source.name}"

    def close(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._root.exists():
            shutil.rmtree(self._root, ignore_errors=True)
