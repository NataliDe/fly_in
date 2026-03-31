from typing import Dict, List, Tuple

from .models import Drone, MapData
from .pathfinding import Planner

MOVE_TIME_PER_TURN = 0.45


class Simulator:
    """Discrete turn simulator with capacity-aware scheduling."""

    def __init__(self, map_data: MapData) -> None:
        """Initialize the simulator state and create the path planner."""
        self.map_data = map_data
        self.planner = Planner(map_data)
        self.turn = 0
        self.finished_count = 0
        self.move_logs: List[str] = []
        self.drones: List[Drone] = []
        self.dispatch_memory: Dict[str, int] = {}
        self.reset()

    def reset(self) -> None:
        """Reset the simulation to its initial state and recreate all drones."""
        self.turn = 0
        self.finished_count = 0
        self.move_logs = []
        self.dispatch_memory = {}
        self.drones = [
            Drone(drone_id=index + 1, current_hub=self.map_data.start_name)
            for index in range(self.map_data.nb_drones)
        ]

    def is_finished(self) -> bool:
        """Return True when all drones have reached the end hub."""
        return self.finished_count == len(self.drones)

    def _hub_occupancy(self) -> Dict[str, int]:
        """Count how many drones are currently standing in each hub."""
        occupancy = {name: 0 for name in self.map_data.hubs}
        for drone in self.drones:
            if drone.finished or not drone.is_moving:
                occupancy[drone.current_hub] += 1
        return occupancy

    def _incoming_counts(self) -> Dict[str, int]:
        """Count how many drones are currently moving toward each hub."""
        counts = {name: 0 for name in self.map_data.hubs}
        for drone in self.drones:
            if drone.is_moving and drone.to_hub is not None:
                counts[drone.to_hub] += 1
        return counts

    def _active_link_load(self) -> Dict[Tuple[str, str], int]:
        """Count how many drones are currently occupying each connection."""
        load = {key: 0 for key in self.map_data.connections}
        for drone in self.drones:
            key = drone.active_connection_key()
            if key is not None:
                load[key] += 1
        return load

    def capacity_snapshot(self) -> tuple[Dict[str, int], Dict[Tuple[str, str], int]]:
        """Return current hub occupancy and active link usage for debugging or display."""
        return self._hub_occupancy(), self._active_link_load()

    def _connection_log_text(self, from_hub: str, to_hub: str) -> str:
        """Build the text label used when logging movement on a connection."""
        return f"{from_hub}-{to_hub}"

    def _start_move(self, drone: Drone, next_hub_name: str) -> str:
        """
        Start a move for one drone and return the output token for this turn.

        For normal or priority hubs, the drone arrives immediately and the
        output is D<ID>-<hub>.

        For restricted hubs, the drone spends the first turn on the connection
        and the output is D<ID>-<from>-<to>. The arrival is logged later.
        """
        current = drone.current_hub
        target = self.map_data.hubs[next_hub_name]
        travel_cost = target.travel_cost()

        drone.from_hub = current
        drone.to_hub = next_hub_name
        drone.remaining_turns = travel_cost
        drone.total_move_turns = travel_cost
        drone.progress = 0.0
        drone.move_duration = MOVE_TIME_PER_TURN * drone.total_move_turns

        if travel_cost == 1:
            drone.last_hub = current
            drone.current_hub = next_hub_name
            drone.from_hub = None
            drone.to_hub = None
            drone.remaining_turns = 0
            drone.total_move_turns = 0
            drone.progress = 0.0

            if drone.current_hub == self.map_data.end_name and not drone.finished:
                drone.finished = True
                self.finished_count += 1

            return f"{drone.name()}-{next_hub_name}"

        return f"{drone.name()}-{self._connection_log_text(current, next_hub_name)}"

    def _preferred_neighbors(self, current: str, candidates: List[str]) -> List[str]:
        """Rotate equally good candidates to spread traffic more fairly over time."""
        if len(candidates) <= 1:
            return candidates
        cursor = self.dispatch_memory.get(current, 0)
        return candidates[cursor:] + candidates[:cursor]

    def _remember_dispatch(self, current: str, chosen: str, candidates: List[str]) -> None:
        """Remember the last chosen direction so future drones can be balanced better."""
        if len(candidates) <= 1:
            return
        if chosen not in candidates:
            return
        index = candidates.index(chosen)
        self.dispatch_memory[current] = (index + 1) % len(candidates)

    def _finish_in_progress_moves(self, turn_moves: List[str]) -> None:
        """Advance all moving drones by one turn and log arrivals that finish now."""
        for drone in self.drones:
            if not drone.is_moving:
                continue

            drone.remaining_turns -= 1

            if (
                drone.remaining_turns <= 0
                and drone.to_hub is not None
                and drone.from_hub is not None
            ):
                origin = drone.from_hub
                destination = drone.to_hub

                drone.current_hub = destination
                drone.last_hub = origin
                drone.from_hub = None
                drone.to_hub = None
                drone.total_move_turns = 0
                drone.remaining_turns = 0
                drone.progress = 1.0

                if drone.current_hub == self.map_data.end_name and not drone.finished:
                    drone.finished = True
                    self.finished_count += 1

                turn_moves.append(f"{drone.name()}-{drone.current_hub}")

    def step(self) -> None:
        """
        Execute one simulation turn.

        This method first completes drones already in transit, then checks all
        idle drones, chooses valid next moves for them, enforces hub and link
        capacities, and stores the output tokens for the current turn.
        """
        if self.is_finished():
            self.move_logs = []
            return

        self.turn += 1
        turn_moves: List[str] = []

        self._finish_in_progress_moves(turn_moves)
        # ті, хто не долетів спочатку прибувають

        if self.is_finished():
            self.move_logs = turn_moves
            return

        occupancy = self._hub_occupancy()
        incoming = self._incoming_counts()
        link_load = self._active_link_load()

        reserved_targets = {name: 0 for name in self.map_data.hubs}
        reserved_links = {key: 0 for key in self.map_data.connections}

        idle_drones = [
            drone for drone in self.drones
            if not drone.finished and not drone.is_moving
        ]
        idle_drones.sort(
            key=lambda drone: (
                self.planner.base_distance.get(drone.current_hub, 10**9),
                drone.drone_id,
            )
        )

        for drone in idle_drones:
            if drone.current_hub == self.map_data.end_name:
                if not drone.finished:
                    drone.finished = True
                    self.finished_count += 1
                continue

            blocked_hubs = set()
            for hub_name, hub in self.map_data.hubs.items():
                if hub.kind == "end":
                    continue

                used = (
                    occupancy[hub_name]
                    + incoming[hub_name]
                    + reserved_targets[hub_name]
                )
                if used >= hub.effective_capacity():
                    blocked_hubs.add(hub_name)

            blocked_links = set()
            for key, conn in self.map_data.connections.items():
                used = link_load[key] + reserved_links[key]
                if used >= conn.max_link_capacity:
                    blocked_links.add(key)

            ranked = self.planner.ranked_candidates(
                current=drone.current_hub,
                blocked_hubs=blocked_hubs,
                blocked_links=blocked_links,
                incoming=incoming,
                occupancy=occupancy,
                link_load=link_load,
                last_hub=drone.last_hub,
                reserved_targets=reserved_targets,
                reserved_links=reserved_links,
            )
            if not ranked:
                continue

            candidate_names = [
                item.next_hub
                for item in ranked
                if item.score <= ranked[0].score + 0.20
            ]

            preferred_neighbors = self._preferred_neighbors(
                drone.current_hub,
                candidate_names,
            )

            next_hop = self.planner.choose_next_hop(
                current=drone.current_hub,
                blocked_hubs=blocked_hubs,
                blocked_links=blocked_links,
                incoming=incoming,
                occupancy=occupancy,
                link_load=link_load,
                last_hub=drone.last_hub,
                reserved_targets=reserved_targets,
                reserved_links=reserved_links,
                preferred_neighbors=preferred_neighbors,
            )
            if next_hop is None:
                continue

            target_hub = self.map_data.hubs[next_hop]
            conn = self.map_data.get_connection(drone.current_hub, next_hop)

            future_occ = (
                occupancy[next_hop]
                + incoming[next_hop]
                + reserved_targets[next_hop]
            )
            if target_hub.kind != "end" and future_occ >= target_hub.effective_capacity():
                continue

            future_link = link_load[conn.key] + reserved_links[conn.key]
            if future_link >= conn.max_link_capacity:
                continue

            occupancy[drone.current_hub] -= 1
            reserved_links[conn.key] += 1

            if target_hub.travel_cost() == 1:
                occupancy[next_hop] += 1
            else:
                reserved_targets[next_hop] += 1

            self._remember_dispatch(
                drone.current_hub,
                next_hop,
                candidate_names,
            )

            move_text = self._start_move(drone, next_hop)
            if move_text:
                turn_moves.append(move_text)

        self.move_logs = turn_moves

    def update_animation(self, dt: float) -> None:
        """Update smooth movement progress for all drones based on frame time."""
        for drone in self.drones:
            if drone.is_moving:
                drone.progress += dt / drone.move_duration
                if drone.progress > 1.0:
                    drone.progress = 1.0
            else:
                drone.progress = 0.0