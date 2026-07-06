from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QGroupBox,
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

from ..actions.runtime import launch, open_file_with_default_app
from ..actions.media_share import MediaShareServer
from ..capabilities.detection import detect_capabilities
from ..discovery.models import LGTVDevice
from ..discovery.ssdp import discover_lg_tvs
from ..discovery.upnp import cast_media_to_device, upnp_service_details
from .styles import APP_STYLE

LOGGER = logging.getLogger(__name__)


@dataclass
class MediaAction:
    label: str
    kinds: tuple[str, ...]


MEDIA_ACTIONS = {
    "video": MediaAction("Enviar vídeo", (".mp4", ".mkv", ".avi", ".webm", ".mov")),
    "image": MediaAction("Enviar imagen", (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")),
    "music": MediaAction("Enviar música", (".mp3", ".flac", ".wav", ".ogg", ".m4a")),
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


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("LG TV Tools")
        self.resize(1200, 760)
        self.devices: list[LGTVDevice] = []
        self.capabilities = detect_capabilities()
        self.worker: DiscoveryWorker | None = None
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

        self.status_label = QLabel("Listo")
        self.selected_label = QLabel("TV: ninguna")
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
            "DLNA depende del modelo LG y de la red local. La URL temporal requiere que la TV pueda acceder al host."
        )
        self.note_box.setWordWrap(True)
        self.capability_box.setMinimumHeight(140)
        self.diagnose_box.setMinimumHeight(140)
        self.upnp_card.setMinimumHeight(170)
        self.log_box.setMinimumHeight(200)

        scan_btn = QPushButton("Buscar otra vez")
        scan_btn.clicked.connect(self.scan_network)

        self.btn_mirror = QPushButton("Duplicar")
        self.btn_cast = QPushButton("Transmitir")
        self.btn_video = QPushButton("Vídeo")
        self.btn_image = QPushButton("Imagen")
        self.btn_music = QPushButton("Música")
        self.btn_copy_url = QPushButton("Copiar URL")
        self.btn_copy_media_url = QPushButton("Copiar media_url")
        self.btn_gnd = QPushButton("Abrir GND")
        self.btn_vlc = QPushButton("Abrir VLC")

        self.btn_mirror.clicked.connect(self.start_mirror)
        self.btn_cast.clicked.connect(self.start_cast)
        self.btn_video.clicked.connect(lambda: self._send_media("video"))
        self.btn_image.clicked.connect(lambda: self._send_media("image"))
        self.btn_music.clicked.connect(lambda: self._send_media("music"))
        self.btn_copy_url.clicked.connect(self.copy_local_url)
        self.btn_copy_media_url.clicked.connect(self.copy_media_url)
        self.btn_gnd.clicked.connect(lambda: self._launch_app("gnome-network-displays"))
        self.btn_vlc.clicked.connect(lambda: self._launch_app("vlc"))

        left = QGroupBox("TVs LG")
        left_l = QVBoxLayout(left)
        left_l.addWidget(self.device_list)
        left_l.addWidget(scan_btn)

        center = QGroupBox("Acciones")
        center_l = QVBoxLayout(center)
        for btn in [
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

        right = QGroupBox("Diagnóstico")
        right_l = QVBoxLayout(right)
        right_l.addWidget(QLabel("Deps"))
        right_l.addWidget(self.capability_box)
        right_l.addWidget(QLabel("Ayuda"))
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
            state = "instalado" if cap.installed else "falta"
            lines.append(f"{cap.name}: {state}")
        self.capability_box.setPlainText("\n".join(lines))
        self._refresh_diagnostics()

    def _refresh_diagnostics(self) -> None:
        missing = [cap for cap in self.capabilities if not cap.installed]
        if not missing:
            text = "Todo listo."
        else:
            text = "\n".join(
                [
                    "Faltan deps:",
                    *[f"- {cap.name}" for cap in missing],
                    "",
                    "Kali:",
                    "sudo apt update && sudo apt install gnome-network-displays vlc ffmpeg rygel pulseaudio pipewire miraclecast",
                ]
            )
        self.diagnose_box.setPlainText(text)

    def _set_action_enabled(self, enabled: bool) -> None:
        for btn in [
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
        self.selected_label.setText(f"TV: {device.display_name() if device else 'ninguna'}")
        self._refresh_upnp_card()
        self.status_label.setText("TV lista" if enabled else "Sin TV")

    def scan_network(self) -> None:
        self.status_label.setText("Buscando TVs...")
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
        self._append_log(f"Escaneo: {len(devices)} TV(s)")

    def _scan_failed(self, message: str) -> None:
        self.status_label.setText("Error de red")
        self._append_log(f"SSDP: {message}")
        QMessageBox.warning(self, "LG TV Tools", f"Falló el escaneo:\n{message}")

    def _append_log(self, message: str) -> None:
        self.log_box.append(message)

    def _launch_app(self, command: str) -> None:
        result = launch(command)
        self._append_log(result.message)
        if not result.ok:
            QMessageBox.information(self, "LG TV Tools", result.message)

    def start_mirror(self) -> None:
        result = launch("gnome-network-displays")
        if not result.ok:
            fallback = "Instala gnome-network-displays o miraclecast."
            self._append_log(fallback)
            QMessageBox.information(self, "LG TV Tools", f"{result.message}\n{fallback}")
            return
        self._append_log("Duplicación: gnome-network-displays")

    def start_cast(self) -> None:
        result = launch("gnome-network-displays")
        if result.ok:
            self._append_log("Transmisión: gnome-network-displays")
            return
        if launch("miraclecast").ok:
            self._append_log("Transmisión: miraclecast")
            return
        QMessageBox.information(
            self,
            "LG TV Tools",
            "Falta backend de casting: gnome-network-displays o miraclecast.",
        )

    def _send_media(self, media_kind: str) -> None:
        action = MEDIA_ACTIONS[media_kind]
        filter_string = "Archivos (*" + " *".join(action.kinds) + ")"
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
            result = cast_media_to_device(device, share_url, p.name)
            if result.ok:
                self._append_log(f"UPnP: {device.display_name()}")
                self.status_label.setText("Enviado")
                return
            self._append_log(f"UPnP: {result.status.value} - {result.message}")
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
                "VLC no está instalado. Se abrió con la app predeterminada.\n"
                "Para DLNA real, instala VLC o rygel.",
            )
            return
        QMessageBox.information(
            self,
            "LG TV Tools",
            f"No hay app para reproducir.\nURL: {share_url}",
        )
        self.last_share_url = share_url

    def copy_local_url(self) -> None:
        device = self._current_device()
        if not device:
            QMessageBox.information(self, "LG TV Tools", "Selecciona una TV primero.")
            return
        url = self.last_share_url or f"http://127.0.0.1:{self.share_server.port}/"
        QGuiApplication.clipboard().setText(url)
        self._append_log(f"Copiada URL: {url}")
        QMessageBox.information(self, "LG TV Tools", f"Copiada:\n{url}")

    def copy_media_url(self) -> None:
        device = self._current_device()
        if not device or not self.last_share_url:
            QMessageBox.information(self, "LG TV Tools", "Primero selecciona y comparte un archivo.")
            return
        QGuiApplication.clipboard().setText(self.last_share_url)
        self._append_log(f"Copiada media_url: {self.last_share_url}")
        QMessageBox.information(self, "LG TV Tools", f"Copiada:\n{self.last_share_url}")

    def _refresh_upnp_card(self) -> None:
        device = self._current_device()
        if not device:
            self.upnp_card.setPlainText("Sin TV.")
            return
        services = upnp_service_details(device)
        short_names = ", ".join(svc.short_name() for svc in services) if services else "ninguno"
        avtransport = next((svc for svc in services if "AVTransport" in svc.service_type), None)
        lines = [
            f"TV: {device.display_name()}",
            f"Estado: {'OK' if avtransport else 'sin AVTransport'}",
            f"Servicios: {short_names}",
        ]
        if avtransport:
            lines.append(f"AVTransport: {avtransport.control_url}")
        elif services:
            lines.append("Sin AVTransport apto.")
        else:
            lines.append("Sin servicios UPnP.")
        self.upnp_card.setPlainText("\n".join(lines))

    def closeEvent(self, event) -> None:
        try:
            self.share_server.close()
        finally:
            super().closeEvent(event)
