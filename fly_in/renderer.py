from __future__ import annotations

import math
from typing import Dict, Tuple

import pygame

from .models import MapData
from .simulator import Simulator

SCREEN_W = 1800
SCREEN_H = 1100
BG_COLOR = (20, 23, 31)
GRID_COLOR = (38, 42, 52)
TEXT_COLOR = (235, 235, 240)
SUBTLE_TEXT = (210, 210, 220)
LINK_COLOR = (105, 110, 130)
LINK_BUSY_COLOR = (255, 190, 70)
DRONE_BODY = (28, 28, 32)
DRONE_TEXT = (255, 255, 255)
DEFAULT_SCALE = 90
FPS = 60
TOP_UI_HEIGHT = 150
MAP_MARGIN_X = 120
MAP_MARGIN_Y = 80
Y_SPACING_FACTOR = 3.0


def color_from_name(name: str, kind: str, zone: str) -> Tuple[int, int, int]:
    palette = {
        "green": (60, 210, 90),
        "red": (220, 60, 60),
        "blue": (70, 140, 255),
        "yellow": (245, 220, 70),
        "orange": (255, 145, 50),
        "purple": (170, 95, 255),
        "cyan": (70, 220, 220),
        "black": (35, 35, 35),
        "brown": (130, 90, 50),
        "gold": (240, 190, 60),
        "maroon": (120, 40, 60),
        "darkred": (130, 20, 20),
        "violet": (170, 100, 220),
        "crimson": (200, 30, 80),
        "lime": (140, 220, 60),
        "magenta": (220, 80, 200),
        "rainbow": (255, 255, 255),
        "none": (190, 190, 190),
    }
    if name in palette:
        return palette[name]
    if kind == "start":
        return (60, 210, 90)
    if kind == "end":
        return (220, 80, 80)
    if zone == "restricted":
        return (180, 120, 80)
    if zone == "priority":
        return (80, 220, 220)
    if zone == "blocked":
        return (35, 35, 35)
    return (180, 180, 190)


