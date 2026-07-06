from __future__ import annotations

import logging
import socket
import time
import xml.etree.ElementTree as ET
import os
from urllib.request import urlopen
from urllib.parse import urlparse

from .models import LGTVDevice

LOGGER = logging.getLogger(__name__)
SSDP_ADDR = ("239.255.255.250", 1900)
M_SEARCH = (
    'M-SEARCH * HTTP/1.1\r\n'
    'HOST: 239.255.255.250:1900\r\n'
    'MAN: "ssdp:discover"\r\n'
    'MX: 2\r\n'
    'ST: ssdp:all\r\n\r\n'
)


def _parse_headers(payload: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in payload.split("\r\n")[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    return headers


def _manufacturer_filter_enabled() -> bool:
    value = os.environ.get("LGTVTOOLS_STRICT_MANUFACTURER_FILTER", "0").strip().lower()
    return value in {"1", "true", "yes", "on"}


def discover_lg_tvs(timeout: float = 3.0) -> list[LGTVDevice]:
    devices: dict[str, LGTVDevice] = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.settimeout(0.5)
    sock.bind(("", 0))
    sock.sendto(M_SEARCH.encode("utf-8"), SSDP_ADDR)
    end = time.time() + timeout

    try:
        while time.time() < end:
            try:
                data, _addr = sock.recvfrom(65535)
            except socket.timeout:
                continue
            payload = data.decode("utf-8", "ignore")
            headers = _parse_headers(payload)
            server = headers.get("server", "")
            location = headers.get("location", "")
            usn = headers.get("usn", location or server)
            if "lg" not in (server + " " + location + " " + usn).lower():
                continue
            parsed = urlparse(location)
            ip = parsed.hostname or ""
            name = headers.get("friendlyname", "") or headers.get("name", "") or "LG TV"
            model = headers.get("modelname", "") or headers.get("model", "")
            services = [headers.get("st", ""), headers.get("nt", "")]
            device = LGTVDevice(
                usn=usn,
                name=name,
                ip=ip,
                location=location,
                model=model,
                server=server,
                friendly_name=name,
                services=[s for s in services if s],
            )
            if location:
                try:
                    with urlopen(location, timeout=2) as response:
                        xml = response.read().decode("utf-8", "ignore")
                    root = ET.fromstring(xml)
                    ns = {"d": "urn:schemas-upnp-org:device-1-0"}
                    friendly = root.findtext(".//d:friendlyName", default="", namespaces=ns)
                    model = root.findtext(".//d:modelName", default=model, namespaces=ns)
                    manufacturer = root.findtext(".//d:manufacturer", default="", namespaces=ns)
                    if friendly:
                        device.name = friendly
                        device.friendly_name = friendly
                    if model:
                        device.model = model
                    if _manufacturer_filter_enabled() and manufacturer and "lg" not in manufacturer.lower():
                        continue
                    svc_names = []
                    for svc in root.findall(".//d:service", {"d": "urn:schemas-upnp-org:device-1-0"}):
                        service_type = svc.findtext("d:serviceType", default="", namespaces={"d": "urn:schemas-upnp-org:device-1-0"})
                        if service_type:
                            svc_names.append(service_type.rsplit(":", 1)[-1])
                    if svc_names:
                        device.services = svc_names
                except Exception:
                    LOGGER.debug("Could not enrich device from %s", location, exc_info=True)
            devices[usn] = device
    finally:
        sock.close()

    LOGGER.info("SSDP discovered %d LG candidate devices", len(devices))
    return list(devices.values())
