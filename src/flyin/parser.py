from __future__ import annotations

from typing import Dict, Optional, Tuple

from .model import Connection, Graph, Zone, ZoneType


def _strip_comment(line: str) -> str:
    return line.split("#", 1)[0].strip()


def _split_meta(line: str) -> Tuple[str, Dict[str, str]]:
    """
    Splits: "start 0 0 [color=green max_drones=8]" -> ("start 0 0", {"color":"green","max_drones":"8"})
    Metadata tokens are SPACE-separated (as in your provided maps).
    """
    if "[" not in line:
        return line.strip(), {}
    before, after = line.split("[", 1)
    meta_raw = "[" + after
    meta_raw = meta_raw.strip()
    if not meta_raw.endswith("]"):
        raise ValueError("metadata missing closing ']'")
    inner = meta_raw[1:-1].strip()
    meta: Dict[str, str] = {}
    if inner:
        for tok in inner.split():
            if "=" not in tok:
                raise ValueError(f"bad metadata token: {tok}")
            k, v = tok.split("=", 1)
            meta[k.strip()] = v.strip()
    return before.strip(), meta


def parse_map_file(path: str) -> Tuple[Graph, int]:
    g = Graph()
    nb_drones: Optional[int] = None

    with open(path, "r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = _strip_comment(raw)
            if not line:
                continue

            try:
                if line.startswith("nb_drones:"):
                    nb_drones = int(line.split(":", 1)[1].strip())
                    if nb_drones <= 0:
                        raise ValueError("nb_drones must be positive")
                    continue

                if line.startswith(("start_hub:", "end_hub:", "hub:")):
                    kind, rest = line.split(":", 1)
                    main, meta = _split_meta(rest.strip())

                    name, xs, ys = main.split()
                    x, y = int(xs), int(ys)

                    zone_type = ZoneType(meta.get("zone", "normal"))
                    color = meta.get("color")
                    max_drones = int(meta.get("max_drones", "1"))
                    if max_drones <= 0:
                        raise ValueError("max_drones must be positive")

                    is_start = kind == "start_hub"
                    is_end = kind == "end_hub"

                    z = Zone(
                        name=name,
                        x=x,
                        y=y,
                        zone_type=zone_type,
                        color=color,
                        max_drones=max_drones,
                        is_start=is_start,
                        is_end=is_end,
                    )
                    g.add_zone(z)
                    if is_start:
                        if g.start:
                            raise ValueError("multiple start_hub")
                        g.start = name
                    if is_end:
                        if g.end:
                            raise ValueError("multiple end_hub")
                        g.end = name
                    continue

                if line.startswith("connection:"):
                    rest = line.split(":", 1)[1].strip()
                    main, meta = _split_meta(rest)

                    if "-" not in main:
                        raise ValueError("connection must be zone1-zone2")
                    a, b = [s.strip() for s in main.split("-", 1)]
                    cap = int(meta.get("max_link_capacity", "1"))
                    if cap <= 0:
                        raise ValueError("max_link_capacity must be positive")

                    g.add_connection(Connection(a=a, b=b, max_link_capacity=cap))
                    continue

                raise ValueError(f"unknown line type: {line}")

            except Exception as e:
                raise ValueError(f"Parse error on line {lineno}: {e}") from e

    if nb_drones is None:
        raise ValueError("nb_drones not specified")
    if not g.start or not g.end:
        raise ValueError("start_hub or end_hub missing")

    return g, nb_drones