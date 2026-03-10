from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import pygame

from .model import Graph, Zone, ZoneType


_COLOR_MAP: Dict[str, Tuple[int, int, int]] = {
    "green": (46, 204, 113),
    "red": (231, 76, 60),
    "blue": (52, 152, 219),
    "yellow": (241, 196, 15),
    "orange": (230, 126, 34),
    "purple": (155, 89, 182),
    "cyan": (26, 188, 156),
    "lime": (0, 255, 0),
    "magenta": (255, 0, 255),
    "gold": (255, 215, 0),
    "gray": (120, 120, 120),
    "brown": (139, 69, 19),
}


def _zone_fill_color(z: Zone) -> Tuple[int, int, int]:
    if z.zone_type == ZoneType.BLOCKED:
        return (80, 80, 80)
    if z.zone_type == ZoneType.RESTRICTED:
        return (200, 80, 80)
    if z.zone_type == ZoneType.PRIORITY:
        return (80, 200, 200)
    if z.color and z.color in _COLOR_MAP:
        return _COLOR_MAP[z.color]
    return (180, 180, 180)


@dataclass
class VisualState:
    # For now: all drones are in start
    nb_drones: int


class PygameViewer:
    def __init__(self, g: Graph, vs: VisualState, cell: int = 80) -> None:
        self.g = g
        self.vs = vs
        self.cell = cell

        xs = [z.x for z in g.zones.values()]
        ys = [z.y for z in g.zones.values()]
        self.min_x, self.max_x = min(xs), max(xs)
        self.min_y, self.max_y = min(ys), max(ys)

        self.pad = 2
        w = (self.max_x - self.min_x + 1 + self.pad * 2) * self.cell
        h = (self.max_y - self.min_y + 1 + self.pad * 2) * self.cell

        pygame.init()
        self.screen = pygame.display.set_mode((w, h))
        pygame.display.set_caption("Fly-in (Part 1) - Graph Viewer")
        self.font = pygame.font.SysFont(None, 18)
        self.clock = pygame.time.Clock()

    def _to_screen(self, x: int, y: int) -> Tuple[int, int]:
        sx = (x - self.min_x + self.pad) * self.cell + self.cell // 2
        sy = (y - self.min_y + self.pad) * self.cell + self.cell // 2
        return sx, sy

    def run(self) -> None:
        running = True
        while running:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False

            self.screen.fill((20, 20, 24))
            self._draw_edges()
            self._draw_nodes()
            self._draw_drones_at_start()

            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()

    def _draw_edges(self) -> None:
        drawn = set()
        for a, conns in self.g.adj.items():
            for c in conns:
                k = c.key()
                if k in drawn:
                    continue
                drawn.add(k)
                za = self.g.zones[c.a]
                zb = self.g.zones[c.b]
                ax, ay = self._to_screen(za.x, za.y)
                bx, by = self._to_screen(zb.x, zb.y)
                pygame.draw.line(self.screen, (90, 90, 100), (ax, ay), (bx, by), 3)

                # show capacity if >1
                if c.max_link_capacity != 1:
                    mx, my = (ax + bx) // 2, (ay + by) // 2
                    txt = self.font.render(f"cap={c.max_link_capacity}", True, (220, 220, 220))
                    self.screen.blit(txt, (mx + 4, my + 4))

    def _draw_nodes(self) -> None:
        for z in self.g.zones.values():
            x, y = self._to_screen(z.x, z.y)
            fill = _zone_fill_color(z)

            radius = 18
            pygame.draw.circle(self.screen, fill, (x, y), radius)
            pygame.draw.circle(self.screen, (10, 10, 10), (x, y), radius, 2)

            # label
            name = z.name
            if z.is_start:
                name = f"{name} (S)"
            elif z.is_end:
                name = f"{name} (E)"
            txt = self.font.render(name, True, (240, 240, 240))
            self.screen.blit(txt, (x + 22, y - 8))

            # show max_drones if not default OR if start/end
            if z.is_start or z.is_end or z.max_drones != 1:
                cap_txt = self.font.render(f"zcap={z.max_drones}", True, (210, 210, 210))
                self.screen.blit(cap_txt, (x + 22, y + 8))

    def _draw_drones_at_start(self) -> None:
        start = self.g.zones[self.g.start]
        sx, sy = self._to_screen(start.x, start.y)

        # draw drones around start in a small spiral-ish layout
        n = self.vs.nb_drones
        for i in range(1, n + 1):
            dx = ((i - 1) % 6) * 10 - 25
            dy = ((i - 1) // 6) * 10 - 10
            pygame.draw.circle(self.screen, (250, 250, 250), (sx + dx, sy + dy), 5)