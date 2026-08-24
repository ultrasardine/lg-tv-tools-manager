from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..actions.media_share import MediaShareServer
from ..actions.runtime import (
    launch,
    open_file_with_default_app,
)
from ..capabilities.detection import detect_capabilities, install_command_summary
from ..discovery import discover_lg_tvs
from ..discovery.models import LGTVDevice
from ..discovery.upnp import cast_media_to_device, upnp_service_details
from ..mirror.content_picker import ContentPicker
from ..mirror.sources import enumerate_sources
from ..mirror.worker import MirrorWorker
from ..system.platform import detect_platform, platform_label
from ..webos.client import WebOSClient, WebOSResult, connect_to_tv
from .styles import APP_STYLE

LOGGER = logging.getLogger(__name__)


@dataclass
class MediaAction:
    label: str
    kinds: tuple[str, ...]


MEDIA_ACTIONS = {
    "video": MediaAction("Select video", (".mp4", ".mkv", ".avi", ".webm", ".mov")),
    "image": MediaAction("Select image", (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")),
    "music": MediaAction("Select music", (".mp3", ".flac", ".wav", ".ogg", ".m4a")),
}


class DiscoveryWorker(QThread):
    finished_devices = pyqtSignal(list)
    failed = pyqtSignal(str)

    def run(self) -> None:
        try:
            self.finished_devices.emit(discover_lg_tvs())
        except Exception as exc:
            LOGGER.exception("Discovery failed")
            self.failed.emit(str(exc))


class WebOSWorker(QThread):
    """Background thread for webOS operations (pairing, commands)."""

    finished = pyqtSignal(object)  # WebOSResult
    pairing_prompt = pyqtSignal()  # Emitted when TV shows pairing prompt

    def __init__(self, ip: str, action: str, url: str = "", title: str = "") -> None:
        super().__init__()
        self.ip = ip
        self.action = action  # "pair", "cast_url", "cast_media"
        self.url = url
        self.title = title

    def run(self) -> None:
        try:
            client, connect_result = connect_to_tv(self.ip, timeout=30.0)
            if not connect_result.ok:
                self.finished.emit(connect_result)
                return

            if self.action == "pair":
                # Just pairing - show toast to confirm
                client.show_toast("LG TV Tools connected!")
                self.finished.emit(connect_result)
            elif self.action == "cast_url":
                result = client.launch_browser(self.url)
                self.finished.emit(result)
            elif self.action == "cast_media":
                result = client.open_media_url(self.url, self.title)
                self.finished.emit(result)
            else:
                self.finished.emit(WebOSResult(False, f"Unknown action: {self.action}"))

            client.disconnect()
        except Exception as exc:
            LOGGER.exception("WebOS worker failed")
            self.finished.emit(WebOSResult(False, str(exc)))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("LG TV Tools")
        self.resize(1200, 760)
        self.devices: list[LGTVDevice] = []
        self.capabilities = detect_capabilities()
        self.worker: DiscoveryWorker | None = None
        self.webos_worker: WebOSWorker | None = None
        self.mirror_worker: MirrorWorker | None = None
        self.share_server = MediaShareServer()
        self.last_share_url = ""
        self._build_ui()
        self._refresh_capabilities()
        self.scan_network()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QGridLayout(root)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 1)

        self.device_list = QListWidget()
        self.device_list.currentRowChanged.connect(self._selection_changed)

        self.status_label = QLabel("Ready")
        self.selected_label = QLabel("TV: none")
        self.selected_label.setWordWrap(True)
        self.capability_box = QTextEdit()
        self.capability_box.setReadOnly(True)
        self.diagnose_box = QTextEdit()
        self.diagnose_box.setReadOnly(True)
        self.upnp_card = QTextEdit()
        self.upnp_card.setReadOnly(True)
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.note_box = QLabel(
            "DLNA depends on the LG model and local network. The temporary URL requires the TV to reach this host."
        )
        self.note_box.setWordWrap(True)
        self.capability_box.setMinimumHeight(140)
        self.diagnose_box.setMinimumHeight(140)
        self.upnp_card.setMinimumHeight(170)
        self.log_box.setMinimumHeight(200)

        scan_btn = QPushButton("Scan again")
        scan_btn.clicked.connect(self.scan_network)

        self.btn_mirror = QPushButton("Mirror")
        self.btn_cast = QPushButton("Cast URL")
        self.btn_pair = QPushButton("Pair TV")
        self.btn_video = QPushButton("Video")
        self.btn_image = QPushButton("Image")
        self.btn_music = QPushButton("Music")
        self.btn_copy_url = QPushButton("Copy URL")
        self.btn_copy_media_url = QPushButton("Copy media_url")
        self.btn_gnd = QPushButton("Open GND")
        self.btn_vlc = QPushButton("Open VLC")

        self.btn_mirror.clicked.connect(self.start_mirror)
        self.btn_cast.clicked.connect(self.start_cast)
        self.btn_pair.clicked.connect(self.pair_tv)
        self.btn_video.clicked.connect(lambda: self._send_media("video"))
        self.btn_image.clicked.connect(lambda: self._send_media("image"))
        self.btn_music.clicked.connect(lambda: self._send_media("music"))
        self.btn_copy_url.clicked.connect(self.copy_local_url)
        self.btn_copy_media_url.clicked.connect(self.copy_media_url)
        self.btn_gnd.clicked.connect(lambda: self._launch_app("gnome-network-displays"))
        self.btn_vlc.clicked.connect(lambda: self._launch_app("vlc"))

        left = QGroupBox("LG TVs")
        left_l = QVBoxLayout(left)
        left_l.addWidget(self.device_list)
        left_l.addWidget(scan_btn)

        center = QGroupBox("Actions")
        center_l = QVBoxLayout(center)
        for btn in [
            self.btn_pair,
            self.btn_mirror,
            self.btn_cast,
            self.btn_video,
            self.btn_image,
            self.btn_music,
            self.btn_copy_url,
            self.btn_copy_media_url,
            self.btn_gnd,
            self.btn_vlc,
        ]:
            center_l.addWidget(btn)
        center_l.addWidget(self.selected_label)
        center_l.addWidget(self.status_label)

        right = QGroupBox("Diagnostics")
        right_l = QVBoxLayout(right)
        right_l.addWidget(QLabel("Deps"))
        right_l.addWidget(self.capability_box)
        right_l.addWidget(QLabel("Help"))
        right_l.addWidget(self.diagnose_box)
        right_l.addWidget(QLabel("UPnP"))
        right_l.addWidget(self.upnp_card)
        right_l.addWidget(self.note_box)
        right_l.addWidget(QLabel("Logs"))
        right_l.addWidget(self.log_box)

        layout.addWidget(left, 0, 0)
        layout.addWidget(center, 0, 1)
        layout.addWidget(right, 0, 2)
        left.setMinimumWidth(260)
        center.setMinimumWidth(260)
        right.setMinimumWidth(340)

        self.setStyleSheet(APP_STYLE)
        self._set_action_enabled(False)

    def _refresh_capabilities(self) -> None:
        lines: list[str] = []
        for cap in self.capabilities:
            state = "installed" if cap.installed else "missing"
            lines.append(f"{cap.name}: {state}")
        self.capability_box.setPlainText("\n".join(lines))
        self._refresh_diagnostics()

    def _refresh_diagnostics(self) -> None:
        missing = [cap for cap in self.capabilities if not cap.installed]
        if not missing:
            text = "All dependencies installed."
        else:
            lines = [
                "Missing dependencies:",
                *[f"  - {cap.name}" for cap in missing],
                "",
                f"Platform: {platform_label()}",
            ]
            summary = install_command_summary()
            if summary:
                lines.append(summary)
            else:
                # Fallback: list individual hints
                for cap in missing:
                    lines.append(f"  {cap.hint}")
            text = "\n".join(lines)
        self.diagnose_box.setPlainText(text)

    def _set_action_enabled(self, enabled: bool) -> None:
        for btn in [
            self.btn_pair,
            self.btn_mirror,
            self.btn_cast,
            self.btn_video,
            self.btn_image,
            self.btn_music,
            self.btn_copy_url,
            self.btn_copy_media_url,
        ]:
            btn.setEnabled(enabled)

    def _current_device(self) -> LGTVDevice | None:
        row = self.device_list.currentRow()
        if 0 <= row < len(self.devices):
            return self.devices[row]
        return None

    def _selection_changed(self) -> None:
        device = self._current_device()
        enabled = device is not None
        self._set_action_enabled(enabled)
        self.selected_label.setText(f"TV: {device.display_name() if device else 'none'}")
        self._refresh_upnp_card()
        self.status_label.setText("TV ready" if enabled else "No TV")

    def scan_network(self) -> None:
        self.status_label.setText("Scanning for TVs...")
        self.worker = DiscoveryWorker()
        self.worker.finished_devices.connect(self._populate_devices)
        self.worker.failed.connect(self._scan_failed)
        self.worker.start()

    def _populate_devices(self, devices: list) -> None:
        self.devices = devices
        self.device_list.clear()
        for dev in devices:
            item = QListWidgetItem(dev.display_name())
            item.setToolTip(dev.location)
            self.device_list.addItem(item)
        self.status_label.setText(f"{len(devices)} TV(s)")
        if devices:
            self.device_list.setCurrentRow(0)
        else:
            self._selection_changed()
        self._append_log(f"Scan: {len(devices)} TV(s)")

    def _scan_failed(self, message: str) -> None:
        self.status_label.setText("Network error")
        self._append_log(f"SSDP: {message}")
        QMessageBox.warning(self, "LG TV Tools", f"Scan failed:\n{message}")

    def _append_log(self, message: str) -> None:
        self.log_box.append(message)

    def _launch_app(self, command: str) -> None:
        result = launch(command)
        self._append_log(result.message)
        if not result.ok:
            QMessageBox.information(self, "LG TV Tools", result.message)

    def start_mirror(self) -> None:
        """Start or stop screen mirroring based on current state.

        If mirroring is not active:
        - Checks for ffmpeg availability
        - Enumerates available capture sources
        - Shows content picker dialog
        - Starts MirrorWorker on source selection

        If mirroring is active (button shows "Stop Mirror"):
        - Stops the current mirror session
        """
        # Check if currently mirroring - if so, stop it
        if self.btn_mirror.text() == "Stop Mirror":
            self._stop_mirror()
            return

        device = self._current_device()
        if not device:
            QMessageBox.information(self, "LG TV Tools", "Select a TV first.")
            return

        # Check ffmpeg availability (Requirement 7.3)
        from lgtvtools.system.bundled import which as bundled_which

        if not bundled_which("ffmpeg"):
            QMessageBox.warning(
                self,
                "LG TV Tools",
                "ffmpeg is required for screen mirroring.\n\n"
                "Please install ffmpeg and try again.",
            )
            self._append_log("Mirror: ffmpeg not found")
            return

        # Enumerate available capture sources
        platform = detect_platform()
        sources = enumerate_sources(platform)

        if not sources:
            QMessageBox.warning(
                self,
                "LG TV Tools",
                "No capture sources found.\n\n"
                "Make sure your system supports screen capture.",
            )
            self._append_log("Mirror: No capture sources found")
            return

        # Show content picker dialog (Requirements 1.1, 1.3, 7.4)
        picker = ContentPicker(sources, parent=self)
        if picker.exec() != QDialog.DialogCode.Accepted:
            self._append_log("Mirror: User cancelled source selection")
            return

        source = picker.selected_source()
        if not source:
            self._append_log("Mirror: No source selected")
            return

        # Create and start mirror worker (Requirements 6.4, 6.5)
        self._append_log(f"Mirror: Starting with {source.name}")
        self.status_label.setText("Starting mirror...")

        self.mirror_worker = MirrorWorker(
            device_ip=device.ip,
            source=source,
            parent=self,
        )
        self.mirror_worker.started.connect(self._mirror_started)
        self.mirror_worker.stopped.connect(self._mirror_stopped)
        self.mirror_worker.error.connect(self._mirror_error)
        self.mirror_worker.start()

        # Update button to indicate active mirroring (Requirement 6.5)
        self.btn_mirror.setText("Stop Mirror")

    def _stop_mirror(self) -> None:
        """Stop the current mirror session.

        Called when the user clicks the button while mirroring is active.
        Signals the MirrorWorker to stop and resets the button state.
        """
        if self.mirror_worker is not None:
            self._append_log("Mirror: Stopping...")
            self.status_label.setText("Stopping mirror...")
            self.mirror_worker.request_stop()
        # Reset button immediately for responsive UI
        self.btn_mirror.setText("Mirror")

    def _mirror_started(self) -> None:
        """Handle MirrorWorker started signal.

        Called when the mirror session successfully starts streaming to the TV.
        """
        self._append_log("Mirror: Stream live on TV")
        self.status_label.setText("Mirroring")

    def _mirror_stopped(self) -> None:
        """Handle MirrorWorker stopped signal.

        Called when the mirror session ends, whether by user request or error.
        Cleans up the worker reference and resets the UI.
        """
        self._append_log("Mirror: Session ended")
        self.status_label.setText("Ready")
        self.btn_mirror.setText("Mirror")
        self.mirror_worker = None

    def _mirror_error(self, message: str) -> None:
        """Handle MirrorWorker error signal.

        Called when an error occurs during the mirror session.
        Shows an error dialog and resets the UI.

        Args:
            message: The error message from the worker.
        """
        self._append_log(f"Mirror error: {message}")
        self.status_label.setText("Mirror failed")
        self.btn_mirror.setText("Mirror")
        self.mirror_worker = None
        QMessageBox.warning(
            self,
            "LG TV Tools",
            f"Screen mirroring failed:\n\n{message}",
        )

    def start_cast(self) -> None:
        device = self._current_device()
        if not device:
            QMessageBox.information(self, "LG TV Tools", "Select a TV first.")
            return
        url, ok = QInputDialog.getText(
            self,
            "Cast URL",
            f"Enter URL to cast to {device.display_name()}:",
        )
        if not ok or not url.strip():
            return
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = "http://" + url
        self._append_log(f"Casting URL: {url}")
        self.status_label.setText("Casting...")
        # Try webOS WebSocket API (works for AirPlay-only LG TVs)
        self._start_webos_action("cast_url", url=url)

    def _send_media(self, media_kind: str) -> None:
        action = MEDIA_ACTIONS[media_kind]
        filter_string = "Files (*" + " *".join(action.kinds) + ")"
        path, _ = QFileDialog.getOpenFileName(self, action.label, filter=filter_string)
        if not path:
            return
        p = Path(path)
        self._append_log(f"{action.label}: {p.name}")
        share_url = self.share_server.publish(str(p))
        self.last_share_url = share_url
        self._append_log(f"URL: {share_url}")
        device = self._current_device()
        if device:
            # Try UPnP first
            result = cast_media_to_device(device, share_url, p.name)
            if result.ok:
                self._append_log(f"UPnP: {device.display_name()}")
                self.status_label.setText("Sent")
                return
            self._append_log(f"UPnP: {result.status.value} - {result.message}")
            # Try webOS WebSocket API
            self.status_label.setText("Sending via webOS...")
            self._start_webos_action("cast_media", url=share_url, title=p.name)
            return
        if launch("vlc", [str(p)]).ok:
            self._append_log(f"VLC: {p.name}")
            self.last_share_url = share_url
            return
        if open_file_with_default_app(str(p)).ok:
            self._append_log(f"Default app: {p.name}")
            self.last_share_url = share_url
            QMessageBox.information(
                self,
                "LG TV Tools",
                "VLC is not installed. Opened with the default application.\n"
                "For proper DLNA, install VLC or rygel.",
            )
            return
        QMessageBox.information(
            self,
            "LG TV Tools",
            f"No application available to play this file.\nURL: {share_url}",
        )
        self.last_share_url = share_url

    def copy_local_url(self) -> None:
        device = self._current_device()
        if not device:
            QMessageBox.information(self, "LG TV Tools", "Select a TV first.")
            return
        url = self.last_share_url or f"http://127.0.0.1:{self.share_server.port}/"
        QGuiApplication.clipboard().setText(url)
        self._append_log(f"Copied URL: {url}")
        QMessageBox.information(self, "LG TV Tools", f"Copied:\n{url}")

    def copy_media_url(self) -> None:
        device = self._current_device()
        if not device or not self.last_share_url:
            QMessageBox.information(self, "LG TV Tools", "Select a TV and share a file first.")
            return
        QGuiApplication.clipboard().setText(self.last_share_url)
        self._append_log(f"Copied media_url: {self.last_share_url}")
        QMessageBox.information(self, "LG TV Tools", f"Copied:\n{self.last_share_url}")

    def _refresh_upnp_card(self) -> None:
        device = self._current_device()
        if not device:
            self.upnp_card.setPlainText("No TV selected.")
            return
        services = upnp_service_details(device)
        short_names = ", ".join(svc.short_name() for svc in services) if services else "none"
        avtransport = next((svc for svc in services if "AVTransport" in svc.service_type), None)
        lines = [
            f"TV: {device.display_name()}",
            f"Status: {'OK' if avtransport else 'no AVTransport'}",
            f"Services: {short_names}",
        ]
        if avtransport:
            lines.append(f"AVTransport: {avtransport.control_url}")
        elif services:
            lines.append("No compatible AVTransport found.")
        else:
            lines.append("No UPnP services found.")
        self.upnp_card.setPlainText("\n".join(lines))

    def pair_tv(self) -> None:
        """Initiate pairing with the selected TV via webOS WebSocket."""
        device = self._current_device()
        if not device:
            QMessageBox.information(self, "LG TV Tools", "Select a TV first.")
            return
        # Check if already paired
        client = WebOSClient(device.ip)
        if client.is_paired():
            reply = QMessageBox.question(
                self,
                "LG TV Tools",
                f"{device.display_name()} is already paired.\nRe-pair?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.status_label.setText("Pairing... Check TV for prompt")
        self._append_log(f"Pairing with {device.display_name()}...")
        QMessageBox.information(
            self,
            "LG TV Tools",
            f"A pairing prompt will appear on {device.display_name()}.\n"
            f"Please accept it on your TV within 30 seconds.",
        )
        self._start_webos_action("pair")

    def _start_webos_action(self, action: str, url: str = "", title: str = "") -> None:
        """Start a webOS operation in a background thread."""
        device = self._current_device()
        if not device:
            return
        self.webos_worker = WebOSWorker(device.ip, action, url, title)
        self.webos_worker.finished.connect(self._webos_finished)
        self.webos_worker.start()

    def _webos_finished(self, result: WebOSResult) -> None:
        """Handle completion of a webOS background operation."""
        self._append_log(f"webOS: {result.message}")
        if result.ok:
            self.status_label.setText("Done")
        else:
            self.status_label.setText("Failed")
            QMessageBox.warning(self, "LG TV Tools", result.message)

    def closeEvent(self, event) -> None:
        """Handle application close event.

        Ensures all resources are cleaned up:
        - Stops active mirror session (Requirement 6.6)
        - Closes the media share server
        """
        try:
            # Stop active mirror session on app exit (Requirement 6.6)
            if self.mirror_worker is not None and self.mirror_worker.is_active:
                LOGGER.info("Stopping mirror session on app exit")
                self.mirror_worker.request_stop()
                # Wait briefly for clean shutdown
                self.mirror_worker.wait(3000)  # 3 second timeout
            self.share_server.close()
        finally:
            super().closeEvent(event)
