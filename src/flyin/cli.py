from __future__ import annotations

import argparse

from .parser import parse_map_file
from .viz_pygame import PygameViewer, VisualState


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("map_path")
    ap.add_argument("--viz", action="store_true")
    args = ap.parse_args()

    g, nb = parse_map_file(args.map_path)

    if args.viz:
        viewer = PygameViewer(g, VisualState(nb_drones=nb))
        viewer.run()
    else:
        print(f"Loaded map with {nb} drones, zones={len(g.zones)}")


if __name__ == "__main__":
    main()