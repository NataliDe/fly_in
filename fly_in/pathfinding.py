from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from .models import MapData


@dataclass(frozen=True)
class MoveCandidate:
    next_hub: str
    score: float
    progress_gain: float
    flexibility: int


class Planner:
    """Reusable weighted path helper for the simulator."""

    def __init__(self, map_data: MapData) -> None:
        self.map_data = map_data
        self.base_distance = self._build_reverse_distances()

    def _build_reverse_distances(self) -> Dict[str, float]:
        dist: Dict[str, float] = {name: math.inf for name in self.map_data.hubs}
        goal = self.map_data.end_name
        dist[goal] = 0.0
        heap: List[Tuple[float, str]] = [(0.0, goal)]

        while heap:
            curr_dist, curr_name = heapq.heappop(heap)
            if curr_dist > dist[curr_name]:
                continue

            curr_hub = self.map_data.hubs[curr_name]
            for neighbor_name in curr_hub.neighbors:
                neighbor_hub = self.map_data.hubs[neighbor_name]
                if neighbor_hub.zone_type == "blocked":
                    continue
                move_cost = float(curr_hub.travel_cost())
                if curr_hub.zone_type == "priority":
                    move_cost -= 0.20
                new_dist = curr_dist + move_cost
                if new_dist < dist[neighbor_name]:
                    dist[neighbor_name] = new_dist
                    heapq.heappush(heap, (new_dist, neighbor_name))
        return dist

    def _forward_flexibility(self, current: str, neighbor_name: str) -> int:
        flex = 0
        for next_name in self.map_data.hubs[neighbor_name].neighbors:
            if next_name == current:
                continue
            next_hub = self.map_data.hubs[next_name]
            if next_hub.zone_type == "blocked":
                continue
            if self.base_distance.get(next_name, math.inf) == math.inf:
                continue
            flex += 1
        return flex

    def ranked_candidates(
        self,
        current: str,
        blocked_hubs: Set[str],
        blocked_links: Set[Tuple[str, str]],
        incoming: Dict[str, int],
        occupancy: Dict[str, int],
        link_load: Dict[Tuple[str, str], int],
        last_hub: Optional[str],
        reserved_targets: Optional[Dict[str, int]] = None,
        reserved_links: Optional[Dict[Tuple[str, str], int]] = None,
    ) -> List[MoveCandidate]:
        candidates: List[MoveCandidate] = []
        current_dist = self.base_distance.get(current, math.inf)
        reserved_targets = reserved_targets or {}
        reserved_links = reserved_links or {}

        for neighbor_name in self.map_data.hubs[current].neighbors:
            neighbor = self.map_data.hubs[neighbor_name]
            if neighbor.zone_type == "blocked":
                continue
            if neighbor_name in blocked_hubs and neighbor.kind != "end":
                continue

            conn = self.map_data.get_connection(current, neighbor_name)
            key = conn.key
            if key in blocked_links:
                continue
            if self.base_distance[neighbor_name] == math.inf:
                continue

            future_occ = occupancy[neighbor_name] + incoming[neighbor_name] + reserved_targets.get(neighbor_name, 0)
            cap = max(1, neighbor.effective_capacity())
            future_link = link_load[key] + reserved_links.get(key, 0)

            score = float(neighbor.travel_cost()) + self.base_distance[neighbor_name]
            if neighbor.zone_type == "priority":
                score -= 0.35

            score += 0.55 * (future_occ / cap)
            score += 0.70 * (future_link / max(1, conn.max_link_capacity))

            if last_hub is not None and neighbor_name == last_hub:
                score += 1.10

            flexibility = self._forward_flexibility(current, neighbor_name)
            if flexibility == 0 and neighbor.kind != "end":
                score += 0.35
            else:
                score -= 0.06 * flexibility

            progress_gain = current_dist - self.base_distance[neighbor_name]
            if progress_gain <= 0:
                score += 0.85
            else:
                score -= min(0.30, 0.08 * progress_gain)

            candidates.append(
                MoveCandidate(
                    next_hub=neighbor_name,
                    score=score,
                    progress_gain=progress_gain,
                    flexibility=flexibility,
                )
            )

        candidates.sort(
            key=lambda item: (
                item.score,
                -item.progress_gain,
                -item.flexibility,
                item.next_hub,
            )
        )
        return candidates

    def choose_next_hop(
        self,
        current: str,
        blocked_hubs: Set[str],
        blocked_links: Set[Tuple[str, str]],
        incoming: Dict[str, int],
        occupancy: Dict[str, int],
        link_load: Dict[Tuple[str, str], int],
        last_hub: Optional[str],
        reserved_targets: Optional[Dict[str, int]] = None,
        reserved_links: Optional[Dict[Tuple[str, str], int]] = None,
        preferred_neighbors: Optional[List[str]] = None,
    ) -> Optional[str]:
        candidates = self.ranked_candidates(
            current=current,
            blocked_hubs=blocked_hubs,
            blocked_links=blocked_links,
            incoming=incoming,
            occupancy=occupancy,
            link_load=link_load,
            last_hub=last_hub,
            reserved_targets=reserved_targets,
            reserved_links=reserved_links,
        )
        if not candidates:
            return None

        if preferred_neighbors:
            candidate_by_name = {item.next_hub: item for item in candidates}
            best_score = candidates[0].score
            for name in preferred_neighbors:
                candidate = candidate_by_name.get(name)
                if candidate is None:
                    continue
                if candidate.score <= best_score + 0.20:
                    return name

        return candidates[0].next_hub
