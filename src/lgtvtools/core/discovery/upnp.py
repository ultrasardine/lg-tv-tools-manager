"""UPnP (Universal Plug and Play) control implementation.

This module provides UPnP/DLNA media casting functionality for LG TVs.
It implements the AVTransport service protocol for SetAVTransportURI
and Play actions.
"""

from __future__ import annotations

import logging
import mimetypes
import urllib.request
import xml.etree.ElementTree as ET
import xml.sax.saxutils
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

from lgtvtools.core.models import LGTVDevice, UPnPResult, UPnPStatus

LOGGER = logging.getLogger(__name__)

# XML namespaces for UPnP and SOAP
NS = {
    "d": "urn:schemas-upnp-org:device-1-0",
    "s": "http://schemas.xmlsoap.org/soap/envelope/",
}

__all__ = [
    "UPnPService",
    "UPnPResult",
    "UPnPStatus",
    "get_upnp_services",
    "upnp_service_details",
    "summarize_upnp_services",
    "cast_media_to_device",
]


@dataclass
class UPnPService:
    """A UPnP service discovered on a device.

    Attributes:
        service_type: Full service type URN.
        control_url: URL for SOAP control requests.
        service_id: Service identifier.
    """

    service_type: str
    control_url: str
    service_id: str = ""

    def short_name(self) -> str:
        """Extract the short service name from the URN."""
        return self.service_type.rsplit(":", 1)[-1]


def _device_xml(url: str) -> ET.Element | None:
    """Fetch and parse a device description XML."""
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return ET.fromstring(response.read().decode("utf-8", "ignore"))
    except Exception:
        LOGGER.debug("Failed to load device description for %s", url, exc_info=True)
        return None


def get_upnp_services(device: LGTVDevice) -> list[UPnPService]:
    """Get all UPnP services available on a device.

    Fetches device description XML from all known locations and
    extracts service information.

    Args:
        device: The LG TV device to query.

    Returns:
        List of UPnPService objects.
    """
    xml_cache: dict[str, ET.Element] = {}
    services: list[UPnPService] = []
    seen_services: set[tuple[str, str]] = set()

    for location in device.locations:
        root = xml_cache.get(location) or _device_xml(location)
        if root is None:
            continue
        xml_cache[location] = root

        base_url = location.rsplit("/", 1)[0] + "/"
        for service in root.findall(".//d:service", NS):
            service_type = service.findtext("d:serviceType", default="", namespaces=NS)
            control = service.findtext("d:controlURL", default="", namespaces=NS)
            service_id = service.findtext("d:serviceId", default="", namespaces=NS)
            if service_type and control:
                service_key = (service_type, control)
                if service_key not in seen_services:
                    seen_services.add(service_key)
                    services.append(
                        UPnPService(
                            service_type=service_type,
                            control_url=urljoin(base_url, control),
                            service_id=service_id,
                        )
                    )
    return services


def summarize_upnp_services(device: LGTVDevice) -> list[str]:
    """Get a human-readable summary of UPnP services.

    Args:
        device: The LG TV device to query.

    Returns:
        List of service summary strings.
    """
    services = get_upnp_services(device)
    lines = []
    for svc in services:
        lines.append(f"{svc.short_name()} [{svc.service_id or 'no serviceId'}]")
    return lines


def upnp_service_details(device: LGTVDevice) -> list[UPnPService]:
    """Get detailed UPnP service information.

    This is an alias for get_upnp_services for backwards compatibility.
    """
    return get_upnp_services(device)


def _soap_action(
    control_url: str,
    service_type: str,
    action: str,
    arguments: dict[str, str],
) -> tuple[bool, str]:
    """Execute a SOAP action on a UPnP service.

    Args:
        control_url: URL for the service control endpoint.
        service_type: Full service type URN.
        action: SOAP action name.
        arguments: Dictionary of action arguments.

    Returns:
        Tuple of (success, error_message).
    """
    envelope = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
        's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">',
        "<s:Body>",
        f'<u:{action} xmlns:u="{service_type}">',
    ]

    for key, value in arguments.items():
        if key == "CurrentURIMetaData":
            envelope.append(f"<{key}>{xml.sax.saxutils.escape(value)}</{key}>")
        else:
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


