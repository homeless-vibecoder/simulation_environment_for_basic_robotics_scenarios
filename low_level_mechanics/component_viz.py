"""Reusable component renderers for the pygame visualizer."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Callable, Dict, Iterable, Tuple

import pygame

from .world import Pose2D

Color = Tuple[int, int, int]
Point = Tuple[float, float]


@dataclass(frozen=True)
class ComponentToggleState:
    icons: bool = True
    sensor_details: bool = False
    numeric_labels: bool = False


class _DrawContext:
    def __init__(
        self,
        surface: pygame.Surface,
        world_to_screen: Callable[[Point], Tuple[int, int]],
        scale: float,
        font: pygame.font.Font,
        toggles: ComponentToggleState,
    ) -> None:
        self.surface = surface
        self.world_to_screen = world_to_screen
        self.scale = scale
        self.font = font
        self.toggles = toggles


class ComponentVisualizer:
    """Dispatches tag-specific renderers for mounted components."""

    ICON_COLORS: Dict[str, Color] = {
        "motor": (255, 190, 120),
        "sensor": (150, 220, 255),
        "other": (210, 210, 210),
    }

    def __init__(self, surface: pygame.Surface) -> None:
        self.surface = surface
        self._renderers: Dict[str, Callable[[Pose2D, Dict[str, Any], _DrawContext], None]] = {
            "motor.wheel": self._render_wheel_motor,
            "sensor.line": self._render_line_sensor,
            "sensor.line_array": self._render_line_array,
            "sensor.distance": self._render_distance_sensor,
            "sensor.imu": self._render_imu_sensor,
        }

    def draw_for_object(
        self,
        obj: Any,
        *,
        world_to_screen: Callable[[Point], Tuple[int, int]],
        scale: float,
        font: pygame.font.Font,
        toggles: ComponentToggleState,
    ) -> None:
        components: Iterable[Any] = getattr(obj, "components", ())  # type: ignore[assignment]
        ctx = _DrawContext(self.surface, world_to_screen, scale, font, toggles)
        for component in components or ():
            tag = getattr(component, "visual_tag", None)
            if not tag:
                continue
            state_fn = getattr(component, "visual_state", None)
            pose_fn = getattr(component, "world_pose", None)
            if not callable(state_fn) or not callable(pose_fn):
                continue
            pose = pose_fn()
            state = state_fn() or {}
            if toggles.icons:
                self._draw_icon(tag, pose, ctx)
            renderer = self._renderers.get(tag)
            if renderer:
                renderer(pose, state, ctx)

    def _draw_icon(self, tag: str, pose: Pose2D, ctx: _DrawContext) -> None:
        group = tag.split(".", 1)[0]
        color = self.ICON_COLORS.get(group, self.ICON_COLORS["other"])
        if group == "motor":
            self._draw_motor_icon(pose, color, ctx)
        elif group == "sensor":
            self._draw_sensor_icon(tag, pose, color, ctx)
        else:
            radius = max(3, int(ctx.scale * 0.015))
            center = ctx.world_to_screen((pose.x, pose.y))
            pygame.draw.circle(ctx.surface, color, center, radius)

    # --- Renderers -----------------------------------------------------

    def _render_wheel_motor(self, pose: Pose2D, state: Dict[str, Any], ctx: _DrawContext) -> None:
        command = float(state.get("command", 0.0))
        magnitude = min(1.0, max(0.0, abs(command)))
        direction = 1.0 if command >= 0.0 else -1.0
        base_length = 0.1
        arrow_length = base_length * (0.55 + 0.45 * magnitude)
        rim_r = max(3, int(ctx.scale * 0.012))
        hub_screen = ctx.world_to_screen((pose.x, pose.y))
        pygame.draw.circle(ctx.surface, (28, 34, 42), hub_screen, rim_r)
        pygame.draw.circle(ctx.surface, (90, 120, 150), hub_screen, rim_r, 2)
        start_world = pose.transform_point((0.02 * direction, 0.0))
        end_world = pose.transform_point(((arrow_length + 0.02) * direction, 0.0))
        start = ctx.world_to_screen(start_world)
        end = ctx.world_to_screen(end_world)
        color = (120, 255, 140) if command >= 0 else (255, 120, 120)
        pygame.draw.line(ctx.surface, color, start, end, 3)
        self._draw_arrow_head(start_world, end_world, color, ctx)
        if ctx.toggles.numeric_labels:
            label = f"{command:+.2f}"
            ctx.surface.blit(ctx.font.render(label, True, color), (end[0] + 4, end[1] - 12))

    def _render_line_sensor(self, pose: Pose2D, state: Dict[str, Any], ctx: _DrawContext) -> None:
        if not ctx.toggles.sensor_details:
            return
        value = state.get("value", 0.0) or 0.0
        point = state.get("point", (pose.x, pose.y))
        color = self._value_to_color(value)
        radius = max(3, int(ctx.scale * 0.01))
        pygame.draw.circle(ctx.surface, color, ctx.world_to_screen(point), radius)
        if ctx.toggles.numeric_labels:
            ctx.surface.blit(ctx.font.render(f"{value:.2f}", True, color), (ctx.world_to_screen(point)[0] + 6, ctx.world_to_screen(point)[1] - 10))

    def _render_line_array(self, pose: Pose2D, state: Dict[str, Any], ctx: _DrawContext) -> None:
        if not ctx.toggles.sensor_details:
            return
        points = state.get("points", [])
        values = state.get("values", [])
        for point, value in zip(points, values):
            color = self._value_to_color(value)
            radius = max(3, int(ctx.scale * 0.01))
            pygame.draw.circle(ctx.surface, color, ctx.world_to_screen(point), radius)

    def _render_distance_sensor(self, pose: Pose2D, state: Dict[str, Any], ctx: _DrawContext) -> None:
        if not ctx.toggles.sensor_details:
            return
        start = ctx.world_to_screen(state.get("start", (pose.x, pose.y)))
        end = ctx.world_to_screen(state.get("end", (pose.x, pose.y)))
        hit = bool(state.get("hit", False))
        color = (255, 100, 120) if hit else (140, 255, 170)
        pygame.draw.line(ctx.surface, color, start, end, 2)
        if ctx.toggles.numeric_labels:
            distance = float(state.get("distance", 0.0))
            ctx.surface.blit(ctx.font.render(f"{distance:.2f}m", True, color), (end[0] + 4, end[1] - 12))

    def _render_imu_sensor(self, pose: Pose2D, state: Dict[str, Any], ctx: _DrawContext) -> None:
        if not ctx.toggles.numeric_labels:
            return
        text = f"vx:{state.get('lin', (0.0, 0.0))[0]:+.2f} vy:{state.get('lin', (0.0, 0.0))[1]:+.2f} ω:{state.get('ang', 0.0):+.2f}"
        pos = ctx.world_to_screen((pose.x, pose.y))
        ctx.surface.blit(ctx.font.render(text, True, (220, 220, 220)), (pos[0] + 8, pos[1] + 4))

    # --- Helpers -------------------------------------------------------

    @staticmethod
    def _value_to_color(value: float) -> Color:
        clamped = max(0.0, min(1.0, float(value)))
        return (
            int(80 + 170 * clamped),
            int(70 + 40 * clamped),
            int(220 - 120 * clamped),
        )


    def _draw_motor_icon(self, pose: Pose2D, color: Color, ctx: _DrawContext) -> None:
        radius = max(4, int(ctx.scale * 0.018))
        center_world = (pose.x, pose.y)
        center = ctx.world_to_screen(center_world)
        pygame.draw.circle(ctx.surface, color, center, radius)
        pygame.draw.circle(ctx.surface, (26, 26, 26), center, max(2, radius // 2), 2)
        spoke_end = ctx.world_to_screen(pose.transform_point((0.05, 0.0)))
        pygame.draw.line(ctx.surface, (18, 18, 18), center, spoke_end, 2)

    def _draw_sensor_icon(self, tag: str, pose: Pose2D, color: Color, ctx: _DrawContext) -> None:
        size = 0.025
        if tag == "sensor.distance":
            local = [
                (size * 1.5, 0.0),
                (-size * 0.6, size * 0.8),
                (-size * 0.6, -size * 0.8),
            ]
        else:
            local = [
                (0.0, size),
                (size, 0.0),
                (0.0, -size),
                (-size, 0.0),
            ]
        points = [ctx.world_to_screen(pose.transform_point(pt)) for pt in local]
        pygame.draw.polygon(ctx.surface, color, points)

    def _draw_arrow_head(self, start: Point, end: Point, color: Color, ctx: _DrawContext) -> None:
        vx = end[0] - start[0]
        vy = end[1] - start[1]
        length = math.hypot(vx, vy)
        if length == 0:
            return
        nx = vx / length
        ny = vy / length
        px = -ny
        py = nx
        head_len = 0.03
        head_half_width = 0.012
        left = (
            end[0] - nx * head_len + px * head_half_width,
            end[1] - ny * head_len + py * head_half_width,
        )
        right = (
            end[0] - nx * head_len - px * head_half_width,
            end[1] - ny * head_len - py * head_half_width,
        )
        tip = ctx.world_to_screen(end)
        left_px = ctx.world_to_screen(left)
        right_px = ctx.world_to_screen(right)
        pygame.draw.polygon(ctx.surface, color, [tip, left_px, right_px])

    @staticmethod
    def _value_to_color(value: float) -> Color:
        clamped = max(0.0, min(1.0, float(value)))
        return (
            int(80 + 170 * clamped),
            int(70 + 40 * clamped),
            int(220 - 120 * clamped),
        )


__all__ = ["ComponentVisualizer", "ComponentToggleState"]

