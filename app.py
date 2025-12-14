"""Milestone 1 GUI runner with pygame + pygame_gui."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional, Tuple

import pygame
import pygame_gui

from core import (
    Simulator,
    load_scenario,
    save_snapshot,
    load_snapshot,
    save_scenario,
    RobotConfig,
    WorldConfig,
)
from low_level_mechanics.world import Pose2D
from low_level_mechanics.geometry import Polygon


ASSET_PATH = Path(__file__).parent


class SimpleTextEditor:
    """Very small text editor for controller code."""

    def __init__(self, rect: pygame.Rect, font: pygame.font.Font, text: str = "") -> None:
        self.rect = rect
        self.font = font
        self.lines = text.splitlines() or [""]
        self.cursor = [0, 0]  # line, col
        self.has_focus = False

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.has_focus = self.rect.collidepoint(event.pos)
        if not self.has_focus:
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self._backspace()
            elif event.key == pygame.K_RETURN:
                self._newline()
            elif event.key == pygame.K_TAB:
                self._insert("    ")
            elif event.unicode:
                self._insert(event.unicode)

    def _insert(self, text: str) -> None:
        line = self.lines[self.cursor[0]]
        before = line[: self.cursor[1]]
        after = line[self.cursor[1] :]
        self.lines[self.cursor[0]] = before + text + after
        self.cursor[1] += len(text)

    def _newline(self) -> None:
        line = self.lines[self.cursor[0]]
        before = line[: self.cursor[1]]
        after = line[self.cursor[1] :]
        self.lines[self.cursor[0]] = before
        self.lines.insert(self.cursor[0] + 1, after)
        self.cursor = [self.cursor[0] + 1, 0]

    def _backspace(self) -> None:
        if self.cursor == [0, 0]:
            return
        line = self.lines[self.cursor[0]]
        if self.cursor[1] > 0:
            self.lines[self.cursor[0]] = line[: self.cursor[1] - 1] + line[self.cursor[1] :]
            self.cursor[1] -= 1
        else:
            prev_line = self.lines[self.cursor[0] - 1]
            self.cursor[1] = len(prev_line)
            self.lines[self.cursor[0] - 1] = prev_line + line
            del self.lines[self.cursor[0]]
            self.cursor[0] -= 1

    def text(self) -> str:
        return "\n".join(self.lines)

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, (25, 25, 25), self.rect)
        pygame.draw.rect(surface, (70, 70, 70), self.rect, 1)
        x, y = self.rect.topleft
        line_height = self.font.get_height() + 2
        for i, line in enumerate(self.lines):
            if y + i * line_height > self.rect.bottom:
                break
            txt_surf = self.font.render(line, True, (220, 220, 220))
            surface.blit(txt_surf, (x + 4, y + i * line_height + 2))
        if self.has_focus:
            cursor_x = x + 4 + self.font.size(self.lines[self.cursor[0]][: self.cursor[1]])[0]
            cursor_y = y + self.cursor[0] * line_height + 2
            pygame.draw.line(surface, (240, 200, 120), (cursor_x, cursor_y), (cursor_x, cursor_y + line_height - 4), 2)


class SimulationApp:
    def __init__(self, scenario_path: Path) -> None:
        pygame.init()
        pygame.display.set_caption("Robotics Sim (Milestone 1)")
        self.window_size = (1200, 720)
        self.window_surface = pygame.display.set_mode(self.window_size)
        self.manager = pygame_gui.UIManager(self.window_size)
        self.clock = pygame.time.Clock()
        self.running = True
        self.playing = True
        self.scenario_path = scenario_path

        self.world_cfg: WorldConfig
        self.robot_cfg: RobotConfig
        self.world_cfg, self.robot_cfg = load_scenario(self.scenario_path)
        self.sim = Simulator()
        self.sim.load(self.scenario_path, self.world_cfg, self.robot_cfg, top_down=True, ignore_terrain=True)

        self.viewport_rect = pygame.Rect(20, 70, self.window_size[0] - 460, self.window_size[1] - 90)
        self.add_point_mode: bool = False

        self._build_ui()
        self.code_editor = self._load_editor()

    def _build_ui(self) -> None:
        self.btn_play = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((20, 20), (80, 30)), text="Pause", manager=self.manager
        )
        self.btn_step = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((110, 20), (80, 30)), text="Step", manager=self.manager
        )
        self.btn_snap = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((200, 20), (140, 30)), text="Save snapshot", manager=self.manager
        )
        self.btn_load_snap = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((350, 20), (140, 30)), text="Load snapshot", manager=self.manager
        )
        self.btn_reload = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((500, 20), (140, 30)), text="Reload code", manager=self.manager
        )
        self.btn_save_code = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((650, 20), (140, 30)), text="Save code", manager=self.manager
        )
        body_names = list(self.sim.bodies.keys())
        self.body_dropdown = pygame_gui.elements.UIDropDownMenu(
            options_list=body_names or ["<none>"],
            starting_option=body_names[0] if body_names else "<none>",
            relative_rect=pygame.Rect((20, 60), (160, 30)),
            manager=self.manager,
        )
        self.btn_add_point = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((190, 60), (140, 30)), text="Add point", manager=self.manager
        )
        self.btn_save_robot = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((340, 60), (140, 30)), text="Save robot", manager=self.manager
        )

    def _load_editor(self) -> SimpleTextEditor:
        controller_path = self.scenario_path / "controller.py"
        text = controller_path.read_text(encoding="utf-8") if controller_path.exists() else ""
        font = pygame.font.Font(pygame.font.get_default_font(), 16)
        rect = pygame.Rect(self.window_size[0] - 420, 70, 400, self.window_size[1] - 90)
        return SimpleTextEditor(rect, font, text)

    def _save_editor(self) -> None:
        controller_path = self.scenario_path / "controller.py"
        controller_path.write_text(self.code_editor.text(), encoding="utf-8")

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.running = False
                if event.type == pygame.MOUSEBUTTONDOWN and self.add_point_mode:
                    self._handle_add_point(event.pos)
                self._handle_ui_event(event)
                self.code_editor.handle_event(event)
                self.manager.process_events(event)
            self.manager.update(dt)
            if self.playing:
                steps = max(1, int(dt / self.sim.dt))
                for _ in range(steps):
                    self.sim.step(self.sim.dt)
            self._draw()
        pygame.quit()

    def _handle_ui_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame_gui.UI_BUTTON_PRESSED:
            return
        if event.ui_element == self.btn_play:
            self.playing = not self.playing
            self.btn_play.set_text("Play" if not self.playing else "Pause")
        elif event.ui_element == self.btn_step:
            self.playing = False
            self.btn_play.set_text("Play")
            self.sim.step(self.sim.dt)
        elif event.ui_element == self.btn_snap:
            self._save_snapshot()
        elif event.ui_element == self.btn_load_snap:
            self._load_latest_snapshot()
        elif event.ui_element == self.btn_reload:
            self.sim.reload_controller(keep_previous=False)
        elif event.ui_element == self.btn_save_code:
            self._save_editor()
            self.sim.reload_controller(keep_previous=False)
        elif event.ui_element == self.btn_add_point:
            self.add_point_mode = True
        elif event.ui_element == self.btn_save_robot:
            self._save_robot()

    def _save_snapshot(self) -> None:
        snap = self.sim.snapshot()
        snap_dir = self.scenario_path / "snapshots"
        snap_path = snap_dir / f"snap_{self.sim.step_index:06d}.json"
        save_snapshot(snap_path, snap)
        print(f"Saved snapshot to {snap_path}")

    def _load_latest_snapshot(self) -> None:
        snap_dir = self.scenario_path / "snapshots"
        if not snap_dir.exists():
            return
        snaps = sorted(snap_dir.glob("snap_*.json"))
        if not snaps:
            return
        snap = load_snapshot(snaps[-1])
        self.sim.apply_snapshot(snap)
        print(f"Loaded snapshot {snaps[-1].name}")

    def _draw(self) -> None:
        self.window_surface.fill((18, 18, 18))
        # Viewport area
        pygame.draw.rect(self.window_surface, (10, 10, 10), self.viewport_rect)
        pygame.draw.rect(self.window_surface, (80, 80, 80), self.viewport_rect, 1)
        self._draw_world(self.viewport_rect, self.window_surface)
        self.code_editor.draw(self.window_surface)
        self.manager.draw_ui(self.window_surface)
        pygame.display.update()

    def _world_to_screen(
        self, point: Tuple[float, float], viewport: pygame.Rect, scale: float = 400.0
    ) -> Tuple[int, int]:
        cx = viewport.x + viewport.width // 2
        cy = viewport.y + viewport.height // 2
        return (int(cx + point[0] * scale), int(cy - point[1] * scale))

    def _draw_world(self, viewport: pygame.Rect, surface: pygame.Surface) -> None:
        scale = 400.0
        for body in self.sim.bodies.values():
            color = getattr(body.material, "custom", {}).get("color", None) or getattr(body.material, "reflectivity", 0.3)
            if isinstance(color, (tuple, list)) and len(color) == 3:
                draw_color = color
            else:
                shade = int(100 + 100 * getattr(body.material, "reflectivity", 0.3))
                draw_color = (shade, shade, shade)
            if isinstance(body.shape, Polygon):
                verts = body.shape._world_vertices(body.pose)
                pts = [self._world_to_screen(v, viewport, scale) for v in verts]
                pygame.draw.polygon(surface, draw_color, pts, 0)
                pygame.draw.polygon(surface, (30, 30, 30), pts, 1)
        # basic wheel arrows from motor commands
        for motor in self.sim.motors.values():
            parent = motor.parent
            if not parent:
                continue
            pose = parent.pose.compose(motor.mount_pose)
            start = self._world_to_screen((pose.x, pose.y), viewport, scale)
            direction = (math.cos(pose.theta), math.sin(pose.theta))
            length = 0.05 + abs(motor.last_command) * 0.1
            end_world = (pose.x + direction[0] * length, pose.y + direction[1] * length)
            end = self._world_to_screen(end_world, viewport, scale)
            color = (0, 200, 120) if motor.last_command >= 0 else (200, 80, 80)
            pygame.draw.line(surface, color, start, end, 3)
            pygame.draw.circle(surface, color, end, 4)

    def _handle_add_point(self, screen_pos: Tuple[int, int]) -> None:
        self.add_point_mode = False
        selected = self.body_dropdown.selected_option
        if not selected or selected == "<none>":
            return
        if not self.viewport_rect.collidepoint(screen_pos):
            return
        world_point = self._screen_to_world(screen_pos, self.viewport_rect, scale=400.0)
        body = self.sim.bodies.get(selected)
        if not body or not isinstance(body.shape, Polygon):
            return
        inv_pose = body.pose.inverse()
        local_point = inv_pose.transform_point(world_point)
        new_vertices = list(body.shape.vertices) + [local_point]
        body.shape = Polygon(new_vertices)
        # refresh robot cfg
        for cfg_body in self.robot_cfg.bodies:
            if cfg_body.name == selected:
                cfg_body.points = [(float(x), float(y)) for x, y in new_vertices]
                cfg_body.edges = [(i, (i + 1) % len(new_vertices)) for i in range(len(new_vertices))]
                break

    def _screen_to_world(self, pos: Tuple[int, int], viewport: pygame.Rect, scale: float = 400.0) -> Tuple[float, float]:
        cx = viewport.x + viewport.width // 2
        cy = viewport.y + viewport.height // 2
        wx = (pos[0] - cx) / scale
        wy = -(pos[1] - cy) / scale
        return (wx, wy)

    def _save_robot(self) -> None:
        save_scenario(self.scenario_path, self.world_cfg, self.robot_cfg)
        print("Saved robot to robot.json")


def main():
    scenario_path = ASSET_PATH / "scenarios" / "generic"
    app = SimulationApp(scenario_path)
    app.run()


if __name__ == "__main__":
    main()

