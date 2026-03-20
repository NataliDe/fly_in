import sys

import pygame

from .parser import ParseError, parse_map
from .renderer import FPS, Renderer
from .simulator import Simulator


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 -m fly_in.main path/to/map.txt [--auto] [--log]")
        return

    map_path = sys.argv[1]
    auto = "--auto" in sys.argv[2:]
    show_log = "--log" in sys.argv[2:]

    try:
        map_data = parse_map(map_path)
    except (OSError, ParseError) as exc:
        print(f"Parse error: {exc}")
        return

    renderer = Renderer(map_data)
    simulator = Simulator(map_data)
    running = auto
    step_cooldown = 0.0

    while True:
        dt = renderer.clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    return
                if event.key == pygame.K_SPACE:
                    running = not running
                if event.key == pygame.K_r:
                    simulator.reset()
                    running = False
                    step_cooldown = 0.0
                if event.key == pygame.K_n and not simulator.is_finished():
                    simulator.step()
                    if show_log and simulator.move_logs:
                        print(" ".join(simulator.move_logs))

        simulator.update_animation(dt)
        nobody_moving = all((not drone.is_moving)
                            or drone.progress >= 1.0
                            for drone in simulator.drones)

        if running and not simulator.is_finished():
            step_cooldown += dt
            if nobody_moving and step_cooldown >= 0.08:
                simulator.step()
                if show_log and simulator.move_logs:
                    print(" ".join(simulator.move_logs))
                step_cooldown = 0.0

        renderer.draw(simulator, running)


if __name__ == "__main__":
    main()
