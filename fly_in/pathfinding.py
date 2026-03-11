from __future__ import annotations

import heapq
from typing import Dict, List, Optional, Set, Tuple

from .models import Hub, MapData


INF = 10 ** 12


def build_reverse_distances(map_data: MapData) -> Dict[str, int]:
    goal = map_data.end_name
    distances: Dict[str, int] = {name: INF for name in map_data.hubs}
    distances[goal] = 0
    heap: List[Tuple[int, str]] = [(0, goal)]

    while heap:
        dist, current = heapq.heappop(heap)
        if dist != distances[current]:
            continue
        for neighbor in map_data.hubs[current].neighbors:
            neighbor_hub = map_data.hubs[neighbor]
            if neighbor_hub.zone_type == "blocked":
                continue
            cost = map_data.hubs[current].travel_cost()
            cand = dist + cost
            if cand < distances[neighbor]:
                distances[neighbor] = cand
                heapq.heappush(heap, (cand, neighbor))
    return distances


def next_step_candidates(
    map_data: MapData,
    current: str,
    dist_to_goal: Dict[str, int],
    banned_nodes: Set[str],
) -> List[str]:
    result: List[Tuple[int, int, str]] = []
    for neighbor in map_data.hubs[current].neighbors:
        hub = map_data.hubs[neighbor]
        if hub.zone_type == "blocked" or neighbor in banned_nodes:
            continue
        if dist_to_goal.get(neighbor, INF) >= INF:
            continue
        priority_bonus = 0 if hub.zone_type == "priority" else 1
        result.append((dist_to_goal[neighbor], priority_bonus, neighbor))
    result.sort()
    return [name for _, _, name in result]


def full_path_greedy(
    map_data: MapData,
    start: str,
    dist_to_goal: Dict[str, int],
) -> List[str]:
    path = [start]
    seen = {start}
    current = start
    while current != map_data.end_name:
        candidates = next_step_candidates(map_data, current, dist_to_goal, seen)
        if not candidates:
            break
        current = candidates[0]
        path.append(current)
        seen.add(current)
    return path
