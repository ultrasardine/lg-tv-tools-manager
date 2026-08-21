from __future__ import annotations

import logging
import os
import socket
import struct
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from urllib.request import urlopen

# netifaces is optional
try:
    import netifaces
    _NETIFACES_AVAILABLE = True
except ImportError:
    netifaces = None  # type: ignore
    _NETIFACES_AVAILABLE = False

from .models import LGTVDevice

LOGGER = logging.getLogger(__name__)
SSDP_ADDR = ("239.255.255.250", 1900)
SSDP_PORT = 1900

# Use multiple search targets to maximize discovery chances.
# Some LG TVs only respond to specific ST values.
M_SEARCH_TEMPLATES = [
    (
        'M-SEARCH * HTTP/1.1\r\n'
        'HOST: 239.255.255.250:1900\r\n'
        'MAN: "ssdp:discover"\r\n'
        'MX: 3\r\n'
        'ST: ssdp:all\r\n\r\n'
    ),
    (
        'M-SEARCH * HTTP/1.1\r\n'
        'HOST: 239.255.255.250:1900\r\n'
        'MAN: "ssdp:discover"\r\n'
        'MX: 3\r\n'
        'ST: urn:schemas-upnp-org:device:MediaRenderer:1\r\n\r\n'
    ),
    (
        'M-SEARCH * HTTP/1.1\r\n'
        'HOST: 239.255.255.250:1900\r\n'
        'MAN: "ssdp:discover"\r\n'
        'MX: 3\r\n'
        'ST: urn:dial-multiscreen-org:service:dial:1\r\n\r\n'
    ),
]

# Number of times to send each M-SEARCH packet (UDP is unreliable)
M_SEARCH_REPEAT = 3
# Delay between repeated sends (seconds)
M_SEARCH_INTERVAL = 0.3


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


def _get_local_ips() -> list[str]:
    """Get all local IPv4 addresses on non-loopback interfaces."""
    ips: list[str] = []

    # Try netifaces if available
    if _NETIFACES_AVAILABLE and netifaces is not None:
        try:
            for iface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(iface)
                for addr_info in addrs.get(netifaces.AF_INET, []):
                    ip = addr_info.get("addr", "")
                    if ip and not ip.startswith("127."):
                        ips.append(ip)
        except Exception:
            LOGGER.debug("Failed to enumerate interfaces via netifaces", exc_info=True)

    if not ips:
        # Fallback: use connect trick to determine outbound IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ips.append(s.getsockname()[0])
            s.close()
        except Exception:
            pass
    return ips


def _is_lg_device_from_headers(headers: dict[str, str]) -> bool:
    """Quick pre-filter on SSDP response headers.
    
    Returns True if there's any hint this might be an LG device,
    or if we can't tell (so we don't skip it prematurely).
    """
    combined = " ".join([
        headers.get("server", ""),
        headers.get("location", ""),
        headers.get("usn", ""),
        headers.get("st", ""),
    ]).lower()
    # Known LG indicators in headers
    lg_indicators = ("lg", "webos", "lge")
    for indicator in lg_indicators:
        if indicator in combined:
            return True
    # If it's a MediaRenderer or DIAL device, let it through for XML check
    # (LG TVs often don't put "LG" in headers but do in XML)
    media_indicators = ("mediarenderer", "dial", "avtransport")
    for indicator in media_indicators:
        if indicator in combined:
            return True
    return False


def _is_lg_device_from_xml(root: ET.Element) -> bool:
    """Check the device description XML to confirm this is an LG device."""
    ns = {"d": "urn:schemas-upnp-org:device-1-0"}
    manufacturer = (root.findtext(".//d:manufacturer", default="", namespaces=ns) or "").lower()
    friendly = (root.findtext(".//d:friendlyName", default="", namespaces=ns) or "").lower()
    model = (root.findtext(".//d:modelName", default="", namespaces=ns) or "").lower()
    combined = f"{manufacturer} {friendly} {model}"
    lg_indicators = ("lg", "webos", "lge")
    return any(indicator in combined for indicator in lg_indicators)


