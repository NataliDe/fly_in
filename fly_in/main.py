from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pygame

from .parser import ParseError, parse_map
from .renderer import PygameRenderer
from .simulator import DroneSimulator


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fly-in drone simulator with pygame")
    parser.add_argument("map_file", help="Path to the map file")
    parser.add_argument("--width", type=int, default=1400)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--auto", action="store_true", help="Start simulation automatically")
    return parser


def restart_simulator(map_file: str) -> tuple[DroneSimulator, object]:
    map_data = parse_map(map_file)
    simulator = DroneSimulator(map_data)
    return simulator, map_data


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    try:
        simulator, map_data = restart_simulator(args.map_file)
    except (ParseError, ValueError, OSError) as exc:
        print(f"Error: {exc}")
        return 1

    pygame.init()
    pygame.display.set_caption("Fly-in")
    screen = pygame.display.set_mode((args.width, args.height))
    clock = pygame.time.Clock()
    renderer = PygameRenderer(screen, map_data)
    auto_run = args.auto
    step_accumulator = 0
    running = True

    while running:
        dt = clock.tick(args.fps)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    auto_run = not auto_run
                elif event.key == pygame.K_n:
                    if not simulator.is_finished():
                        simulator.step()
                elif event.key == pygame.K_r:
                    simulator, map_data = restart_simulator(args.map_file)
                    renderer = PygameRenderer(screen, map_data)
                    step_accumulator = 0

        if auto_run and not simulator.is_finished():
            step_accumulator += dt
            if step_accumulator >= 600:
                simulator.step()
                step_accumulator = 0

        renderer.draw(simulator, auto_run)

    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
