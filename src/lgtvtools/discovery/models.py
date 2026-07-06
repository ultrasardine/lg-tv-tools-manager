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

    def display_name(self) -> str:
        parts = [self.name.strip() or "LG TV"]
        if self.model:
            parts.append(self.model)
        if self.ip:
            parts.append(self.ip)
        return " - ".join(parts)
