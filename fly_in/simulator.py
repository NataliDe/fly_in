from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

from .models import Drone, MapData, SimulationStats, TurnLog
from .pathfinding import build_reverse_distances, next_step_candidates


@dataclass
class MovingSprite:
    drone_id: int
    start: str
    end: str
    progress: float


class DroneSimulator:
    def __init__(self, map_data: MapData) -> None:
        self.map_data = map_data
        self.dist_to_goal = build_reverse_distances(map_data)
        self.turn = 0
        self.stats = SimulationStats()
        self.logs: List[TurnLog] = []
        self.drones: List[Drone] = [
            Drone(drone_id=index + 1, current_hub=map_data.start_name)
            for index in range(map_data.nb_drones)
        ]
        self._validate_solvable()

    def _validate_solvable(self) -> None:
        if self.dist_to_goal.get(self.map_data.start_name, 10 ** 12) >= 10 ** 12:
            raise ValueError("No valid path from start to end.")

    def delivered_count(self) -> int:
        return sum(1 for drone in self.drones if drone.finished)

    def active_count(self) -> int:
        return len(self.drones) - self.delivered_count()

    def is_finished(self) -> bool:
        return self.delivered_count() == len(self.drones)

    def hub_occupancy(self) -> Dict[str, int]:
        occupancy = {name: 0 for name in self.map_data.hubs}
        for drone in self.drones:
            if drone.finished:
                occupancy[self.map_data.end_name] += 1
            elif not drone.in_transit:
                occupancy[drone.current_hub] += 1
        return occupancy

    def moving_sprites(self) -> List[MovingSprite]:
        result: List[MovingSprite] = []
        for drone in self.drones:
            if drone.in_transit and drone.from_hub and drone.to_hub:
                total = self.map_data.hubs[drone.to_hub].travel_cost()
                completed = total - drone.remaining_turns
                progress = max(0.0, min(1.0, completed / total))
                result.append(
                    MovingSprite(
                        drone_id=drone.drone_id,
                        start=drone.from_hub,
                        end=drone.to_hub,
                        progress=progress,
                    )
                )
        return result

    def step(self) -> TurnLog:
        if self.is_finished():
            return TurnLog(turn_number=self.turn, moves=[])

        self.turn += 1
        log = TurnLog(turn_number=self.turn)
        occupancy = self.hub_occupancy()
        reserved_incoming: Dict[str, int] = {name: 0 for name in self.map_data.hubs}
        reserved_edges: Dict[Tuple[str, str], int] = {
            key: 0 for key in self.map_data.connections
        }

        # Finish drones already in transit if their timer ends now.
        for drone in self.drones:
            drone.just_started_transit = False

        for drone in sorted(self.drones, key=lambda d: d.drone_id):
            if not drone.in_transit:
                continue
            drone.remaining_turns -= 1
            if drone.remaining_turns == 0:
                assert drone.to_hub is not None
                destination = drone.to_hub
                drone.current_hub = destination
                drone.in_transit = False
                drone.from_hub = None
                drone.to_hub = None
                occupancy[destination] += 1
                log.moves.append(f"{drone.name()}-{destination}")
                if destination == self.map_data.end_name:
                    drone.finished = True
            else:
                assert drone.from_hub is not None and drone.to_hub is not None
                edge_key = tuple(sorted((drone.from_hub, drone.to_hub)))
                reserved_edges[edge_key] += 1
                log.moves.append(f"{drone.name()}-{drone.from_hub}-{drone.to_hub}")

        # Plan new moves.
        banned_nodes: Set[str] = set()
        for drone in sorted(self.drones, key=lambda d: d.drone_id):
            if drone.finished or drone.in_transit:
                continue
            current = drone.current_hub
            if current == self.map_data.end_name:
                drone.finished = True
                continue

            candidates = next_step_candidates(
                self.map_data,
                current,
                self.dist_to_goal,
                banned_nodes,
            )
            moved = False
            for nxt in candidates:
                dest_hub = self.map_data.hubs[nxt]
                edge = self.map_data.get_connection(current, nxt)
                edge_key = edge.key
                if reserved_edges[edge_key] >= edge.max_link_capacity:
                    continue
                future_occupancy = occupancy[nxt] + reserved_incoming[nxt]
                if nxt not in {self.map_data.start_name, self.map_data.end_name}:
                    if future_occupancy >= dest_hub.max_drones:
                        continue
                elif nxt == self.map_data.end_name:
                    pass
                travel_cost = dest_hub.travel_cost()
                if travel_cost == 10 ** 9:
                    continue
                occupancy[current] -= 1
                reserved_edges[edge_key] += 1
                if travel_cost == 1:
                    occupancy[nxt] += 1
                    drone.current_hub = nxt
                    log.moves.append(f"{drone.name()}-{nxt}")
                    if nxt == self.map_data.end_name:
                        drone.finished = True
                else:
                    reserved_incoming[nxt] += 1
                    drone.in_transit = True
                    drone.from_hub = current
                    drone.to_hub = nxt
                    drone.remaining_turns = travel_cost
                    drone.just_started_transit = True
                    log.moves.append(f"{drone.name()}-{current}-{nxt}")
                moved = True
                break
            if not moved:
                banned_nodes.add(current)

        self.logs.append(log)
        self.stats.total_turns = self.turn
        self.stats.delivered = self.delivered_count()
        return log
