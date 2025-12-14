"""Scenario runner app: pick a scenario, run sim, edit controller code, snapshots."""
from __future__ import annotations

import csv
import json
import math
import sys
import textwrap
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Callable, Set, Tuple

import pygame
import pygame_gui
from pygame_gui.windows import UIFileDialog

sys.path.append(str(Path(__file__).resolve().parent.parent))

from core import load_scenario, save_scenario, load_robot_design, Simulator, save_snapshot, load_snapshot  # noqa: E402
from core.config import WorldConfig, RobotConfig  # noqa: E402
from core.controller_store import (  # noqa: E402
    ControllerDefinition,
    build_controller_code,
    load_controller_definition,
    save_controller_definition,
    list_controllers,
    controller_path,
)
from apps.help_content import (  # noqa: E402
    HELP_TOPICS,
    CAPTURE_MENU_LABELS,
    ROUNDING_DIGITS,
    serialize_help_topics,
    serialize_capture_menu,
)
from apps.shared_ui import list_scenarios, SimpleTextEditor, world_to_screen, screen_to_world, HoverMenu  # noqa: E402
from low_level_mechanics.geometry import Polygon  # noqa: E402


def frange(start: float, stop: float, step: float):
    x = start
    while x <= stop + 1e-9:
        yield x
        x += step


class _ConsoleTee:
    """Capture stdout while mirroring to original."""

    def __init__(self, original, sink: Callable[[str], None]) -> None:
        self.original = original
        self.sink = sink

    def write(self, data: str) -> None:
        try:
            self.original.write(data)
        except Exception:
            pass
        self.sink(data)

    def flush(self) -> None:
        try:
            self.original.flush()
        except Exception:
            pass


@dataclass
class DockItem:
    id: str
    title: str
    rect: pygame.Rect
    dock: str  # "floating" | "left" | "right" | "bottom"
    visible: bool = True
    min_size: Tuple[int, int] = (260, 200)
    z: int = 0


@dataclass
class ControllerTabSpec:
    key: str
    title: str
    desc: str


class TabbedControllerEditor:
    """Multi-tab wrapper around SimpleTextEditor for controller sections."""

    def __init__(self, rect: pygame.Rect, font: pygame.font.Font, tabs: List[ControllerTabSpec]) -> None:
        self.rect = rect
        self.font = font
        self.tab_font = pygame.font.Font(pygame.font.get_default_font(), 15)
        self.desc_font = pygame.font.Font(pygame.font.get_default_font(), 13)
        self.tabs = tabs
        self.active = tabs[2].key if len(tabs) >= 3 else (tabs[0].key if tabs else "")
        self.editors: Dict[str, SimpleTextEditor] = {spec.key: SimpleTextEditor(rect, font, "") for spec in tabs}
        self.help_text: str = ""
        self.preview_text: str = ""
        self.context_text: str = ""
        self.show_helpers: bool = False
        self._toggle_rect: Optional[pygame.Rect] = None
        self.snippets: List[Tuple[str, str]] = [
            ("Read sensor", "dist = sensors.get('front_distance')\nif dist is not None:\n    pass\n"),
            ("Set motor", "motor = self.sim.motors.get('left_motor')\nif motor:\n    motor.command(0.3, self.sim, dt)\n"),
            ("Use dt", "self.integral += error * dt\n"),
        ]
        self.tab_rects: Dict[str, pygame.Rect] = {}
        self.snippet_rects: List[Tuple[pygame.Rect, str]] = []

    def set_rect(self, rect: pygame.Rect) -> None:
        self.rect = rect
        for editor in self.editors.values():
            editor.rect = rect

    def set_content(self, sections: Dict[str, str], help_text: str = "", preview: str = "") -> None:
        for key, editor in self.editors.items():
            if key == "help":
                editor.set_text(help_text or "")
                continue
            editor.set_text(sections.get(key, ""))
        self.help_text = help_text or ""
        self.preview_text = preview

    def content(self) -> Tuple[Dict[str, str], str]:
        sections: Dict[str, str] = {}
        for key, editor in self.editors.items():
            if key == "help":
                continue
            sections[key] = editor.text()
        help_text = self.editors.get("help").text() if "help" in self.editors else self.help_text
        return sections, help_text

    def has_focus(self) -> bool:
        active_editor = self.editors.get(self.active)
        return bool(active_editor and active_editor.has_focus)

    def _tab_height(self) -> int:
        return 30

    def _desc_height(self) -> int:
        return 52

    def _compute_layout(self) -> Tuple[int, pygame.Rect]:
        tab_h = self._tab_height()
        desc_h = self._desc_height()
        inner = pygame.Rect(self.rect.x, self.rect.y + tab_h + desc_h, self.rect.width, max(10, self.rect.height - tab_h - desc_h))
        return tab_h, inner

    def _maybe_insert_snippet(self, label: str) -> None:
        if not self.snippets:
            return
        for snippet_label, snippet_body in self.snippets:
            if snippet_label == label:
                editor = self.editors.get(self.active)
                if editor:
                    text = editor.text()
                    joiner = "\n\n" if text.strip() else ""
                    editor.set_text(text + (joiner if not text.endswith("\n") else "\n") + snippet_body)
                break

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._toggle_rect and self._toggle_rect.collidepoint(event.pos):
                self.show_helpers = not self.show_helpers
                return
            # Tabs
            for key, rect in self.tab_rects.items():
                if rect.collidepoint(event.pos):
                    self.active = key
                    return
            # Snippet buttons
            if self.show_helpers:
                for rect, label in self.snippet_rects:
                    if rect.collidepoint(event.pos):
                        self._maybe_insert_snippet(label)
                        return
        if self.active == "help":
            return
        active_editor = self.editors.get(self.active)
        if active_editor:
            active_editor.handle_event(event)

    def draw(self, surface: pygame.Surface) -> None:
        tab_h, inner_rect = self._compute_layout()
        # Tab bar
        self.tab_rects.clear()
        x = self.rect.x
        for spec in self.tabs:
            label = spec.title
            w = self.tab_font.size(label)[0] + 28
            rect = pygame.Rect(x, self.rect.y, w, tab_h)
            self.tab_rects[spec.key] = rect
            active = spec.key == self.active
            bg = (52, 56, 64) if active else (32, 36, 42)
            pygame.draw.rect(surface, bg, rect, border_radius=6)
            pygame.draw.rect(surface, (90, 110, 130), rect, 1, border_radius=6)
            surface.blit(self.tab_font.render(label, True, (230, 234, 240)), (rect.x + 10, rect.y + 6))
            x += w + 6

        # Description + context + snippets row
        desc_rect = pygame.Rect(self.rect.x + 4, self.rect.y + tab_h + 4, self.rect.width - 8, self._desc_height() - 8)
        pygame.draw.rect(surface, (28, 30, 34), desc_rect, border_radius=6)
        spec_lookup = {spec.key: spec for spec in self.tabs}
        desc_lines: List[str] = []
        if self.active in spec_lookup:
            desc_lines.append(spec_lookup[self.active].desc)
        if self.context_text:
            desc_lines.append(self.context_text)
        for i, line in enumerate(desc_lines[:3]):
            surface.blit(self.desc_font.render(line, True, (200, 210, 220)), (desc_rect.x + 8, desc_rect.y + 4 + i * 16))
        # Toggle for helper/notes (hidden by default)
        btn_label = "Show notes/help" if not self.show_helpers else "Hide notes/help"
        btn_w = self.desc_font.size(btn_label)[0] + 12
        btn_rect = pygame.Rect(desc_rect.right - btn_w - 6, desc_rect.y + 6, btn_w, 20)
        self._toggle_rect = btn_rect
        pygame.draw.rect(surface, (40, 44, 52), btn_rect, border_radius=4)
        pygame.draw.rect(surface, (90, 110, 130), btn_rect, 1, border_radius=4)
        surface.blit(self.desc_font.render(btn_label, True, (210, 220, 230)), (btn_rect.x + 6, btn_rect.y + 2))

        # Snippet buttons (right aligned)
        self.snippet_rects = []
        if self.show_helpers:
            btn_x = desc_rect.right - 10
            btn_y = desc_rect.bottom - 24
            for label, _body in reversed(self.snippets):
                btn_w = self.desc_font.size(label)[0] + 14
                btn_x -= btn_w + 6
                rect = pygame.Rect(btn_x, btn_y, btn_w, 20)
                self.snippet_rects.append((rect, label))
                pygame.draw.rect(surface, (40, 44, 52), rect, border_radius=4)
                pygame.draw.rect(surface, (90, 110, 130), rect, 1, border_radius=4)
                surface.blit(self.desc_font.render(label, True, (200, 210, 220)), (rect.x + 6, rect.y + 2))
            self.snippet_rects = list(reversed(self.snippet_rects))

        # Editor region
        active_editor = self.editors.get(self.active)
        if self.active == "help":
            # Render help text as read-only
            if self.show_helpers:
                help_lines = (self.help_text or "").splitlines()
                help_lines = help_lines or ["Help is empty."]
                y = inner_rect.y + 4
                for line in help_lines:
                    surface.blit(self.desc_font.render(line, True, (210, 220, 230)), (inner_rect.x + 6, y))
                    y += 16
                if self.preview_text:
                    surface.blit(self.desc_font.render("Preview (generated code):", True, (210, 220, 230)), (inner_rect.x + 6, y + 8))
                    preview_lines = self.preview_text.splitlines()
                    for i, line in enumerate(preview_lines[:40]):
                        surface.blit(
                            self.desc_font.render(line, True, (170, 180, 190)),
                            (inner_rect.x + 10, y + 26 + i * 14),
                        )
            else:
                msg = "Notes/help hidden. Click 'Show notes/help' to view."
                surface.blit(self.desc_font.render(msg, True, (200, 210, 220)), (inner_rect.x + 6, inner_rect.y + 6))
        elif active_editor:
            active_editor.rect = inner_rect
            active_editor.draw(surface)