def discover_lg_tvs(timeout: float = 5.0) -> list[LGTVDevice]:
    """Discover LG TVs on the local network using SSDP multicast.
    
    Sends multiple M-SEARCH packets across multiple search targets and
    joins the multicast group on all local interfaces for reliable reception.
    """
    # Phase 1: Collect all unique logical devices
    logical_devices: dict[str, LGTVDevice] = {}

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # Allow multiple sockets to use the same port (macOS needs SO_REUSEPORT)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except (AttributeError, OSError):
        pass
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 4)
    # Enable loopback so we receive our own multicast if needed
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
    sock.settimeout(0.5)
    sock.bind(("", SSDP_PORT))

    # Join the SSDP multicast group on all local interfaces
    local_ips = _get_local_ips()
    mcast_group = socket.inet_aton("239.255.255.250")
    joined_any = False
    for local_ip in local_ips:
        try:
            mreq = mcast_group + socket.inet_aton(local_ip)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            LOGGER.debug("Joined SSDP multicast on interface %s", local_ip)
            joined_any = True
        except OSError as exc:
            LOGGER.debug("Could not join multicast on %s: %s", local_ip, exc)

    if not joined_any:
        # Fallback: join on default interface
        try:
            mreq = mcast_group + struct.pack("!I", 0)  # INADDR_ANY
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            LOGGER.debug("Joined SSDP multicast on default interface")
        except OSError as exc:
            LOGGER.debug("Could not join multicast on default interface: %s", exc)

    # Send M-SEARCH packets multiple times for reliability (UDP has no delivery guarantee)
    send_failed = True
    for _repeat in range(M_SEARCH_REPEAT):
        for template in M_SEARCH_TEMPLATES:
            try:
                sock.sendto(template.encode("utf-8"), SSDP_ADDR)
                send_failed = False
            except OSError as exc:
                LOGGER.debug("M-SEARCH send failed: %s", exc)
        if _repeat < M_SEARCH_REPEAT - 1:
            time.sleep(M_SEARCH_INTERVAL)

    if send_failed:
        LOGGER.warning("Cannot send any SSDP multicast (no active network route?)")
        sock.close()
        return []

    end = time.time() + timeout
    seen_locations: set[str] = set()

    try:
        while time.time() < end:
            try:
                data, _addr = sock.recvfrom(65535)
            except TimeoutError:
                continue
            payload = data.decode("utf-8", "ignore")
            headers = _parse_headers(payload)
            location = headers.get("location", "")
            
            # Skip responses without a location (can't fetch device description)
            if not location:
                continue
            
            # Skip duplicate locations early
            if location in seen_locations:
                continue
            seen_locations.add(location)

            server = headers.get("server", "")
            usn = headers.get("usn", location or server)

            # Quick pre-filter: skip responses that are clearly not LG
            if not _is_lg_device_from_headers(headers):
                continue

            # Use USN as unique key for initial collection
            if usn in logical_devices:
                # Still add the location to the existing device
                logical_devices[usn].locations.add(location)
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

            # Enrich from XML device description
            is_confirmed_lg = False
            if location:
                try:
                    with urlopen(location, timeout=3) as response:
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

                    # Confirm this is actually an LG device via XML
                    is_confirmed_lg = _is_lg_device_from_xml(root)

                    if _manufacturer_filter_enabled() and manufacturer and "lg" not in manufacturer.lower():
                        continue

                    for svc in root.findall(".//d:service", {"d": "urn:schemas-upnp-org:device-1-0"}):
                        service_type = svc.findtext(
                            "d:serviceType", default="",
                            namespaces={"d": "urn:schemas-upnp-org:device-1-0"},
                        )
                        if service_type:
                            svc_short = service_type.rsplit(":", 1)[-1]
                            if svc_short and svc_short not in device.services:
                                device.services.append(svc_short)
                except Exception:
                    LOGGER.debug("Could not enrich device %s", usn, exc_info=True)

            # Only add devices confirmed as LG (from headers or XML)
            combined_headers = (server + " " + location + " " + usn).lower()
            header_has_lg = any(ind in combined_headers for ind in ("lg", "webos", "lge"))
            if not header_has_lg and not is_confirmed_lg:
                LOGGER.debug("Skipping non-LG device: %s (%s)", device.name, ip)
                continue

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
            for loc in dev.locations:
                p_dev.locations.add(loc)

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
