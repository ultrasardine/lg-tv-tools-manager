from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from .models import LGTVDevice
from .ssdp import discover_lg_tvs as discover_lg_tvs_ssdp

# Import mdns only if zeroconf is available
try:
    from .mdns import discover_lg_tvs_mdns
    _MDNS_AVAILABLE = True
except ImportError:
    _MDNS_AVAILABLE = False
    def discover_lg_tvs_mdns(timeout: float = 5.0) -> list[LGTVDevice]:
        return []

LOGGER = logging.getLogger(__name__)


def discover_lg_tvs(timeout: float = 5.0) -> list[LGTVDevice]:
    """Discover LG TVs using all available protocols (SSDP + mDNS).

    Runs SSDP and mDNS discovery in parallel, then merges and
    deduplicates results by IP address.
    """
    all_devices: list[LGTVDevice] = []

    # Define tasks based on available modules
    tasks = [
        ("ssdp", discover_lg_tvs_ssdp),
    ]
    if _MDNS_AVAILABLE:
        tasks.append(("mdns", discover_lg_tvs_mdns))

    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        futures = {
            executor.submit(func, timeout): protocol
            for protocol, func in tasks
        }
        for future in as_completed(futures):
            protocol = futures[future]
            try:
                devices = future.result()
                LOGGER.info("%s discovered %d device(s)", protocol.upper(), len(devices))
                all_devices.extend(devices)
            except Exception:
                LOGGER.warning("%s discovery failed", protocol.upper(), exc_info=True)

    # Deduplicate by IP address, merging device info
    merged: dict[str, LGTVDevice] = {}
    for dev in all_devices:
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
            if dev.name != "LG TV" and (existing.name == "LG TV" or len(dev.name) > len(existing.name)):
                existing.name = dev.name
                existing.friendly_name = dev.friendly_name
            # Keep model if available
            if dev.model and not existing.model:
                existing.model = dev.model
            # Merge services
            for svc in dev.services:
                if svc not in existing.services:
                    existing.services.append(svc)
        else:
            merged[ip] = dev

    result = list(merged.values())
    LOGGER.info("Combined discovery found %d unique LG device(s)", len(result))
    return result
