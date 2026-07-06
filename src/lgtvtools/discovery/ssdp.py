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
    # Phase 1: Collect all unique logical devices
    logical_devices: dict[str, LGTVDevice] = {}
    
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
            
            # Use USN as unique key for initial collection
            if usn in logical_devices:
                continue
            
            parsed = urlparse(location)
            ip = parsed.hostname or ""
            
            device = LGTVDevice(
                usn=usn,
                name=headers.get("friendlyname", "") or headers.get("name", "") or "LG TV",
                ip=ip,
                location=location,
                model=headers.get("modelname", "") or headers.get("model", ""),
                server=server,
                friendly_name=headers.get("friendlyname", "") or headers.get("name", "") or "LG TV",
                services=[s for s in [headers.get("st", ""), headers.get("nt", "")] if s],
            )
            
            # Enrich from XML
            if location:
                try:
                    with urlopen(location, timeout=2) as response:
                        xml_data = response.read()
                        root = ET.fromstring(xml_data.decode("utf-8", "ignore"))
                    ns = {"d": "urn:schemas-upnp-org:device-1-0"}
                    friendly = root.findtext(".//d:friendlyName", default="", namespaces=ns)
                    model_xml = root.findtext(".//d:modelName", default="", namespaces=ns)
                    manufacturer = root.findtext(".//d:manufacturer", default="", namespaces=ns)
                    
                    if friendly:
                        device.name = friendly
                        device.friendly_name = friendly
                    if model_xml:
                        device.model = model_xml
                    
                    if _manufacturer_filter_enabled() and manufacturer and "lg" not in manufacturer.lower():
                        continue
                    
                    for svc in root.findall(".//d:service", {"d": "urn:schemas-upnp-org:device-1-0"}):
                        service_type = svc.findtext("d:serviceType", default="", namespaces={"d": "urn:schemas-upnp-org:device-1-0"})
                        if service_type:
                            svc_short = service_type.rsplit(":", 1)[-1]
                            if svc_short and svc_short not in device.services:
                                device.services.append(svc_short)
                except Exception:
                    LOGGER.debug("Could not enrich device %s", usn, exc_info=True)
            
            logical_devices[usn] = device
    finally:
        sock.close()

    # Phase 2: Consolidate by IP
    physical_devices: dict[str, LGTVDevice] = {}
    
    for dev in logical_devices.values():
        ip = dev.ip
        if not ip:
            # Fallback for devices without IP (unlikely for LG TV)
            ip = dev.location 
            
        if ip in physical_devices:
            # Merge into existing physical device
            p_dev = physical_devices[ip]
            if dev.location:
                p_dev.locations.add(dev.location)
            
            # Keep the friendliest name
            if dev.name != "LG TV" and (p_dev.name == "LG TV" or len(dev.name) > len(p_dev.name)):
                p_dev.name = dev.name
                p_dev.friendly_name = dev.friendly_name
            
            # Keep model if available
            if dev.model and not p_dev.model:
                p_dev.model = dev.model
                
            # Merge services without duplicates
            for svc in dev.services:
                if svc not in p_dev.services:
                    p_dev.services.append(svc)
        else:
            physical_devices[ip] = dev

    LOGGER.info("SSDP discovered %d logical and %d physical LG devices", 
                len(logical_devices), len(physical_devices))
    
    return list(physical_devices.values())
