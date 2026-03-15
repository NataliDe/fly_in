from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Tuple

from .models import Connection, Hub, MapData, ZONE_TYPES


class ParseError(ValueError):
    """Raised when the input map is invalid."""


def _remove_comment(line: str) -> str:
    if "#" in line:
        return line.split("#", 1)[0].rstrip()
    return line.rstrip()


def _split_main_and_meta(line: str) -> tuple[str, str]:
    if "[" in line:
        left, right = line.split("[", 1)
        return left.strip(), right.strip()
    return line.strip(), ""


def _parse_metadata(meta_text: str, line_number: int) -> Dict[str, str]:
    result: Dict[str, str] = {}
    if not meta_text:
        return result

    meta_text = meta_text.strip()
    if not meta_text.endswith("]"):
        raise ParseError(f"line {line_number}: invalid metadata block")

    inner = meta_text[:-1].strip()
    if not inner:
        return result

    for item in inner.split():
        if "=" not in item:
            raise ParseError(f"line {line_number}: invalid metadata entry '{item}'")
        key, value = item.split("=", 1)
        if not key or not value:
            raise ParseError(f"line {line_number}: invalid metadata entry '{item}'")
        result[key.strip()] = value.strip()
    return result


def _parse_hub_line(line: str, line_number: int) -> tuple[str, str, str, str, Dict[str, str]]:
    main_part, meta_text = _split_main_and_meta(line)
    prefix, sep, rest = main_part.partition(":")
    if sep == "":
        raise ParseError(f"line {line_number}: unsupported syntax")

    prefix = prefix.strip()
    rest = rest.strip()
    if prefix not in {"start_hub", "end_hub", "hub"}:
        raise ParseError(f"line {line_number}: unsupported syntax")

    parts = rest.split()
    if len(parts) != 3:
        raise ParseError(f"line {line_number}: invalid hub definition")

    name, x_text, y_text = parts
    if "-" in name or " " in name:
        raise ParseError(f"line {line_number}: invalid hub name '{name}'")

    return prefix, name, x_text, y_text, _parse_metadata(meta_text, line_number)


def _parse_connection_line(line: str, line_number: int) -> tuple[str, str, Dict[str, str]]:
    main_part, meta_text = _split_main_and_meta(line)
    prefix, sep, rest = main_part.partition(":")
    if sep == "" or prefix.strip() != "connection":
        raise ParseError(f"line {line_number}: unsupported syntax")

    parts = rest.strip().split()
    if len(parts) != 1 or "-" not in parts[0]:
        raise ParseError(f"line {line_number}: invalid connection definition")

    a, b = parts[0].split("-", 1)
    a = a.strip()
    b = b.strip()
    if not a or not b or "-" in a or "-" in b:
        raise ParseError(f"line {line_number}: invalid connection definition")

    return a, b, _parse_metadata(meta_text, line_number)


def parse_map(path: str | Path) -> MapData:
    """Parse a map file into strongly typed project models."""
    file_path = Path(path)
    raw_lines = file_path.read_text(encoding="utf-8").splitlines()
    if not raw_lines:
        raise ParseError("empty file")

    nb_drones: Optional[int] = None
    hubs: Dict[str, Hub] = {}
    connections: Dict[Tuple[str, str], Connection] = {}
    start_name: Optional[str] = None
    end_name: Optional[str] = None
    title = file_path.stem

    for index, raw_line in enumerate(raw_lines, start=1):
        stripped = raw_line.strip()
        if index == 1 and stripped.startswith("#"):
            title = stripped.lstrip("# ").strip() or title

        line = _remove_comment(raw_line).strip()
        if not line:
            continue

        if line.startswith("nb_drones:"):
            if nb_drones is not None:
                raise ParseError(f"line {index}: nb_drones declared more than once")
            value = line.split(":", 1)[1].strip()
            if not value.isdigit() or int(value) <= 0:
                raise ParseError(f"line {index}: nb_drones must be a positive integer")
            nb_drones = int(value)
            continue

        if line.startswith(("start_hub:", "end_hub:", "hub:")):
            prefix, name, x_text, y_text, meta = _parse_hub_line(line, index)
            if name in hubs:
                raise ParseError(f"line {index}: duplicate hub name '{name}'")

            try:
                x = int(x_text)
                y = int(y_text)
            except ValueError as exc:
                raise ParseError(f"line {index}: coordinates must be integers") from exc

            zone_type = meta.get("zone", "normal")
            if zone_type not in ZONE_TYPES:
                raise ParseError(f"line {index}: invalid zone type '{zone_type}'")

            max_drones_text = meta.get("max_drones", "1")
            if not max_drones_text.isdigit() or int(max_drones_text) <= 0:
                raise ParseError(f"line {index}: max_drones must be a positive integer")

            kind = "hub"
            if prefix == "start_hub":
                kind = "start"
            elif prefix == "end_hub":
                kind = "end"

            hubs[name] = Hub(
                name=name,
                x=x,
                y=y,
                kind=kind,
                color=meta.get("color", "none"),
                zone_type=zone_type,
                max_drones=int(max_drones_text),
            )

            if kind == "start":
                if start_name is not None:
                    raise ParseError(f"line {index}: multiple start hubs declared")
                start_name = name
            if kind == "end":
                if end_name is not None:
                    raise ParseError(f"line {index}: multiple end hubs declared")
                end_name = name
            continue

        if line.startswith("connection:"):
            a, b, meta = _parse_connection_line(line, index)
            if a not in hubs or b not in hubs:
                raise ParseError(f"line {index}: connection uses undefined hubs")

            key = tuple(sorted((a, b)))
            if key in connections:
                raise ParseError(f"line {index}: duplicate connection '{a}-{b}'")

            max_link_text = meta.get("max_link_capacity", "1")
            if not max_link_text.isdigit() or int(max_link_text) <= 0:
                raise ParseError(
                    f"line {index}: max_link_capacity must be a positive integer"
                )

            connection = Connection(a=a, b=b, max_link_capacity=int(max_link_text))
            connections[key] = connection
            hubs[a].neighbors.append(b)
            hubs[b].neighbors.append(a)
            continue

        raise ParseError(f"line {index}: unsupported syntax")

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