class RunnerApp:
    def __init__(self) -> None:
        pygame.init()
        # Enable key repeat for held keys (e.g., arrows, delete)
        pygame.key.set_repeat(300, 35)
        pygame.display.set_caption("Runner")
        self.window_size = (1280, 760)
        self.window_surface = pygame.display.set_mode(self.window_size, pygame.RESIZABLE)
        self.manager = pygame_gui.UIManager(self.window_size)
        self.clock = pygame.time.Clock()
        self.running = True
        self.playing = True
        # Track whether we paused because of a blocking error; logs may persist for context.
        self.error_paused = False
        # Keep the viewport overlay disabled by default; status/console carry error notices.
        self.show_error_overlay = False

        self.base_path = Path(__file__).resolve().parent.parent
        self.scenario_root = self.base_path / "scenarios"
        self.current_scenario_path: Optional[Path] = None
        self.scenario_entries = list_scenarios(self.scenario_root, with_metadata=True)
        self.scenario_lookup = {entry.id: entry for entry in self.scenario_entries}
        self.scenario_names = [entry.id for entry in self.scenario_entries]
        self.scenario_name = self.scenario_names[0] if self.scenario_names else None
        self.sim: Optional[Simulator] = None
        self.world_cfg: Optional[WorldConfig] = None
        self.robot_cfg: Optional[RobotConfig] = None
        self.active_robot_id: Optional[str] = None
        self.robot_roster: List[str] = []
        self.loaded_robots: List[object] = []
        self.scenario_description: Optional[str] = None
        self.scenario_thumbnail: Optional[pygame.Surface] = None
        self.scenario_thumbnail_path: Optional[Path] = None
        self._sim_time_accum = 0.0
        self.playback_rate: float = 1.0
        # Layout parameters
        self.viewport_min = 520
        self.panel_header_h = 28
        self.panel_padding = 8
        self.scale = 400.0
        self.offset = (0.0, 0.0)
        self.pan_active = False
        self.pan_start: Optional[Tuple[int, int]] = None
        self.view_options = {"grid": False, "motor_arrows": True, "path_trace": False}
        # Panel/docking state
        self.dock_items: Dict[str, DockItem] = {}
        self.panel_inner_rects: Dict[str, pygame.Rect] = {}
        self.dock_dragging: Optional[Tuple[str, Tuple[int, int]]] = None
        self.dock_resizing: Optional[Tuple[str, str, Tuple[int, int]]] = None
        self.dock_active_panel: Optional[str] = None
        self.dock_last_action: Optional[str] = None
        self.hover_menu: Optional[HoverMenu] = None
        self.top_down_mode: bool = True
        self.force_empty_world: bool = True
        self.panel_menu_open = False
        self.panel_menu_regions: Dict[str, pygame.Rect] = {}
        self.panel_menu_anchor = "right"
        self.dock_z_counter = 0
        self.panel_layout_path = self.base_path / "runner_layout.json"
        self.reposition_target: Optional[Tuple[float, float]] = None
        self.reposition_angle: float = 0.0
        self._stepped_this_frame = False
        self._manual_step_dt: float = 0.0
        self.robot_dragging = False
        self.robot_drag_start: Optional[Tuple[float, float]] = None
        self.robot_drag_center: Optional[Tuple[float, float]] = None
        self.robot_drag_theta: float = 0.0
        self.hover_robot_center: bool = False
        self.show_device_help = True
        self.pose_history: List[Tuple[float, float, float]] = []
        self.pose_redo: List[Tuple[float, float, float]] = []
        self.error_log: List[Dict[str, str]] = []
        self.console_lines: List[str] = []
        self._console_buffer: str = ""
        self.path_trace: List[Tuple[float, float]] = []
        self.live_state: Dict[str, Dict[str, object]] = {"motors": {}, "sensors": {}}
        self.logger_selected: Set[str] = set()
        self.logger_samples: List[Dict[str, object]] = []
        self.logger_enabled = False
        self.logger_interval = 1.0 / 30.0
        self.logger_duration = 15.0
        self._logger_timer = 0.0
        self._logger_elapsed = 0.0
        self.logger_status = "Logger idle"
        self.signal_hitboxes: Dict[str, pygame.Rect] = {}
        self.roster_hitboxes: Dict[str, pygame.Rect] = {}
        self.plot_data: Dict[str, List[Optional[float]]] = {}
        self.plot_selected_cols: Set[str] = set()
        self.plot_source: Optional[Path] = None
        self.plot_status: str = "No CSV loaded"
        self.plot_hitboxes: Dict[str, pygame.Rect] = {}
        self.plot_dialog: Optional[UIFileDialog] = None
        self.speed_slider_window: Optional[pygame_gui.elements.UIWindow] = None
        self.speed_slider: Optional[pygame_gui.elements.UIHorizontalSlider] = None
        self.speed_label: Optional[pygame_gui.elements.UILabel] = None
        self.robot_dialog: Optional[UIFileDialog] = None
        self.round_digits = ROUNDING_DIGITS
        self.help_topics = HELP_TOPICS
        self.help_open = False
        self.help_active_topic = self.help_topics[0]["id"] if self.help_topics else None
        self.help_scroll = 0
        self.help_scroll_min = 0
        self.help_last_content_height = 0
        self.help_nav_hitboxes: Dict[str, pygame.Rect] = {}
        self.help_content_rect: Optional[pygame.Rect] = None
        self.help_close_rect: Optional[pygame.Rect] = None
        self.capture_menu_labels = CAPTURE_MENU_LABELS
        self.snapshot_dialog: Optional[UIFileDialog] = None
        self.snapshot_dialog_mode: Optional[str] = None
        # Reserve bottom space in the right column for error drawer.
        self.viewport_rect = pygame.Rect(0, 0, 0, 0)  # set in _update_layout
        self.editor_rect = pygame.Rect(0, 0, 0, 0)
        self.controller_definition: Optional[ControllerDefinition] = None
        self.status_text = "Ctrl+S to save/apply controller"
        self._orig_stdout = sys.stdout
        sys.stdout = _ConsoleTee(sys.stdout, self._append_console)
        self.view_rotation: float = 0.0

        self._build_ui()
        self._init_dock_panels()
        self._init_hover_menu()
        self._load_panel_layout()
        self._update_layout()
        self.controller_editor = self._load_editor()
        self._load_controller_into_editor()
        self._load_sim()

    def _build_ui(self) -> None:
        self.dropdown = pygame_gui.elements.UIDropDownMenu(
            options_list=self.scenario_names or ["<none>"],
            starting_option=self.scenario_name or "<none>",
            relative_rect=pygame.Rect((20, 20), (200, 30)),
            manager=self.manager,
        )
        self.btn_reload_scenario = pygame_gui.elements.UIButton(
            pygame.Rect((230, 20), (120, 30)), "Load", manager=self.manager
        )
        self.btn_play = pygame_gui.elements.UIButton(
            pygame.Rect((360, 20), (80, 30)), "Pause", manager=self.manager
        )
        self.btn_step = pygame_gui.elements.UIButton(
            pygame.Rect((450, 20), (80, 30)), "Step", manager=self.manager
        )
        self.btn_reload_code = pygame_gui.elements.UIButton(
            pygame.Rect((840, 20), (120, 30)), "Reload code", manager=self.manager
        )
        self.btn_save_code = pygame_gui.elements.UIButton(
            pygame.Rect((970, 20), (120, 30)), "Save code", manager=self.manager
        )
        self.btn_format_code = pygame_gui.elements.UIButton(
            pygame.Rect((1100, 20), (100, 30)), "Format", manager=self.manager
        )
        self.btn_clear_errors = pygame_gui.elements.UIButton(
            pygame.Rect((0, 0), (180, 30)),  # positioned in _update_layout
            "Clear errors",
            manager=self.manager,
        )
        self.btn_toggle_panel = pygame_gui.elements.UIButton(
            pygame.Rect((0, 0), (210, 30)),  # positioned in _update_layout
            "Clear console",
            manager=self.manager,
        )
        # State/logging controls
        self.btn_logger_toggle = pygame_gui.elements.UIButton(
            pygame.Rect((0, 0), (140, 28)), "Start logging", manager=self.manager
        )
        self.btn_logger_export = pygame_gui.elements.UIButton(
            pygame.Rect((0, 0), (130, 28)), "Export log", manager=self.manager
        )
        self.dropdown_logger_rate = pygame_gui.elements.UIDropDownMenu(
            options_list=["120 Hz", "60 Hz", "30 Hz", "10 Hz"],
            starting_option="60 Hz",
            relative_rect=pygame.Rect((0, 0), (110, 28)),
            manager=self.manager,
        )
        self.dropdown_logger_duration = pygame_gui.elements.UIDropDownMenu(
            options_list=["5 s", "15 s", "60 s", "Unlimited"],
            starting_option="15 s",
            relative_rect=pygame.Rect((0, 0), (120, 28)),
            manager=self.manager,
        )
        # Hide old top-row buttons; hover menus will replace them.
        for btn in [
            self.dropdown,
            self.btn_reload_scenario,
            self.btn_play,
            self.btn_step,
            self.btn_reload_code,
            self.btn_save_code,
            self.btn_format_code,
        ]:
            btn.hide()

    def _init_dock_panels(self) -> None:
        w, h = self.window_size
        right_w = 420
        bottom_h = 260
        base_x = max(220, w - right_w - 20)
        self.dock_items = {
            "code": DockItem(
                "code",
                "Code",
                pygame.Rect(base_x, 70, right_w, max(360, h - 200)),
                "right",
                True,
                (320, 260),
            ),
            "devices": DockItem(
                "devices", "Devices", pygame.Rect(base_x, 70, right_w, 260), "right", True, (280, 200)
            ),
            "state": DockItem(
                "state", "State", pygame.Rect(base_x, 70, right_w, 320), "right", True, (320, 240)
            ),
            "logs": DockItem(
                "logs",
                "Logs",
                pygame.Rect(base_x, h - bottom_h - 40, right_w, bottom_h),
                "bottom",
                True,
                (280, 200),
            ),
            "console": DockItem(
                "console",
                "Console",
                pygame.Rect(base_x - right_w - 20, h - bottom_h - 40, right_w, bottom_h),
                "bottom",
                True,
                (280, 200),
            ),
            "plot": DockItem(
                "plot",
                "CSV Plot",
                pygame.Rect(base_x - right_w - 20, 70, right_w, 260),
                "floating",
                False,
                (300, 220),
            ),
        }
        for i, item in enumerate(self.dock_items.values()):
            item.z = i
        self.panel_inner_rects = {}

    def _init_hover_menu(self) -> None:
        # Initialize hover menu with the dynamic builder.
        self.hover_menu = None
        self._refresh_hover_menu()

    # Menu helpers (shared actions for hover menu)
    def _can_run(self) -> bool:
        if self.error_log:
            self.status_text = "Paused after error; clear errors before running" if self.error_paused else "Clear errors before running"
            return False
        if not self.sim:
            self.status_text = "Load a scenario before running"
            return False
        return True

    def _set_play_button(self, playing: bool) -> None:
        try:
            self.btn_play.set_text("Pause" if playing else "Play")
        except Exception:
            pass

    def _toggle_play(self) -> None:
        if not self._can_run():
            self.playing = False
            self._set_play_button(False)
            self._refresh_hover_menu()
            return
        resuming_from_error = self.error_paused
        self.error_paused = False
        self.playing = not self.playing
        if self.playing and resuming_from_error:
            self.status_text = "Running after error; check Logs for details"
        else:
            self.status_text = "Running" if self.playing else "Paused"
        self._set_play_button(self.playing)
        self._refresh_hover_menu()

    def _step_once(self) -> None:
        self._manual_step_dt = 0.0
        if not self._can_run():
            self.playing = False
            self._set_play_button(False)
            self._refresh_hover_menu()
            return
        self.playing = False
        self._set_play_button(False)
        if self.sim:
            try:
                step_dt = float(getattr(self.sim, "dt", 0.0) or 0.0)
                self.sim.step(step_dt)
                # Flag that we advanced so live state/logging update this frame.
                self._stepped_this_frame = True
                self._manual_step_dt = step_dt
                self._sim_time_accum = 0.0
                self.status_text = "Stepped once"
            except Exception:
                self._manual_step_dt = 0.0
                self._record_error("Simulation error", traceback.format_exc())
            self._report_controller_errors("Controller error")
        self._refresh_hover_menu()

    def _set_playback_rate(self, value: float) -> None:
        self.playback_rate = max(0.05, float(value))
        if self.speed_slider:
            self.speed_slider.set_current_value(self.playback_rate)
        if self.speed_label:
            self.speed_label.set_text(f"Speed: {self.playback_rate:.2f}x")
        self.status_text = f"Speed {self.playback_rate:.2f}x"
        self._refresh_hover_menu()

    def _set_active_robot(self, robot_id: str) -> None:
        if robot_id not in self.robot_roster:
            return
        self.active_robot_id = robot_id
        self.status_text = f"Active robot: {robot_id}"
        # Keep editor in sync with the selected robot's controller.
        self._load_controller_into_editor()
        self._refresh_hover_menu()

    def _cycle_active_robot(self, direction: int = 1) -> None:
        """Cycle active robot in roster; direction=1 next, -1 previous."""
        if not self.robot_roster:
            return
        if self.active_robot_id not in self.robot_roster:
            self._set_active_robot(self.robot_roster[0])
            return
        idx = self.robot_roster.index(self.active_robot_id)
        idx = (idx + direction) % len(self.robot_roster)
        self._set_active_robot(self.robot_roster[idx])

    def _open_speed_slider(self) -> None:
        if self.speed_slider_window:
            try:
                self.speed_slider_window.kill()
            except Exception:
                pass
        self.speed_slider_window = None
        self.speed_slider = None
        self.speed_label = None
        win_rect = pygame.Rect((self.window_size[0] - 320, 70), (280, 120))
        self.speed_slider_window = pygame_gui.elements.UIWindow(
            rect=win_rect,
            manager=self.manager,
            window_display_title="Sim speed",
            object_id="#speed_slider_window",
        )
        self.speed_slider = pygame_gui.elements.UIHorizontalSlider(
            relative_rect=pygame.Rect(16, 50, win_rect.width - 32, 20),
            start_value=self.playback_rate,
            value_range=(0.1, 4.0),
            manager=self.manager,
            container=self.speed_slider_window,
            object_id="#speed_slider",
        )
        self.speed_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(16, 20, win_rect.width - 32, 20),
            text=f"Speed: {self.playback_rate:.2f}x",
            manager=self.manager,
            container=self.speed_slider_window,
            object_id="#speed_slider_label",
        )

    def _reload_code(self) -> None:
        if self.sim:
            rid = self.active_robot_id
            self.sim.clear_controller_error(rid)
            self.sim.reload_controller(rid, keep_previous=False)
            self._report_controller_errors("Controller reload failed")
        self._refresh_hover_menu()

    def _select_scenario(self, name: str) -> None:
        self.scenario_name = name if name and name != "<none>" else None
        self._load_sim()
        self._refresh_hover_menu()

    def _toggle_panel(self, pid: str) -> None:
        item = self.dock_items.get(pid)
        if not item:
            return
        item.visible = not item.visible
        self._bump_panel(pid)
        self._update_layout()
        self._save_panel_layout()
        self._refresh_hover_menu()

    def _panel_header_rect(self, item: DockItem) -> pygame.Rect:
        return pygame.Rect(item.rect.x, item.rect.y, item.rect.width, self.panel_header_h)

    def _panel_close_rect(self, item: DockItem) -> pygame.Rect:
        return pygame.Rect(item.rect.right - 26, item.rect.y + 4, 20, 20)

    def _panel_resize_handles(self, item: DockItem) -> List[Tuple[str, pygame.Rect]]:
        size = 14
        r = item.rect
        handles = [
            ("tl", pygame.Rect(r.left - size // 2, r.top - size // 2, size, size)),
            ("tr", pygame.Rect(r.right - size // 2, r.top - size // 2, size, size)),
            ("bl", pygame.Rect(r.left - size // 2, r.bottom - size // 2, size, size)),
            ("br", pygame.Rect(r.right - size // 2, r.bottom - size // 2, size, size)),
            ("l", pygame.Rect(r.left - size // 2, r.centery - size // 2, size, size)),
            ("r", pygame.Rect(r.right - size // 2, r.centery - size // 2, size, size)),
            ("t", pygame.Rect(r.centerx - size // 2, r.top - size // 2, size, size)),
            ("b", pygame.Rect(r.centerx - size // 2, r.bottom - size // 2, size, size)),
        ]
        return handles

    def _panel_menu_rect(self) -> pygame.Rect:
        # Place below the top control row to avoid overlap with the Format button.
        y = 60
        if self.panel_menu_anchor == "left":
            return pygame.Rect(20, y, 180, 30)
        return pygame.Rect(self.window_size[0] - 200, y, 180, 30)

    def _panel_inner_rect(self, item: DockItem) -> pygame.Rect:
        pad = self.panel_padding
        inner_width = max(40, item.rect.width - 2 * pad)
        inner_height = max(32, item.rect.height - self.panel_header_h - pad)
        return pygame.Rect(item.rect.x + pad, item.rect.y + self.panel_header_h, inner_width, inner_height)

    def _panel_visible(self, panel_id: str) -> bool:
        item = self.dock_items.get(panel_id)
        return bool(item and item.visible)

    def _bump_panel(self, panel_id: str) -> None:
        item = self.dock_items.get(panel_id)
        if not item:
            return
        self.dock_z_counter += 1
        item.z = self.dock_z_counter

    def _load_panel_layout(self) -> None:
        if not self.panel_layout_path.exists():
            return
        try:
            data = json.loads(self.panel_layout_path.read_text(encoding="utf-8"))
        except Exception:
            return
        panels = data.get("panels", {})
        for pid, cfg in panels.items():
            item = self.dock_items.get(pid)
            if not item or not isinstance(cfg, dict):
                continue
            rect = cfg.get("rect")
            if rect and len(rect) == 4:
                item.rect = pygame.Rect(rect[0], rect[1], rect[2], rect[3])
            dock = cfg.get("dock")
            if dock in ("floating", "left", "right", "bottom"):
                item.dock = dock
            visible = cfg.get("visible")
            if isinstance(visible, bool):
                item.visible = visible

    def _save_panel_layout(self) -> None:
        try:
            payload = {
                "panels": {
                    pid: {
                        "rect": [item.rect.x, item.rect.y, item.rect.width, item.rect.height],
                        "dock": item.dock,
                        "visible": item.visible,
                    }
                    for pid, item in self.dock_items.items()
                }
            }
            self.panel_layout_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            # Persistence is best-effort; avoid crashing on save errors.
            pass

    def _load_editor(self) -> TabbedControllerEditor:
        # Prefer a compact monospace font for code
        font = (
            pygame.font.SysFont("Menlo", 15)
            or pygame.font.SysFont("Consolas", 15)
            or pygame.font.SysFont("DejaVu Sans Mono", 15)
            or pygame.font.Font(pygame.font.get_default_font(), 15)
        )
        rect = self.editor_rect
        tabs = [
            ControllerTabSpec("imports", "Imports", "Runs once; add modules/constants here."),
            ControllerTabSpec("init", "__init__", "Runs on reset; set state. self.sim & self.robot_id available."),
            ControllerTabSpec("step", "Step", "Runs each timestep. Inputs: sensors (dict), dt (seconds)."),
            ControllerTabSpec("helpers", "Helpers", "Optional class helpers (methods)."),
            ControllerTabSpec("help", "Help", "Docs, devices, generated preview."),
        ]
        return TabbedControllerEditor(rect, font, tabs)

    def _prime_logger_signals(self) -> None:
        self.logger_selected = set()
        if not self.sim:
            self.logger_samples.clear()
            return
        for name in self.sim.motors.keys():
            self.logger_selected.add(f"motor:{name}")
        for name in self.sim.sensors.keys():
            self.logger_selected.add(f"sensor:{name}")
        self.logger_samples.clear()
        self.logger_enabled = False
        self.logger_status = "Logger idle"
        self._logger_timer = 0.0
        self._logger_elapsed = 0.0

    def _update_layout(self) -> None:
        w, h = self.window_size
        margin = 20
        top_y = 70
        bottom_margin = 20

        dock_left = [i for i in self.dock_items.values() if i.visible and i.dock == "left"]
        dock_right = [i for i in self.dock_items.values() if i.visible and i.dock == "right"]
        dock_bottom = [i for i in self.dock_items.values() if i.visible and i.dock == "bottom"]

        left_w = max((max(i.rect.width, i.min_size[0]) for i in dock_left), default=0)
        right_w = max((max(i.rect.width, i.min_size[0]) for i in dock_right), default=0)
        bottom_h = max((max(i.rect.height, i.min_size[1]) for i in dock_bottom), default=0)

        max_side_space = max(0, w - 2 * margin - self.viewport_min)
        if left_w + right_w > max_side_space and (left_w + right_w) > 0:
            scale = max_side_space / (left_w + right_w)
            left_w = int(left_w * scale)
            right_w = int(right_w * scale)

        viewport_width = max(self.viewport_min, w - 2 * margin - left_w - right_w)
        viewport_height = max(260, h - top_y - bottom_margin - bottom_h)

        self.viewport_rect = pygame.Rect(margin + left_w, top_y, viewport_width, viewport_height)

        right_area = pygame.Rect(self.viewport_rect.right + 10, top_y, right_w, viewport_height) if right_w else pygame.Rect(0, 0, 0, 0)
        left_area = pygame.Rect(margin, top_y, left_w, viewport_height) if left_w else pygame.Rect(0, 0, 0, 0)
        bottom_area = (
            pygame.Rect(self.viewport_rect.x, self.viewport_rect.bottom + 10, viewport_width, bottom_h)
            if bottom_h
            else pygame.Rect(0, 0, 0, 0)
        )

        def stack_vertical(items: List[DockItem], area: pygame.Rect) -> None:
            if not items or area.width <= 0 or area.height <= 0:
                return
            gap = 8
            n = len(items)
            avail = max(0, area.height - gap * (n - 1))
            base_h = avail // n if n else 0
            y = area.y
            for idx, item in enumerate(items):
                height = max(item.min_size[1], base_h)
                max_allowed = area.y + area.height - y - gap * max(0, n - idx - 1)
                height = min(height, max_allowed)
                item.rect = pygame.Rect(area.x, y, max(area.width, item.min_size[0]), height)
                y += height + gap

        stack_vertical(sorted(dock_left, key=lambda d: d.z), left_area)
        stack_vertical(sorted(dock_right, key=lambda d: d.z), right_area)
        stack_vertical(sorted(dock_bottom, key=lambda d: d.z), bottom_area)

        # Keep floating panels inside the window bounds
        for item in self.dock_items.values():
            if not item.visible:
                continue
            if item.dock != "floating":
                continue
            item.rect.x = max(margin, min(item.rect.x, w - item.rect.width - margin))
            item.rect.y = max(top_y, min(item.rect.y, h - item.rect.height - bottom_margin))
            item.rect.width = max(item.min_size[0], min(item.rect.width, w - 2 * margin))
            item.rect.height = max(item.min_size[1], min(item.rect.height, h - top_y - bottom_margin))

        self.panel_inner_rects = {pid: self._panel_inner_rect(item) for pid, item in self.dock_items.items() if item.visible}
        self._position_panel_controls()

    def _position_panel_controls(self) -> None:
        controls = [
            self.btn_logger_toggle,
            self.btn_logger_export,
            self.dropdown_logger_rate,
            self.dropdown_logger_duration,
            self.btn_clear_errors,
            self.btn_toggle_panel,
        ]
        for c in controls:
            c.hide()

        # Code panel/editor placement
        code_inner = self.panel_inner_rects.get("code")
        if code_inner:
            self.editor_rect = code_inner
            if hasattr(self, "controller_editor"):
                self.controller_editor.set_rect(self.editor_rect)

        # State panel controls
        # Logs/errors
        if self._panel_visible("logs"):
            item = self.dock_items["logs"]
            self.btn_clear_errors.show()
            self.btn_clear_errors.set_relative_position((item.rect.x + 8, item.rect.y + self.panel_header_h + 4))

        # Console clear
        if self._panel_visible("console"):
            item = self.dock_items["console"]
            self.btn_toggle_panel.set_text("Clear console")
            self.btn_toggle_panel.show()
            self.btn_toggle_panel.set_relative_position((item.rect.x + 8, item.rect.y + self.panel_header_h + 4))

    def _panel_at_point(self, pos: Tuple[int, int]) -> Optional[DockItem]:
        visible_items = [i for i in self.dock_items.values() if i.visible]
        for item in sorted(visible_items, key=lambda d: d.z, reverse=True):
            if item.rect.collidepoint(pos):
                return item
        return None

    def _snap_panel(self, panel_id: Optional[str]) -> None:
        if not panel_id:
            return
        item = self.dock_items.get(panel_id)
        if not item:
            return
        margin = 20
        snap = 6
        w, h = self.window_size
        bottom_margin = 20
        near_left = 0 <= (item.rect.left - margin) <= snap
        near_right = 0 <= (w - margin - item.rect.right) <= snap
        near_bottom = 0 <= (h - bottom_margin - item.rect.bottom) <= snap
        if near_left:
            item.dock = "left"
        elif near_right:
            item.dock = "right"
        elif near_bottom:
            item.dock = "bottom"
        else:
            item.dock = "floating"

    def _handle_dock_mouse_down(self, event: pygame.event.Event) -> bool:
        if event.button != 1:
            return False
        target = self._panel_at_point(event.pos)
        if not target:
            return False
        if self._panel_close_rect(target).collidepoint(event.pos):
            target.visible = False
            self._save_panel_layout()
            self._update_layout()
            return True
        for mode, rect in self._panel_resize_handles(target):
            if rect.collidepoint(event.pos):
                self.dock_resizing = (target.id, mode, (event.pos[0], event.pos[1]))
                self.dock_active_panel = target.id
                self._bump_panel(target.id)
                self.dock_last_action = "resize"
                return True
        if self._panel_header_rect(target).collidepoint(event.pos):
            self.dock_dragging = (target.id, (event.pos[0] - target.rect.x, event.pos[1] - target.rect.y))
            self.dock_active_panel = target.id
            self._bump_panel(target.id)
            self.dock_last_action = "drag"
            return True
        return False

    def _handle_dock_mouse_motion(self, event: pygame.event.Event) -> bool:
        handled = False
        if self.dock_dragging:
            pid, offset = self.dock_dragging
            item = self.dock_items.get(pid)
            if item:
                item.dock = "floating"
                self.dock_last_action = "drag"
                item.rect.x = event.pos[0] - offset[0]
                item.rect.y = event.pos[1] - offset[1]
                handled = True
        if self.dock_resizing:
            pid, mode, start = self.dock_resizing
            item = self.dock_items.get(pid)
            if item:
                item.dock = "floating"
                self.dock_last_action = "resize"
                start_x, start_y = start
                dx = event.pos[0] - start[0]
                dy = event.pos[1] - start[1]
                r = item.rect
                min_w, min_h = item.min_size
                if "l" in mode:
                    new_x = r.x + dx
                    new_w = r.width - dx
                    if new_w >= min_w:
                        r.width = new_w
                        r.x = new_x
                        start_x = event.pos[0]
                if "r" in mode:
                    new_w = r.width + dx
                    if new_w >= min_w:
                        r.width = new_w
                        start_x = event.pos[0]
                if "t" in mode:
                    new_y = r.y + dy
                    new_h = r.height - dy
                    if new_h >= min_h:
                        r.height = new_h
                        r.y = new_y
                        start_y = event.pos[1]
                if "b" in mode:
                    new_h = r.height + dy
                    if new_h >= min_h:
                        r.height = new_h
                        start_y = event.pos[1]
                self.dock_resizing = (pid, mode, (start_x, start_y))
                handled = True
        if handled:
            self._update_layout()
        return handled

    def _handle_dock_mouse_up(self, event: pygame.event.Event) -> None:
        if event.button != 1:
            return
        active = self.dock_active_panel
        self.dock_dragging = None
        self.dock_resizing = None
        if active and self.dock_last_action == "drag":
            self._snap_panel(active)
            self._update_layout()
            self._save_panel_layout()
        self.dock_active_panel = None
        self.dock_last_action = None

    def _load_sim(self) -> None:
        if not self.scenario_name:
            return
        self._clear_errors()
        self._clear_console()
        self._clear_plot_data()
        self.world_cfg = None
        self.robot_cfg = None
        self.active_robot_id = None
        entry = self.scenario_lookup.get(self.scenario_name)
        scenario_path = entry.path if entry else (self.scenario_root / self.scenario_name)
        self.current_scenario_path = scenario_path
        try:
            scenario = load_scenario(scenario_path)
            self.world_cfg = scenario.world
            self.robot_cfg = scenario.primary_robot
            self.active_robot_id = scenario.robots[0].id if scenario.robots else None
            self.robot_roster = [r.id for r in scenario.robots]
            self.loaded_robots = scenario.robots
            self.scenario_description = scenario.descriptor.description
            self._load_thumbnail_for_scenario(self.scenario_lookup.get(self.scenario_name))
            self.sim = Simulator()
            self.sim.load(
                scenario_path,
                scenario.world,
                robots=scenario.robots,
                top_down=self.top_down_mode,
                ignore_terrain=self.force_empty_world,
            )
        except Exception:
            self._record_error("Scenario load failed", traceback.format_exc())
            return
        meta_suffix = self._scenario_status_suffix(scenario.descriptor)
        desc_suffix = f" — {meta_suffix}" if meta_suffix else ""
        self.status_text = f"Loaded scenario '{self.scenario_name}'{desc_suffix}"
        self._sim_time_accum = 0.0
        self.path_trace = []
        # refresh editor text
        self._load_controller_into_editor(scenario_path)
        self._report_controller_errors("Controller import failed")
        self._prime_logger_signals()
        pose = self._robot_pose_now()
        if pose:
            self.pose_history = [pose]
            self.pose_redo.clear()
        self._refresh_hover_menu()

    def _scenario_status_suffix(self, descriptor) -> str:
        """Build a compact status suffix from scenario metadata."""
        if not descriptor:
            return ""
        parts: List[str] = []
        desc = getattr(descriptor, "description", None)
        if desc:
            parts.append(str(desc))
        meta = getattr(descriptor, "metadata", {}) or {}
        tags = meta.get("tags")
        if isinstance(tags, (list, tuple)) and tags:
            parts.append("tags: " + ", ".join(str(t) for t in tags))
        seed = getattr(descriptor, "seed", None)
        if seed is not None:
            parts.append(f"seed {seed}")
        return " | ".join(parts)

    def _load_controller_into_editor(self, scenario_path: Optional[Path] = None) -> None:
        """Populate tabbed editor from structured controller definition."""
        if not hasattr(self, "controller_editor"):
            return
        scenario_dir = scenario_path or self.current_scenario_path
        if not scenario_dir:
            entry = self.scenario_lookup.get(self.scenario_name) if self.scenario_name else None
            scenario_dir = entry.path if entry else None
        if not scenario_dir:
            return
        module_name: Optional[str] = None
        if self.loaded_robots:
            target_id = self.active_robot_id or self.loaded_robots[0].id
            for robot in self.loaded_robots:
                if robot.id == target_id:
                    module_name = robot.controller or getattr(robot.config, "controller_module", None)
                    break
        if not module_name:
            module_name = self._current_controller_module()
        module_name = module_name or "controller"
        json_path = controller_path(scenario_dir, module_name)
        should_save_new = not json_path.exists()
        definition = load_controller_definition(scenario_dir, module_name)
        self.controller_definition = definition
        if should_save_new:
            try:
                save_controller_definition(scenario_dir, module_name, definition, backup=False)
            except Exception:
                pass
        preview = build_controller_code(definition)
        help_text = self._controller_help_text(definition, scenario_dir)
        self.controller_editor.set_content(definition.sections, help_text=help_text, preview=preview)
        self.controller_editor.active = "step"

    def _load_thumbnail_for_scenario(self, entry) -> None:
        # Thumbnails are disabled to avoid image-related hangs; keep fields cleared.
        self.scenario_thumbnail = None
        self.scenario_thumbnail_path = None

    def _reload_with_current_assets(self) -> None:
        """Reload sim using current in-memory world/robot without reloading files."""
        if not (self.scenario_name and self.world_cfg and self.robot_cfg):
            self.status_text = "Load a scenario before reloading"
            return
        self._clear_errors()
        self._clear_console()
        self._clear_plot_data()
        entry = self.scenario_lookup.get(self.scenario_name)
        scenario_path = entry.path if entry else (self.scenario_root / self.scenario_name)
        robots_arg = self.loaded_robots if self.loaded_robots else None
        try:
            self.sim = Simulator()
            self.sim.load(
                scenario_path,
                self.world_cfg,
                None if robots_arg else self.robot_cfg,
                robots=robots_arg,
                top_down=self.top_down_mode,
                ignore_terrain=self.force_empty_world,
            )
        except Exception:
            self._record_error("Scenario reload failed", traceback.format_exc())
            return
        desc_suffix = f" — {self.scenario_description}" if self.scenario_description else ""
        self.status_text = f"Reloaded scenario '{self.scenario_name}'{desc_suffix}"
        self._sim_time_accum = 0.0
        self.path_trace = []
        self._load_controller_into_editor(scenario_path)
        self._report_controller_errors("Controller import failed")
        self._prime_logger_signals()
        pose = self._robot_pose_now()
        if pose:
            self.pose_history = [pose]
            self.pose_redo.clear()
        self._refresh_hover_menu()

    def run(self) -> None:
        try:
            while self.running:
                dt = self.clock.tick(60) / 1000.0
                self._stepped_this_frame = False
                self._manual_step_dt = 0.0
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                        self.running = False
                    if event.type == pygame.KEYDOWN:
                        mods = getattr(event, "mod", 0)
                        code_focused = self._panel_visible("code") and self.controller_editor.has_focus()
                        # Editor-focused keys still go through, but we intercept global transport when editor unfocused.
                        if not code_focused:
                            if event.key == pygame.K_SPACE:
                                # toggle play/pause with error gating + menu refresh
                                self._toggle_play()
                            elif event.key == pygame.K_RIGHT:
                                # single step
                                self._step_once()
                            elif event.key == pygame.K_TAB:
                                direction = -1 if (mods & pygame.KMOD_SHIFT) else 1
                                self._cycle_active_robot(direction)
                        if event.key in (pygame.K_EQUALS, pygame.K_PLUS):
                            self._zoom(1.1)
                        if event.key in (pygame.K_MINUS, pygame.K_UNDERSCORE):
                            self._zoom(1.0 / 1.1)
                        if (event.key == pygame.K_z) and (mods & (pygame.KMOD_CTRL | pygame.KMOD_META | pygame.KMOD_GUI)):
                            if mods & pygame.KMOD_SHIFT:
                                self._redo_robot_pose()
                            else:
                                self._undo_robot_pose()
                        if event.key in (pygame.K_y,) and (mods & (pygame.KMOD_CTRL | pygame.KMOD_META | pygame.KMOD_GUI)):
                            self._redo_robot_pose()
                    if event.type == pygame.VIDEORESIZE:
                        self.window_size = (event.w, event.h)
                        self.window_surface = pygame.display.set_mode(self.window_size, pygame.RESIZABLE)
                        self.manager.set_window_resolution(self.window_size)
                        self._update_layout()
                    if event.type == pygame.MOUSEBUTTONDOWN:
                        if self._handle_help_mouse(event):
                            continue
                        if self.hover_menu and self.hover_menu.handle_event(event):
                            continue
                        if self._handle_dock_mouse_down(event):
                            continue
                        self._handle_state_click(event)
                        self._handle_plot_click(event)
                        self._handle_pan_start(event)
                    if event.type == pygame.MOUSEBUTTONUP:
                        if event.button in (1, 2, 3):
                            self.pan_active = False
                            self.pan_start = None
                        if event.button == 1:
                            self._finalize_reposition()
                            self._handle_dock_mouse_up(event)
                    if event.type == pygame.MOUSEMOTION:
                        if self.hover_menu:
                            self.hover_menu.handle_event(event)
                        if self._handle_dock_mouse_motion(event):
                            continue
                        self._handle_pan_motion(event)
                    if event.type == pygame.MOUSEWHEEL:
                        if self._handle_help_mouse(event):
                            continue
                        self._handle_scroll(event)
                    if event.type == pygame.KEYDOWN:
                        mods = getattr(event, "mod", 0)
                        if event.key == pygame.K_s and (mods & (pygame.KMOD_CTRL | pygame.KMOD_META | pygame.KMOD_GUI)):
                            self._save_code()
                        if event.key == pygame.K_f and (mods & (pygame.KMOD_CTRL | pygame.KMOD_META | pygame.KMOD_GUI)):
                            self._format_code()
                    # Always pass events to UI and editor so mouse clicks work
                    self.manager.process_events(event)
                    if self._panel_visible("code"):
                        self.controller_editor.handle_event(event)
                    self._handle_ui_event(event)
                self.manager.update(dt)
                sim_advanced = 0.0
                if self.playing and self.sim:
                    try:
                        sim_dt = self.sim.dt
                        # Accumulate time scaled by playback_rate with a cap to avoid runaway after stalls.
                        rate = max(0.05, min(self.playback_rate, 8.0))
                        self._sim_time_accum = min(self._sim_time_accum + dt * rate, sim_dt * 8.0 * rate)
                        steps = 0
                        while self._sim_time_accum >= sim_dt and steps < 8 * max(1, int(rate)):
                            self.sim.step(sim_dt)
                            self._sim_time_accum -= sim_dt
                            steps += 1
                        if steps:
                            sim_advanced = steps * sim_dt
                            self._stepped_this_frame = True
                    except Exception:
                        self._record_error("Simulation error", traceback.format_exc())
                self._report_controller_errors("Controller error")
                if self._stepped_this_frame and not sim_advanced and self._manual_step_dt:
                    sim_advanced = self._manual_step_dt
                self._manual_step_dt = 0.0
                # Only log when the sim actually advances
                self._update_live_state(sim_advanced if self._stepped_this_frame else 0.0, self._stepped_this_frame)
                if self.hover_menu:
                    self.hover_menu.update_hover(pygame.mouse.get_pos())
                self._draw()
        finally:
            self._save_panel_layout()
            sys.stdout = self._orig_stdout
        pygame.quit()

    def _handle_ui_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame_gui.UI_FILE_DIALOG_PATH_PICKED:
            if self.snapshot_dialog and event.ui_element == self.snapshot_dialog:
                path = Path(event.text)
                if self.snapshot_dialog_mode == "save":
                    self._save_snapshot_to_path(path)
                else:
                    self._load_snapshot_from_path(path)
                self.snapshot_dialog = None
                self.snapshot_dialog_mode = None
            elif self.plot_dialog and event.ui_element == self.plot_dialog:
                self._load_plot_from_path(Path(event.text))
                self.plot_dialog = None
            elif self.robot_dialog and event.ui_element == self.robot_dialog:
                self._load_robot_from_path(Path(event.text))
                self.robot_dialog = None
            return
        if event.type == pygame_gui.UI_WINDOW_CLOSE:
            if self.snapshot_dialog and event.ui_element == self.snapshot_dialog:
                self.snapshot_dialog = None
                self.snapshot_dialog_mode = None
            if self.speed_slider_window and event.ui_element == self.speed_slider_window:
                self.speed_slider_window = None
                self.speed_slider = None
                self.speed_label = None
            if self.robot_dialog and event.ui_element == self.robot_dialog:
                self.robot_dialog = None
                return
        if event.type == pygame_gui.UI_HORIZONTAL_SLIDER_MOVED and self.speed_slider and event.ui_element == self.speed_slider:
            self._set_playback_rate(float(event.value))
            return
        if event.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
            if event.ui_element == self.dropdown:
                self.scenario_name = event.text if event.text != "<none>" else None
            elif event.ui_element == self.dropdown_logger_rate:
                self._set_logger_rate(event.text)
            elif event.ui_element == self.dropdown_logger_duration:
                self._set_logger_duration(event.text)
        if event.type != pygame_gui.UI_BUTTON_PRESSED:
            return
        if event.ui_element == self.btn_reload_scenario:
            self._load_sim()
        elif event.ui_element == self.btn_play:
            self._toggle_play()
        elif event.ui_element == self.btn_step:
            self._step_once()
        elif event.ui_element == self.btn_reload_code:
            if self.sim:
                self.sim.clear_controller_error()
                self.sim.reload_controller(keep_previous=False)
                self._report_controller_errors("Controller reload failed")
        elif event.ui_element == self.btn_save_code:
            self._save_code()
        elif event.ui_element == self.btn_format_code:
            self._format_code()
        elif event.ui_element == self.btn_clear_errors:
            self._clear_errors()
        elif event.ui_element == self.btn_toggle_panel:
            self._clear_console()
        elif event.ui_element == self.btn_logger_toggle:
            self._toggle_logging()
        elif event.ui_element == self.btn_logger_export:
            self._export_logger()

    def _report_controller_errors(self, title: str, clear: bool = True) -> None:
        if not self.sim:
            return
        errors = dict(getattr(self.sim, "last_controller_errors", {}) or {})
        if not errors and getattr(self.sim, "last_controller_error", None):
            errors = {"primary": self.sim.last_controller_error}
        if not errors:
            return
        details = "; ".join(f"{rid}: {msg}" for rid, msg in errors.items())
        # Do not pause the sim; surface as status + console line only.
        self.status_text = f"{title} — {details}"
        self._append_console(f"{title}: {details}")
        if clear:
            try:
                self.sim.clear_controller_error()
            except Exception:
                pass

    def _record_error(self, title: str, details: str, pause: bool = True) -> None:
        entry: Dict[str, str] = {"title": title, "details": details}
        hint = self._extract_line_hint(details)
        if hint:
            entry["line"] = hint
        self.error_log.append(entry)
        if len(self.error_log) > 6:
            self.error_log = self.error_log[-6:]
        if pause:
            self.error_paused = True
            self.playing = False
            self._set_play_button(False)
        # Surface errors via status + console so pauses are never silent.
        state = "paused" if pause else "logged"
        self.status_text = f"{title} ({state}); see Logs"
        try:
            self._append_console(f"{title}: {details}")
        except Exception:
            pass
        logs_panel = self.dock_items.get("logs")
        if logs_panel:
            logs_panel.visible = True
            self._bump_panel("logs")
            self._update_layout()
        self._refresh_hover_menu()

    def _clear_errors(self) -> None:
        self.error_log.clear()
        self.error_paused = False
        if self.sim:
            self.sim.clear_controller_error()
        self.status_text = "Errors cleared; ready to run"
        self._refresh_hover_menu()

    def _clear_console(self) -> None:
        self.console_lines.clear()
        self._console_buffer = ""
        self.status_text = "Console cleared"

    def _append_console(self, data: str) -> None:
        # Accumulate by lines to keep panel tidy.
        self._console_buffer += data
        while "\n" in self._console_buffer:
            line, self._console_buffer = self._console_buffer.split("\n", 1)
            self.console_lines.append(line)
        if len(self.console_lines) > 200:
            self.console_lines = self.console_lines[-200:]

    def _extract_line_hint(self, tb: str) -> Optional[str]:
        for line in reversed(tb.splitlines()):
            if ("controller.py" in line) or (".controller.json" in line) or (".generated_controllers" in line):
                return line.strip()
        return None

    def _wrap_text(self, text: str, font: pygame.font.Font, max_width: int) -> List[str]:
        lines: List[str] = []
        for raw_line in text.splitlines():
            words = raw_line.split(" ")
            current = ""
            for w in words:
                trial = f"{current} {w}".strip()
                if font.size(trial)[0] > max_width and current:
                    lines.append(current)
                    current = w
                else:
                    current = trial
            lines.append(current)
        return lines

    def _fmt_value(self, value: object) -> str:
        """Format numeric-ish values with consistent rounding for display."""
        decimals = max(1, self.round_digits)
        small_decimals = min(decimals + 1, 4)
        if isinstance(value, dict):
            parts = [f"{k}: {self._fmt_value(v)}" for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))]
            return "{" + ", ".join(parts) + "}"
        if isinstance(value, set):
            parts = [self._fmt_value(v) for v in sorted(value, key=lambda v: str(v))]
            return "{" + ", ".join(parts) + "}"
        try:
            if isinstance(value, (list, tuple)):
                return "(" + ", ".join(self._fmt_value(v) for v in value) + ")"
            num = float(value)
        except (TypeError, ValueError):
            return str(value)
        places = small_decimals if 0 < abs(num) < 1 else decimals
        fmt = f"{{0:.{places}f}}"
        return fmt.format(num)

    def _toggle_help_overlay(self) -> None:
        self.help_open = not self.help_open
        if self.help_open:
            self.help_scroll = 0
        self.status_text = "Help open" if self.help_open else "Help closed"
        self._refresh_hover_menu()

    def _open_help_topic(self, topic_id: str) -> None:
        if any(t["id"] == topic_id for t in self.help_topics):
            self.help_active_topic = topic_id
            self.help_scroll = 0

    def _clamp_help_scroll(self, content_height: int, viewport_h: int) -> None:
        self.help_scroll_min = min(0, viewport_h - content_height - 12)
        if self.help_scroll < self.help_scroll_min:
            self.help_scroll = self.help_scroll_min
        if self.help_scroll > 0:
            self.help_scroll = 0

    def _handle_help_mouse(self, event: pygame.event.Event) -> bool:
        if not self.help_open:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.help_close_rect and self.help_close_rect.collidepoint(event.pos):
                self._toggle_help_overlay()
                return True
            for tid, rect in self.help_nav_hitboxes.items():
                if rect.collidepoint(event.pos):
                    self._open_help_topic(tid)
                    return True
        if event.type == pygame.MOUSEWHEEL and self.help_content_rect:
            self.help_scroll += event.y * 24
            self._clamp_help_scroll(self.help_last_content_height, self.help_content_rect.height)
            return True
        return False

    def _update_live_state(self, sim_dt: float, stepped: bool) -> None:
        if not self.sim:
            self.live_state = {"motors": {}, "sensors": {}, "per_robot": {}, "controller_errors": {}}
            return
        motors = {name: getattr(motor, "last_command", 0.0) for name, motor in self.sim.motors.items()}
        sensors = dict(getattr(self.sim, "last_sensor_readings", {}) or {})
        owners_m = getattr(self.sim, "motor_owners", {}) or {}
        owners_s = getattr(self.sim, "sensor_owners", {}) or {}
        per_robot: Dict[str, Dict[str, Dict[str, object]]] = {
            rid: {"motors": {}, "sensors": {}} for rid in getattr(self.sim, "robot_ids", []) or []
        }
        for name, val in motors.items():
            rid = owners_m.get(name)
            if rid:
                per_robot.setdefault(rid, {"motors": {}, "sensors": {}})["motors"][name] = val
        for name, val in sensors.items():
            rid = owners_s.get(name)
            if rid:
                per_robot.setdefault(rid, {"motors": {}, "sensors": {}})["sensors"][name] = val
        self.live_state = {
            "motors": motors,
            "sensors": sensors,
            "per_robot": per_robot,
            "physics_warning": getattr(self.sim, "last_physics_warning", None),
            "controller_errors": dict(getattr(self.sim, "last_controller_errors", {})),
        }
        if self.view_options.get("path_trace", False) and stepped:
            center = self._current_robot_center()
            if center:
                self.path_trace.append(center)
                if len(self.path_trace) > 400:
                    self.path_trace = self.path_trace[-400:]
        elif not self.view_options.get("path_trace", False):
            if self.path_trace:
                self.path_trace.clear()
        if self.logger_enabled and stepped:
            self._logger_timer += sim_dt
            self._logger_elapsed += sim_dt
            if self._logger_timer >= self.logger_interval:
                self._logger_timer = 0.0
                sample: Dict[str, object] = {"t": getattr(self.sim, "time", 0.0)}
                for sig in sorted(self.logger_selected):
                    if sig.startswith("motor:"):
                        name = sig.split(":", 1)[1]
                        sample[sig] = motors.get(name, 0.0)
                    elif sig.startswith("sensor:"):
                        name = sig.split(":", 1)[1]
                        sample[sig] = sensors.get(name, None)
                self.logger_samples.append(sample)
                if len(self.logger_samples) > 1000:
                    self.logger_samples = self.logger_samples[-1000:]
                self.logger_status = "Logging"
            if self.logger_duration > 0 and self._logger_elapsed >= self.logger_duration:
                self.logger_enabled = False
                self.logger_status = "Logger stopped (duration reached)"
                self._logger_elapsed = 0.0
        elif not stepped:
            self._logger_timer = 0.0

    def _zoom(self, factor: float) -> None:
        self.scale = max(40.0, min(2000.0, self.scale * factor))
        self.status_text = f"Scale {self.scale:.1f}"

    def _handle_scroll(self, event: pygame.event.Event) -> None:
        mouse_pos = pygame.mouse.get_pos()
        if self.viewport_rect.collidepoint(mouse_pos):
            self._zoom(1.0 + 0.1 * event.y)
            self._update_hover_center(mouse_pos)

    def _handle_pan_start(self, event: pygame.event.Event) -> None:
        if not self.viewport_rect.collidepoint(event.pos):
            return
        target_robot = self._robot_under_cursor(event.pos)
        if event.button == 1 and target_robot and target_robot != self.active_robot_id:
            # Switch selection on click; second click on same robot can drag/rotate.
            self._set_active_robot(target_robot)
            return
        world_point = screen_to_world(event.pos, self.viewport_rect, self.scale, self.offset)
        center = self._current_robot_center()
        near_center = False
        if center:
            cx, cy = world_to_screen(center, self.viewport_rect, self.scale, self.offset)
            dist = math.hypot(event.pos[0] - cx, event.pos[1] - cy)
            near_center = dist <= 14
        if event.button == 1 and near_center and self.sim:
            pose = self._robot_pose_now()
            if pose:
                self._ensure_pose_history_seed(pose)
                self.robot_dragging = True
                self.robot_drag_start = world_point
                self.robot_drag_center = center
                self.robot_drag_theta = pose[2]
                self.reposition_target = center
                self.status_text = "Drag to move robot; hold Shift while dragging to rotate"
        elif event.button in (1, 2, 3):
            # default pan
            self.pan_active = True
            self.pan_start = event.pos

    def _handle_pan_motion(self, event: pygame.event.Event) -> None:
        if self.robot_dragging and self.sim:
            world_point = screen_to_world(event.pos, self.viewport_rect, self.scale, self.offset)
            start = self.robot_drag_start or world_point
            center = self.robot_drag_center or start
            dx = world_point[0] - start[0]
            dy = world_point[1] - start[1]
            mods = pygame.key.get_mods()
            if mods & pygame.KMOD_SHIFT:
                start_angle = math.atan2(start[1] - center[1], start[0] - center[0])
                curr_angle = math.atan2(world_point[1] - center[1], world_point[0] - center[0])
                dtheta = curr_angle - start_angle
                self.reposition_angle = self.robot_drag_theta + dtheta
                self._apply_robot_reposition(center, self.reposition_angle)
            else:
                self.reposition_target = (center[0] + dx, center[1] + dy)
                self._apply_robot_reposition(self.reposition_target, self.robot_drag_theta)
            return
        if self.pan_active and self.pan_start:
            dx = (event.pos[0] - self.pan_start[0]) / max(self.scale, 1e-6)
            dy = (event.pos[1] - self.pan_start[1]) / max(self.scale, 1e-6)
            # Dragging right moves view right (invert previous direction)
            self.offset = (self.offset[0] + dx, self.offset[1] - dy)
            self.pan_start = event.pos
        else:
            self._update_hover_center(event.pos)

    def _view_reset(self) -> None:
        self.offset = (0.0, 0.0)
        self.scale = 400.0
        self.status_text = "View reset"

    def _view_center_robot(self) -> None:
        center = self._current_robot_center()
        if center:
            self.offset = (-center[0], -center[1])
            self.status_text = "View centered on robot"

    def _view_toggle_grid(self) -> None:
        self.view_options["grid"] = not self.view_options["grid"]
        self.status_text = "Grid on" if self.view_options["grid"] else "Grid off"

    def _view_toggle_motor_arrows(self) -> None:
        self.view_options["motor_arrows"] = not self.view_options["motor_arrows"]
        self.status_text = "Motor arrows on" if self.view_options["motor_arrows"] else "Motor arrows off"

    def _view_toggle_path_trace(self) -> None:
        self.view_options["path_trace"] = not self.view_options["path_trace"]
        if not self.view_options["path_trace"]:
            self.path_trace.clear()
        self.status_text = "Path trace on" if self.view_options["path_trace"] else "Path trace off"

    def _current_robot_center(self) -> Optional[Tuple[float, float]]:
        if not self.sim:
            return None
        rid = self.active_robot_id or (self.sim.robot_ids[0] if getattr(self.sim, "robot_ids", None) else None)
        cfg = self.sim.robot_configs.get(rid) if rid and hasattr(self.sim, "robot_configs") else self.sim.robot_cfg
        if not cfg or not cfg.bodies:
            return None
        xs: List[float] = []
        ys: List[float] = []
        for body_cfg in cfg.bodies:
            body = self.sim.bodies.get(body_cfg.name)
            if not body:
                continue
            xs.append(body.pose.x)
            ys.append(body.pose.y)
        if not xs or not ys:
            return None
        return (sum(xs) / len(xs), sum(ys) / len(ys))

    def _robot_under_cursor(self, pos: Tuple[int, int], radius: float = 18.0) -> Optional[str]:
        """Return the robot id nearest to the cursor within radius (pixels)."""
        if not self.sim:
            return None
        for rid in getattr(self.sim, "robot_ids", []):
            cfg = self.sim.robot_configs.get(rid) if hasattr(self.sim, "robot_configs") else None
            if not cfg or not cfg.bodies:
                continue
            root = cfg.bodies[0]
            body = self.sim.bodies.get(root.name)
            if not body:
                continue
            sx, sy = world_to_screen((body.pose.x, body.pose.y), self.viewport_rect, self.scale, self.offset)
            if math.hypot(pos[0] - sx, pos[1] - sy) <= radius:
                return rid
        return None

    def _update_hover_center(self, mouse_pos: Tuple[int, int]) -> None:
        center = self._current_robot_center()
        if not center:
            self.hover_robot_center = False
            return
        sx, sy = world_to_screen(center, self.viewport_rect, self.scale, self.offset)
        self.hover_robot_center = math.hypot(mouse_pos[0] - sx, mouse_pos[1] - sy) <= 14

    def _finalize_reposition(self) -> None:
        if self.robot_dragging:
            self.robot_dragging = False
            self.robot_drag_start = None
            self.robot_drag_center = None
            self.status_text = "Robot moved; resume or snapshot to test"
            # record final pose for undo/redo
            pose = self._robot_pose_now()
            if pose:
                self._push_pose_history(pose)
            return

    def _apply_robot_reposition(self, pos: Tuple[float, float], theta: float) -> None:
        if not self.sim:
            return
        self.playing = False
        self.btn_play.set_text("Play")
        self.sim.reposition_robot((pos[0], pos[1], theta), zero_velocity=True, set_as_spawn=False, robot_id=self.active_robot_id)
        self.reposition_target = pos

    def _robot_pose_now(self) -> Optional[Tuple[float, float, float]]:
        if not self.sim:
            return None
        rid = self.active_robot_id or (self.sim.robot_ids[0] if getattr(self.sim, "robot_ids", None) else None)
        cfg = self.sim.robot_configs.get(rid) if rid and hasattr(self.sim, "robot_configs") else self.sim.robot_cfg
        if not cfg or not cfg.bodies:
            return None
        root_cfg = cfg.bodies[0]
        body = self.sim.bodies.get(root_cfg.name)
        if not body:
            return None
        return (body.pose.x - root_cfg.pose[0], body.pose.y - root_cfg.pose[1], body.pose.theta - root_cfg.pose[2])

    def _ensure_pose_history_seed(self, pose: Tuple[float, float, float]) -> None:
        if not self.pose_history:
            self.pose_history.append(pose)

    def _push_pose_history(self, pose: Tuple[float, float, float]) -> None:
        if self.pose_history and pose == self.pose_history[-1]:
            return
        self.pose_history.append(pose)
        if len(self.pose_history) > 50:
            self.pose_history = self.pose_history[-50:]
        self.pose_redo.clear()

    def _undo_robot_pose(self) -> None:
        if len(self.pose_history) < 2:
            self.status_text = "No undo available"
            return
        current = self.pose_history.pop()
        self.pose_redo.append(current)
        pose = self.pose_history[-1]
        self._apply_robot_reposition((pose[0], pose[1]), pose[2])
        self.status_text = "Undo robot pose"

    def _redo_robot_pose(self) -> None:
        if not self.pose_redo:
            self.status_text = "No redo available"
            return
        pose = self.pose_redo.pop()
        self._apply_robot_reposition((pose[0], pose[1]), pose[2])
        self.pose_history.append(pose)
        self.status_text = "Redo robot pose"

    def _handle_state_click(self, event: pygame.event.Event) -> None:
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        panel = self.dock_items.get("state")
        if not panel or not panel.visible or not panel.rect.collidepoint(event.pos):
            return
        for rid, rect in self.roster_hitboxes.items():
            if rect.collidepoint(event.pos):
                self._set_active_robot(rid)
                return
        for sig, rect in self.signal_hitboxes.items():
            if rect.collidepoint(event.pos):
                if sig in self.logger_selected:
                    self.logger_selected.remove(sig)
                else:
                    self.logger_selected.add(sig)
                return

    def _handle_plot_click(self, event: pygame.event.Event) -> None:
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        panel = self.dock_items.get("plot")
        if not panel or not panel.visible or not panel.rect.collidepoint(event.pos):
            return
        for key, rect in self.plot_hitboxes.items():
            if rect.collidepoint(event.pos):
                if key == "__open__":
                    self._open_plot_dialog()
                elif key == "__clear__":
                    self._clear_plot_data()
                else:
                    if key in self.plot_selected_cols:
                        self.plot_selected_cols.remove(key)
                    else:
                        self.plot_selected_cols.add(key)
                return

    def _set_logger_rate(self, label: str) -> None:
        mapping = {"120 Hz": 1.0 / 120.0, "60 Hz": 1.0 / 60.0, "30 Hz": 1.0 / 30.0, "10 Hz": 0.1}
        self.logger_interval = mapping.get(label, 1.0 / 30.0)
        self.status_text = f"Logger rate {label}"

    def _set_logger_duration(self, label: str) -> None:
        mapping = {"5 s": 5.0, "15 s": 15.0, "60 s": 60.0, "Unlimited": 0.0}
        self.logger_duration = mapping.get(label, 15.0)
        self.status_text = f"Logger duration {label}"

    def _toggle_logging(self) -> None:
        if not self.sim:
            self.status_text = "Load a scenario before logging"
            return
        self.logger_enabled = not self.logger_enabled
        self._logger_elapsed = 0.0
        self._logger_timer = 0.0
        self.logger_status = "Logging…" if self.logger_enabled else "Logger paused"
        try:
            self.btn_logger_toggle.set_text("Stop logging" if self.logger_enabled else "Start logging")
        except Exception:
            pass

    def _export_logger(self) -> None:
        if not self.scenario_name or not self.logger_samples:
            self.status_text = "No log samples to export"
            return
        log_dir = self.scenario_root / self.scenario_name / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        fname = log_dir / f"log_{self.sim.step_index:06d}.csv" if self.sim else log_dir / "log.csv"
        all_keys: List[str] = []
        for sample in self.logger_samples:
            for k in sample.keys():
                if k not in all_keys:
                    all_keys.append(k)
        try:
            with fname.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=all_keys)
                writer.writeheader()
                writer.writerows(self.logger_samples)
            self.status_text = f"Exported {len(self.logger_samples)} samples to {fname.name}"
        except Exception:
            self.status_text = "Failed to export log"

    def _save_code(self) -> None:
        if not self.scenario_name:
            return
        rid, _, module_name = self._active_controller_target()
        scenario_dir = self.current_scenario_path
        if not scenario_dir:
            entry = self.scenario_lookup.get(self.scenario_name)
            scenario_dir = entry.path if entry else None
        if not scenario_dir:
            self.status_text = "No scenario path to save controller"
            return
        try:
            sections, help_text = self.controller_editor.content()
            if not sections.get("step", "").strip():
                self.status_text = "Step section is required"
                return
            definition = ControllerDefinition(name=module_name, sections=sections, help=help_text)
            self.controller_definition = definition
            save_controller_definition(scenario_dir, module_name, definition)
            # update preview after save
            preview = build_controller_code(definition)
            help_txt = self._controller_help_text(definition, scenario_dir)
            self.controller_editor.set_content(definition.sections, help_text=help_txt, preview=preview)
            if self.sim:
                self.sim.clear_controller_error(rid)
                self.sim.reload_controller(rid, keep_previous=False)
                self._report_controller_errors("Controller reload failed")
                if self.error_log:
                    return
            who = rid or "controller"
            self.status_text = f"Saved {module_name} for {who}"
        except Exception:
            self._record_error("Save/reload failed", traceback.format_exc())

    def _format_code(self) -> None:
        active = getattr(self.controller_editor, "active", "step")
        editor = self.controller_editor.editors.get(active) if hasattr(self, "controller_editor") else None
        if not editor:
            self.status_text = "No editor available"
            return
        text = editor.text()
        if not text.strip():
            self.status_text = "Nothing to format"
            return

        def _wrap(snippet: str) -> str:
            if active in ("init", "step"):
                return "def _func():\n" + textwrap.indent(snippet, "    ")
            return snippet

        def _unwrap(snippet: str) -> str:
            if active in ("init", "step"):
                lines = snippet.splitlines()
                body = lines[1:] if len(lines) > 1 else []
                return "\n".join([line[4:] if line.startswith("    ") else line for line in body]).strip() + "\n"
            return snippet

        formatted = None
        formatter = None
        wrapped = _wrap(text)
        try:
            import black

            formatted = black.format_str(wrapped, mode=black.Mode())
            formatter = "black"
        except Exception:
            try:
                import autopep8

                formatted = autopep8.fix_code(wrapped)
                formatter = "autopep8"
            except Exception:
                formatter = None
        if formatted:
            new_text = _unwrap(formatted)
            editor.set_text(new_text)
            self.status_text = f"Formatted {active} with {formatter}"
        else:
            self.status_text = "Formatter unavailable; left text unchanged"

    def _save_snapshot(self) -> None:
        if not self.sim or not self.scenario_name:
            return
        snap = self.sim.snapshot()
        snap_dir = self.scenario_root / self.scenario_name / "snapshots"
        snap_path = snap_dir / f"snap_{self.sim.step_index:06d}.json"
        save_snapshot(snap_path, snap)
        print(f"Saved snapshot {snap_path}")

    def _load_snapshot(self) -> None:
        if not self.scenario_name or not self.sim:
            return
        snaps = self._list_snapshots(limit=1)
        if not snaps:
            print("No snapshots found")
            return
        snap_path = snaps[-1]
        snap = load_snapshot(snap_path)
        self.sim.apply_snapshot(snap)
        print(f"Loaded snapshot {snap_path.name}")

    def _save_snapshot_to_path(self, path: Path) -> None:
        if not self.sim or not self.scenario_name:
            return
        path = path.with_suffix(".json")
        path.parent.mkdir(parents=True, exist_ok=True)
        save_snapshot(path, self.sim.snapshot())
        print(f"Saved snapshot {path}")

    def _load_snapshot_from_path(self, path: Path) -> None:
        if not self.sim:
            return
        if not path.exists():
            print(f"Snapshot not found: {path}")
            return
        snap = load_snapshot(path)
        self.sim.apply_snapshot(snap)
        print(f"Loaded snapshot {path.name}")

    def _open_plot_dialog(self) -> None:
        if not self.scenario_name:
            return
        log_dir = self.scenario_root / self.scenario_name / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        rect = pygame.Rect(
            max(40, self.window_size[0] // 2 - 220),
            max(40, self.window_size[1] // 2 - 160),
            440,
            320,
        )
        if self.plot_dialog:
            try:
                self.plot_dialog.kill()
            except Exception:
                pass
        self.plot_dialog = UIFileDialog(
            rect=rect,
            manager=self.manager,
            window_title="Open CSV log",
            initial_file_path=str(log_dir),
            allow_existing_files_only=True,
        )

    def _clear_plot_data(self) -> None:
        self.plot_data = {}
        self.plot_selected_cols.clear()
        self.plot_source = None
        self.plot_status = "No CSV loaded"
        self.plot_hitboxes = {}

    def _load_plot_from_path(self, path: Path) -> None:
        if not path.exists():
            self.plot_status = f"File not found: {path.name}"
            return
        try:
            with path.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    self.plot_status = "No columns found in CSV"
                    self.plot_data = {}
                    return
                data: Dict[str, List[Optional[float]]] = {col: [] for col in reader.fieldnames}
                for row in reader:
                    for col in reader.fieldnames:
                        raw = row.get(col, "")
                        try:
                            data[col].append(float(raw))
                        except Exception:
                            data[col].append(None)
                self.plot_data = data
                numeric_cols = [c for c, vals in data.items() if any(v is not None for v in vals)]
                defaults = [c for c in numeric_cols if c != "t"][:2] or numeric_cols[:2]
                self.plot_selected_cols = set(defaults)
                self.plot_source = path
                self.plot_status = f"Loaded {path.name} ({len(next(iter(data.values()), []))} rows)"
                plot_panel = self.dock_items.get("plot")
                if plot_panel:
                    plot_panel.visible = True
                    self._bump_panel("plot")
                    self._update_layout()
        except Exception:
            self.plot_status = "Failed to parse CSV"
            self.plot_data = {}
            self.plot_selected_cols.clear()

    def _list_snapshots(self, limit: int = 6) -> List[Path]:
        if not self.scenario_name:
            return []
        snap_dir = self.scenario_root / self.scenario_name / "snapshots"
        if not snap_dir.exists():
            return []
        snaps = sorted(snap_dir.glob("*.json"))
        if limit > 0:
            return snaps[-limit:]
        return snaps

    def _open_snapshot_dialog(self, mode: str) -> None:
        if not self.scenario_name:
            return
        snaps_dir = self.scenario_root / self.scenario_name / "snapshots"
        snaps_dir.mkdir(parents=True, exist_ok=True)
        if self.snapshot_dialog:
            try:
                self.snapshot_dialog.kill()
            except Exception:
                pass
        rect = pygame.Rect(
            max(40, self.window_size[0] // 2 - 220),
            max(40, self.window_size[1] // 2 - 160),
            440,
            320,
        )
        initial = snaps_dir if mode == "load" else snaps_dir / "snapshot.json"
        self.snapshot_dialog = UIFileDialog(
            rect=rect,
            manager=self.manager,
            window_title="Save snapshot" if mode == "save" else "Load snapshot",
            initial_file_path=str(initial),
            allow_existing_files_only=mode == "load",
        )
        self.snapshot_dialog_mode = mode

    def _open_robot_dialog(self) -> None:
        if not self.scenario_name or not self.world_cfg:
            self.status_text = "Load a scenario before replacing robot"
            return
        base = (self.base_path / "assets" / "robots") if (self.base_path / "assets" / "robots").exists() else self.scenario_root
        if self.robot_dialog:
            try:
                self.robot_dialog.kill()
            except Exception:
                pass
        rect = pygame.Rect(
            max(40, self.window_size[0] // 2 - 220),
            max(40, self.window_size[1] // 2 - 160),
            440,
            320,
        )
        self.robot_dialog = UIFileDialog(
            rect=rect,
            manager=self.manager,
            window_title="Replace robot from file",
            initial_file_path=str(base),
            allow_existing_files_only=True,
        )

    def _load_robot_from_path(self, path: Path) -> None:
        if not path.exists():
            self.status_text = f"Robot file not found: {path}"
            return
        try:
            self.robot_cfg = load_robot_design(path)
            self._reload_with_current_assets()
            self.status_text = f"Loaded robot from {path.name}"
        except Exception:
            self._record_error("Robot load failed", traceback.format_exc())

    def _toggle_device_help(self) -> None:
        self.show_device_help = not self.show_device_help
        self.status_text = "Device tips on" if self.show_device_help else "Device tips off"
        self._refresh_hover_menu()

    def _current_controller_module(self) -> Optional[str]:
        if not self.sim:
            return None
        active_id = self.active_robot_id or (self.sim.robot_ids[0] if getattr(self.sim, "robot_ids", None) else None)
        if active_id and hasattr(self.sim, "robot_configs"):
            cfg = self.sim.robot_configs.get(active_id)
            if cfg and getattr(cfg, "controller_module", None):
                return cfg.controller_module
        if self.sim.robot_cfg:
            return getattr(self.sim.robot_cfg, "controller_module", None)
        return None

    def _active_controller_target(self) -> Tuple[Optional[str], Optional[Path], str]:
        """Return (robot_id, controller_path, module_name) for the active robot."""
        scenario_dir = self.current_scenario_path
        if not scenario_dir:
            entry = self.scenario_lookup.get(self.scenario_name) if self.scenario_name else None
            scenario_dir = entry.path if entry else None
        rid = self.active_robot_id or (self.robot_roster[0] if self.robot_roster else None)
        module_name = self._current_controller_module()
        if not module_name and self.loaded_robots:
            for robot in self.loaded_robots:
                if rid and robot.id == rid:
                    module_name = robot.controller or getattr(robot.config, "controller_module", None)
                    break
        module_name = module_name or "controller"
        path = controller_path(scenario_dir, module_name) if scenario_dir else None
        if path and not path.exists():
            # Legacy fallback
            legacy = scenario_dir / f"{module_name}.py" if scenario_dir else None
            path = legacy if legacy and legacy.exists() else path
        return rid, path, module_name

    def _controller_context_line(self) -> str:
        motors = sorted(self.sim.motors.keys()) if self.sim and getattr(self.sim, "motors", None) else []
        sensors = sorted(self.sim.sensors.keys()) if self.sim and getattr(self.sim, "sensors", None) else []
        dt = getattr(self.sim, "dt", None)
        parts: List[str] = []
        if dt:
            parts.append(f"dt≈{dt:.4f}s")
        if motors:
            parts.append("motors: " + ", ".join(motors))
        if sensors:
            parts.append("sensors: " + ", ".join(sensors))
        return " | ".join(parts)

    def _controller_help_text(self, definition: ControllerDefinition, scenario_dir: Optional[Path]) -> str:
        lines: List[str] = [
            "Step signature: step(sensors, dt) — runs every sim tick.",
            "Sensors: dict keyed by sensor names; values depend on sensor type.",
            "Motors: access via self.sim.motors['name'].command(value, self.sim, dt).",
            "Context: self.sim (physics + devices), self.robot_id (id for multi-robot).",
            "Common patterns: clamp outputs, read sensors safely, respect dt for rates.",
        ]
        if self.sim:
            motors = sorted(self.sim.motors.keys())
            sensors = sorted(self.sim.sensors.keys())
            if motors:
                lines.append(f"Available motors: {', '.join(motors)}")
            if sensors:
                lines.append(f"Available sensors: {', '.join(sensors)}")
        if definition.help:
            lines.append("")
            lines.append("Notes:")
            lines.extend(definition.help.splitlines())
        return "\n".join(lines)

    def _controller_choices(self) -> List[str]:
        if not self.scenario_name:
            return []
        entry = self.scenario_lookup.get(self.scenario_name)
        scenario_path = entry.path if entry else (self.scenario_root / self.scenario_name)
        if not scenario_path.exists():
            return []
        names = list_controllers(scenario_path)
        if not names:
            names = sorted({p.stem for p in scenario_path.glob("controller*.py")})
        return names or ["controller"]

    def _switch_controller(self, module_name: str) -> None:
        if not self.sim or not self.scenario_name:
            return
        entry = self.scenario_lookup.get(self.scenario_name)
        scenario_path = entry.path if entry else (self.scenario_root / self.scenario_name)
        target_id = self.active_robot_id or (self.sim.robot_ids[0] if getattr(self.sim, "robot_ids", None) else "robot")
        target_cfg = self.sim.robot_configs.get(target_id) if hasattr(self.sim, "robot_configs") else None
        if target_cfg:
            target_cfg.controller_module = module_name
        for robot in self.loaded_robots:
            if robot.id == target_id:
                robot.controller = module_name
                if hasattr(robot, "config"):
                    robot.config.controller_module = module_name
                break
        if self.robot_cfg and target_id == (self.sim.robot_ids[0] if getattr(self.sim, "robot_ids", None) else "robot"):
            self.robot_cfg.controller_module = module_name
        self.sim._load_controller_for_robot(target_id, module_name, scenario_path, keep_previous=False)  # type: ignore[attr-defined]
        has_errors = bool(getattr(self.sim, "last_controller_errors", {}) or getattr(self.sim, "last_controller_error", None))
        if has_errors:
            self._report_controller_errors("Controller load failed")
            return
        else:
            definition = load_controller_definition(scenario_path, module_name)
            preview = build_controller_code(definition)
            help_text = self._controller_help_text(definition, scenario_path)
            self.controller_definition = definition
            self.controller_editor.set_content(definition.sections, help_text=help_text, preview=preview)
            self.controller_editor.active = "step"
            self.status_text = f"Loaded controller {module_name}"
            try:
                if self.world_cfg and self.robot_cfg:
                    save_scenario(scenario_path, self.world_cfg, self.robot_cfg)
            except Exception:
                pass
        self._refresh_hover_menu()

    def _refresh_hover_menu(self) -> None:
        font = pygame.font.Font(pygame.font.get_default_font(), 14)

        def panel_toggle(pid: str, title: str) -> Dict[str, object]:
            return {
                "label": title,
                "action": lambda pid=pid: self._toggle_panel(pid),
                "checked": lambda pid=pid: self.dock_items.get(pid, None) and self.dock_items[pid].visible,
            }

        def scenario_entry(name: str) -> Dict[str, object]:
            label = self.scenario_lookup.get(name).name if name in self.scenario_lookup else name
            return {"label": label, "action": lambda n=name: self._select_scenario(n)}

        def controller_entry(name: str) -> Dict[str, object]:
            return {
                "label": f"Use {name}",
                "action": lambda n=name: self._switch_controller(n),
                "checked": lambda n=name: self._current_controller_module() == n,
            }

        controller_items = [controller_entry(n) for n in self._controller_choices()] or [
            {"label": "No controllers found", "action": lambda: None}
        ]

        robot_entries: List[Dict[str, object]] = []
        if self.robot_roster:
            for rid in self.robot_roster:
                robot_entries.append(
                    {
                        "label": rid,
                        "action": (lambda r=rid: self._set_active_robot(r)),
                        "checked": (lambda r=rid: self.active_robot_id == r),
                    }
                )

        snapshot_entries: List[Dict[str, object]] = [
            {"label": "Quick snapshot", "action": self._save_snapshot},
            {"label": "Save snapshot as...", "action": lambda: self._open_snapshot_dialog("save")},
        ]
        snapshots = self._list_snapshots(limit=6)
        recent_snapshot_entries: List[Dict[str, object]] = []
        if snapshots:
            latest = snapshots[-1]
            recent_snapshot_entries.append(
                {"label": f"Latest ({latest.name})", "action": lambda p=latest: self._load_snapshot_from_path(p)}
            )
            for snap in reversed(snapshots):
                recent_snapshot_entries.append({"label": snap.name, "action": lambda p=snap: self._load_snapshot_from_path(p)})
        else:
            recent_snapshot_entries.append({"label": "No recent snapshots", "action": lambda: None})

        logger_entries = [
            {"label": "Start/Stop logging", "action": self._toggle_logging},
            {"label": "Export log", "action": self._export_logger},
            {"label": "Open CSV plotter", "action": self._open_plot_dialog},
            {
                "label": "Show plot panel",
                "action": lambda: self._toggle_panel("plot"),
                "checked": lambda: self._panel_visible("plot"),
            },
            {"label": "Clear plot", "action": self._clear_plot_data},
            {"label": "Logger rate 120 Hz", "action": lambda: self._set_logger_rate("120 Hz"), "checked": lambda: self.dropdown_logger_rate.selected_option == "120 Hz"},
            {"label": "Logger rate 60 Hz", "action": lambda: self._set_logger_rate("60 Hz"), "checked": lambda: self.dropdown_logger_rate.selected_option == "60 Hz"},
            {"label": "Logger rate 30 Hz", "action": lambda: self._set_logger_rate("30 Hz"), "checked": lambda: self.dropdown_logger_rate.selected_option == "30 Hz"},
            {"label": "Logger rate 10 Hz", "action": lambda: self._set_logger_rate("10 Hz"), "checked": lambda: self.dropdown_logger_rate.selected_option == "10 Hz"},
            {"label": "Logger duration 5 s", "action": lambda: self._set_logger_duration("5 s"), "checked": lambda: self.dropdown_logger_duration.selected_option == "5 s"},
            {"label": "Logger duration 15 s", "action": lambda: self._set_logger_duration("15 s"), "checked": lambda: self.dropdown_logger_duration.selected_option == "15 s"},
            {"label": "Logger duration 60 s", "action": lambda: self._set_logger_duration("60 s"), "checked": lambda: self.dropdown_logger_duration.selected_option == "60 s"},
            {"label": "Logger duration Unlimited", "action": lambda: self._set_logger_duration("Unlimited"), "checked": lambda: self.dropdown_logger_duration.selected_option == "Unlimited"},
        ]

        speed_presets = [0.25, 0.5, 1.0, 1.5, 2.0, 3.0]
        speed_entries: List[Dict[str, object]] = [
            {
                "label": f"{val}x",
                "action": (lambda v=val: self._set_playback_rate(v)),
                "checked": (lambda v=val: math.isclose(self.playback_rate, v, rel_tol=1e-3)),
            }
            for val in speed_presets
        ]
        speed_entries.append({"label": "Open speed slider", "action": self._open_speed_slider})

        capture_menu = [
            {"label": "Snapshots", "children": snapshot_entries},
            {"label": "Logging", "children": logger_entries},
        ]

        resume_entries: List[Dict[str, object]] = [{"label": "Load snapshot from file", "action": lambda: self._open_snapshot_dialog("load")}]
        resume_entries.extend(recent_snapshot_entries)

        scenario_items: List[Dict[str, object]] = [{"label": "Reload", "action": self._load_sim}, {"label": "Replace robot from file", "action": self._open_robot_dialog}]
        scenario_items += [scenario_entry(n) for n in self.scenario_names]
        if len(robot_entries) > 1:
            scenario_items.append({"label": "Active robot", "children": robot_entries})

        self.hover_menu = HoverMenu(
            [
                (
                    "Scenario",
                    scenario_items,
                ),
                (
                    "Run",
                    [
                        {"label": "Play" if not self.playing else "Pause", "action": self._toggle_play},
                        {"label": "Step", "action": self._step_once},
                        {"label": f"Speed {self.playback_rate:.2f}x", "children": speed_entries},
                        {"label": "Resume from snapshot", "children": resume_entries},
                    ],
                ),
                (
                    "Controller",
                    [
                        {"label": "Reload controller", "action": self._reload_code},
                        {"label": "Save + reload controller", "action": self._save_code},
                        {"label": "Format controller (black/autopep8)", "action": self._format_code},
                        *controller_items,
                    ],
                ),
                ("Capture", capture_menu),
                (
                    "View",
                    [
                        {"label": "Toggle grid", "action": self._view_toggle_grid, "checked": lambda: self.view_options.get("grid", False)},
                        {
                            "label": "Toggle motor arrows",
                            "action": self._view_toggle_motor_arrows,
                            "checked": lambda: self.view_options.get("motor_arrows", True),
                        },
                        {
                            "label": "Toggle path trace",
                            "action": self._view_toggle_path_trace,
                            "checked": lambda: self.view_options.get("path_trace", False),
                        },
                    ],
                ),
                (
                    "Panels",
                    [
                        panel_toggle("code", "Code"),
                        panel_toggle("devices", "Devices"),
                        panel_toggle("state", "State"),
                        panel_toggle("logs", "Logs"),
                        panel_toggle("console", "Console"),
                    ],
                ),
                (
                    "Help",
                    [
                        {"label": "Open help overlay" if not self.help_open else "Close help overlay", "action": self._toggle_help_overlay},
                        {
                            "label": "Device tips",
                            "action": self._toggle_device_help,
                            "checked": lambda: self.show_device_help,
                        },
                        {"label": "Quick start", "action": lambda: self._open_help_topic("quickstart")},
                        {"label": "Controllers", "action": lambda: self._open_help_topic("controllers")},
                        {"label": "Required functions", "action": lambda: self._open_help_topic("required-fns")},
                        {"label": "Sensors & motors", "action": lambda: self._open_help_topic("sensors-motors")},
                        {"label": "Simulation loop", "action": lambda: self._open_help_topic("simulation")},
                        {"label": "Logging & snapshots", "action": lambda: self._open_help_topic("logging-snapshots")},
                    ],
                ),
            ],
            pos=(20, 8),
            font=font,
        )

    def _draw_help_overlay(self) -> None:
        if not self.help_open or not self.help_topics:
            return
        w, h = self.window_size
        outer = pygame.Rect(40, 40, max(400, w - 80), max(320, h - 80))
        nav_w = 220
        padding = 12
        font_title = pygame.font.Font(pygame.font.get_default_font(), 18)
        font_nav = pygame.font.Font(pygame.font.get_default_font(), 15)
        font_body = pygame.font.Font(pygame.font.get_default_font(), 14)
        pygame.draw.rect(self.window_surface, (18, 20, 26), outer)
        pygame.draw.rect(self.window_surface, (90, 110, 140), outer, 2)
        nav_rect = pygame.Rect(outer.x + padding, outer.y + padding + 34, nav_w - padding * 2, outer.height - padding * 2 - 42)
        content_rect = pygame.Rect(nav_rect.right + padding, outer.y + padding + 34, outer.width - nav_w - padding * 3, outer.height - padding * 2 - 42)
        self.help_content_rect = content_rect
        title = font_title.render("Runner help", True, (220, 230, 240))
        self.window_surface.blit(title, (outer.x + padding, outer.y + padding))
        self.help_close_rect = pygame.Rect(outer.right - 26, outer.y + 10, 16, 16)
        pygame.draw.rect(self.window_surface, (90, 70, 70), self.help_close_rect)
        pygame.draw.rect(self.window_surface, (180, 130, 130), self.help_close_rect, 1)
        self.window_surface.blit(font_nav.render("×", True, (240, 210, 210)), (self.help_close_rect.x + 2, self.help_close_rect.y - 1))
        # Nav list
        self.help_nav_hitboxes = {}
        nav_y = nav_rect.y
        for topic in self.help_topics:
            rect = pygame.Rect(nav_rect.x, nav_y, nav_rect.width, 26)
            active = topic["id"] == self.help_active_topic
            pygame.draw.rect(self.window_surface, (36, 40, 48) if active else (26, 28, 32), rect)
            pygame.draw.rect(self.window_surface, (90, 110, 140), rect, 1)
            self.window_surface.blit(font_nav.render(str(topic["title"]), True, (210, 220, 230)), (rect.x + 6, rect.y + 4))
            self.help_nav_hitboxes[topic["id"]] = pygame.Rect(rect)
            nav_y += 28
        # Content
        topic = next((t for t in self.help_topics if t["id"] == self.help_active_topic), self.help_topics[0])
        lines: List[str] = []
        for line in topic.get("lines", []):
            lines.extend(self._wrap_text(str(line), font_body, content_rect.width - 12))
        content_height = len(lines) * 20 + 10
        self.help_last_content_height = content_height
        self._clamp_help_scroll(content_height, content_rect.height)
        pygame.draw.rect(self.window_surface, (26, 28, 32), content_rect)
        pygame.draw.rect(self.window_surface, (90, 110, 140), content_rect, 1)
        y = content_rect.y + 8 + self.help_scroll
        for line in lines:
            self.window_surface.blit(font_body.render(line, True, (210, 220, 230)), (content_rect.x + 8, y))
            y += 20
        # Footer
        footer = font_body.render("Topics snapshotted for deterministic help", True, (150, 170, 190))
        self.window_surface.blit(footer, (outer.x + padding, outer.bottom - padding - 16))
    def _draw(self) -> None:
        self.window_surface.fill((18, 18, 18))
        pygame.draw.rect(self.window_surface, (10, 10, 10), self.viewport_rect)
        pygame.draw.rect(self.window_surface, (80, 80, 80), self.viewport_rect, 1)
        if self.sim:
            self.window_surface.set_clip(self.viewport_rect)
            if self.view_options.get("grid", False):
                self._draw_grid()
            if self.world_cfg:
                self._draw_environment_overlays()
            self._draw_world()
            self.window_surface.set_clip(None)
        if self.error_paused and self.show_error_overlay and self.error_log:
            overlay_rect = pygame.Rect(self.viewport_rect.x + 12, self.viewport_rect.y + 12, 280, 60)
            pygame.draw.rect(self.window_surface, (60, 30, 30), overlay_rect)
            pygame.draw.rect(self.window_surface, (160, 80, 80), overlay_rect, 1)
            font_small = pygame.font.Font(pygame.font.get_default_font(), 14)
            self.window_surface.blit(
                font_small.render("Paused due to errors.", True, (240, 180, 180)),
                (overlay_rect.x + 8, overlay_rect.y + 8),
            )
            self.window_surface.blit(
                font_small.render("Open the Logs panel to inspect.", True, (220, 200, 200)),
                (overlay_rect.x + 8, overlay_rect.y + 30),
            )
        visible_panels = [item for item in self.dock_items.values() if item.visible]
        ordered = sorted(visible_panels, key=lambda d: (0 if d.dock != "floating" else 1, d.z))
        for item in ordered:
            self._render_panel(item)
        self.manager.draw_ui(self.window_surface)
        if self.hover_menu:
            self.hover_menu.draw(self.window_surface)
        font = pygame.font.Font(pygame.font.get_default_font(), 16)
        status = f"Scenario: {self.scenario_name or '<none>'} | Scale: {self.scale:.1f} | Offset: ({self.offset[0]:.2f},{self.offset[1]:.2f})"
        status_surf = font.render(status, True, (220, 220, 220))
        self.window_surface.blit(status_surf, (20, self.window_size[1] - 44))
        hint_surf = font.render(self.status_text, True, (190, 210, 230))
        self.window_surface.blit(hint_surf, (20, self.window_size[1] - 24))
        self._draw_help_overlay()
        pygame.display.update()

    def _render_panel(self, item: DockItem) -> None:
        rect = item.rect
        header_rect = self._panel_header_rect(item)
        inner_rect = self.panel_inner_rects.get(item.id, self._panel_inner_rect(item))
        panel_radius = 8
        pygame.draw.rect(self.window_surface, (24, 28, 32), rect, border_radius=panel_radius)
        pygame.draw.rect(self.window_surface, (90, 110, 130), rect, 1, border_radius=panel_radius)
        pygame.draw.rect(self.window_surface, (36, 42, 50), header_rect, border_radius=panel_radius)
        pygame.draw.rect(self.window_surface, (110, 130, 150), header_rect, 1, border_radius=panel_radius)
        font = pygame.font.Font(pygame.font.get_default_font(), 14)
        self.window_surface.blit(font.render(item.title, True, (210, 220, 230)), (header_rect.x + 8, header_rect.y + 5))
        dock_label = {"left": "L", "right": "R", "bottom": "B", "floating": "F"}.get(item.dock, "")
        if dock_label:
            self.window_surface.blit(font.render(dock_label, True, (160, 190, 210)), (header_rect.right - 60, header_rect.y + 5))
        close_rect = self._panel_close_rect(item)
        pygame.draw.rect(self.window_surface, (70, 50, 50), close_rect, border_radius=4)
        pygame.draw.rect(self.window_surface, (140, 110, 110), close_rect, 1, border_radius=4)
        self.window_surface.blit(font.render("×", True, (240, 200, 200)), (close_rect.x + 5, close_rect.y + 2))
        for _, hrect in self._panel_resize_handles(item):
            pygame.draw.rect(self.window_surface, (50, 60, 70), hrect, border_radius=4)
            pygame.draw.rect(self.window_surface, (120, 140, 160), hrect, 1, border_radius=4)
        if inner_rect.width > 0 and inner_rect.height > 0:
            self._draw_panel_content(item.id, inner_rect)

    def _draw_panel_content(self, panel_id: str, inner_rect: pygame.Rect) -> None:
        if panel_id == "code":
            self.controller_editor.rect = inner_rect
            # update contextual info for header (motors/sensors/dt)
            self.controller_editor.context_text = self._controller_context_line()
            self.controller_editor.draw(self.window_surface)
        elif panel_id == "devices":
            self._draw_devices_panel(inner_rect)
        elif panel_id == "state":
            self._draw_state_panel(inner_rect)
        elif panel_id == "logs":
            self._draw_logs_panel(inner_rect)
        elif panel_id == "console":
            self._draw_console_panel(inner_rect)
        elif panel_id == "plot":
            self._draw_plot_panel(inner_rect)

    def _draw_grid(self) -> None:
        min_x, min_y = screen_to_world(self.viewport_rect.bottomleft, self.viewport_rect, self.scale, self.offset)
        max_x, max_y = screen_to_world(self.viewport_rect.topright, self.viewport_rect, self.scale, self.offset)
        min_x, max_x = sorted([min_x, max_x])
        min_y, max_y = sorted([min_y, max_y])
        spacing = 0.25
        if self.scale > 600:
            spacing = 0.1
        elif self.scale < 150:
            spacing = 0.5
        start_x = math.floor(min_x / spacing) * spacing
        start_y = math.floor(min_y / spacing) * spacing
        end_x = math.ceil(max_x / spacing) * spacing
        end_y = math.ceil(max_y / spacing) * spacing
        color = (28, 32, 36)
        for x in frange(start_x, end_x + spacing, spacing):
            p1 = world_to_screen((x, min_y), self.viewport_rect, self.scale, self.offset)
            p2 = world_to_screen((x, max_y), self.viewport_rect, self.scale, self.offset)
            pygame.draw.line(self.window_surface, color, p1, p2, 1)
        for y in frange(start_y, end_y + spacing, spacing):
            p1 = world_to_screen((min_x, y), self.viewport_rect, self.scale, self.offset)
            p2 = world_to_screen((max_x, y), self.viewport_rect, self.scale, self.offset)
            pygame.draw.line(self.window_surface, color, p1, p2, 1)

    def _draw_devices_panel(self, rect: pygame.Rect) -> None:
        pygame.draw.rect(self.window_surface, (24, 28, 32), rect, border_radius=8)
        pygame.draw.rect(self.window_surface, (90, 110, 140), rect, 1, border_radius=8)
        header = pygame.font.SysFont(pygame.font.get_default_font(), 18, bold=True)
        section = pygame.font.SysFont(pygame.font.get_default_font(), 15, bold=True)
        body = pygame.font.Font(pygame.font.get_default_font(), 14)
        mono = pygame.font.SysFont("Menlo", 14) or body

        self.window_surface.blit(header.render("Available devices", True, (200, 220, 240)), (rect.x + 10, rect.y + 8))
        y = rect.y + 38

        motors_list: List[str] = []
        sensors_list: List[str] = []
        if self.sim:
            for name, motor in self.sim.motors.items():
                tag = getattr(motor, "visual_tag", "") or motor.__class__.__name__
                motors_list.append(f"{name} ({tag})" if tag else name)
            for name, sensor in self.sim.sensors.items():
                stype = getattr(sensor, "visual_tag", "") or sensor.__class__.__name__
                sensors_list.append(f"{name} ({stype})" if stype else name)

        def draw_list(title: str, items: List[str]) -> None:
            nonlocal y
            self.window_surface.blit(section.render(title, True, (190, 205, 230)), (rect.x + 10, y))
            y += 22
            if not items:
                self.window_surface.blit(body.render("• none detected", True, (180, 185, 190)), (rect.x + 18, y))
                y += 20
                return
            for idx, item in enumerate(items, 1):
                text = f"{idx}. {item}"
                self.window_surface.blit(body.render(text, True, (210, 215, 225)), (rect.x + 16, y))
                y += 18
            y += 10

        draw_list("Motors", motors_list)
        draw_list("Sensors", sensors_list)

        if not self.show_device_help:
            return

        self.window_surface.blit(section.render("Controller hints", True, (190, 205, 230)), (rect.x + 10, y))
        y += 22
        examples = [
            "Command: sim.motors['left'].command(0.5, sim, dt)",
            "Read:    sensors['front']",
            "Encoders: sensors['enc'].value",
        ]
        for line in examples:
            self.window_surface.blit(mono.render(line, True, (205, 220, 235)), (rect.x + 16, y))
            y += 18
        y += 6
        tips = [
            "Use State to watch + log signals.",
            "Hover menu holds view and snapshot toggles.",
        ]
        for line in tips:
            self.window_surface.blit(body.render(f"• {line}", True, (190, 205, 215)), (rect.x + 16, y))
            y += 18

    def _draw_state_panel(self, rect: pygame.Rect) -> None:
        pygame.draw.rect(self.window_surface, (22, 24, 28), rect, border_radius=8)
        pygame.draw.rect(self.window_surface, (70, 90, 120), rect, 1, border_radius=8)
        font = pygame.font.Font(pygame.font.get_default_font(), 16)
        small = pygame.font.Font(pygame.font.get_default_font(), 14)
        self.signal_hitboxes = {}
        self.roster_hitboxes = {}
        self.window_surface.blit(font.render("Live state + logger", True, (190, 210, 230)), (rect.x + 8, rect.y + 6))
        roster = list(getattr(self.sim, "robot_ids", []) or [])
        active_id = self.active_robot_id or (roster[0] if roster else None)
        ctrl_errors: Dict[str, str] = self.live_state.get("controller_errors", {}) or {}
        y = rect.y + 32
        if roster:
            self.window_surface.blit(small.render("Robots:", True, (180, 200, 220)), (rect.x + 8, y))
            y += 20
            chip_x = rect.x + 12
            chip_y = y
            for rid in roster:
                err = ctrl_errors.get(rid)
                label = rid
                text = small.render(label, True, (230, 235, 240))
                chip_w = text.get_width() + 16
                chip_rect = pygame.Rect(chip_x, chip_y, chip_w, 22)
                fill = (60, 70, 80)
                border = (90, 110, 130)
                if rid == active_id:
                    fill = (50, 80, 70)
                    border = (120, 200, 150)
                if err:
                    fill = (70, 40, 40)
                    border = (200, 120, 120)
                pygame.draw.rect(self.window_surface, fill, chip_rect, border_radius=6)
                pygame.draw.rect(self.window_surface, border, chip_rect, 1, border_radius=6)
                self.window_surface.blit(text, (chip_rect.x + 8, chip_rect.y + 3))
                self.roster_hitboxes[rid] = chip_rect
                chip_x = chip_rect.right + 8
                if chip_x > rect.right - chip_w:
                    chip_x = rect.x + 12
                    chip_y += 26
            y = chip_y + 30
        logger_line = f"{self.logger_status} | samples: {len(self.logger_samples)} | rate: {1.0/self.logger_interval:.1f} Hz"
        self.window_surface.blit(small.render(logger_line, True, (200, 210, 220)), (rect.x + 8, y))
        y += 18
        self.window_surface.blit(small.render("Use Capture menu to start/stop and export logs.", True, (170, 190, 210)), (rect.x + 8, y))
        y += 18
        physics_warn = self.live_state.get("physics_warning")
        if physics_warn:
            self.window_surface.blit(small.render(f"Physics: {physics_warn}", True, (220, 170, 150)), (rect.x + 8, y))
            y += 18
        if active_id and ctrl_errors.get(active_id):
            self.window_surface.blit(
                small.render(f"{active_id}: controller error logged", True, (220, 170, 170)),
                (rect.x + 8, y),
            )
            y += 18
        per_robot = self.live_state.get("per_robot", {}) or {}
        grouped = per_robot if per_robot else {"signals": {"motors": self.live_state.get("motors", {}), "sensors": self.live_state.get("sensors", {})}}
        self.window_surface.blit(small.render("Live signals:", True, (180, 200, 220)), (rect.x + 8, y))
        y += 18

        def draw_sig(label: str, enabled: bool, y_pos: int) -> None:
            box = pygame.Rect(rect.x + 12, y_pos, 14, 14)
            pygame.draw.rect(self.window_surface, (60, 70, 80), box, 1)
            if enabled:
                pygame.draw.rect(self.window_surface, (80, 200, 140), box.inflate(-4, -4))
            text = small.render(label, True, (210, 220, 230))
            self.window_surface.blit(text, (box.right + 6, y_pos - 2))
            self.signal_hitboxes[label] = pygame.Rect(box)

        for rid, state in grouped.items():
            label = "Active robot" if rid == active_id else ("Signals" if rid == "signals" else f"Robot {rid}")
            self.window_surface.blit(small.render(label, True, (180, 210, 230)), (rect.x + 10, y))
            y += 18
            motors = state.get("motors", {}) or {}
            sensors = state.get("sensors", {}) or {}
            if not motors and not sensors:
                self.window_surface.blit(small.render("• no signals yet", True, (170, 180, 190)), (rect.x + 18, y))
                y += 18
            for name, val in motors.items():
                line = f"motor {name}: {self._fmt_value(val)}"
                self.window_surface.blit(small.render(line, True, (180, 220, 180)), (rect.x + 18, y))
                y += 16
                draw_sig(f"motor:{name}", f"motor:{name}" in self.logger_selected, y)
                y += 18
            for name, val in sensors.items():
                line = f"sensor {name}: {self._fmt_value(val)}"
                self.window_surface.blit(small.render(line, True, (200, 200, 180)), (rect.x + 18, y))
                y += 16
                draw_sig(f"sensor:{name}", f"sensor:{name}" in self.logger_selected, y)
                y += 18
            y += 8

    def _panel_menu_options(self) -> List[Tuple[str, str]]:
        return [
            ("code", "Code"),
            ("console", "Console"),
            ("devices", "Devices"),
            ("state", "State"),
            ("logs", "Logs"),
            ("plot", "CSV Plot"),
        ]

    def _handle_panel_menu_event(self, event: pygame.event.Event) -> bool:
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return False
        btn_rect = self._panel_menu_rect()
        if btn_rect.collidepoint(event.pos):
            self.panel_menu_open = not self.panel_menu_open
            return True
        if not self.panel_menu_open:
            return False
        for pid, rect in self.panel_menu_regions.items():
            if rect.collidepoint(event.pos):
                item = self.dock_items.get(pid)
                if item:
                    item.visible = not item.visible
                    self._bump_panel(pid)
                    self._update_layout()
                    self._save_panel_layout()
                return True
        # Close if clicked outside menu
        self.panel_menu_open = False
        return False

    def _draw_panel_menu(self) -> None:
        btn_rect = self._panel_menu_rect()
        pygame.draw.rect(self.window_surface, (30, 34, 38), btn_rect)
        pygame.draw.rect(self.window_surface, (90, 110, 130), btn_rect, 1)
        font = pygame.font.Font(pygame.font.get_default_font(), 14)
        label = "Panels ▼" if not self.panel_menu_open else "Panels ▲"
        self.window_surface.blit(font.render(label, True, (200, 210, 220)), (btn_rect.x + 8, btn_rect.y + 6))
        if not self.panel_menu_open:
            self.panel_menu_regions = {}
            return
        options = self._panel_menu_options()
        menu_w = 220
        menu_h = len(options) * 28 + 12
        menu_rect = pygame.Rect(btn_rect.x, btn_rect.bottom + 4, menu_w, menu_h)
        pygame.draw.rect(self.window_surface, (24, 26, 30), menu_rect)
        pygame.draw.rect(self.window_surface, (80, 100, 120), menu_rect, 1)
        self.panel_menu_regions = {}
        for i, (pid, label) in enumerate(options):
            row = pygame.Rect(menu_rect.x + 6, menu_rect.y + 6 + i * 28, menu_w - 12, 24)
            pygame.draw.rect(self.window_surface, (30, 34, 40), row)
            pygame.draw.rect(self.window_surface, (70, 90, 110), row, 1)
            item = self.dock_items.get(pid)
            checked = bool(item and item.visible)
            box = pygame.Rect(row.x + 6, row.y + 4, 16, 16)
            pygame.draw.rect(self.window_surface, (90, 110, 130), box, 1)
            if checked:
                pygame.draw.rect(self.window_surface, (120, 200, 150), box.inflate(-4, -4))
            self.window_surface.blit(font.render(label, True, (210, 220, 230)), (box.right + 6, row.y + 4))
            self.panel_menu_regions[pid] = row

    def _draw_logs_panel(self, rect: pygame.Rect) -> None:
        content_font = pygame.font.Font(pygame.font.get_default_font(), 14)
        font = pygame.font.Font(pygame.font.get_default_font(), 15)
        has_error = bool(self.error_log)
        bg = (30, 22, 22) if has_error else (22, 26, 22)
        pygame.draw.rect(self.window_surface, bg, rect, border_radius=8)
        pygame.draw.rect(self.window_surface, (90, 70, 70) if has_error else (70, 90, 70), rect, 1, border_radius=8)
        header = f"Errors ({len(self.error_log)})"
        self.window_surface.blit(
            font.render(header, True, (240, 140, 140) if has_error else (160, 190, 160)),
            (rect.x + 8, rect.y + 6),
        )
        y = rect.y + 28
        max_width = rect.width - 16
        if not has_error:
            self.window_surface.blit(
                content_font.render("No errors. Happy coding!", True, (170, 190, 170)),
                (rect.x + 8, y),
            )
            return
        latest = self.error_log[-1]
        body_lines: List[str] = []
        if latest.get("title"):
            body_lines.extend(self._wrap_text(latest["title"], content_font, max_width))
        if latest.get("line"):
            body_lines.append(latest["line"])
        detail_lines = self._wrap_text(latest.get("details", ""), content_font, max_width)
        body_lines.extend(detail_lines[-8:])
        for line in body_lines:
            if y > rect.bottom - 18:
                break
            self.window_surface.blit(content_font.render(line, True, (230, 200, 200)), (rect.x + 8, y))
            y += 18

    def _draw_console_panel(self, rect: pygame.Rect) -> None:
        content_font = pygame.font.Font(pygame.font.get_default_font(), 14)
        font = pygame.font.Font(pygame.font.get_default_font(), 15)
        bg = (22, 26, 30)
        pygame.draw.rect(self.window_surface, bg, rect, border_radius=8)
        pygame.draw.rect(self.window_surface, (70, 90, 120), rect, 1, border_radius=8)
        header = "Console output"
        self.window_surface.blit(font.render(header, True, (180, 210, 240)), (rect.x + 8, rect.y + 6))
        y = rect.y + 28
        max_width = rect.width - 16
        lines = self.console_lines[-20:] if self.console_lines else []
        if not lines:
            self.window_surface.blit(
                content_font.render("No prints yet.", True, (170, 190, 210)), (rect.x + 8, y)
            )
            return
        for line in lines:
            wrapped = self._wrap_text(line, content_font, max_width)
            for w in wrapped:
                if y > rect.bottom - 18:
                    return
                self.window_surface.blit(content_font.render(w, True, (210, 220, 230)), (rect.x + 8, y))
                y += 18

    def _draw_plot_panel(self, rect: pygame.Rect) -> None:
        font = pygame.font.Font(pygame.font.get_default_font(), 15)
        small = pygame.font.Font(pygame.font.get_default_font(), 13)
        bg = (22, 26, 30)
        pygame.draw.rect(self.window_surface, bg, rect, border_radius=8)
        pygame.draw.rect(self.window_surface, (70, 90, 120), rect, 1, border_radius=8)
        self.window_surface.blit(font.render("CSV plotter", True, (190, 210, 240)), (rect.x + 8, rect.y + 6))
        self.plot_hitboxes = {}
        open_rect = pygame.Rect(rect.x + 8, rect.y + 32, 120, 24)
        pygame.draw.rect(self.window_surface, (40, 60, 80), open_rect, border_radius=4)
        pygame.draw.rect(self.window_surface, (110, 140, 170), open_rect, 1, border_radius=4)
        self.window_surface.blit(small.render("Load CSV…", True, (210, 220, 230)), (open_rect.x + 8, open_rect.y + 4))
        self.plot_hitboxes["__open__"] = open_rect
        clear_rect = pygame.Rect(open_rect.right + 8, open_rect.y, 90, 24)
        pygame.draw.rect(self.window_surface, (50, 50, 60), clear_rect, border_radius=4)
        pygame.draw.rect(self.window_surface, (110, 110, 130), clear_rect, 1, border_radius=4)
        self.window_surface.blit(small.render("Clear", True, (210, 210, 220)), (clear_rect.x + 8, clear_rect.y + 4))
        self.plot_hitboxes["__clear__"] = clear_rect
        info_y = clear_rect.bottom + 6
        source_label = f"Source: {self.plot_source.name}" if self.plot_source else "Source: —"
        self.window_surface.blit(small.render(source_label, True, (190, 200, 210)), (rect.x + 8, info_y))
        info_y += 18
        self.window_surface.blit(small.render(self.plot_status, True, (170, 200, 220)), (rect.x + 8, info_y))
        toggle_x = rect.x + 8
        toggle_y = info_y + 18
        columns = [c for c in self.plot_data.keys() if c]
        if "t" in columns:
            columns = [c for c in columns if c != "t"] + ["t"]
        for col in columns:
            box = pygame.Rect(toggle_x, toggle_y, 14, 14)
            pygame.draw.rect(self.window_surface, (60, 70, 80), box, 1)
            if col in self.plot_selected_cols:
                pygame.draw.rect(self.window_surface, (90, 170, 120), box.inflate(-4, -4))
            label = small.render(col, True, (210, 220, 230))
            self.window_surface.blit(label, (box.right + 6, box.y - 2))
            self.plot_hitboxes[col] = pygame.Rect(box)
            toggle_y += 18
            if toggle_y > rect.bottom - 40:
                toggle_y = info_y + 18
                toggle_x += 140
        plot_rect = pygame.Rect(rect.x + 8 + 140, rect.y + 60, rect.width - 156, rect.height - 70)
        pygame.draw.rect(self.window_surface, (18, 20, 24), plot_rect, border_radius=4)
        pygame.draw.rect(self.window_surface, (80, 90, 110), plot_rect, 1, border_radius=4)
        if not self.plot_data or not self.plot_selected_cols:
            msg = "Select a CSV file and choose columns."
            self.window_surface.blit(small.render(msg, True, (180, 190, 200)), (plot_rect.x + 12, plot_rect.y + 12))
            return
        time_axis = self.plot_data.get("t")
        if not time_axis:
            any_series = next(iter(self.plot_data.values()), [])
            time_axis = list(range(len(any_series)))
        selected_cols = [c for c in self.plot_selected_cols if c in self.plot_data]
        if not selected_cols:
            return
        max_len = min(len(time_axis), *(len(self.plot_data[c]) for c in selected_cols))
        if max_len <= 1:
            self.window_surface.blit(small.render("Not enough samples to plot.", True, (190, 180, 180)), (plot_rect.x + 12, plot_rect.y + 12))
            return
        xs = [float(time_axis[i]) for i in range(max_len) if time_axis[i] is not None]
        x_min = min(xs) if xs else 0.0
        x_max = max(xs) if xs else 1.0
        if abs(x_max - x_min) < 1e-9:
            x_max = x_min + 1.0
        color_palette = [
            (120, 200, 255),
            (200, 160, 120),
            (140, 220, 170),
            (220, 140, 180),
            (180, 180, 120),
        ]
        y_min = float("inf")
        y_max = float("-inf")
        for col in selected_cols:
            series = self.plot_data[col]
            for i in range(min(max_len, len(series))):
                val = series[i]
                if val is None:
                    continue
                y_min = min(y_min, val)
                y_max = max(y_max, val)
        if not math.isfinite(y_min) or not math.isfinite(y_max) or abs(y_max - y_min) < 1e-9:
            y_min, y_max = -1.0, 1.0
        padding = max(1e-3, (y_max - y_min) * 0.05)
        y_min -= padding
        y_max += padding

        def to_screen(x_val: float, y_val: float) -> Tuple[int, int]:
            x_norm = (x_val - x_min) / (x_max - x_min)
            y_norm = (y_val - y_min) / (y_max - y_min)
            sx = plot_rect.x + int(x_norm * (plot_rect.width - 6)) + 3
            sy = plot_rect.bottom - int(y_norm * (plot_rect.height - 6)) - 3
            return (sx, sy)

        for idx, col in enumerate(selected_cols):
            series = self.plot_data[col]
            pts: List[Tuple[int, int]] = []
            for i in range(min(max_len, len(series))):
                y_val = series[i]
                x_val = float(time_axis[i]) if i < len(time_axis) else float(i)
                if y_val is None or not math.isfinite(y_val):
                    if len(pts) > 1:
                        pygame.draw.lines(self.window_surface, color_palette[idx % len(color_palette)], False, pts, 2)
                    pts = []
                    continue
                pts.append(to_screen(x_val, float(y_val)))
            if len(pts) > 1:
                pygame.draw.lines(self.window_surface, color_palette[idx % len(color_palette)], False, pts, 2)
            label = small.render(col, True, color_palette[idx % len(color_palette)])
            self.window_surface.blit(label, (plot_rect.x + 10 + idx * 80, plot_rect.bottom - 22))

    def _draw_environment_overlays(self) -> None:
        if not self.world_cfg:
            return
        rot = getattr(self, "view_rotation", 0.0)
        if getattr(self.world_cfg, "bounds", None):
            b = self.world_cfg.bounds
            assert b
            corners = [
                (b.min_x, b.min_y),
                (b.min_x, b.max_y),
                (b.max_x, b.max_y),
                (b.max_x, b.min_y),
            ]
            pts = [world_to_screen(c, self.viewport_rect, self.scale, self.offset, rot) for c in corners]
            pygame.draw.polygon(self.window_surface, (70, 90, 120), pts, max(1, int(0.02 * self.scale)))
        strokes = getattr(self.world_cfg, "drawings", []) or []
        for stroke in strokes:
            if not getattr(stroke, "points", None) or len(stroke.points) < 2:
                continue
            color = tuple(getattr(stroke, "color", (140, 200, 255)))
            pts = [world_to_screen(p, self.viewport_rect, self.scale, self.offset, rot) for p in stroke.points]
            width = max(1, int(max(1.0, stroke.thickness * self.scale)))
            pygame.draw.lines(self.window_surface, color, False, pts, width)
            if getattr(stroke, "kind", "mark") != "wall":
                continue
            pygame.draw.lines(self.window_surface, (40, 50, 60), False, pts, 1)

    def _draw_world(self) -> None:
        assert self.sim
        for body in self.sim.bodies.values():
            color = getattr(body.material, "custom", {}).get("color", None) or (140, 140, 140)
            if isinstance(body.shape, Polygon):
                verts = body.shape._world_vertices(body.pose)
                pts = [world_to_screen(v, self.viewport_rect, self.scale, self.offset) for v in verts]
                pygame.draw.polygon(self.window_surface, color, pts, 0)
                pygame.draw.polygon(self.window_surface, (30, 30, 30), pts, 1)
        if self.view_options.get("path_trace", False) and self.path_trace:
            pts = [world_to_screen(p, self.viewport_rect, self.scale, self.offset) for p in self.path_trace]
            if len(pts) >= 2:
                pygame.draw.lines(self.window_surface, (90, 160, 230), False, pts, 2)
            else:
                pygame.draw.circle(self.window_surface, (90, 160, 230), pts[0], 3)
        if self.robot_dragging and self.reposition_target:
            px, py = self.reposition_target
            center = world_to_screen((px, py), self.viewport_rect, self.scale, self.offset)
            pygame.draw.circle(self.window_surface, (120, 160, 220), center, 8, 2)
            pygame.draw.line(self.window_surface, (120, 160, 220), (center[0] - 8, center[1]), (center[0] + 8, center[1]), 1)
            pygame.draw.line(self.window_surface, (120, 160, 220), (center[0], center[1] - 8), (center[0], center[1] + 8), 1)
        # motor arrows
        if self.view_options.get("motor_arrows", True):
            def draw_arrow_with_head(start: Tuple[int, int], end: Tuple[int, int], color: Tuple[int, int, int]) -> None:
                pygame.draw.line(self.window_surface, color, start, end, 3)
                vx = end[0] - start[0]
                vy = end[1] - start[1]
                length = math.hypot(vx, vy)
                if length < 1e-3:
                    return
                nx, ny = vx / length, vy / length
                perp = (-ny, nx)
                head_len = 10
                head_w = 5
                tip = end
                left = (end[0] - nx * head_len + perp[0] * head_w, end[1] - ny * head_len + perp[1] * head_w)
                right = (end[0] - nx * head_len - perp[0] * head_w, end[1] - ny * head_len - perp[1] * head_w)
                pygame.draw.polygon(self.window_surface, color, [tip, left, right])
            for motor in self.sim.motors.values():
                parent = motor.parent
                if not parent:
                    continue
                pose = parent.pose.compose(motor.mount_pose)
                direction = (pygame.math.Vector2(1, 0).rotate_rad(pose.theta).x, pygame.math.Vector2(1, 0).rotate_rad(pose.theta).y)
                sign = 1 if motor.last_command >= 0 else -1
                length = 0.06 + abs(motor.last_command) * 0.09
                start_world = (pose.x + direction[0] * 0.02 * sign, pose.y + direction[1] * 0.02 * sign)
                end_world = (pose.x + direction[0] * (length + 0.02) * sign, pose.y + direction[1] * (length + 0.02) * sign)
                start = world_to_screen(start_world, self.viewport_rect, self.scale, self.offset)
                end = world_to_screen(end_world, self.viewport_rect, self.scale, self.offset)
                color = (0, 200, 120) if motor.last_command >= 0 else (200, 80, 80)
                wheel_radius = max(3, int(self.scale * 0.01))
                pygame.draw.circle(self.window_surface, (28, 34, 42), start, wheel_radius)
                pygame.draw.circle(self.window_surface, color, start, wheel_radius, 2)
                draw_arrow_with_head(start, end, color)
        # robot center hover indicator
        center = self._current_robot_center()
        if center:
            screen_center = world_to_screen(center, self.viewport_rect, self.scale, self.offset)
            color = (140, 200, 255) if (self.hover_robot_center or self.robot_dragging) else (90, 130, 170)
            pygame.draw.circle(self.window_surface, color, screen_center, 7, 2)
            pygame.draw.line(self.window_surface, color, (screen_center[0] - 6, screen_center[1]), (screen_center[0] + 6, screen_center[1]), 1)
            pygame.draw.line(self.window_surface, color, (screen_center[0], screen_center[1] - 6), (screen_center[0], screen_center[1] + 6), 1)


def main():
    app = RunnerApp()
    app.run()


if __name__ == "__main__":
    main()

