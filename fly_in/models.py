from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

ZONE_TYPES = {"normal", "restricted", "priority", "blocked"}


@dataclass
class Hub:
    """A node in the drone network."""

    name: str
    x: int
    y: int
    kind: str
    color: str = "none"
    zone_type: str = "normal"
    max_drones: int = 1
    neighbors: List[str] = field(default_factory=list)

    def travel_cost(self) -> int:
        """Return movement cost when entering this hub."""
        if self.zone_type == "blocked":
            return 10**9
        if self.zone_type == "restricted":
            return 2
        return 1

    def effective_capacity(self) -> int:
        """Return runtime capacity with start/end exceptions."""
        if self.kind in {"start", "end"}:
            return 10**9
        return self.max_drones


@dataclass(frozen=True)
class Connection:
    """Bidirectional edge between hubs."""

    a: str
    b: str
    max_link_capacity: int = 1

    @property
    def key(self) -> Tuple[str, str]:
        return tuple(sorted((self.a, self.b)))

    def display_name(self) -> str:
        left, right = self.key
        return f"{left}-{right}"


@dataclass
class MapData:
    """Parsed map definition."""

    nb_drones: int
    hubs: Dict[str, Hub]
    connections: Dict[Tuple[str, str], Connection]
    start_name: str
    end_name: str
    title: str = "Unnamed map"

    def get_connection(self, a: str, b: str) -> Connection:
        return self.connections[tuple(sorted((a, b)))]


@dataclass
class Drone:
    """Runtime state of a drone."""

    drone_id: int
    current_hub: str
    finished: bool = False
    from_hub: Optional[str] = None
    to_hub: Optional[str] = None
    remaining_turns: int = 0
    total_move_turns: int = 0
    progress: float = 0.0
    move_duration: float = 0.35
    last_hub: Optional[str] = None

    def name(self) -> str:
        return f"D{self.drone_id}"

    @property
    def is_moving(self) -> bool:
        return self.from_hub is not None and self.to_hub is not None

    def active_connection_key(self) -> Optional[Tuple[str, str]]:
        if self.from_hub is None or self.to_hub is None:
            return None
        return tuple(sorted((self.from_hub, self.to_hub)))
