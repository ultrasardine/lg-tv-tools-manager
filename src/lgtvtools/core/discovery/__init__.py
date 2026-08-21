"""TV Discovery module for LG TV Tools.

This module provides multi-protocol TV discovery:
- SSDP (Simple Service Discovery Protocol) - Primary discovery method
- mDNS (Multicast DNS / Bonjour) - Secondary discovery for AirPlay-capable TVs
- UPnP (Universal Plug and Play) - Device control after discovery

The discovery functions run protocols in parallel and merge results.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

from lgtvtools.core.models import LGTVDevice

if TYPE_CHECKING:
    pass

LOGGER = logging.getLogger(__name__)

__all__ = [
    "discover_lg_tvs",
    "discover_lg_tvs_ssdp",
    "discover_lg_tvs_mdns",
    "LGTVDevice",
]


def discover_lg_tvs_ssdp(timeout: float = 5.0) -> list[LGTVDevice]:
    """Discover LG TVs using SSDP protocol.

    This is a re-export from the ssdp module for convenience.
    """
    from lgtvtools.core.discovery.ssdp import discover_lg_tvs as _discover
    return _discover(timeout)


def discover_lg_tvs_mdns(timeout: float = 5.0) -> list[LGTVDevice]:
    """Discover LG TVs using mDNS protocol.

    This is a re-export from the mdns module for convenience.
    Falls back gracefully if zeroconf is not installed.
    """
    try:
        from lgtvtools.core.discovery.mdns import discover_lg_tvs as _discover
        return _discover(timeout)
    except ImportError:
        LOGGER.debug("mDNS discovery not available (zeroconf not installed)")
        return []


def discover_lg_tvs(timeout: float = 5.0) -> list[LGTVDevice]:
    """Discover LG TVs using all available protocols (SSDP + mDNS).

    Runs SSDP and mDNS discovery in parallel, then merges and
    deduplicates results by IP address.

    Args:
        timeout: Discovery timeout in seconds (applies to each protocol).

    Returns:
        List of discovered LG TV devices, deduplicated by IP.
    """
    all_devices: list[LGTVDevice] = []

    # Define discovery tasks
    tasks = [
        ("ssdp", discover_lg_tvs_ssdp),
    ]

    # Only include mDNS if zeroconf is available
    try:
        import zeroconf  # noqa: F401
        tasks.append(("mdns", discover_lg_tvs_mdns))
    except ImportError:
        LOGGER.debug("mDNS discovery skipped (zeroconf not installed)")

    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        futures = {
            executor.submit(func, timeout): protocol
            for protocol, func in tasks
        }

        for future in as_completed(futures):
            protocol = futures[future]
            try:
                devices = future.result()
                # Tag devices with discovery source
                for dev in devices:
                    dev.discovery_source = protocol
                LOGGER.info("%s discovered %d device(s)", protocol.upper(), len(devices))
                all_devices.extend(devices)
            except Exception:
                LOGGER.warning("%s discovery failed", protocol.upper(), exc_info=True)

    # Deduplicate by IP address, merging device info
    merged = _merge_devices(all_devices)

    LOGGER.info("Combined discovery found %d unique LG device(s)", len(merged))
    return merged


def _merge_devices(devices: list[LGTVDevice]) -> list[LGTVDevice]:
    """Merge and deduplicate devices by IP address.

    When the same device is found by multiple protocols, merge their
    information (locations, services, etc.) into a single entry.

    Args:
        devices: List of devices to merge.

    Returns:
        List of unique devices with merged information.
    """
    merged: dict[str, LGTVDevice] = {}

    for dev in devices:
        ip = dev.ip
        if not ip:
            ip = dev.usn  # Fallback key

        if ip in merged:
            existing = merged[ip]

            # Merge locations
            for loc in dev.locations:
                existing.locations.add(loc)
            if dev.location:
                existing.locations.add(dev.location)

            # Prefer longer/more descriptive name
            if dev.name != "LG TV" and (
                existing.name == "LG TV" or len(dev.name) > len(existing.name)
            ):
                existing.name = dev.name
                existing.friendly_name = dev.friendly_name

            # Keep model if available
            if dev.model and not existing.model:
                existing.model = dev.model

            # Merge services
            for svc in dev.services:
                if svc not in existing.services:
                    existing.services.append(svc)

            # Update discovery source to indicate multiple protocols
            if existing.discovery_source != dev.discovery_source:
                existing.discovery_source = "both"
        else:
            merged[ip] = dev

    return list(merged.values())
