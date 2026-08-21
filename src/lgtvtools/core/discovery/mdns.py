"""mDNS (Multicast DNS / Bonjour) discovery implementation.

This module provides LG TV discovery using mDNS service browsing.
It looks for AirPlay and RAOP services and filters for LG devices
by checking service names and TXT record properties.

Note: This module requires the `zeroconf` package to be installed.
On mobile platforms, native mDNS APIs should be used instead.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zeroconf import Zeroconf, ServiceInfo

from lgtvtools.core.models import LGTVDevice

LOGGER = logging.getLogger(__name__)

# mDNS service types that LG webOS TVs commonly advertise
LG_SERVICE_TYPES = [
    "_airplay._tcp.local.",
    "_raop._tcp.local.",  # Remote Audio Output Protocol (AirPlay audio)
]

# Indicators that a discovered service belongs to an LG TV
LG_INDICATORS = ("lg", "webos", "lge")


class _LGServiceListener:
    """Collects mDNS service info for LG TV devices."""

    def __init__(self, zc: Zeroconf) -> None:
        self._zc = zc
        self.devices: dict[str, LGTVDevice] = {}

    def _extract_text_property(self, properties: dict[bytes, bytes | None], key: str) -> str:
        """Safely extract a text property from mDNS TXT record."""
        value = properties.get(key.encode("utf-8"))
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", "ignore")
        return str(value)

    def _is_lg_device(self, name: str, properties: dict[bytes, bytes | None]) -> bool:
        """Determine if a service belongs to an LG TV."""
        # Check service name
        if any(ind in name.lower() for ind in LG_INDICATORS):
            return True

        # Check TXT record properties
        manufacturer = self._extract_text_property(properties, "manufacturer")
        model = self._extract_text_property(properties, "model")
        integrator = self._extract_text_property(properties, "integrator")
        combined = f"{manufacturer} {model} {integrator}".lower()
        return any(ind in combined for ind in LG_INDICATORS)

    def add_service(self, zc: Zeroconf, service_type: str, name: str) -> None:
        self._handle_service(zc, service_type, name)

    def update_service(self, zc: Zeroconf, service_type: str, name: str) -> None:
        self._handle_service(zc, service_type, name)

    def remove_service(self, zc: Zeroconf, service_type: str, name: str) -> None:
        pass

    def _handle_service(self, zc: Zeroconf, service_type: str, name: str) -> None:
        info = zc.get_service_info(service_type, name)
        if info is None:
            LOGGER.debug("Could not resolve mDNS service: %s", name)
            return

        properties = info.properties or {}

        if not self._is_lg_device(name, properties):
            LOGGER.debug("Skipping non-LG mDNS service: %s", name)
            return

        # Extract IP addresses
        addresses = info.parsed_addresses()
        if not addresses:
            LOGGER.debug("No addresses for mDNS service: %s", name)
            return

        # Use the first IPv4 address
        ip = ""
        for addr in addresses:
            if ":" not in addr:  # Skip IPv6
                ip = addr
                break
        if not ip and addresses:
            ip = addresses[0]

        # Extract device metadata from TXT record
        model = self._extract_text_property(properties, "model")
        manufacturer = self._extract_text_property(properties, "manufacturer")
        device_id = self._extract_text_property(properties, "deviceid")

        # Build a friendly name from the service instance name
        friendly_name = name.replace(f".{service_type}", "").strip(".")

        # Use IP as the deduplication key
        if ip in self.devices:
            # Merge service info into existing device
            dev = self.devices[ip]
            svc_short = service_type.rstrip(".").replace("._tcp", "").replace("._udp", "").lstrip("_")
            if svc_short and svc_short not in dev.services:
                dev.services.append(svc_short)
            # Keep longer/more descriptive name
            if friendly_name and len(friendly_name) > len(dev.name):
                dev.name = friendly_name
                dev.friendly_name = friendly_name
            return

        svc_short = service_type.rstrip(".").replace("._tcp", "").replace("._udp", "").lstrip("_")
        device = LGTVDevice(
            usn=device_id or f"mdns:{ip}:{info.port}",
            name=friendly_name or "LG TV",
            ip=ip,
            location=f"http://{ip}:{info.port}/",
            model=model,
            server=f"{manufacturer} webOS" if manufacturer else "LG webOS",
            friendly_name=friendly_name or "LG TV",
            services=[svc_short] if svc_short else [],
            discovery_source="mdns",
        )
        self.devices[ip] = device
        LOGGER.debug("mDNS discovered LG device: %s at %s:%d", friendly_name, ip, info.port)


def discover_lg_tvs(timeout: float = 5.0) -> list[LGTVDevice]:
    """Discover LG TVs using mDNS/Bonjour service browsing.

    Browses for AirPlay and RAOP services, filtering for LG devices
    by name and TXT record properties.

    Args:
        timeout: Discovery timeout in seconds.

    Returns:
        List of discovered LG TV devices.

    Raises:
        ImportError: If zeroconf is not installed.
    """
    from zeroconf import ServiceBrowser, Zeroconf

    zc = Zeroconf()
    listener = _LGServiceListener(zc)

    browsers = []
    for service_type in LG_SERVICE_TYPES:
        try:
            browser = ServiceBrowser(zc, service_type, listener)
            browsers.append(browser)
        except Exception:
            LOGGER.debug("Failed to browse for %s", service_type, exc_info=True)

    # Wait for responses
    time.sleep(timeout)

    # Cleanup
    for browser in browsers:
        browser.cancel()
    zc.close()

    devices = list(listener.devices.values())
    LOGGER.info("mDNS discovered %d LG device(s)", len(devices))
    return devices


# Backwards compatibility alias
discover_lg_tvs_mdns = discover_lg_tvs
