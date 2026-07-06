from __future__ import annotations

import logging
import socket
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urljoin

from .models import LGTVDevice

LOGGER = logging.getLogger(__name__)

NS = {
    "d": "urn:schemas-upnp-org:device-1-0",
    "s": "http://schemas.xmlsoap.org/soap/envelope/",
}


@dataclass
class UPnPService:
    service_type: str
    control_url: str
    service_id: str = ""

    def short_name(self) -> str:
        return self.service_type.rsplit(":", 1)[-1]


class UPnPStatus(str, Enum):
    OK = "ok"
    NO_AVTRANSPORT = "no_avtransport"
    SET_FAILED = "set_failed"
    PLAY_FAILED = "play_failed"
    DEVICE_UNREACHABLE = "device_unreachable"
    NO_SERVICES = "no_services"
    INVALID_URL = "invalid_url"


@dataclass
class UPnPResult:
    status: UPnPStatus
    message: str
    service: UPnPService | None = None

    @property
    def ok(self) -> bool:
        return self.status == UPnPStatus.OK


def _device_xml(device: LGTVDevice) -> ET.Element | None:
    try:
        with urllib.request.urlopen(device.location, timeout=3) as response:
            return ET.fromstring(response.read().decode("utf-8", "ignore"))
    except Exception:
        LOGGER.debug("Failed to load device description for %s", device.location, exc_info=True)
        return None


def get_upnp_services(device: LGTVDevice) -> list[UPnPService]:
    root = _device_xml(device)
    if root is None:
        return []
    services: list[UPnPService] = []
    base_url = device.location.rsplit("/", 1)[0] + "/"
    for service in root.findall(".//d:service", NS):
        service_type = service.findtext("d:serviceType", default="", namespaces=NS)
        control = service.findtext("d:controlURL", default="", namespaces=NS)
        service_id = service.findtext("d:serviceId", default="", namespaces=NS)
        if service_type and control:
            services.append(
                UPnPService(
                    service_type=service_type,
                    control_url=urljoin(base_url, control),
                    service_id=service_id,
                )
            )
    return services


def summarize_upnp_services(device: LGTVDevice) -> list[str]:
    services = get_upnp_services(device)
    lines = []
    for svc in services:
        lines.append(f"{svc.short_name()} [{svc.service_id or 'sin serviceId'}]")
    return lines


def upnp_service_details(device: LGTVDevice) -> list[UPnPService]:
    return get_upnp_services(device)


def _soap_action(control_url: str, service_type: str, action: str, arguments: dict[str, str]) -> tuple[bool, str]:
    envelope = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">',
        "<s:Body>",
        f'<u:{action} xmlns:u="{service_type}">',
    ]
    for key, value in arguments.items():
        envelope.append(f"<{key}>{value}</{key}>")
    envelope.extend([f"</u:{action}>", "</s:Body>", "</s:Envelope>"])
    body = "".join(envelope).encode("utf-8")
    req = urllib.request.Request(
        control_url,
        data=body,
        headers={
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPACTION": f'"{service_type}#{action}"',
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            response.read()
        return True, "ok"
    except Exception as exc:
        LOGGER.debug("SOAP action failed: %s %s", action, control_url, exc_info=True)
        return False, str(exc)


def cast_media_to_device(device: LGTVDevice, media_url: str, title: str = "LG TV Tools") -> UPnPResult:
    if not media_url.startswith("http://") and not media_url.startswith("https://"):
        return UPnPResult(UPnPStatus.INVALID_URL, "La URL de media no es HTTP/HTTPS")
    services = get_upnp_services(device)
    av_transport = next((s for s in services if "AVTransport" in s.service_type), None)
    if not av_transport:
        return UPnPResult(UPnPStatus.NO_AVTRANSPORT, "La TV no expone AVTransport")
    set_ok, set_err = _soap_action(
        av_transport.control_url,
        av_transport.service_type,
        "SetAVTransportURI",
        {
            "InstanceID": "0",
            "CurrentURI": media_url,
            "CurrentURIMetaData": "",
        },
    )
    if not set_ok:
        return UPnPResult(UPnPStatus.SET_FAILED, f"SetAVTransportURI falló: {set_err}", av_transport)
    play_ok, play_err = _soap_action(
        av_transport.control_url,
        av_transport.service_type,
        "Play",
        {"InstanceID": "0", "Speed": "1"},
    )
    if not play_ok:
        return UPnPResult(UPnPStatus.PLAY_FAILED, f"Play falló: {play_err}", av_transport)
    return UPnPResult(UPnPStatus.OK, f"UPnP OK: {title}", av_transport)