def _generate_didl_lite(media_url: str, filename: str) -> str:
    """Generate DIDL-Lite metadata for a media item.

    Args:
        media_url: URL of the media file.
        filename: Display name for the media.

    Returns:
        DIDL-Lite XML string.
    """
    mime_map = {
        ".mkv": "video/x-matroska",
        ".avi": "video/x-msvideo",
        ".mp4": "video/mp4",
        ".mp3": "audio/mpeg",
        ".flac": "audio/flac",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
    }

    ext = Path(urlparse(media_url).path).suffix.lower()
    mime_type = mime_map.get(ext)
    if not mime_type:
        mime_type, _ = mimetypes.guess_type(media_url)
    mime_type = mime_type or "application/octet-stream"

    if mime_type.startswith("video/"):
        upnp_class = "object.item.videoItem"
    elif mime_type.startswith("audio/"):
        upnp_class = "object.item.audioItem"
    elif mime_type.startswith("image/"):
        upnp_class = "object.item.imageItem"
    else:
        upnp_class = "object.item"

    protocol_info = f"http-get:*:{mime_type}:*"

    return (
        '<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">'
        f'<item id="0" parentID="0" restricted="1">'
        f'<dc:title>{xml.sax.saxutils.escape(filename)}</dc:title>'
        f'<upnp:class>{upnp_class}</upnp:class>'
        f'<res protocolInfo="{protocol_info}">{xml.sax.saxutils.escape(media_url)}</res>'
        '</item></DIDL-Lite>'
    )


def cast_media_to_device(
    device: LGTVDevice,
    media_url: str,
    title: str = "LG TV Tools",
) -> UPnPResult:
    """Cast a media URL to a TV using UPnP/DLNA.

    This sends SetAVTransportURI followed by Play to the TV's
    AVTransport service.

    Args:
        device: Target LG TV device.
        media_url: HTTP/HTTPS URL of the media to play.
        title: Display title for the media.

    Returns:
        UPnPResult indicating success or failure.
    """
    if not media_url.startswith(("http://", "https://")):
        return UPnPResult(
            ok=False,
            status=UPnPStatus.UNKNOWN_ERROR,
            message="Media URL must be HTTP/HTTPS",
        )

    services = get_upnp_services(device)
    av_transport = next((s for s in services if "AVTransport" in s.service_type), None)

    if not av_transport:
        return UPnPResult(
            ok=False,
            status=UPnPStatus.NO_AV_TRANSPORT,
            message="TV does not expose AVTransport service",
        )

    # Set the media URI
    set_ok, set_err = _soap_action(
        av_transport.control_url,
        av_transport.service_type,
        "SetAVTransportURI",
        {
            "InstanceID": "0",
            "CurrentURI": media_url,
            "CurrentURIMetaData": _generate_didl_lite(media_url, title),
        },
    )

    if not set_ok:
        return UPnPResult(
            ok=False,
            status=UPnPStatus.SOAP_ERROR,
            message=f"SetAVTransportURI failed: {set_err}",
        )

    # Start playback
    play_ok, play_err = _soap_action(
        av_transport.control_url,
        av_transport.service_type,
        "Play",
        {"InstanceID": "0", "Speed": "1"},
    )

    if not play_ok:
        return UPnPResult(
            ok=False,
            status=UPnPStatus.SOAP_ERROR,
            message=f"Play failed: {play_err}",
        )

    return UPnPResult(
        ok=True,
        status=UPnPStatus.SUCCESS,
        message=f"UPnP cast started: {title}",
    )