class Renderer:
    """Pygame renderer for the simulation."""

    def __init__(self, map_data: MapData) -> None:
        pygame.init()
        pygame.display.set_caption("Fly-in Drone Simulation")
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.clock = pygame.time.Clock()
        self.map_data = map_data
        self.font_small = pygame.font.SysFont("arial", 20, bold=False)
        self.font = pygame.font.SysFont("arial", 26, bold=True)
        self.font_big = pygame.font.SysFont("arial", 34, bold=True)
        self.font_caps = pygame.font.SysFont("arial", 18, bold=True)
        self.scale = DEFAULT_SCALE
        self.offset_x = SCREEN_W // 2
        self.offset_y = (TOP_UI_HEIGHT + SCREEN_H) // 2
        self._recalculate_view()

    def _recalculate_view(self) -> None:
        xs = [hub.x for hub in self.map_data.hubs.values()]
        ys = [hub.y for hub in self.map_data.hubs.values()]
        if not xs or not ys:
            return

        min_x = min(xs)
        max_x = max(xs)
        min_y = min(ys)
        max_y = max(ys)

        span_x = max(1, max_x - min_x)
        span_y = max(1, max_y - min_y)

        available_w = SCREEN_W - MAP_MARGIN_X * 2
        available_h = SCREEN_H - TOP_UI_HEIGHT - MAP_MARGIN_Y * 2
        scale_x = available_w / max(1, span_x)
        scale_y = available_h / max(1, span_y * Y_SPACING_FACTOR)
        self.scale = max(36, min(DEFAULT_SCALE, int(min(scale_x, scale_y))))

        map_pixel_w = span_x * self.scale
        map_pixel_h = span_y * self.scale * Y_SPACING_FACTOR
        self.offset_x = int((SCREEN_W - map_pixel_w) / 2 - min_x * self.scale)
        self.offset_y = int(
            TOP_UI_HEIGHT
            + (available_h - map_pixel_h) / 2
            + max_y * self.scale * Y_SPACING_FACTOR
            + MAP_MARGIN_Y
        )

    def world_to_screen(self, x: float, y: float) -> Tuple[int, int]:
        return (
            int(self.offset_x + x * self.scale),
            int(self.offset_y - y * self.scale * Y_SPACING_FACTOR),
        )

    def draw_grid(self) -> None:
        for x in range(0, SCREEN_W, 50):
            pygame.draw.line(self.screen, GRID_COLOR, (x, TOP_UI_HEIGHT), (x, SCREEN_H), 1)
        for y in range(TOP_UI_HEIGHT, SCREEN_H, 50):
            pygame.draw.line(self.screen, GRID_COLOR, (0, y), (SCREEN_W, y), 1)

    def draw_links(self, sim: Simulator) -> None:
        busy_keys = set()
        for drone in sim.drones:
            key = drone.active_connection_key()
            if key is not None:
                busy_keys.add(key)

        for key, conn in self.map_data.connections.items():
            a = self.map_data.hubs[conn.a]
            b = self.map_data.hubs[conn.b]
            p1 = self.world_to_screen(a.x, a.y)
            p2 = self.world_to_screen(b.x, b.y)
            color = LINK_BUSY_COLOR if key in busy_keys else LINK_COLOR
            width = 7 if key in busy_keys else 4
            pygame.draw.line(self.screen, color, p1, p2, width)
            mx = (p1[0] + p2[0]) // 2
            my = (p1[1] + p2[1]) // 2
            box = pygame.Rect(mx - 16, my - 15, 32, 28)
            pygame.draw.rect(self.screen, BG_COLOR, box, border_radius=8)
            pygame.draw.rect(self.screen, color, box, 2, border_radius=8)
            cap_text = self.font_caps.render(str(conn.max_link_capacity), True, TEXT_COLOR)
            self.screen.blit(cap_text, (mx - cap_text.get_width() // 2, my - cap_text.get_height() // 2))

    def draw_hubs(self, sim: Simulator) -> None:
        occupancy = {name: 0 for name in self.map_data.hubs}
        for drone in sim.drones:
            if not drone.is_moving:
                occupancy[drone.current_hub] += 1

        for hub in self.map_data.hubs.values():
            pos = self.world_to_screen(hub.x, hub.y)
            color = color_from_name(hub.color, hub.kind, hub.zone_type)
            radius = 34 if hub.kind in {"start", "end"} else 28
            pygame.draw.circle(self.screen, color, pos, radius)
            pygame.draw.circle(self.screen, (12, 12, 15), pos, radius, 4)

            cap_display = "∞" if hub.kind in {"start", "end"} else str(hub.max_drones)
            cap_surf = self.font.render(cap_display, True, (10, 10, 14))
            self.screen.blit(
                cap_surf,
                (pos[0] - cap_surf.get_width() // 2, pos[1] - cap_surf.get_height() // 2),
            )

            occ_text = self.font_small.render(f"{occupancy[hub.name]}", True, SUBTLE_TEXT)
            occ_bg = pygame.Rect(pos[0] - 16, pos[1] + radius + 6, 32, 24)
            pygame.draw.rect(self.screen, BG_COLOR, occ_bg, border_radius=8)
            pygame.draw.rect(self.screen, color, occ_bg, 2, border_radius=8)
            self.screen.blit(
                occ_text,
                (occ_bg.centerx - occ_text.get_width() // 2, occ_bg.centery - occ_text.get_height() // 2),
            )

    def draw_drones(self, sim: Simulator) -> None:
        parked_count: Dict[str, int] = {name: 0 for name in self.map_data.hubs}
        for drone in sim.drones:
            if drone.is_moving and drone.from_hub and drone.to_hub:
                a = self.map_data.hubs[drone.from_hub]
                b = self.map_data.hubs[drone.to_hub]
                p1 = self.world_to_screen(a.x, a.y)
                p2 = self.world_to_screen(b.x, b.y)
                x = p1[0] + (p2[0] - p1[0]) * drone.progress
                y = p1[1] + (p2[1] - p1[1]) * drone.progress
            else:
                hub = self.map_data.hubs[drone.current_hub]
                base_x, base_y = self.world_to_screen(hub.x, hub.y)
                index = parked_count[drone.current_hub]
                parked_count[drone.current_hub] += 1
                angle = index * 0.95
                radius = 14 + (index // 6) * 12
                x = base_x + math.cos(angle) * radius
                y = base_y + math.sin(angle) * radius

            pygame.draw.circle(self.screen, (255, 255, 255), (int(x), int(y)), 14)
            pygame.draw.circle(self.screen, DRONE_BODY, (int(x), int(y)), 12)
            text = self.font_caps.render(str(drone.drone_id), True, DRONE_TEXT)
            self.screen.blit(text, (int(x) - text.get_width() // 2, int(y) - text.get_height() // 2))

    def draw_ui(self, sim: Simulator, running: bool) -> None:
        title = self.font_big.render(self.map_data.title, True, TEXT_COLOR)
        self.screen.blit(title, (24, 18))
        lines = [
            f"Turn: {sim.turn}",
            f"Delivered: {sim.finished_count}/{len(sim.drones)}",
            f"State: {'RUNNING' if running else 'PAUSED'}",
            "Keys: SPACE play/pause | N next turn | R restart | ESC exit",
            "On hubs: big number = capacity, small bottom number = drones inside, on links = link capacity",
        ]
        y = 60
        for line in lines:
            surf = self.font_small.render(line, True, TEXT_COLOR)
            self.screen.blit(surf, (24, y))
            y += 24

        pygame.draw.line(self.screen, GRID_COLOR, (0, TOP_UI_HEIGHT - 6), (SCREEN_W, TOP_UI_HEIGHT - 6), 2)

    def draw(self, sim: Simulator, running: bool) -> None:
        self.screen.fill(BG_COLOR)
        self.draw_grid()
        self.draw_links(sim)
        self.draw_hubs(sim)
        self.draw_drones(sim)
        self.draw_ui(sim, running)
        pygame.display.flip()
