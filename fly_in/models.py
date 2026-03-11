from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


ZONE_TYPES = {"normal", "blocked", "restricted", "priority"}


@dataclass
class Hub:
    name: str
    x: int
    y: int
    kind: str  # start, hub, end
    color: str = "none"
    zone_type: str = "normal"
    max_drones: int = 1
    neighbors: List[str] = field(default_factory=list)

    def travel_cost(self) -> int:
        if self.zone_type == "restricted":
            return 2
        if self.zone_type in {"normal", "priority"}:
            return 1
        return 10 ** 9


@dataclass
class Connection:
    a: str
    b: str
    max_link_capacity: int = 1

    @property
    def key(self) -> Tuple[str, str]:
        return tuple(sorted((self.a, self.b)))

    def label(self) -> str:
        return f"{self.a}-{self.b}"


@dataclass
class Drone:
    drone_id: int
    current_hub: str
    finished: bool = False
    in_transit: bool = False
    from_hub: Optional[str] = None
    to_hub: Optional[str] = None
    remaining_turns: int = 0
    just_started_transit: bool = False

    def name(self) -> str:
        return f"D{self.drone_id}"


@dataclass
class MapData:
    nb_drones: int
    hubs: Dict[str, Hub]
    connections: Dict[Tuple[str, str], Connection]
    start_name: str
    end_name: str
    title: str = "Unnamed map"

    def get_connection(self, a: str, b: str) -> Connection:
        return self.connections[tuple(sorted((a, b)))]


@dataclass
class TurnLog:
    turn_number: int
    moves: List[str] = field(default_factory=list)


@dataclass
class SimulationStats:
    total_turns: int = 0
    delivered: int = 0
