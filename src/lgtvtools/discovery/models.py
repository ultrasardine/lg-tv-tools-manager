from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LGTVDevice:
    usn: str
    name: str
    ip: str
    location: str
    model: str = ""
    server: str = ""
    friendly_name: str = ""
    services: list[str] = field(default_factory=list)
    locations: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.location and not self.locations:
            self.locations.add(self.location)

    def display_name(self) -> str:
        parts = [self.name.strip() or "LG TV"]
        if self.model:
            parts.append(self.model)
        if self.ip:
            parts.append(self.ip)
        return " - ".join(parts)
