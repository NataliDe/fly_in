import sys

import pygame

from .parser import ParseError, parse_map
from .renderer import FPS, Renderer
from .simulator import Simulator


def print_turn_output(simulator: Simulator, show_log: bool) -> None:
    """Print moves from the current turn when log output is enabled."""
    if show_log and simulator.move_logs:
        print(" ".join(simulator.move_logs))


def run_gui_mode(
    simulator: Simulator,
    auto: bool,
    show_log: bool,
) -> None:
    """Run the pygame loop and update the simulation frame by frame."""
    renderer = Renderer(simulator.map_data)
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
                    print_turn_output(simulator, show_log=show_log)

        simulator.update_animation(dt)

        nobody_moving = all(
            (not drone.is_moving) or drone.progress >= 1.0
            for drone in simulator.drones
        )

        if running and not simulator.is_finished():
            step_cooldown += dt
            if nobody_moving and step_cooldown >= 0.08:
                simulator.step()
                print_turn_output(simulator, show_log=show_log)
                step_cooldown = 0.0

        renderer.draw(simulator, running)


def main() -> None:
    """Parse command-line arguments, load the map, and start the GUI."""
    if len(sys.argv) < 2:
        print(
            "Usage: python3 -m fly_in.main path/to/map.txt "
            "[--auto] [--log]"
        )
        return

    map_path = sys.argv[1]
    flags = sys.argv[2:]

    auto = "--auto" in flags
    show_log = "--log" in flags

    try:
        map_data = parse_map(map_path)
    except (OSError, ParseError) as exc:
        print(f"Parse error: {exc}")
        return

    simulator = Simulator(map_data)

    run_gui_mode(
        simulator=simulator,
        auto=auto,
        show_log=show_log,
    )


if __name__ == "__main__":
    main()