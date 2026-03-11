from __future__ import annotations

from typing import Dict, Tuple

import pygame

from .models import MapData
from .simulator import DroneSimulator


COLOR_MAP: Dict[str, Tuple[int, int, int]] = {
    "none": (180, 180, 180),
    "green": (46, 204, 113),
    "red": (231, 76, 60),
    "blue": (52, 152, 219),
    "yellow": (241, 196, 15),
    "orange": (243, 156, 18),
    "purple": (155, 89, 182),
    "cyan": (26, 188, 156),
    "black": (44, 62, 80),
    "brown": (141, 110, 99),
    "gray": (127, 140, 141),
    "grey": (127, 140, 141),
    "gold": (212, 175, 55),
    "maroon": (128, 0, 0),
    "darkred": (139, 0, 0),
    "violet": (142, 68, 173),
    "crimson": (220, 20, 60),
    "lime": (50, 205, 50),
    "magenta": (255, 0, 255),
    "rainbow": (255, 105, 180),
}

BACKGROUND = (245, 247, 250)
TEXT = (33, 37, 41)
EDGE = (130, 140, 150)
DRONE = (25, 25, 25)
PANEL = (255, 255, 255)


class PygameRenderer:
    def __init__(self, screen: pygame.Surface, map_data: MapData) -> None:
        self.screen = screen
        self.map_data = map_data
        self.font = pygame.font.SysFont("arial", 18)
        self.small_font = pygame.font.SysFont("arial", 14)
        self.big_font = pygame.font.SysFont("arial", 24, bold=True)
        self.margin_x = 90
        self.margin_y = 90
        self.cell = 70
        self.panel_width = 320

    def _world_to_screen(self, x: int, y: int) -> Tuple[int, int]:
        return self.margin_x + x * self.cell, self.screen.get_height() // 2 - y * self.cell

    def _hub_color(self, color_name: str, zone_type: str) -> Tuple[int, int, int]:
        if color_name in COLOR_MAP:
            return COLOR_MAP[color_name]
        if zone_type == "restricted":
            return (210, 140, 70)
        if zone_type == "priority":
            return (70, 170, 240)
        if zone_type == "blocked":
            return (90, 90, 90)
        return COLOR_MAP["none"]

    def draw(self, simulator: DroneSimulator, auto_run: bool) -> None:
        self.screen.fill(BACKGROUND)
        self._draw_connections()
        self._draw_hubs(simulator)
        self._draw_transit(simulator)
        self._draw_side_panel(simulator, auto_run)
        pygame.display.flip()

    def _draw_connections(self) -> None:
        for connection in self.map_data.connections.values():
            a = self.map_data.hubs[connection.a]
            b = self.map_data.hubs[connection.b]
            ax, ay = self._world_to_screen(a.x, a.y)
            bx, by = self._world_to_screen(b.x, b.y)
            pygame.draw.line(self.screen, EDGE, (ax, ay), (bx, by), 3)
            mid_x = (ax + bx) // 2
            mid_y = (ay + by) // 2
            cap_text = self.small_font.render(str(connection.max_link_capacity), True, TEXT)
            self.screen.blit(cap_text, (mid_x + 4, mid_y + 4))

    def _draw_hubs(self, simulator: DroneSimulator) -> None:
        occupancy = simulator.hub_occupancy()
        for hub in self.map_data.hubs.values():
            sx, sy = self._world_to_screen(hub.x, hub.y)
            radius = 22 if hub.kind == "hub" else 28
            color = self._hub_color(hub.color, hub.zone_type)
            pygame.draw.circle(self.screen, color, (sx, sy), radius)
            pygame.draw.circle(self.screen, TEXT, (sx, sy), radius, 2)
            label = self.small_font.render(hub.name, True, TEXT)
            self.screen.blit(label, (sx - label.get_width() // 2, sy + radius + 6))
            occ_value = occupancy.get(hub.name, 0)
            occ_text = self.small_font.render(
                f"{occ_value}/{hub.max_drones}" if hub.kind == "hub" else str(occ_value),
                True,
                TEXT,
            )
            self.screen.blit(occ_text, (sx - occ_text.get_width() // 2, sy - 9))
            if hub.zone_type == "blocked":
                pygame.draw.line(self.screen, (255, 255, 255), (sx - 10, sy - 10), (sx + 10, sy + 10), 3)
                pygame.draw.line(self.screen, (255, 255, 255), (sx + 10, sy - 10), (sx - 10, sy + 10), 3)

    def _draw_transit(self, simulator: DroneSimulator) -> None:
        for moving in simulator.moving_sprites():
            start_hub = self.map_data.hubs[moving.start]
            end_hub = self.map_data.hubs[moving.end]
            sx, sy = self._world_to_screen(start_hub.x, start_hub.y)
            ex, ey = self._world_to_screen(end_hub.x, end_hub.y)
            x = sx + (ex - sx) * moving.progress
            y = sy + (ey - sy) * moving.progress
            pygame.draw.circle(self.screen, DRONE, (int(x), int(y)), 8)
            tag = self.small_font.render(str(moving.drone_id), True, (255, 255, 255))
            self.screen.blit(tag, (int(x) - tag.get_width() // 2, int(y) - tag.get_height() // 2))

    def _draw_side_panel(self, simulator: DroneSimulator, auto_run: bool) -> None:
        x = self.screen.get_width() - self.panel_width
        panel_rect = pygame.Rect(x, 0, self.panel_width, self.screen.get_height())
        pygame.draw.rect(self.screen, PANEL, panel_rect)
        pygame.draw.line(self.screen, EDGE, (x, 0), (x, self.screen.get_height()), 2)

        y = 24
        lines = [
            self.big_font.render("Fly-in", True, TEXT),
            self.font.render(self.map_data.title, True, TEXT),
            self.font.render(f"Turn: {simulator.turn}", True, TEXT),
            self.font.render(f"Delivered: {simulator.delivered_count()}/{len(simulator.drones)}", True, TEXT),
            self.font.render(f"Auto-run: {'ON' if auto_run else 'OFF'}", True, TEXT),
            self.font.render("Keys:", True, TEXT),
            self.small_font.render("SPACE - play/pause", True, TEXT),
            self.small_font.render("N - next turn", True, TEXT),
            self.small_font.render("R - restart", True, TEXT),
            self.small_font.render("ESC - quit", True, TEXT),
            self.font.render("Last turn moves:", True, TEXT),
        ]
        for surface in lines:
            self.screen.blit(surface, (x + 18, y))
            y += surface.get_height() + 8

        last_moves = simulator.logs[-1].moves if simulator.logs else []
        if not last_moves:
            last_moves = ["No moves yet"]
        for move in last_moves[-15:]:
            txt = self.small_font.render(move, True, TEXT)
            self.screen.blit(txt, (x + 18, y))
            y += txt.get_height() + 4
