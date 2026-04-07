from pathlib import Path
from typing import Dict, Optional, Tuple

from .models import Connection, Hub, MapData, ZONE_TYPES


class ParseError(ValueError):
    """Raised when a map file contains invalid syntax or data."""


def _remove_comment(line: str) -> str:
    """Remove the comment part of a line and keep trailing content clean."""
    if "#" in line:
        return line.split("#", 1)[0].rstrip()
    return line.rstrip()


def _split_main_and_meta(line: str) -> tuple[str, str]:
    """Split a line into its main part and optional metadata block."""
    if "[" in line:
        left, right = line.split("[", 1)
        return left.strip(), right.strip()
    return line.strip(), ""


def _parse_metadata(meta_text: str, line_number: int) -> Dict[str, str]:
    """Parse a metadata block into a key-value dictionary."""
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
            raise ParseError(
                f"line {line_number}: invalid metadata entry '{item}'"
            )
        key, value = item.split("=", 1)
        if not key or not value:
            raise ParseError(
                f"line {line_number}: invalid metadata entry '{item}'"
            )
        result[key.strip()] = value.strip()
    return result


def _parse_hub_line(
    line: str,
    line_number: int,
) -> tuple[str, str, str, str, Dict[str, str]]:
    """Parse a hub definition line and return its raw components."""
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

    return (prefix,
            name, x_text, y_text, _parse_metadata(meta_text, line_number))


def _parse_connection_line(
    line: str,
    line_number: int,
) -> tuple[str, str, Dict[str, str]]:
    """Parse a connection definition
        line and return its endpoints and metadata."""
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


def _parse_nb_drones(
    line: str,
    line_number: int,
    current_value: Optional[int],
) -> int:
    """Parse the drone count line and return the validated value."""
    if current_value is not None:
        raise ParseError(f"line {line_number}: "
                         f"nb_drones declared more than once")

    value = line.split(":", 1)[1].strip()
    if not value.isdigit() or int(value) <= 0:
        raise ParseError(f"line {line_number}: "
                         f"nb_drones must be a positive integer")

    return int(value)


def _build_hub(
    line: str,
    line_number: int,
    hubs: Dict[str, Hub],
    start_name: Optional[str],
    end_name: Optional[str],
    nb_drones: int
) -> tuple[Optional[str], Optional[str]]:
    """Parse one hub line, validate it, and add the hub to the map state."""
    prefix, name, x_text, y_text, meta = _parse_hub_line(line, line_number)

    if name in hubs:
        raise ParseError(f"line {line_number}: duplicate hub name '{name}'")

    try:
        x = int(x_text)
        y = int(y_text)
    except ValueError as exc:
        raise ParseError(f"line {line_number}:"
                         f" coordinates must be integers") from exc

    zone_type = meta.get("zone", "normal")
    if zone_type not in ZONE_TYPES:
        raise ParseError(f"line {line_number}: "
                         f"invalid zone type '{zone_type}'")

    max_drones_text = meta.get("max_drones", "1")
    if not max_drones_text.isdigit() or int(max_drones_text) <= 0:
        raise ParseError(f"line {line_number}: "
                         f"max_drones mustbe a positive integer")

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
        max_drones=int(max_drones_text) if kind == "hub" else nb_drones,
    )

    if kind == "start":
        if start_name is not None:
            raise ParseError(f"line {line_number}: "
                             f"multiple start hubs declared")
        start_name = name

    if kind == "end":
        if end_name is not None:
            raise ParseError(f"line {line_number}: multiple end hubs declared")
        end_name = name

    return start_name, end_name


def _build_connection(
    line: str,
    line_number: int,
    hubs: Dict[str, Hub],
    connections: Dict[Tuple[str, str], Connection],
) -> None:
    """Parse one connection line, validate it, and add it to the map state."""
    a, b, meta = _parse_connection_line(line, line_number)

    if a not in hubs or b not in hubs:
        raise ParseError(f"line {line_number}: connection uses undefined hubs")

    if a <= b:
        key = (a, b)
    else:
        key = (b, a)
    if key in connections:
        raise ParseError(f"line {line_number}: duplicate connection '{a}-{b}'")

    max_link_text = meta.get("max_link_capacity", "1")
    if not max_link_text.isdigit() or int(max_link_text) <= 0:
        raise ParseError(
            f"line {line_number}: max_link_capacity must be a positive integer"
        )

    connection = Connection(
        a=a,
        b=b,
        max_link_capacity=int(max_link_text),
    )
    connections[key] = connection
    hubs[a].neighbors.append(b)
    hubs[b].neighbors.append(a)


def _validate_required_parts(
    nb_drones: Optional[int],
    start_name: Optional[str],
    end_name: Optional[str],
) -> tuple[int, str, str]:
    """Validate required top-level map fields and return finalized values."""
    if nb_drones is None:
        raise ParseError("missing nb_drones declaration")
    if start_name is None:
        raise ParseError("missing start_hub declaration")
    if end_name is None:
        raise ParseError("missing end_hub declaration")
    return nb_drones, start_name, end_name


def parse_map(path: str | Path) -> MapData:
    """Read a map file and convert it into validated project models."""
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
            nb_drones = _parse_nb_drones(line, index, nb_drones)
            continue

        if line.startswith(("start_hub:", "end_hub:", "hub:")):
            start_name, end_name = _build_hub(
                line,
                index,
                hubs,
                start_name,
                end_name,
                nb_drones
            )
            continue

        if line.startswith("connection:"):
            _build_connection(
                line,
                index,
                hubs,
                connections,
            )
            continue

        raise ParseError(f"line {index}: unsupported syntax")

    nb_drones, start_name, end_name = _validate_required_parts(
        nb_drones,
        start_name,
        end_name,
    )

    return MapData(
        nb_drones,
        hubs,
        connections,
        start_name,
        end_name,
        title,
    )
