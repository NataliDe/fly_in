from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class ZoneType(str, Enum):
    NORMAL = "normal"
    BLOCKED = "blocked"
    RESTRICTED = "restricted"
    PRIORITY = "priority"


@dataclass(frozen=True)
class Zone:
    name: str
    x: int
    y: int
    zone_type: ZoneType = ZoneType.NORMAL
    color: Optional[str] = None
    max_drones: int = 1
    is_start: bool = False
    is_end: bool = False


@dataclass(frozen=True)
class Connection:
    a: str
    b: str
    max_link_capacity: int = 1

    def other(self, z: str) -> str:
        if z == self.a:
            return self.b
        if z == self.b:
            return self.a
        raise ValueError("zone not in connection")

    def key(self) -> Tuple[str, str]:
        return tuple(sorted((self.a, self.b)))


@dataclass
class Graph:
    zones: Dict[str, Zone] = field(default_factory=dict)
    adj: Dict[str, List[Connection]] = field(default_factory=dict)
    start: str = ""
    end: str = ""

    def add_zone(self, z: Zone) -> None:
        if z.name in self.zones:
            raise ValueError(f"Duplicate zone: {z.name}")
        self.zones[z.name] = z
        self.adj[z.name] = []

    def add_connection(self, c: Connection) -> None:
        if c.a not in self.zones or c.b not in self.zones:
            raise ValueError(f"Unknown zone in connection: {c.a}-{c.b}")

        # prevent duplicates (a-b == b-a)
        for existing in self.adj[c.a]:
            if existing.key() == c.key():
                raise ValueError(f"Duplicate connection: {c.a}-{c.b}")

        self.adj[c.a].append(c)
        self.adj[c.b].append(c)