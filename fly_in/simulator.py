from typing import Dict, List, Optional, Set, Tuple

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
        """Reset the simulation to its initial
        state and recreate all drones."""
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

    def _set_turn_log(
        self,
        log_order: List[int],
        log_tokens: Dict[int, str],
        drone: Drone,
        token: str,
    ) -> None:
        """Store the latest token for a drone
        while keeping turn order stable."""
        if drone.drone_id not in log_tokens:
            log_order.append(drone.drone_id)
        log_tokens[drone.drone_id] = token

    def _finalize_turn_logs(
        self,
        log_order: List[int],
        log_tokens: Dict[int, str],
    ) -> List[str]:
        """Build final ordered logs for the current turn."""
        return [log_tokens[drone_id] for drone_id in log_order]

    def _start_move(self, drone: Drone, next_hub_name: str) -> str:
        """
        Start a move for one drone and return the output token for this turn.

        For normal or priority hubs, print destination zone.
        For restricted hubs, print the connection while in flight.
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
            return f"{drone.name()}-{next_hub_name}"
        return f"{drone.name()}-{current}-{next_hub_name}"

    def _preferred_neighbors(
        self,
        current: str,
        candidates: List[str],
    ) -> List[str]:
        """Rotate equally good candidates to
        spread traffic more fairly over time."""
        if len(candidates) <= 1:
            return candidates
        cursor = self.dispatch_memory.get(current, 0)
        return candidates[cursor:] + candidates[:cursor]

    def _remember_dispatch(
        self,
        current: str,
        chosen: str,
        candidates: List[str],
    ) -> None:
        """Remember the last chosen direction
        so future drones can be balanced better."""
        if len(candidates) <= 1:
            return
        if chosen not in candidates:
            return
        index = candidates.index(chosen)
        self.dispatch_memory[current] = (index + 1) % len(candidates)

    def _finish_in_progress_moves(
        self,
        log_order: List[int],
        log_tokens: Dict[int, str],
    ) -> None:
        """Advance all moving drones by one turn and record arrivals."""
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
                move_turns = drone.total_move_turns

                drone.current_hub = destination
                drone.last_hub = origin
                drone.from_hub = None
                drone.to_hub = None
                drone.total_move_turns = 0
                drone.remaining_turns = 0
                drone.progress = 1.0

                # Log arrival only for restricted (multi-turn) moves.
                if move_turns > 1:
                    self._set_turn_log(
                        log_order,
                        log_tokens,
                        drone,
                        f"{drone.name()}-{drone.current_hub}",
                    )

                if (
                    drone.current_hub == self.map_data.end_name
                    and not drone.finished
                ):
                    drone.finished = True
                    self.finished_count += 1

    def _build_turn_state(
        self,
    ) -> tuple[
        Dict[str, int],
        Dict[str, int],
        Dict[Tuple[str, str], int],
        Dict[str, int],
        Dict[Tuple[str, str], int],
    ]:
        """Build all mutable state dictionaries needed for one turn."""
        occupancy = self._hub_occupancy()
        incoming = self._incoming_counts()
        link_load = self._active_link_load()
        reserved_targets = {name: 0 for name in self.map_data.hubs}
        reserved_links = {key: 0 for key in self.map_data.connections}
        return occupancy, incoming, link_load, reserved_targets, reserved_links

    def _get_idle_drones(self) -> List[Drone]:
        """Return idle drones sorted by urgency and id."""
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
        return idle_drones

    def _mark_goal_drone_finished(self, drone: Drone) -> bool:
        """Mark an idle drone as finished if it is already on the goal hub."""
        if drone.current_hub == self.map_data.end_name:
            if not drone.finished:
                drone.finished = True
                self.finished_count += 1
            return True
        return False

    def _compute_blocked_hubs(
        self,
        occupancy: Dict[str, int],
        incoming: Dict[str, int],
        reserved_targets: Dict[str, int],
    ) -> Set[str]:
        """Compute hubs that cannot accept more drones this turn."""
        blocked_hubs: Set[str] = set()

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

        return blocked_hubs

    def _compute_blocked_links(
        self,
        link_load: Dict[Tuple[str, str], int],
        reserved_links: Dict[Tuple[str, str], int],
    ) -> Set[Tuple[str, str]]:
        """Compute links that cannot accept more drones this turn."""
        blocked_links: Set[Tuple[str, str]] = set()

        for key, conn in self.map_data.connections.items():
            used = link_load[key] + reserved_links[key]
            if used >= conn.max_link_capacity:
                blocked_links.add(key)

        return blocked_links

    def _pick_next_hop(
        self,
        drone: Drone,
        occupancy: Dict[str, int],
        incoming: Dict[str, int],
        link_load: Dict[Tuple[str, str], int],
        reserved_targets: Dict[str, int],
        reserved_links: Dict[Tuple[str, str], int],
    ) -> tuple[Optional[str], List[str]]:
        """Pick the next hop for one drone and
        return chosen hub plus close candidates."""
        blocked_hubs = self._compute_blocked_hubs(
            occupancy,
            incoming,
            reserved_targets,
        )
        blocked_links = self._compute_blocked_links(
            link_load,
            reserved_links,
        )

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
            return None, []

        candidate_names = [
            item.next_hub
            for item in ranked
            if item.score <= ranked[0].score + 0.20
        ]

        preferred_neighbors = self._preferred_neighbors(
            drone.current_hub,
            candidate_names,
        )

        ranked_by_name = {item.next_hub: item for item in ranked}
        best_score = ranked[0].score

        for name in preferred_neighbors:
            candidate = ranked_by_name.get(name)
            if candidate is None:
                continue
            if candidate.score <= best_score + 0.20:
                return name, candidate_names

        return ranked[0].next_hub, candidate_names

    def _move_is_allowed(
        self,
        drone: Drone,
        next_hop: str,
        occupancy: Dict[str, int],
        incoming: Dict[str, int],
        link_load: Dict[Tuple[str, str], int],
        reserved_targets: Dict[str, int],
        reserved_links: Dict[Tuple[str, str], int],
    ) -> bool:
        """Check final hub and link capacity
        constraints before starting a move."""
        target_hub = self.map_data.hubs[next_hop]
        conn = self.map_data.get_connection(drone.current_hub, next_hop)

        future_occ = (
            occupancy[next_hop]
            + incoming[next_hop]
            + reserved_targets[next_hop]
        )
        if (
            target_hub.kind != "end"
            and future_occ >= target_hub.effective_capacity()
        ):
            return False

        future_link = link_load[conn.key] + reserved_links[conn.key]
        if future_link >= conn.max_link_capacity:
            return False

        return True

    def _reserve_move_capacity(
        self,
        drone: Drone,
        next_hop: str,
        occupancy: Dict[str, int],
        reserved_targets: Dict[str, int],
        reserved_links: Dict[Tuple[str, str], int],
    ) -> None:
        """Reserve hub and link capacity for a chosen move."""
        target_hub = self.map_data.hubs[next_hop]
        conn = self.map_data.get_connection(drone.current_hub, next_hop)

        occupancy[drone.current_hub] -= 1
        reserved_links[conn.key] += 1

        if target_hub.travel_cost() == 1:
            occupancy[next_hop] += 1
        else:
            reserved_targets[next_hop] += 1

    def _process_idle_drone(
        self,
        drone: Drone,
        log_order: List[int],
        log_tokens: Dict[int, str],
        occupancy: Dict[str, int],
        incoming: Dict[str, int],
        link_load: Dict[Tuple[str, str], int],
        reserved_targets: Dict[str, int],
        reserved_links: Dict[Tuple[str, str], int],
    ) -> None:
        """Try to start a move for one idle drone."""
        if self._mark_goal_drone_finished(drone):
            return

        next_hop, candidate_names = self._pick_next_hop(
            drone,
            occupancy,
            incoming,
            link_load,
            reserved_targets,
            reserved_links,
        )
        if next_hop is None:
            return

        if not self._move_is_allowed(
            drone,
            next_hop,
            occupancy,
            incoming,
            link_load,
            reserved_targets,
            reserved_links,
        ):
            return

        self._reserve_move_capacity(
            drone,
            next_hop,
            occupancy,
            reserved_targets,
            reserved_links,
        )

        self._remember_dispatch(
            drone.current_hub,
            next_hop,
            candidate_names,
        )

        move_text = self._start_move(drone, next_hop)
        self._set_turn_log(log_order, log_tokens, drone, move_text)

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

        log_order: List[int] = []
        log_tokens: Dict[int, str] = {}

        self._finish_in_progress_moves(log_order, log_tokens)

        if self.is_finished():
            self.move_logs = self._finalize_turn_logs(log_order, log_tokens)
            if self.move_logs:
                self.turn += 1
            return

        occupancy, incoming, link_load, reserved_targets, reserved_links = (
            self._build_turn_state()
        )

        for drone in self._get_idle_drones():
            self._process_idle_drone(
                drone,
                log_order,
                log_tokens,
                occupancy,
                incoming,
                link_load,
                reserved_targets,
                reserved_links,
            )

        self.move_logs = self._finalize_turn_logs(log_order, log_tokens)
        if self.move_logs:
            self.turn += 1

    def update_animation(self, dt: float) -> None:
        """Update smooth movement progress for
        all drones based on frame time."""
        for drone in self.drones:
            if drone.is_moving:
                drone.progress += dt / drone.move_duration
                if drone.progress > 1.0:
                    drone.progress = 1.0
            else:
                drone.progress = 0.0
