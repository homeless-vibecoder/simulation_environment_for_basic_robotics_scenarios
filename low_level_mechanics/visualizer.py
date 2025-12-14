"""Pygame-based visualizer for the low-level mechanics world with camera controls."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

try:  # pragma: no cover - pygame import is environment specific
    import pygame
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "Pygame is required to use the low_level_mechanics.visualizer module."
    ) from exc

from .component_viz import ComponentToggleState, ComponentVisualizer
from .geometry import Circle, Polygon
from .world import World

Color = Tuple[int, int, int]
Point = Tuple[float, float]

DEFAULT_COLORS = {
    "default": (180, 180, 180),
    "movable": (70, 180, 255),
    "line": (20, 20, 20),
}
NAMED_COLORS = {
    "black": (10, 10, 10),
    "white": (235, 235, 235),
    "gray": (120, 120, 120),
    "red": (220, 70, 70),
    "green": (80, 200, 80),
    "blue": (70, 120, 220),
    "yellow": (230, 200, 80),
}


@dataclass
class OverlayPoint:
    position: Point
    color: Color = (255, 95, 95)
    radius: int = 6
    label: Optional[str] = None


@dataclass
class OverlaySegment:
    start: Point
    end: Point
    color: Color = (255, 255, 0)
    width: int = 2


@dataclass
class OverlayData:
    points: List[OverlayPoint] = field(default_factory=list)
    segments: List[OverlaySegment] = field(default_factory=list)

    def extend_points(self, points: Iterable[OverlayPoint]) -> None:
        self.points.extend(points)

    def extend_segments(self, segments: Iterable[OverlaySegment]) -> None:
        self.segments.extend(segments)


class Visualizer:
    """Interactive top-down renderer for a `World` with multiple camera modes."""

    CAMERA_WORLD = "world"
    CAMERA_ROBOT = "robot"

    def __init__(
        self,
        *,
        window_size: Tuple[int, int] = (900, 600),
        pixels_per_meter: float = 260.0,
        background_color: Color = (20, 20, 26),
        target_fps: int = 60,
        sim_dt: Optional[float] = None,
        follow_robot: Optional[str] = None,
        rotate_with_robot: bool = False,
        camera_lag: float = 0.15,
        zoom_limits: Optional[Tuple[float, float]] = None,
    ) -> None:
        pygame.init()
        pygame.display.set_caption("Robotics Simulation Visualizer")
        self.surface = pygame.display.set_mode(window_size)
        self.window_size = window_size
        self.base_center = (window_size[0] / 2.0, window_size[1] / 2.0)
        self.scale = pixels_per_meter
        min_zoom, max_zoom = (
            zoom_limits
            if zoom_limits
            else (pixels_per_meter * 0.25, pixels_per_meter * 4.0)
        )
        self.min_zoom = min_zoom
        self.max_zoom = max_zoom
        self.background_color = background_color
        self.target_fps = target_fps
        self.sim_dt = sim_dt
        self._font = pygame.font.SysFont("Arial", 16)
        self._clock = pygame.time.Clock()
        self.camera_mode = self.CAMERA_ROBOT
        self.follow_robot_name = follow_robot
        self.rotate_with_robot = rotate_with_robot
        self.camera_lag = max(0.0, min(1.0, camera_lag))
        self._camera_pos: Point = (0.0, 0.0)
        self._camera_target_pos: Point = (0.0, 0.0)
        self._camera_angle: float = 0.0
        self._camera_target_angle: float = 0.0
        self._component_viz = ComponentVisualizer(self.surface)
        self._component_toggles = ComponentToggleState()
        self.show_components = True
        self.show_sensor_details = False
        self.show_numeric_labels = False

    def run(
        self,
        world: World,
        *,
        step_callback: Optional[Callable[[World, float], None]] = None,
        overlay_provider: Optional[Callable[[World], Optional[OverlayData]]] = None,
        instructions: Sequence[str] = (),
    ) -> None:
        paused = False
        step_once = False
        running = True
        show_help = False
        dt = self.sim_dt or world.default_dt

        while running:
            robot_cycle = self._collect_robot_names(world)
            if robot_cycle:
                if self.follow_robot_name not in robot_cycle:
                    self.follow_robot_name = robot_cycle[0]
            else:
                self.follow_robot_name = None

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_q):
                        running = False
                    elif event.key == pygame.K_SPACE:
                        paused = not paused
                    elif event.key in (pygame.K_RIGHT, pygame.K_PERIOD):
                        step_once = True
                    elif event.key == pygame.K_h:
                        show_help = not show_help
                    elif event.key == pygame.K_1:
                        self.camera_mode = self.CAMERA_WORLD
                    elif event.key == pygame.K_2:
                        self.camera_mode = self.CAMERA_ROBOT
                    elif event.key == pygame.K_TAB and robot_cycle:
                        current_index = (
                            robot_cycle.index(self.follow_robot_name)
                            if self.follow_robot_name in robot_cycle
                            else -1
                        )
                        self.follow_robot_name = robot_cycle[(current_index + 1) % len(robot_cycle)]
                    elif event.key == pygame.K_r:
                        self.rotate_with_robot = not self.rotate_with_robot
                    elif event.key in (pygame.K_LEFTBRACKET, pygame.K_MINUS, pygame.K_KP_MINUS):
                        self._adjust_zoom(1 / 1.15)
                    elif event.key in (pygame.K_RIGHTBRACKET, pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                        self._adjust_zoom(1.15)
                    elif event.key == pygame.K_v:
                        self.show_components = not self.show_components
                    elif event.key == pygame.K_b:
                        self.show_sensor_details = not self.show_sensor_details
                    elif event.key == pygame.K_n:
                        self.show_numeric_labels = not self.show_numeric_labels

            should_step = (not paused) or step_once
            if should_step:
                if step_callback:
                    step_callback(world, dt)
                world.step(dt)
                step_once = False

            overlays = overlay_provider(world) if overlay_provider else None
            self._draw_frame(world, overlays, paused, instructions, show_help)
            pygame.display.flip()
            self._clock.tick(self.target_fps)

        pygame.quit()

    def _draw_frame(
        self,
        world: World,
        overlays: Optional[OverlayData],
        paused: bool,
        instructions: Sequence[str],
        show_help: bool,
    ) -> None:
        self.surface.fill(self.background_color)
        self._update_camera(world)
        self._component_toggles = ComponentToggleState(
            icons=self.show_components,
            sensor_details=self.show_sensor_details,
            numeric_labels=self.show_numeric_labels,
        )
        for obj in world:
            self._draw_object(obj)
        if overlays:
            self._draw_overlays(overlays)
        self._draw_status(world, paused, instructions, show_help)

    def _draw_object(self, obj) -> None:
        color = self._resolve_color(obj)
        if isinstance(obj.shape, Circle):
            center_px = self._world_to_screen((obj.pose.x, obj.pose.y))
            radius_px = max(1, int(obj.shape.radius * self.scale))
            pygame.draw.circle(self.surface, color, center_px, radius_px, 0)
            if obj.can_move:
                heading = obj.pose.transform_point((obj.shape.radius, 0.0))
                pygame.draw.line(
                    self.surface,
                    (255, 255, 255),
                    center_px,
                    self._world_to_screen(heading),
                    2,
                )
        elif isinstance(obj.shape, Polygon):
            points = [self._world_to_screen(obj.pose.transform_point(v)) for v in obj.shape.vertices]
            pygame.draw.polygon(self.surface, color, points, 0)
        else:
            bbox = obj.bounding_box()
            top_left = self._world_to_screen((bbox.min_x, bbox.max_y))
            width = max(1, int((bbox.max_x - bbox.min_x) * self.scale))
            height = max(1, int((bbox.max_y - bbox.min_y) * self.scale))
            pygame.draw.rect(self.surface, color, (*top_left, width, height), 1)
        self._component_viz.draw_for_object(
            obj,
            world_to_screen=self._world_to_screen,
            scale=self.scale,
            font=self._font,
            toggles=self._component_toggles,
        )

    def _draw_overlays(self, overlays: OverlayData) -> None:
        for pt in overlays.points:
            screen_pt = self._world_to_screen(pt.position)
            pygame.draw.circle(self.surface, pt.color, screen_pt, pt.radius)
            if pt.label:
                text = self._font.render(pt.label, True, pt.color)
                self.surface.blit(text, (screen_pt[0] + 6, screen_pt[1] - 12))
        for seg in overlays.segments:
            pygame.draw.line(
                self.surface,
                seg.color,
                self._world_to_screen(seg.start),
                self._world_to_screen(seg.end),
                seg.width,
            )

    def _draw_status(
        self, world: World, paused: bool, instructions: Sequence[str], show_help: bool
    ) -> None:
        cam_desc = self._camera_status()
        status = (
            f"t={world.time:.2f}s  step={world.step_index}  "
            f"mode={'PAUSED' if paused else 'PLAYING'}  cam={cam_desc}"
        )
        self.surface.blit(self._font.render(status, True, (240, 240, 240)), (8, 8))
        base_y = 30
        if show_help:
            help_lines = [
                "SPACE: play/pause",
                "RIGHT or .: step once",
                "TAB: cycle follow robot",
                "1: world view   2: robot view",
                "R: toggle follow rotation",
                "[ / ] : zoom out / in",
                "V: toggle component icons",
                "B: toggle sensor overlays",
                "N: toggle numeric readouts",
                "Q / ESC: quit",
                "H: hide help",
                *instructions,
            ]
        else:
            help_lines = ["H: show controls"]
        for line in help_lines:
            self.surface.blit(self._font.render(line, True, (200, 200, 200)), (8, base_y))
            base_y += 18

    def _world_to_screen(self, point: Point) -> Tuple[int, int]:
        px = point[0] - self._camera_pos[0]
        py = point[1] - self._camera_pos[1]
        if self.rotate_with_robot and self._camera_angle:
            cos_t = math.cos(-self._camera_angle)
            sin_t = math.sin(-self._camera_angle)
            px, py = (
                px * cos_t - py * sin_t,
                px * sin_t + py * cos_t,
            )
        x = self.base_center[0] + px * self.scale
        y = self.base_center[1] - py * self.scale
        return int(x), int(y)

    def _collect_robot_names(self, world: World) -> List[str]:
        return [obj.name for obj in world if getattr(obj, "can_move", False)]

    def _get_follow_robot(self, world: World):
        if not self.follow_robot_name:
            return None
        try:
            return world.get_object(self.follow_robot_name)
        except KeyError:
            return None

    def _update_camera(self, world: World) -> None:
        if self.camera_mode == self.CAMERA_WORLD:
            target_pos = (0.0, 0.0)
            target_angle = 0.0
            alpha = 1.0
        else:
            robot = self._get_follow_robot(world)
            if robot:
                target_pos = (robot.pose.x, robot.pose.y)
                target_angle = robot.pose.theta if self.rotate_with_robot else 0.0
            else:
                target_pos = (0.0, 0.0)
                target_angle = 0.0
            alpha = self.camera_lag if self.camera_lag > 0 else 1.0
        self._camera_pos = self._lerp_point(self._camera_pos, target_pos, alpha)
        self._camera_angle = self._lerp_angle(self._camera_angle, target_angle, alpha)

    def _camera_status(self) -> str:
        if self.camera_mode == self.CAMERA_WORLD:
            return "world"
        if self.follow_robot_name:
            suffix = " (rot)" if self.rotate_with_robot else ""
            return f"robot:{self.follow_robot_name}{suffix}"
        return "robot:<none>"

    def _adjust_zoom(self, factor: float) -> None:
        new_scale = self.scale * factor
        self.scale = max(self.min_zoom, min(self.max_zoom, new_scale))

    @staticmethod
    def _lerp(a: float, b: float, alpha: float) -> float:
        alpha = max(0.0, min(1.0, alpha))
        return a + (b - a) * alpha

    def _lerp_point(self, current: Point, target: Point, alpha: float) -> Point:
        return (
            self._lerp(current[0], target[0], alpha),
            self._lerp(current[1], target[1], alpha),
        )

    def _lerp_angle(self, current: float, target: float, alpha: float) -> float:
        alpha = max(0.0, min(1.0, alpha))
        diff = (target - current + math.pi) % (2 * math.pi) - math.pi
        return current + diff * alpha

    def _resolve_color(self, obj) -> Color:
        raw = obj.material.custom.get("color") if hasattr(obj.material, "custom") else None
        if raw is None:
            raw = obj.metadata.get("color") if hasattr(obj, "metadata") else None
        color: Optional[Color]
        if isinstance(raw, str):
            color = NAMED_COLORS.get(raw.lower())
        elif isinstance(raw, Sequence) and len(raw) >= 3:
            color = tuple(int(min(255, max(0, c))) for c in raw[:3])  # type: ignore[assignment]
        else:
            color = None
        if color is None:
            color = DEFAULT_COLORS["movable" if getattr(obj, "can_move", False) else "default"]
        return color


__all__ = ["Visualizer", "OverlayData", "OverlayPoint", "OverlaySegment"]
