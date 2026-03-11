from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Tuple

from .models import Connection, Hub, MapData, ZONE_TYPES


HUB_RE = re.compile(
    r"^(start_hub|end_hub|hub):\s+([^\s\-]+)\s+(-?\d+)\s+(-?\d+)\s*(\[(.*?)\])?$"
)
CONN_RE = re.compile(r"^connection:\s+([^\s\-]+)-([^\s\-]+)\s*(\[(.*?)\])?$")
META_ITEM_RE = re.compile(r"(\w+)=([^\s\]]+)")


class ParseError(ValueError):
    pass


def _parse_metadata(meta_text: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    if not meta_text:
        return result
    for key, value in META_ITEM_RE.findall(meta_text):
        result[key] = value
    cleaned = META_ITEM_RE.sub("", meta_text).strip()
    if cleaned:
        raise ParseError(f"invalid metadata content: {meta_text}")
    return result


def parse_map(path: str | Path) -> MapData:
    file_path = Path(path)
    lines = file_path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ParseError("empty file")

    nb_drones = None
    hubs: Dict[str, Hub] = {}
    connections: Dict[Tuple[str, str], Connection] = {}
    start_name = None
    end_name = None
    title = file_path.stem

    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            if line.startswith("#") and idx == 1:
                title = line.lstrip("# ").strip() or title
            continue

        if line.startswith("nb_drones:"):
            if nb_drones is not None:
                raise ParseError(f"line {idx}: nb_drones declared more than once")
            value = line.split(":", 1)[1].strip()
            if not value.isdigit() or int(value) <= 0:
                raise ParseError(f"line {idx}: nb_drones must be a positive integer")
            nb_drones = int(value)
            continue

        hub_match = HUB_RE.match(line)
        if hub_match:
            prefix, name, x_text, y_text, _, meta_text = hub_match.groups()
            if name in hubs:
                raise ParseError(f"line {idx}: duplicate hub name '{name}'")
            meta = _parse_metadata(meta_text or "")
            zone_type = meta.get("zone", "normal")
            if zone_type not in ZONE_TYPES:
                raise ParseError(f"line {idx}: invalid zone type '{zone_type}'")
            max_drones = meta.get("max_drones", "1")
            if not max_drones.isdigit() or int(max_drones) <= 0:
                raise ParseError(f"line {idx}: max_drones must be a positive integer")
            kind = "hub"
            if prefix == "start_hub":
                kind = "start"
            elif prefix == "end_hub":
                kind = "end"
            hub = Hub(
                name=name,
                x=int(x_text),
                y=int(y_text),
                kind=kind,
                color=meta.get("color", "none"),
                zone_type=zone_type,
                max_drones=int(max_drones),
            )
            hubs[name] = hub
            if kind == "start":
                if start_name is not None:
                    raise ParseError(f"line {idx}: multiple start_hub declarations")
                start_name = name
            if kind == "end":
                if end_name is not None:
                    raise ParseError(f"line {idx}: multiple end_hub declarations")
                end_name = name
            continue

        conn_match = CONN_RE.match(line)
        if conn_match:
            a, b, _, meta_text = conn_match.groups()
            if a not in hubs or b not in hubs:
                raise ParseError(
                    f"line {idx}: connection uses undefined hubs '{a}' and/or '{b}'"
                )
            key = tuple(sorted((a, b)))
            if key in connections:
                raise ParseError(f"line {idx}: duplicate connection '{a}-{b}'")
            meta = _parse_metadata(meta_text or "")
            cap = meta.get("max_link_capacity", "1")
            if not cap.isdigit() or int(cap) <= 0:
                raise ParseError(
                    f"line {idx}: max_link_capacity must be a positive integer"
                )
            connection = Connection(a=a, b=b, max_link_capacity=int(cap))
            connections[key] = connection
            hubs[a].neighbors.append(b)
            hubs[b].neighbors.append(a)
            continue

        raise ParseError(f"line {idx}: unsupported syntax -> {line}")

    if nb_drones is None:
        raise ParseError("missing nb_drones declaration")
    if start_name is None:
        raise ParseError("missing start_hub declaration")
    if end_name is None:
        raise ParseError("missing end_hub declaration")

    return MapData(
        nb_drones=nb_drones,
        hubs=hubs,
        connections=connections,
        start_name=start_name,
        end_name=end_name,
        title=title,
    )
