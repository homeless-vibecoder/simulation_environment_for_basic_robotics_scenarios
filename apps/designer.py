"""Robot/world designer app: edit polygons and attach generic devices."""
from __future__ import annotations

import sys
import json
from pathlib import Path
from typing import Optional, Tuple, List, Dict
import copy
import math

import pygame
import pygame_gui
from pygame_gui.windows import UIFileDialog

sys.path.append(str(Path(__file__).resolve().parent.parent))

from core import (  # noqa: E402
    load_scenario,
    save_scenario,
    save_robot_design,
    load_robot_design,
    save_environment_design,
    load_environment_design,
    save_custom_asset,
    load_custom_asset,
)  # noqa: E402
from core.controller_store import list_controllers  # noqa: E402
from core.config import (  # noqa: E402
    RobotConfig,
    WorldConfig,
    BodyConfig,
    ActuatorConfig,
    SensorConfig,
    StrokeConfig,
    EnvironmentBounds,
    WorldObjectConfig,
    CustomObjectConfig,
    DesignerState,
    save_json,
    load_json,
)
from core.simulator import Simulator  # noqa: E402
from apps.shared_ui import (  # noqa: E402
    list_scenarios,
    draw_polygon,
    world_to_screen,
    screen_to_world,
    HoverMenu,
    DESIGNER_THEME,
    lighten_color,
    darken_color,
    with_alpha,
)
from low_level_mechanics.geometry import Polygon  # noqa: E402
from low_level_mechanics.world import Pose2D  # noqa: E402


class DesignerApp:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Designer")
        self.window_size = (1280, 760)
        self.window_surface = pygame.display.set_mode(self.window_size)
        self.manager = pygame_gui.UIManager(self.window_size)
        self.theme = DESIGNER_THEME
        self.clock = pygame.time.Clock()
        self.running = True

        self.base_path = Path(__file__).resolve().parent.parent
        self.scenario_root = self.base_path / "scenarios"
        self.scenario_entries = list_scenarios(self.scenario_root, with_metadata=True)
        self.scenario_lookup = {entry.id: entry for entry in self.scenario_entries}
        self.scenario_names = [entry.id for entry in self.scenario_entries]
        self.scenario_name = None
        self.world_cfg: Optional[WorldConfig] = None
        self.robot_cfg: Optional[RobotConfig] = None
        self.sim: Optional[Simulator] = None
        self.loaded_robots: List[object] = []
        self.active_robot_id: Optional[str] = None
        self.scenario_descriptor: Optional[object] = None  # preserve metadata/robots
        self.scenario_description: Optional[str] = None
        self.scenario_thumbnail: Optional[pygame.Surface] = None
        self.scratch_scenario_name = "__scratch__"

        self.viewport_rect = pygame.Rect(20, 70, self.window_size[0] - 360, self.window_size[1] - 90)
        self.scale = 400.0
        self.offset = (0.0, 0.0)
        self.grid_enabled = False
        self.hover_world: Optional[Tuple[float, float]] = None

        self.body_name: Optional[str] = None
        self.mode: str = "select"  # select/move, add, delete, add_device
        self.hover_point: Optional[int] = None
        self.selected_point: Optional[int] = None
        self.hover_device: Optional[Tuple[str, str]] = None  # (kind, name)
        self.selected_device: Optional[Tuple[str, str]] = None
        self.selected_points: set[int] = set()
        self.marquee_active: bool = False
        self.marquee_start: Optional[Tuple[float, float]] = None
        self.marquee_end: Optional[Tuple[float, float]] = None
        self.dragging: bool = False
        self.drag_mode: Optional[str] = None  # None/move/scale
        self.drag_handle: Optional[str] = None
        self.drag_points_snapshot: Dict[int, Tuple[float, float]] = {}
        self.drag_start_local: Optional[Tuple[float, float]] = None
        self.drag_scale_center: Optional[Tuple[float, float]] = None
        self.drag_scale_origin_vec: Optional[Tuple[float, float]] = None
        self.dragging_device: bool = False
        self.clipboard: Dict[str, object] = {"points": [], "devices": []}
        self.pending_device_type: Optional[str] = None
        self.status_hint: str = ""
        self.pan_active: bool = False
        self.pan_start: Optional[Tuple[int, int]] = None
        self.undo_stack: List[RobotConfig] = []
        self.redo_stack: List[RobotConfig] = []
        self.hover_menu: Optional[HoverMenu] = None
        self.env_tool: str = "off"  # off | mark | wall
        self.env_brush_thickness: float = 0.05
        self.env_drawing: bool = False
        self.env_stroke_points: List[Tuple[float, float]] = []
        self.bounds_mode: bool = False
        self.bounds_start: Optional[Tuple[float, float]] = None
        self.bounds_preview: Optional[Tuple[float, float]] = None
        self.world_undo_stack: List[WorldConfig] = []
        self.world_redo_stack: List[WorldConfig] = []
        self.view_rotation: float = 0.0
        self.rotate_active: bool = False
        self.rotate_anchor: Optional[Tuple[int, int]] = None
        self.rotate_start_angle: float = 0.0
        self.creation_context: str = "robot"  # robot | environment | custom
        self.shape_tool: str = "rect"  # rect | triangle | line
        self.shape_start: Optional[Tuple[float, float]] = None
        self.shape_preview: Optional[Tuple[float, float]] = None
        self.active_tab: str = "robot"  # robot | environment | custom
        self.robot_dirty: bool = False
        self.env_dirty: bool = False
        self.custom_dirty: bool = False
        self.robot_design_name: str = "untitled_robot"
        self.env_design_name: str = "untitled_env"
        self.custom_design_name: str = "untitled_custom"
        self.custom_active: Optional[CustomObjectConfig] = None
        self.pending_tab: Optional[str] = None
        self.pending_dialog: Optional[pygame_gui.windows.UIConfirmationDialog] = None
        self.pending_workspace_action: Optional[Tuple[str, str]] = None  # (action, kind)
        self.custom_undo_stack: List[CustomObjectConfig] = []
        self.custom_redo_stack: List[CustomObjectConfig] = []

        # UI helpers
        self.custom_message = ""
        self.workspace_new_window: Optional[pygame_gui.elements.UIWindow] = None
        self.workspace_new_entry: Optional[pygame_gui.elements.UITextEntryLine] = None
        self.workspace_new_kind: Optional[str] = None
        self.workspace_file_dialog: Optional[UIFileDialog] = None
        self.workspace_file_kind: Optional[str] = None
        self.workspace_file_mode: Optional[str] = None
        self.workspace_dialog: Optional[pygame_gui.elements.UIWindow] = None
        self.workspace_type_dropdown: Optional[pygame_gui.elements.UIDropDownMenu] = None
        self.workspace_action_dropdown: Optional[pygame_gui.elements.UIDropDownMenu] = None
        self.workspace_name_entry: Optional[pygame_gui.elements.UITextEntryLine] = None
        self.workspace_file_type: Optional[str] = None
        self.workspace_save_as_window: Optional[pygame_gui.elements.UIWindow] = None
        self.workspace_save_as_entry: Optional[pygame_gui.elements.UITextEntryLine] = None
        self.workspace_save_as_kind: Optional[str] = None
        self.device_import_dialog: Optional[UIFileDialog] = None

        self._build_ui()
        self._init_hover_menu()
        self._init_blank_workspaces()

    def _build_ui(self) -> None:
        self.dropdown = pygame_gui.elements.UIDropDownMenu(
            options_list=(["<none>"] + self.scenario_names) if self.scenario_names else ["<none>"],
            starting_option=self.scenario_name or "<none>",
            relative_rect=pygame.Rect((20, 20), (200, 30)),
            manager=self.manager,
        )
        self.btn_load = pygame_gui.elements.UIButton(
            pygame.Rect((230, 20), (120, 30)), "Load", manager=self.manager, tool_tip_text="Load selected scenario"
        )
        self.btn_save = pygame_gui.elements.UIButton(
            pygame.Rect((360, 20), (120, 30)), "Save", manager=self.manager, tool_tip_text="Save scenario files"
        )

        self.body_dropdown = pygame_gui.elements.UIDropDownMenu(
            options_list=["<none>"],
            starting_option="<none>",
            relative_rect=pygame.Rect((self.window_size[0] - 320, 20), (140, 30)),
            manager=self.manager,
        )
        self.btn_add_point = pygame_gui.elements.UIButton(
            pygame.Rect((self.window_size[0] - 170, 20), (150, 30)),
            "Add point",
            manager=self.manager,
            tool_tip_text="Add a vertex by clicking in the canvas",
        )
        self.btn_move_point = pygame_gui.elements.UIButton(
            pygame.Rect((self.window_size[0] - 170, 60), (150, 30)),
            "Select/Move",
            manager=self.manager,
            tool_tip_text="Select and drag vertices",
        )
        self.btn_del_point = pygame_gui.elements.UIButton(
            pygame.Rect((self.window_size[0] - 170, 100), (150, 30)),
            "Delete point",
            manager=self.manager,
            tool_tip_text="Delete a vertex by clicking it",
        )
        self.device_dropdown = pygame_gui.elements.UIDropDownMenu(
            options_list=["motor", "distance", "line", "imu", "encoder"],
            starting_option="motor",
            relative_rect=pygame.Rect((self.window_size[0] - 320, 60), (140, 30)),
            manager=self.manager,
        )
        self.btn_undo = pygame_gui.elements.UIButton(
            pygame.Rect((self.window_size[0] - 320, 140), (70, 30)),
            "Undo",
            manager=self.manager,
            tool_tip_text="Undo last edit",
        )
        self.btn_redo = pygame_gui.elements.UIButton(
            pygame.Rect((self.window_size[0] - 240, 140), (70, 30)),
            "Redo",
            manager=self.manager,
            tool_tip_text="Redo last edit",
        )
        # Inspector panel for devices/bodies
        panel_rect = pygame.Rect((self.window_size[0] - 340, 190), (320, 240))
        self.inspector_panel = pygame_gui.elements.UIPanel(relative_rect=panel_rect, manager=self.manager)
        self.lbl_selection = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect((10, 10), (300, 22)),
            text="Selection: none",
            manager=self.manager,
            container=self.inspector_panel,
        )
        self.lbl_selection_type = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect((10, 36), (140, 22)),
            text="Type: —",
            manager=self.manager,
            container=self.inspector_panel,
        )
        self.txt_device_name = pygame_gui.elements.UITextEntryLine(
            relative_rect=pygame.Rect((10, 62), (180, 26)),
            manager=self.manager,
            container=self.inspector_panel,
        )
        self.txt_device_name.set_text("")
        self.lbl_device_body = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect((10, 92), (180, 22)),
            text="Body: —",
            manager=self.manager,
            container=self.inspector_panel,
        )
        self.lbl_pose = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect((10, 118), (300, 22)),
            text="Pose (x,y,θ):",
            manager=self.manager,
            container=self.inspector_panel,
        )
        self.txt_pose_x = pygame_gui.elements.UITextEntryLine(
            relative_rect=pygame.Rect((10, 142), (90, 26)),
            manager=self.manager,
            container=self.inspector_panel,
        )
        self.txt_pose_y = pygame_gui.elements.UITextEntryLine(
            relative_rect=pygame.Rect((110, 142), (90, 26)),
            manager=self.manager,
            container=self.inspector_panel,
        )
        self.txt_pose_theta = pygame_gui.elements.UITextEntryLine(
            relative_rect=pygame.Rect((210, 142), (90, 26)),
            manager=self.manager,
            container=self.inspector_panel,
        )
        self.btn_apply_device = pygame_gui.elements.UIButton(
            pygame.Rect((10, 180), (140, 30)),
            "Apply",
            manager=self.manager,
            container=self.inspector_panel,
        )
        self.btn_delete_device = pygame_gui.elements.UIButton(
            pygame.Rect((170, 180), (140, 30)),
            "Delete",
            manager=self.manager,
            container=self.inspector_panel,
        )
        paint_rect = pygame.Rect((self.window_size[0] - 340, 440), (320, 150))
        self.paint_panel = pygame_gui.elements.UIPanel(relative_rect=paint_rect, manager=self.manager)
        self.paint_mode_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect((10, 8), (200, 22)),
            text="Paint: off",
            manager=self.manager,
            container=self.paint_panel,
        )
        self.btn_brush_mark = pygame_gui.elements.UIButton(
            pygame.Rect((10, 36), (90, 26)),
            "Mark",
            manager=self.manager,
            container=self.paint_panel,
        )
        self.btn_brush_wall = pygame_gui.elements.UIButton(
            pygame.Rect((110, 36), (90, 26)),
            "Wall",
            manager=self.manager,
            container=self.paint_panel,
        )
        self.btn_brush_off = pygame_gui.elements.UIButton(
            pygame.Rect((210, 36), (90, 26)),
            "Exit",
            manager=self.manager,
            container=self.paint_panel,
        )
        self.brush_slider = pygame_gui.elements.UIHorizontalSlider(
            pygame.Rect((10, 70), (200, 22)),
            start_value=self.env_brush_thickness,
            value_range=(0.01, 0.2),
            manager=self.manager,
            container=self.paint_panel,
        )
        self.brush_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect((220, 70), (90, 22)),
            text=f"{self.env_brush_thickness:.3f} m",
            manager=self.manager,
            container=self.paint_panel,
        )
        self.btn_brush_clear = pygame_gui.elements.UIButton(
            pygame.Rect((10, 104), (90, 26)),
            "Clear",
            manager=self.manager,
            container=self.paint_panel,
        )
        self.btn_brush_undo = pygame_gui.elements.UIButton(
            pygame.Rect((110, 104), (90, 26)),
            "Undo env",
            manager=self.manager,
            container=self.paint_panel,
        )
        self.paint_panel.hide()
        self.status_hint = "Select and drag points or devices. Right-drag to pan."
        self._update_mode_buttons()
        # Hide legacy top controls; hover menus will replace them.
        for ctrl in [
            self.dropdown,
            self.btn_load,
            self.btn_save,
            self.body_dropdown,
            self.btn_add_point,
            self.btn_move_point,
            self.btn_del_point,
            self.device_dropdown,
            self.btn_undo,
            self.btn_redo,
        ]:
            ctrl.hide()

    def _init_hover_menu(self) -> None:
        # Build the full menu immediately so all sections are available on first frame.
        self._refresh_hover_menu()

    def _init_blank_workspaces(self) -> None:
        """Start with blank robot/environment/custom instead of autoloading a scenario."""
        self._new_design("robot")
        self._new_design("environment")
        self._new_design("custom")
        self._dirty_flag("robot", False)
        self._dirty_flag("environment", False)
        self._dirty_flag("custom", False)
        self.status_hint = "Scratch workspace: use File menu to create/open robot/env/custom/scenario."

    def _refresh_scenarios_list(self) -> None:
        entries = list_scenarios(self.scenario_root, with_metadata=True)
        self.scenario_entries = entries
        self.scenario_lookup = {e.id: e for e in entries}
        self.scenario_names = [e.id for e in entries]

    # Menu helpers for hover menus
    def _select_scenario_menu(self, name: str) -> None:
        self.scenario_name = name if name and name != "<none>" else None
        self._load_scenario()
        self._refresh_hover_menu()

    def _select_body(self, name: str) -> None:
        if not name or not self.robot_cfg:
            return
        self.body_name = name
        self._refresh_body_dropdown()
        self._refresh_hover_menu()

    def _set_active_robot(self, robot_id: str) -> None:
        target = next((r for r in self.loaded_robots if getattr(r, "id", None) == robot_id), None)
        if not target:
            return
        self.active_robot_id = robot_id
        self.robot_cfg = target.config
        self._ensure_robot_defaults()
        self._refresh_body_dropdown()
        self._rebuild_sim()
        self.status_hint = f"Editing robot {robot_id}"
        self._refresh_hover_menu()

    def _controller_choices(self) -> List[str]:
        if not self.scenario_name:
            return []
        entry = self.scenario_lookup.get(self.scenario_name) if hasattr(self, "scenario_lookup") else None
        scenario_path = entry.path if entry else (self.scenario_root / self.scenario_name)
        if not scenario_path.exists():
            return []
        names = list_controllers(scenario_path)
        if not names:
            names = sorted({p.stem for p in scenario_path.glob("controller*.py")})
        return names or ["controller"]

    def _set_controller_module(self, module_name: str) -> None:
        if not self.robot_cfg:
            return
        self.robot_cfg.controller_module = module_name
        self.status_hint = f"Controller set to {module_name}"
        self._rebuild_sim()
        self._refresh_hover_menu()

    def _set_device_type(self, kind: str) -> None:
        if not kind:
            return
        self.device_dropdown.selected_option = kind
        self.device_dropdown.current_state.selected_option = kind  # ensure UI state
        self.pending_device_type = kind
        self.status_hint = f"Device type: {kind}"
        self._refresh_hover_menu()

    def _device_choice(self) -> str:
        """Normalize the device dropdown selection to a plain string."""
        raw = getattr(self.device_dropdown, "selected_option", None)
        if isinstance(raw, (list, tuple)):
            raw = raw[0] if raw else None
        choice = str(raw or "motor")
        try:
            self.device_dropdown.selected_option = choice
            self.device_dropdown.current_state.selected_option = choice
        except Exception:
            pass
        return choice

    def _set_creation_context(self, context: str) -> None:
        if context not in ("robot", "environment", "custom"):
            return
        self.creation_context = context
        self.status_hint = f"Context: {context}"
        self._refresh_hover_menu()

    def _set_shape_tool(self, tool: str) -> None:
        if tool not in ("rect", "triangle", "line"):
            return
        self.shape_tool = tool
        self.status_hint = f"Shape tool: {tool}"
        self._refresh_hover_menu()

    def _update_status_context(self) -> None:
        scenario_label = self.scenario_name or "scratch"
        dirty_flags = []
        if self.robot_dirty:
            dirty_flags.append("robot*")
        if self.env_dirty:
            dirty_flags.append("env*")
        if self.custom_dirty:
            dirty_flags.append("custom*")
        dirty_suffix = f" • Dirty: {', '.join(dirty_flags)}" if dirty_flags else ""
        self.status_text = (
            f"Active: {self.active_tab} • Scenario: {scenario_label} • Robot: {self.robot_design_name or '<none>'} • "
            f"Env: {self.env_design_name or '<none>'} • Custom: {self.custom_design_name or '<none>'}{dirty_suffix}"
        )

    def _open_new_asset_dialog(self, kind: str) -> None:
        if self.workspace_new_window:
            try:
                self.workspace_new_window.kill()
            except Exception:
                pass
        self.workspace_new_kind = kind
        win_rect = pygame.Rect((self.window_size[0] // 2 - 160, self.window_size[1] // 2 - 70), (320, 140))
        self.workspace_new_window = pygame_gui.elements.UIWindow(
            rect=win_rect,
            manager=self.manager,
            window_display_title=f"New {kind}",
            object_id="#new_asset_window",
        )
        pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(16, 20, win_rect.width - 32, 20),
            text="Name (no extension):",
            manager=self.manager,
            container=self.workspace_new_window,
        )
        self.workspace_new_entry = pygame_gui.elements.UITextEntryLine(
            relative_rect=pygame.Rect(16, 45, win_rect.width - 32, 24),
            manager=self.manager,
            container=self.workspace_new_window,
        )
        default_name = f"untitled_{kind}"
        self.workspace_new_entry.set_text(default_name)
        pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(16, 80, 120, 26),
            text="Create",
            manager=self.manager,
            container=self.workspace_new_window,
            object_id="#new_asset_confirm",
        )
        pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(win_rect.width - 136, 80, 120, 26),
            text="Cancel",
            manager=self.manager,
            container=self.workspace_new_window,
            object_id="#new_asset_cancel",
        )

    def _confirm_new_asset(self) -> None:
        if not self.workspace_new_kind:
            return
        name = (self.workspace_new_entry.get_text() if self.workspace_new_entry else "").strip()
        if not name:
            name = f"untitled_{self.workspace_new_kind}"
        self._create_new_asset(self.workspace_new_kind, name)
        self.workspace_new_window = None
        self.workspace_new_entry = None
        self.workspace_new_kind = None

    def _open_save_as_dialog(self, kind: str) -> None:
        if self.workspace_save_as_window:
            try:
                self.workspace_save_as_window.kill()
            except Exception:
                pass
        self.workspace_save_as_kind = kind
        win_rect = pygame.Rect((self.window_size[0] // 2 - 160, self.window_size[1] // 2 - 70), (320, 140))
        self.workspace_save_as_window = pygame_gui.elements.UIWindow(
            rect=win_rect,
            manager=self.manager,
            window_display_title=f"Save {kind} As",
            object_id="#save_as_window",
        )
        pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(16, 20, win_rect.width - 32, 20),
            text="New name (no extension):",
            manager=self.manager,
            container=self.workspace_save_as_window,
        )
        self.workspace_save_as_entry = pygame_gui.elements.UITextEntryLine(
            relative_rect=pygame.Rect(16, 45, win_rect.width - 32, 24),
            manager=self.manager,
            container=self.workspace_save_as_window,
        )
        current_name = getattr(self, f"{kind}_design_name", "") if kind != "scenario" else (self.scenario_name or "untitled_scenario")
        default_name = f"{current_name}_copy" if current_name else f"untitled_{kind}"
        self.workspace_save_as_entry.set_text(default_name)
        pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(16, 80, 120, 26),
            text="Save",
            manager=self.manager,
            container=self.workspace_save_as_window,
            object_id="#save_as_confirm",
        )
        pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(win_rect.width - 136, 80, 120, 26),
            text="Cancel",
            manager=self.manager,
            container=self.workspace_save_as_window,
            object_id="#save_as_cancel",
        )

    def _confirm_save_as(self) -> None:
        if not self.workspace_save_as_kind:
            return
        name = (self.workspace_save_as_entry.get_text() if self.workspace_save_as_entry else "").strip()
        safe = "".join(c for c in name if c.isalnum() or c in ("_", "-")) or f"untitled_{self.workspace_save_as_kind}"
        kind = self.workspace_save_as_kind
        if kind == "scenario":
            self._save_scenario(target_name=safe)
        else:
            self._save_design(kind, save_as=True, name_override=safe)
        self.workspace_save_as_window = None
        self.workspace_save_as_entry = None
        self.workspace_save_as_kind = None

    def _open_design_dialog(self, kind: str) -> None:
        root = self._design_root(kind) if kind != "scenario" else self.scenario_root
        root.mkdir(parents=True, exist_ok=True)
        if self.workspace_file_dialog:
            try:
                self.workspace_file_dialog.kill()
            except Exception:
                pass
        self.workspace_file_kind = kind
        self.workspace_file_mode = "open"
        rect = pygame.Rect((self.window_size[0] // 2 - 240, self.window_size[1] // 2 - 200), (480, 400))
        self.workspace_file_dialog = UIFileDialog(
            rect=rect,
            manager=self.manager,
            window_title=f"Open {kind}",
            initial_file_path=str(root),
            allow_existing_files_only=True,
        )

    def _create_new_asset(self, kind: str, name: str) -> None:
        safe = "".join(c for c in name if c.isalnum() or c in ("_", "-"))
        safe = safe or f"untitled_{kind}"
        if kind == "robot":
            path = self._design_root("robot") / f"{safe}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            cfg = RobotConfig()
            self.robot_cfg = cfg
            self._ensure_robot_defaults()
            save_robot_design(path, self.robot_cfg)
            self.robot_design_name = safe
            self._dirty_flag("robot", False)
            self._apply_tab_switch("robot")
            self._after_state_change()
            self.status_hint = f"Created robot {safe}"
        elif kind == "environment":
            path = self._design_root("environment") / f"{safe}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            self.world_cfg = WorldConfig()
            self._ensure_world_defaults()
            save_environment_design(path, self.world_cfg)
            self.env_design_name = safe
            self._dirty_flag("environment", False)
            self._apply_tab_switch("environment")
            self._after_world_change()
            self.status_hint = f"Created environment {safe}"
        elif kind == "custom":
            path = self._design_root("custom") / f"{safe}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            self.custom_active = None
            self._ensure_custom_defaults()
            save_custom_asset(path, self.custom_active)
            self.custom_design_name = safe
            self._dirty_flag("custom", False)
            self._apply_tab_switch("custom")
            self.status_hint = f"Created custom asset {safe}"
        else:  # scenario
            scenario_dir = self.scenario_root / safe
            scenario_dir.mkdir(parents=True, exist_ok=True)
            world = WorldConfig()
            robot = RobotConfig()
            self.world_cfg = world
            self.robot_cfg = robot
            self._ensure_world_defaults()
            self._ensure_robot_defaults()
            save_scenario(scenario_dir, world, robot)
            # write descriptor referencing local world/robot
            descriptor = {
                "id": safe,
                "name": safe,
                "environment": "world.json",
                "robot": "robot.json",
                "description": "",
            }
            (scenario_dir / "scenario.json").write_text(json.dumps(descriptor, indent=2), encoding="utf-8")
            self.scenario_name = safe
            self._refresh_scenarios_list()
            self._load_scenario()
            self.status_hint = f"Created scenario {safe}"
        self._update_status_context()

    def _handle_workspace_file_pick(self, path: Path) -> None:
        kind = self.workspace_file_kind
        if not kind:
            return
        try:
            if kind == "scenario" and path.is_dir():
                candidate = path / "scenario.json"
                path = candidate if candidate.exists() else path
            if kind == "robot":
                self.robot_cfg = load_robot_design(path)
                self._ensure_robot_defaults()
                self.robot_design_name = path.stem
                self._dirty_flag("robot", False)
                self._apply_tab_switch("robot")
                self._after_state_change()
                self.status_hint = f"Opened robot {path.name}"
            elif kind == "environment":
                self.world_cfg = load_environment_design(path)
                self._ensure_world_defaults()
                self.env_design_name = path.stem
                self._dirty_flag("environment", False)
                self._apply_tab_switch("environment")
                self._after_world_change()
                self.status_hint = f"Opened environment {path.name}"
            elif kind == "custom":
                self.custom_active = load_custom_asset(path)
                self._ensure_custom_defaults()
                self.custom_design_name = path.stem
                self._dirty_flag("custom", False)
                self._apply_tab_switch("custom")
                self.status_hint = f"Opened custom {path.name}"
            else:  # scenario
                self.scenario_name = (path.parent if path.is_file() else path).name
                self._refresh_scenarios_list()
                self._load_scenario()
                self.status_hint = f"Opened scenario {self.scenario_name}"
        except Exception as exc:
            self.status_hint = f"Failed to open {kind}: {exc}"
        self._update_status_context()

    def _open_device_import_dialog(self) -> None:
        root = self._device_library_root()
        root.mkdir(parents=True, exist_ok=True)
        if self.device_import_dialog:
            try:
                self.device_import_dialog.kill()
            except Exception:
                pass
        rect = pygame.Rect((self.window_size[0] // 2 - 240, self.window_size[1] // 2 - 200), (480, 400))
        self.device_import_dialog = UIFileDialog(
            rect=rect,
            manager=self.manager,
            window_title="Import device",
            initial_file_path=str(root),
            allow_existing_files_only=True,
        )

    def _handle_device_import(self, path: Path) -> None:
        if not self.robot_cfg:
            self.status_hint = "Load a robot before importing devices"
            return
        if not path.exists():
            self.status_hint = "Device file not found"
            return
        try:
            with path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as exc:
            self.status_hint = f"Failed to read device file: {exc}"
            return

        def _as_devices(obj: object) -> List[Tuple[str, Dict[str, object]]]:
            devices: List[Tuple[str, Dict[str, object]]] = []
            if isinstance(obj, dict) and ("actuators" in obj or "sensors" in obj):
                for a in obj.get("actuators", []) or []:
                    if isinstance(a, dict):
                        devices.append(("actuator", a))
                for s in obj.get("sensors", []) or []:
                    if isinstance(s, dict):
                        devices.append(("sensor", s))
                return devices
            if isinstance(obj, list):
                for item in obj:
                    if isinstance(item, dict):
                        devices.append(("actuator" if str(item.get("type", "")).lower() == "motor" else "sensor", item))
                return devices
            if isinstance(obj, dict):
                devices.append(("actuator" if str(obj.get("type", "")).lower() == "motor" else "sensor", obj))
            return devices

        devices = _as_devices(payload)
        if not devices:
            self.status_hint = "No devices found in file"
            return

        self._ensure_robot_defaults()
        default_body = self.body_name or (self.robot_cfg.bodies[0].name if self.robot_cfg.bodies else "body")
        added = 0
        for category, spec in devices:
            dtype = str(spec.get("type") or ("motor" if category == "actuator" else "distance"))
            base_name = str(spec.get("name") or spec.get("id") or dtype)
            name = self._unique_device_name(base_name)
            body_name = str(spec.get("body") or default_body)
            pose = spec.get("mount_pose") or spec.get("pose") or (0.0, 0.0, 0.0)
            params = spec.get("params") or {}
            if category == "actuator":
                self.robot_cfg.actuators.append(
                    ActuatorConfig(name=name, type=dtype, body=body_name, mount_pose=tuple(pose), params=params)
                )
            else:
                self.robot_cfg.sensors.append(
                    SensorConfig(name=name, type=dtype, body=body_name, mount_pose=tuple(pose), params=params)
                )
            added += 1

        if added:
            self._after_state_change()
            self._dirty_flag("robot", True)
            self.status_hint = f"Imported {added} device(s) from {path.name}"
        else:
            self.status_hint = "No devices added"

    def _workspace_action(self, action: str, kind: str) -> None:
        self._perform_workspace_action(action, kind, allow_prompt=True)

    def _perform_workspace_action(self, action: str, kind: str, allow_prompt: bool = True) -> None:
        if kind not in ("robot", "environment", "custom", "scenario"):
            return
        if kind in ("robot", "environment", "custom") and self.active_tab != kind:
            # Respect dirty prompts when hopping tabs via menu actions.
            self._ensure_tab(kind, prompt_dirty=allow_prompt)
            # If a pending dialog is open, wait for confirmation before continuing.
            if self.pending_dialog:
                if allow_prompt:
                    self.pending_workspace_action = (action, kind)
                return
        is_design_kind = kind in ("robot", "environment", "custom")
        if allow_prompt and action in ("new", "open") and is_design_kind and self._dirty_flag(kind):
            # Ask to save the dirty design before replacing/creating.
            self.pending_workspace_action = (action, kind)
            self.pending_dialog = pygame_gui.windows.UIConfirmationDialog(
                rect=pygame.Rect((self.window_size[0] // 2 - 180, self.window_size[1] // 2 - 70), (360, 140)),
                manager=self.manager,
                window_title="Save changes?",
                action_long_desc=f"Save current {kind} design before {action}?",
                action_short_name="Save",
                blocking=True,
            )
            return
        if action == "new":
            self._open_new_asset_dialog(kind)
            return
        if action == "open":
            self._open_design_dialog(kind)
            return
        if action == "save":
            if kind == "scenario":
                self._save_scenario()
            else:
                self._save_design(kind)
        elif action == "save_as":
            self._open_save_as_dialog(kind)
        self._update_status_context()

    def _update_brush_label(self) -> None:
        if self.brush_label:
            self.brush_label.set_text(f"{self.env_brush_thickness:.3f} m")

    def _enter_add_device(self) -> None:
        if not self.pending_device_type:
            self.pending_device_type = self._device_choice()
        self._set_mode("add_device")
        self.status_hint = f"Place device type: {self.pending_device_type}"
        self._refresh_hover_menu()

    def _refresh_hover_menu(self) -> None:
        font = pygame.font.Font(pygame.font.get_default_font(), 14)
        workspace_children = lambda k: [
            {"label": "New", "action": lambda kk=k: self._workspace_action("new", kk)},
            {"label": "Open", "action": lambda kk=k: self._workspace_action("open", kk)},
            {"label": "Save", "action": lambda kk=k: self._workspace_action("save", kk)},
            {"label": "Save as...", "action": lambda kk=k: self._workspace_action("save_as", kk)},
        ]
        scenario_entries = [
            {"label": (self.scenario_lookup.get(n).name if n in self.scenario_lookup else n), "action": (lambda n=n: self._select_scenario_menu(n))}
            for n in self.scenario_names
        ]
        scenario_children = workspace_children("scenario") + [{"label": "Reload current", "action": self._load_scenario}] + scenario_entries
        robot_entries: List[Dict[str, object]] = []
        if len(self.loaded_robots) > 1:
            for r in self.loaded_robots:
                rid = getattr(r, "id", "robot")
                robot_entries.append(
                    {"label": rid, "action": (lambda r=rid: self._set_active_robot(r)), "checked": (lambda r=rid: self.active_robot_id == r)}
                )
        if robot_entries:
            scenario_children.append({"label": "Active robot", "children": robot_entries})
        file_menu = [
            {"label": "Robot", "children": workspace_children("robot")},
            {"label": "Environment", "children": workspace_children("environment")},
            {"label": "Custom", "children": workspace_children("custom")},
            {"label": "Scenario", "children": scenario_children},
        ]
        body_entries: List[Dict[str, object]] = []
        if self.robot_cfg:
            body_entries = [{"label": b.name, "action": (lambda n=b.name: self._select_body(n))} for b in self.robot_cfg.bodies]
        device_types = ["motor", "distance", "line", "imu", "encoder"]
        def _set_and_enter(kind: str) -> None:
            self._set_device_type(kind)
            self._enter_add_device()

        device_entries = [
            {"label": kind, "action": (lambda k=kind: _set_and_enter(k)), "checked": (lambda k=kind: (self._device_choice() == k))}
            for kind in device_types
        ]
        brush_sizes = [("Thin", 0.02), ("Medium", 0.05), ("Thick", 0.1)]
        env_entries: List[Dict[str, object]] = [
            {"label": "Draw mark", "action": lambda: self._set_env_tool("mark"), "checked": lambda: self.env_tool == "mark"},
            {"label": "Draw wall", "action": lambda: self._set_env_tool("wall"), "checked": lambda: self.env_tool == "wall"},
        ]
        env_entries += [
            {
                "label": f"Brush {label}",
                "action": (lambda t=val: self._set_brush_thickness(t)),
                "checked": (lambda t=val: abs(self.env_brush_thickness - t) < 1e-6),
            }
            for label, val in brush_sizes
        ]
        env_entries += [
            {"label": "Exit env drawing", "action": lambda: self._set_env_tool("off"), "checked": lambda: self.env_tool == "off"},
            {"label": "Clear drawings", "action": self._clear_env_drawings},
            {"label": "Set bounds (drag)", "action": self._start_bounds_mode, "checked": lambda: self.bounds_mode},
            {"label": "Clear bounds", "action": self._clear_bounds},
            {"label": "Undo env", "action": self._undo_world},
            {"label": "Redo env", "action": self._redo_world},
        ]
        controller_entries = [
            {
                "label": f"Use {name}",
                "action": (lambda n=name: self._set_controller_module(n)),
                "checked": (lambda n=name: getattr(self.robot_cfg, "controller_module", "controller") == n),
            }
            for name in self._controller_choices()
        ] or [{"label": "<no controllers>", "action": lambda: None}]
        self.hover_menu = HoverMenu(
            [
                ("File", file_menu),
                (
                    "Edit",
                    [
                        {"label": "Undo", "action": self._undo},
                        {"label": "Redo", "action": self._redo},
                        {"label": "Save", "action": self._save_scenario},
                    ],
                ),
                (
                    "Mode",
                    [
                        {"label": "Select/Move", "action": lambda: self._set_mode("select")},
                        {"label": "Add point", "action": lambda: self._set_mode("add")},
                        {"label": "Delete point", "action": lambda: self._set_mode("delete")},
                        {"label": "Draw shape", "action": lambda: self._set_mode("draw_shape")},
                    ],
                ),
                ("Body", body_entries or [{"label": "<none>", "action": lambda: None}]),
                (
                    "Devices",
                    device_entries
                    + [
                        {"label": "Import saved device...", "action": self._open_device_import_dialog},
                        {"label": "Advanced (selected)", "action": self._open_advanced_view},
                    ],
                ),
                ("Controller", controller_entries),
                ("Environment", env_entries),
                (
                    "Shapes",
                    [
                        {"label": "Rectangle", "action": lambda: self._set_shape_tool("rect"), "checked": lambda: self.shape_tool == "rect"},
                        {
                            "label": "Triangle",
                            "action": lambda: self._set_shape_tool("triangle"),
                            "checked": lambda: self.shape_tool == "triangle",
                        },
                        {"label": "Line", "action": lambda: self._set_shape_tool("line"), "checked": lambda: self.shape_tool == "line"},
                        {"label": "Enter draw shape", "action": lambda: self._set_mode("draw_shape")},
                    ],
                ),
                (
                    "View",
                    [
                        {"label": "Reset view", "action": self._view_reset},
                        {"label": "Toggle grid", "action": self._view_toggle_grid, "checked": lambda: self.grid_enabled},
                        {"label": "Reset rotation", "action": self._view_reset_rotation},
                    ],
                ),
                (
                    "Export",
                    [
                        {"label": "Export scenario", "action": self._export_scenario},
                    ],
                ),
            ],
            pos=(20, 8),
            font=font,
        )

    # --- Tab + design helpers ---------------------------------------------
    def _design_root(self, kind: str) -> Path:
        base = self.base_path / "designs"
        if kind == "robot":
            return base / "robots"
        if kind == "environment":
            return base / "environments"
        return base / "custom"

    def _device_library_root(self) -> Path:
        return self.base_path / "designs" / "devices"

    def _dirty_flag(self, kind: str, value: Optional[bool] = None) -> bool:
        if value is None:
            return self.robot_dirty if kind == "robot" else self.env_dirty if kind == "environment" else self.custom_dirty
        if kind == "robot":
            self.robot_dirty = value
        elif kind == "environment":
            self.env_dirty = value
        else:
            self.custom_dirty = value
        return value

    def _switch_tab(self, tab: str) -> None:
        if tab == self.active_tab:
            return
        # prompt if dirty
        current_dirty = self._dirty_flag(self.active_tab)
        if current_dirty and not self.pending_dialog:
            self.pending_tab = tab
            self.pending_dialog = pygame_gui.windows.UIConfirmationDialog(
                rect=pygame.Rect((self.window_size[0] // 2 - 160, self.window_size[1] // 2 - 60), (320, 120)),
                manager=self.manager,
                window_title="Save changes?",
                action_long_desc=f"Save {self.active_tab} design before switching?",
                action_short_name="Save",
                blocking=True,
            )
            return
        self._apply_tab_switch(tab)

    def _ensure_tab(self, tab: str, prompt_dirty: bool = True) -> None:
        """Switch to tab, optionally honoring dirty-check prompts."""
        if tab == self.active_tab:
            return
        if prompt_dirty:
            self._switch_tab(tab)
        else:
            self._apply_tab_switch(tab)

    def _apply_tab_switch(self, tab: str) -> None:
        if self.env_drawing and self.env_stroke_points:
            self._finalize_env_stroke()
        self.active_tab = tab
        self.creation_context = tab
        if tab != "environment":
            self.env_tool = "off"
            self.env_drawing = False
            self.env_stroke_points.clear()
        self.shape_start = None
        self.shape_preview = None
        self.mode = "select"
        self.selected_point = None
        self.selected_points.clear()
        self.selected_device = None
        self._update_mode_buttons()
        self._refresh_hover_menu()
        self.status_hint = f"Now editing {tab}"
        self._update_status_context()
        self._sync_paint_panel()
        if tab == "robot":
            self._refresh_body_dropdown()

    def _new_design(self, kind: str) -> None:
        if kind == "robot":
            self.robot_cfg = RobotConfig()
            self.body_name = None
            self._ensure_robot_defaults()
            self._after_state_change()
            self.robot_design_name = "untitled_robot"
            self._dirty_flag("robot", True)
        elif kind == "environment":
            self.world_cfg = WorldConfig()
            self._ensure_world_defaults()
            self._after_world_change()
            self.env_design_name = "untitled_env"
            self._dirty_flag("environment", True)
        else:
            self.custom_active = None
            self._ensure_custom_defaults()
            self.custom_design_name = "untitled_custom"
            self._dirty_flag("custom", True)
        self._update_status_context()
        self.status_hint = f"New {kind} design"

    def _open_design(self, kind: str) -> None:
        root = self._design_root(kind)
        if not root.exists():
            self.status_hint = f"No {kind} designs yet"
            return
        files = sorted(root.glob("*.json"))
        if not files:
            self.status_hint = f"No {kind} designs found"
            return
        path = files[0]
        try:
            if kind == "robot":
                self.robot_cfg = load_robot_design(path)
                self._ensure_robot_defaults()
                self._after_state_change()
                self.robot_design_name = path.stem
                self._dirty_flag("robot", False)
            elif kind == "environment":
                self.world_cfg = load_environment_design(path)
                self._ensure_world_defaults()
                self._after_world_change()
                self.env_design_name = path.stem
                self._dirty_flag("environment", False)
            else:
                self.custom_active = load_custom_asset(path)
                self._ensure_custom_defaults()
                self.custom_design_name = path.stem
                self._dirty_flag("custom", False)
            self.status_hint = f"Opened {kind} design {path.stem}"
        except Exception as exc:
            self.status_hint = f"Failed to open {kind}: {exc}"
        self._update_status_context()
        self._update_status_context()

    def _save_design(self, kind: str, save_as: bool = False, name_override: Optional[str] = None) -> None:
        root = self._design_root(kind)
        root.mkdir(parents=True, exist_ok=True)
        name = name_override or getattr(self, f"{kind}_design_name", f"untitled_{kind}")
        if save_as and not name_override:
            name = f"{name}_copy"
        safe = "".join(c for c in name if c.isalnum() or c in ("_", "-")) or f"untitled_{kind}"
        path = root / f"{safe}.json"
        try:
            if kind == "robot" and self.robot_cfg:
                save_robot_design(path, self.robot_cfg)
                self.robot_design_name = safe
                self._dirty_flag("robot", False)
            elif kind == "environment" and self.world_cfg:
                save_environment_design(path, self.world_cfg)
                self.env_design_name = safe
                self._dirty_flag("environment", False)
            elif kind == "custom" and self.custom_active:
                save_custom_asset(path, self.custom_active)
                self.custom_design_name = safe
                self._dirty_flag("custom", False)
            else:
                self.status_hint = f"Nothing to save for {kind}"
                return
            self.status_hint = f"Saved {kind} design to {path.name}"
        except Exception as exc:
            self.status_hint = f"Failed to save {kind}: {exc}"
        self._update_status_context()

    def _save_scenario_as(self) -> None:
        # Kept for compatibility; now delegates to unified save-as flow.
        self._open_save_as_dialog("scenario")

    def _export_scenario(self) -> None:
        if not self.scenario_name:
            self.status_hint = "No scenario selected to export"
            return
        target = self.scenario_root / self.scenario_name
        if not target.exists():
            target.mkdir(parents=True, exist_ok=True)
        if not (self.world_cfg and self.robot_cfg):
            self.status_hint = "Need robot and environment to export"
            return
        save_scenario(target, self.world_cfg, self.robot_cfg)
        self.status_hint = f"Exported scenario to {self.scenario_name}"
    def _ensure_world_defaults(self) -> None:
        if not self.world_cfg:
            return
        if getattr(self.world_cfg, "drawings", None) is None:
            self.world_cfg.drawings = []
        if not hasattr(self.world_cfg, "bounds"):
            self.world_cfg.bounds = None
        if not hasattr(self.world_cfg, "shape_objects") or self.world_cfg.shape_objects is None:
            self.world_cfg.shape_objects = []
        if not hasattr(self.world_cfg, "custom_objects") or self.world_cfg.custom_objects is None:
            self.world_cfg.custom_objects = []
        if not hasattr(self.world_cfg, "designer_state") or self.world_cfg.designer_state is None:
            self.world_cfg.designer_state = DesignerState()
        if not self.custom_active and self.world_cfg.custom_objects:
            self.custom_active = self.world_cfg.custom_objects[0]

    def _ensure_robot_defaults(self) -> None:
        if not self.robot_cfg:
            self.robot_cfg = RobotConfig()
        if not getattr(self.robot_cfg, "bodies", None):
            self.robot_cfg.bodies = [
                BodyConfig(
                    name="body",
                    points=[(0.1, -0.06), (0.1, 0.06), (-0.08, 0.06), (-0.08, -0.06)],
                    edges=[(0, 1), (1, 2), (2, 3), (3, 0)],
                    pose=(0.0, 0.0, 0.0),
                    can_move=True,
                )
            ]
        if not getattr(self.robot_cfg, "spawn_pose", None):
            self.robot_cfg.spawn_pose = (0.0, 0.0, 0.0)
        if not self.body_name and self.robot_cfg.bodies:
            self.body_name = self.robot_cfg.bodies[0].name

    def _ensure_custom_defaults(self) -> None:
        if not self.custom_active:
            body = BodyConfig(
                name="custom_body",
                points=[(0.05, -0.05), (0.05, 0.05), (-0.05, 0.05), (-0.05, -0.05)],
                edges=[(0, 1), (1, 2), (2, 3), (3, 0)],
                pose=(0.0, 0.0, 0.0),
                can_move=False,
                mass=0.1,
                inertia=0.01,
            )
            self.custom_active = CustomObjectConfig(name="custom_asset", body=body, kind="custom", metadata={})

    def _w2s(self, point: Tuple[float, float]) -> Tuple[int, int]:
        return world_to_screen(point, self.viewport_rect, self.scale, self.offset, self.view_rotation)

    def _s2w(self, pos: Tuple[int, int]) -> Tuple[float, float]:
        return screen_to_world(pos, self.viewport_rect, self.scale, self.offset, self.view_rotation)

    def _load_scenario(self) -> None:
        if not self.scenario_name:
            return
        entry = self.scenario_lookup.get(self.scenario_name)
        scenario_path = entry.path if entry else (self.scenario_root / self.scenario_name)
        scenario = load_scenario(scenario_path)
        self.loaded_robots = scenario.robots
        self.active_robot_id = scenario.robots[0].id if scenario.robots else None
        self.scenario_descriptor = scenario.descriptor
        self.scenario_description = scenario.descriptor.description
        self._load_thumbnail_for_scenario(entry)
        self.world_cfg = scenario.world
        self.robot_cfg = scenario.primary_robot
        self._ensure_world_defaults()
        self._ensure_robot_defaults()
        ds = getattr(self.world_cfg, "designer_state", DesignerState())
        self.creation_context = getattr(ds, "creation_context", "robot") or "robot"
        self.mode = getattr(ds, "mode", "select") or "select"
        self.env_brush_thickness = float(getattr(ds, "brush_thickness", self.env_brush_thickness))
        self.shape_tool = getattr(ds, "shape_tool", "rect") or "rect"
        brush_kind = getattr(ds, "brush_kind", "mark") or "mark"
        self.env_tool = brush_kind if brush_kind in ("mark", "wall") else "off"
        # Keep UI context aligned with the saved creation tab to avoid state bleed.
        self.active_tab = self.creation_context
        if self.active_tab != "environment":
            self.env_tool = "off"
            self.env_drawing = False
            self.env_stroke_points.clear()
        self.body_name = self.robot_cfg.bodies[0].name if self.robot_cfg.bodies else None
        self._refresh_body_dropdown()
        self._rebuild_sim()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.world_undo_stack.clear()
        self.world_redo_stack.clear()
        self._populate_inspector_from_selection()
        self._update_mode_buttons()
        self._refresh_hover_menu()
        self._sync_paint_panel()
        self._update_status_context()

    def _load_thumbnail_for_scenario(self, entry) -> None:
        # Thumbnails are disabled to avoid image-related hangs; keep fields cleared.
        self.scenario_thumbnail = None
        self._update_status_context()

    def _refresh_body_dropdown(self) -> None:
        options = [b.name for b in self.robot_cfg.bodies] if self.robot_cfg else []
        if not options:
            options = ["<none>"]
            self.body_name = None
        elif self.body_name not in options:
            self.body_name = options[0]
        self.body_dropdown.kill()
        self.body_dropdown = pygame_gui.elements.UIDropDownMenu(
            options_list=options,
            starting_option=self.body_name or options[0],
            relative_rect=pygame.Rect((self.window_size[0] - 320, 20), (140, 30)),
            manager=self.manager,
        )

    def _rebuild_sim(self, preserve_selection: bool = False) -> None:
        if not (self.world_cfg and self.robot_cfg):
            return
        # Allow scratch scenarios when no named scenario is selected
        target_name = self.scenario_name or self.scratch_scenario_name
        scenario_path = self.scenario_root / target_name
        scenario_path.mkdir(parents=True, exist_ok=True)
        prev_selection = self.selected_device if preserve_selection else None
        self.sim = Simulator()
        self.sim.load(scenario_path, self.world_cfg, self.robot_cfg)
        self.hover_device = None
        if preserve_selection and prev_selection and prev_selection[1] in self._device_lookup():
            self.selected_device = prev_selection
            self._populate_inspector_from_selection()
        else:
            self.selected_device = None

    def _push_undo_state(self) -> None:
        if not self.robot_cfg:
            return
        self.undo_stack.append(copy.deepcopy(self.robot_cfg))
        if len(self.undo_stack) > 50:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        self.robot_dirty = True

    def _push_world_undo_state(self) -> None:
        if not self.world_cfg:
            return
        self.world_undo_stack.append(copy.deepcopy(self.world_cfg))
        if len(self.world_undo_stack) > 50:
            self.world_undo_stack.pop(0)
        self.world_redo_stack.clear()
        if self.active_tab == "environment":
            self.env_dirty = True
        elif self.active_tab == "custom":
            self.custom_dirty = True

    def _after_world_change(self) -> None:
        self._ensure_world_defaults()
        self._rebuild_sim(preserve_selection=True)
        self._refresh_hover_menu()
        self._sync_paint_panel()

    def _undo_world(self) -> None:
        if not self.world_undo_stack:
            return
        prev = self.world_undo_stack.pop()
        if self.world_cfg:
            self.world_redo_stack.append(copy.deepcopy(self.world_cfg))
        self.world_cfg = copy.deepcopy(prev)
        self._after_world_change()

    def _redo_world(self) -> None:
        if not self.world_redo_stack:
            return
        nxt = self.world_redo_stack.pop()
        if self.world_cfg:
            self.world_undo_stack.append(copy.deepcopy(self.world_cfg))
        self.world_cfg = copy.deepcopy(nxt)
        self._after_world_change()

    def _push_custom_undo(self) -> None:
        if not self.custom_active:
            return
        self.custom_undo_stack.append(copy.deepcopy(self.custom_active))
        if len(self.custom_undo_stack) > 50:
            self.custom_undo_stack.pop(0)
        self.custom_redo_stack.clear()
        self.custom_dirty = True

    def _undo_custom(self) -> None:
        if not self.custom_undo_stack:
            return
        prev = self.custom_undo_stack.pop()
        if self.custom_active:
            self.custom_redo_stack.append(copy.deepcopy(self.custom_active))
        self.custom_active = prev
        self.custom_dirty = True

    def _redo_custom(self) -> None:
        if not self.custom_redo_stack:
            return
        nxt = self.custom_redo_stack.pop()
        if self.custom_active:
            self.custom_undo_stack.append(copy.deepcopy(self.custom_active))
        self.custom_active = nxt
        self.custom_dirty = True

    def _after_state_change(self) -> None:
        # Keep body selection valid and rebuild runtime objects.
        self._ensure_world_defaults()
        if self.robot_cfg:
            bodies = [b.name for b in self.robot_cfg.bodies]
            if self.body_name not in bodies:
                self.body_name = bodies[0] if bodies else None
        self._refresh_body_dropdown()
        self._rebuild_sim()
        self.hover_point = None
        self.selected_point = None
        self.selected_points.clear()
        self.hover_device = None
        self.selected_device = None
        self.dragging = False
        self.drag_mode = None
        self.drag_handle = None
        self.drag_points_snapshot.clear()
        self.drag_start_local = None
        self.drag_scale_center = None
        self.drag_scale_origin_vec = None
        self.dragging_device = False
        self._populate_inspector_from_selection()

    def _restore_cfg(self, cfg: RobotConfig) -> None:
        self.robot_cfg = copy.deepcopy(cfg)
        self._after_state_change()

    def _set_mode(self, mode: str) -> None:
        self.mode = mode
        if mode != "add_device":
            self.pending_device_type = None
        if mode != "draw_shape":
            self.shape_start = None
            self.shape_preview = None
        try:
            if mode in ("add", "add_device"):
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_CROSSHAIR)
            elif mode == "delete":
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_NO)
            else:
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
        except Exception:
            # Cursor changes can fail on some platforms; ignore.
            pass
        if mode == "add":
            self.status_hint = "Click to place vertices (local to body)."
        elif mode == "delete":
            self.status_hint = "Click a vertex to delete (min 3 vertices)."
        elif mode == "add_device":
            dtype = str(self.pending_device_type or self._device_choice() or "device")
            self.status_hint = f"Click to place {dtype} on the body."
        elif mode == "draw_shape":
            self.status_hint = f"Draw {self.shape_tool} ({self.creation_context})"
        else:
            self.status_hint = "Select and drag points or devices. Right-drag to pan."
        self._update_mode_buttons()
        self._refresh_hover_menu()

    def _update_mode_buttons(self) -> None:
        def mark(base: str, active: bool) -> str:
            return f"● {base}" if active else base

        self.btn_move_point.set_text(mark("Select/Move", self.mode == "select"))
        self.btn_add_point.set_text(mark("Add point", self.mode == "add"))
        self.btn_del_point.set_text(mark("Delete point", self.mode == "delete"))

    def _device_lookup(self) -> Dict[str, Tuple[str, object]]:
        res: Dict[str, Tuple[str, object]] = {}
        if not self.robot_cfg:
            return res
        for act in self.robot_cfg.actuators:
            res[act.name] = ("actuator", act)
        for sensor in self.robot_cfg.sensors:
            res[sensor.name] = ("sensor", sensor)
        return res

    def _unique_device_name(self, base: str) -> str:
        existing = set(self._device_lookup().keys())
        if base not in existing:
            return base
        suffix = 1
        while True:
            candidate = f"{base}_{suffix}"
            if candidate not in existing:
                return candidate
            suffix += 1

    def _populate_inspector_from_selection(self) -> None:
        if not self.selected_device:
            self.lbl_selection.set_text("Selection: none")
            self.lbl_selection_type.set_text("Type: —")
            self.lbl_device_body.set_text("Body: —")
            self.txt_device_name.set_text("")
            self.txt_pose_x.set_text("")
            self.txt_pose_y.set_text("")
            self.txt_pose_theta.set_text("")
            return
        kind, name = self.selected_device
        lookup = self._device_lookup()
        if name not in lookup:
            self.selected_device = None
            return
        dtype, cfg = lookup[name]
        self.lbl_selection.set_text(f"Selection: {name}")
        self.lbl_selection_type.set_text(f"Type: {getattr(cfg, 'type', dtype)}")
        self.lbl_device_body.set_text(f"Body: {cfg.body}")
        self.txt_device_name.set_text(cfg.name)
        mx, my, mtheta = cfg.mount_pose
        self.txt_pose_x.set_text(f"{mx:.3f}")
        self.txt_pose_y.set_text(f"{my:.3f}")
        self.txt_pose_theta.set_text(f"{mtheta:.3f}")

    def _body_cfg_by_name(self, name: str) -> Optional[BodyConfig]:
        if not self.robot_cfg:
            return None
        for b in self.robot_cfg.bodies:
            if b.name == name:
                return b
        return None

    def _device_world_pose(self, device: Tuple[str, str]) -> Optional[Pose2D]:
        if not self.sim:
            return None
        kind, name = device
        if kind == "actuator":
            motor = self.sim.motors.get(name)
            if motor and motor.parent:
                return motor.parent.pose.compose(motor.mount_pose)
        elif kind == "sensor":
            sensor = self.sim.sensors.get(name)
            if sensor and sensor.parent:
                return sensor.parent.pose.compose(sensor.mount_pose)
        return None

    def _selected_local_points(self, body_cfg: BodyConfig) -> List[Tuple[int, Tuple[float, float]]]:
        pts: List[Tuple[int, Tuple[float, float]]] = []
        for idx in sorted(self.selected_points):
            if 0 <= idx < len(body_cfg.points):
                pts.append((idx, body_cfg.points[idx]))
        return pts

    def _selection_centroid(self, body_cfg: BodyConfig) -> Optional[Tuple[float, float]]:
        pts = self._selected_local_points(body_cfg)
        if not pts:
            return None
        sx = sum(p[0] for _, p in pts)
        sy = sum(p[1] for _, p in pts)
        count = len(pts)
        return (sx / count, sy / count)

    def _selection_bbox_local(self, body_cfg: BodyConfig) -> Optional[Tuple[float, float, float, float]]:
        pts = self._selected_local_points(body_cfg)
        if not pts:
            return None
        xs = [p[0] for _, p in pts]
        ys = [p[1] for _, p in pts]
        return (min(xs), min(ys), max(xs), max(ys))

    def _selection_handles(self, body_cfg: BodyConfig) -> Dict[str, pygame.Rect]:
        """Return screen-space rects for selection scale handles."""
        bbox = self._selection_bbox_local(body_cfg)
        if not bbox:
            return {}
        body_pose = self._body_pose(body_cfg)
        minx, miny, maxx, maxy = bbox
        corners_local = {
            "nw": (minx, maxy),
            "ne": (maxx, maxy),
            "sw": (minx, miny),
            "se": (maxx, miny),
        }
        handles: Dict[str, pygame.Rect] = {}
        size = 12
        for name, loc in corners_local.items():
            wx, wy = body_pose.transform_point(loc)
            sx, sy = world_to_screen((wx, wy), self.viewport_rect, self.scale, self.offset, self.view_rotation)
            handles[name] = pygame.Rect(int(sx - size / 2), int(sy - size / 2), size, size)
        return handles

    def _selection_handle_hit(self, body_cfg: BodyConfig, mouse_pos: Tuple[int, int]) -> Optional[Tuple[str, Tuple[float, float]]]:
        """Return (handle_name, corner_local) if a handle is clicked."""
        bbox = self._selection_bbox_local(body_cfg)
        if not bbox:
            return None
        minx, miny, maxx, maxy = bbox
        corners_local = {
            "nw": (minx, maxy),
            "ne": (maxx, maxy),
            "sw": (minx, miny),
            "se": (maxx, miny),
        }
        handles = self._selection_handles(body_cfg)
        for name, rect in handles.items():
            if rect.collidepoint(mouse_pos):
                return name, corners_local[name]
        return None

    def _finalize_marquee_selection(self) -> None:
        if not (self.marquee_active and self.marquee_start and self.marquee_end):
            self.marquee_active = False
            self.marquee_start = None
            self.marquee_end = None
            return
        minx, maxx = sorted([self.marquee_start[0], self.marquee_end[0]])
        miny, maxy = sorted([self.marquee_start[1], self.marquee_end[1]])
        self.marquee_active = False
        self.marquee_start = None
        self.marquee_end = None
        body_cfg = self._current_body_cfg()
        if not body_cfg:
            return
        pose = self._body_pose(body_cfg)
        selected: set[int] = set()
        for idx, pt in enumerate(body_cfg.points):
            wx, wy = pose.transform_point(pt)
            if minx <= wx <= maxx and miny <= wy <= maxy:
                selected.add(idx)
        devices_in_box: list[Tuple[str, str]] = []
        if self.sim:
            for kind, collection in (("actuator", self.sim.motors), ("sensor", self.sim.sensors)):
                for name, obj in collection.items():
                    if not obj.parent:
                        continue
                    pose_w = obj.parent.pose.compose(obj.mount_pose)
                    if minx <= pose_w.x <= maxx and miny <= pose_w.y <= maxy:
                        devices_in_box.append((kind, name))
        if selected:
            self.selected_points = selected
            self.selected_point = next(iter(selected))
            self.selected_device = None
        elif devices_in_box:
            self.selected_device = devices_in_box[0]
            self.selected_points.clear()
            self.selected_point = None
        else:
            self.selected_points.clear()
            self.selected_point = None
            self.selected_device = None
        self._populate_inspector_from_selection()

    def _apply_runtime_device_pose(self, kind: str, name: str, mount_pose: Tuple[float, float, float]) -> None:
        """Keep runtime sim objects in sync with config during live drag."""
        if not self.sim:
            return
        pose_obj = Pose2D(mount_pose[0], mount_pose[1], mount_pose[2])
        if kind == "actuator":
            motor = self.sim.motors.get(name)
            if motor:
                motor.mount_pose = pose_obj
        elif kind == "sensor":
            sensor = self.sim.sensors.get(name)
            if sensor:
                sensor.mount_pose = pose_obj

    def _pick_device(self, world_point: Tuple[float, float], pixel_radius: float = 24.0) -> Optional[Tuple[str, str]]:
        if not self.sim:
            return None
        thresh = pixel_radius / max(self.scale, 1e-6)
        best: Optional[Tuple[str, str]] = None
        best_d = thresh
        for name, motor in self.sim.motors.items():
            parent = motor.parent
            if not parent:
                continue
            pose = parent.pose.compose(motor.mount_pose)
            d = math.hypot(world_point[0] - pose.x, world_point[1] - pose.y)
            if d < best_d:
                best_d = d
                best = ("actuator", name)
        for name, sensor in self.sim.sensors.items():
            parent = sensor.parent
            if not parent:
                continue
            pose = parent.pose.compose(sensor.mount_pose)
            d = math.hypot(world_point[0] - pose.x, world_point[1] - pose.y)
            if d < best_d:
                best_d = d
                best = ("sensor", name)
        return best

    def _create_device_at_point(self, body_cfg: BodyConfig, world_point: Tuple[float, float], dtype: str) -> Optional[Tuple[str, str]]:
        body_pose = self._body_pose(body_cfg)
        local_point = body_pose.inverse().transform_point(world_point)
        mount_pose = (float(local_point[0]), float(local_point[1]), 0.0)
        dtype = dtype.lower()
        if not self.robot_cfg:
            return None
        if dtype == "motor":
            name = f"motor_{len(self.robot_cfg.actuators)+1}"
            self.robot_cfg.actuators.append(
                ActuatorConfig(
                    name=name,
                    type="motor",
                    body=body_cfg.name,
                    mount_pose=mount_pose,
                    params={"max_force": 2.0},
                )
            )
            return ("actuator", name)
        if dtype in ("distance", "line", "imu", "encoder"):
            idx = len(self.robot_cfg.sensors) + 1
            name = f"{dtype}_{idx}"
            params: Dict[str, object] = {"preset": "range_short"} if dtype == "distance" else {}
            self.robot_cfg.sensors.append(
                SensorConfig(
                    name=name,
                    type=dtype,
                    body=body_cfg.name,
                    mount_pose=mount_pose,
                    params=params,
                )
            )
            return ("sensor", name)
        print(f"Unsupported device type {dtype}")
        return None

    def _move_device_to(self, device: Tuple[str, str], world_point: Tuple[float, float]) -> None:
        if not self.robot_cfg:
            return
        kind, name = device
        cfg = None
        if kind == "actuator":
            cfg = next((a for a in self.robot_cfg.actuators if a.name == name), None)
        elif kind == "sensor":
            cfg = next((s for s in self.robot_cfg.sensors if s.name == name), None)
        if not cfg:
            return
        body_cfg = self._body_cfg_by_name(cfg.body)
        if not body_cfg:
            return
        local_point = self._body_pose(body_cfg).inverse().transform_point(world_point)
        cfg.mount_pose = (float(local_point[0]), float(local_point[1]), float(cfg.mount_pose[2]))
        self._apply_runtime_device_pose(kind, name, cfg.mount_pose)
        # Keep device list refreshed when dragging
        self._populate_inspector_from_selection()

    def _unique_device_name(self, base: str, kind: str) -> str:
        if not self.robot_cfg:
            return base
        existing = {a.name for a in self.robot_cfg.actuators} | {s.name for s in self.robot_cfg.sensors}
        if base not in existing:
            return base
        idx = 2
        while f"{base}_{idx}" in existing:
            idx += 1
        return f"{base}_{idx}"

    def _copy_selection(self) -> None:
        body_cfg = self._current_body_cfg()
        if not body_cfg:
            return
        points = []
        if self.selected_points:
            points = [body_cfg.points[idx] for idx in sorted(self.selected_points) if 0 <= idx < len(body_cfg.points)]
        devices = []
        if self.selected_device and self.robot_cfg:
            kind, name = self.selected_device
            cfg = None
            if kind == "actuator":
                cfg = next((a for a in self.robot_cfg.actuators if a.name == name and a.body == body_cfg.name), None)
            elif kind == "sensor":
                cfg = next((s for s in self.robot_cfg.sensors if s.name == name and s.body == body_cfg.name), None)
            if cfg:
                devices.append((kind, copy.deepcopy(cfg)))
        offset_world = (10.0 / max(self.scale, 1e-6), -10.0 / max(self.scale, 1e-6))
        self.clipboard = {"points": points, "devices": devices, "offset_world": offset_world}

    def _paste_selection(self) -> None:
        body_cfg = self._current_body_cfg()
        if not body_cfg or not self.clipboard:
            return
        pts: List[Tuple[float, float]] = self.clipboard.get("points", [])
        devs = self.clipboard.get("devices", [])
        offset_world = self.clipboard.get("offset_world", (0.0, 0.0))
        if not pts and not devs:
            return
        self._push_undo_state()
        theta = self._body_pose(body_cfg).theta
        cos_t = math.cos(-theta)
        sin_t = math.sin(-theta)
        dx_world, dy_world = offset_world
        offset_local = (dx_world * cos_t - dy_world * sin_t, dx_world * sin_t + dy_world * cos_t)
        new_indices: List[int] = []
        for pt in pts:
            nx = float(pt[0] + offset_local[0])
            ny = float(pt[1] + offset_local[1])
            body_cfg.points.append((nx, ny))
            new_indices.append(len(body_cfg.points) - 1)
        if new_indices:
            body_cfg.edges = [(i, (i + 1) % len(body_cfg.points)) for i in range(len(body_cfg.points))]
        last_device: Optional[Tuple[str, str]] = None
        if self.robot_cfg:
            for kind, cfg in devs:
                cfg = copy.deepcopy(cfg)
                mx, my, mtheta = cfg.mount_pose
                cfg.mount_pose = (float(mx + offset_local[0]), float(my + offset_local[1]), float(mtheta))
                cfg.name = self._unique_device_name(cfg.name, kind)
                cfg.body = body_cfg.name
                if kind == "actuator":
                    self.robot_cfg.actuators.append(cfg)  # type: ignore[arg-type]
                elif kind == "sensor":
                    self.robot_cfg.sensors.append(cfg)  # type: ignore[arg-type]
                last_device = (kind, cfg.name)
        # Refresh runtime and restore selection
        self._after_state_change()
        if new_indices:
            self.selected_points = set(new_indices)
            self.selected_point = new_indices[0]
        if last_device:
            self.selected_device = last_device
        if new_indices or last_device:
            self._rebuild_sim(preserve_selection=True)
            self._populate_inspector_from_selection()

    def _apply_device_edit(self) -> None:
        if not self.selected_device or not self.robot_cfg:
            return
        kind, name = self.selected_device
        cfg = None
        if kind == "actuator":
            cfg = next((a for a in self.robot_cfg.actuators if a.name == name), None)
        elif kind == "sensor":
            cfg = next((s for s in self.robot_cfg.sensors if s.name == name), None)
        if not cfg:
            return
        self._push_undo_state()
        new_name = self.txt_device_name.get_text().strip() or cfg.name
        try:
            px = float(self.txt_pose_x.get_text() or cfg.mount_pose[0])
            py = float(self.txt_pose_y.get_text() or cfg.mount_pose[1])
            ptheta = float(self.txt_pose_theta.get_text() or cfg.mount_pose[2])
        except ValueError:
            px, py, ptheta = cfg.mount_pose
        cfg.name = new_name
        cfg.mount_pose = (px, py, ptheta)
        self._after_state_change()
        self.selected_device = (kind, new_name)
        self._populate_inspector_from_selection()

    def _open_advanced_view(self) -> None:
        if not self.selected_device or not self.robot_cfg:
            self.status_hint = "Select a device to open advanced view"
            return
        kind, name = self.selected_device
        cfg = None
        if kind == "actuator":
            cfg = next((a for a in self.robot_cfg.actuators if a.name == name), None)
        elif kind == "sensor":
            cfg = next((s for s in self.robot_cfg.sensors if s.name == name), None)
        if not cfg:
            self.status_hint = "Device missing"
            return
        payload = {
            "name": getattr(cfg, "name", name),
            "type": getattr(cfg, "type", kind),
            "body": getattr(cfg, "body", ""),
            "mount_pose": getattr(cfg, "mount_pose", (0, 0, 0)),
            "params": getattr(cfg, "params", {}),
        }
        html = "<br>".join(
            [
                f"<b>Name</b>: {payload['name']}",
                f"<b>Type</b>: {payload['type']}",
                f"<b>Body</b>: {payload['body']}",
                f"<b>Pose</b>: {payload['mount_pose']}",
                f"<b>Params</b>: {json.dumps(payload['params'], indent=2)}",
                "Edit params in the inspector text fields then click Apply.",
            ]
        )
        pygame_gui.windows.UIMessageWindow(
            rect=pygame.Rect((self.window_size[0] - 360, 440), (320, 260)),
            manager=self.manager,
            window_title=f"Advanced: {name}",
            html_message=html,
        )
        self.status_hint = "Advanced view opened"

    def _delete_selected_device(self) -> None:
        if not self.selected_device or not self.robot_cfg:
            return
        kind, name = self.selected_device
        self._push_undo_state()
        if kind == "actuator":
            self.robot_cfg.actuators = [a for a in self.robot_cfg.actuators if a.name != name]
        elif kind == "sensor":
            self.robot_cfg.sensors = [s for s in self.robot_cfg.sensors if s.name != name]
        self.selected_device = None
        self._after_state_change()

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                if self.hover_menu and self.hover_menu.handle_event(event):
                    continue
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    if event.key in (pygame.K_EQUALS, pygame.K_PLUS):
                        self.scale *= 1.1
                    if event.key in (pygame.K_MINUS, pygame.K_UNDERSCORE):
                        self.scale /= 1.1
                    if event.key == pygame.K_z and (event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META | pygame.KMOD_GUI)):
                        if self.active_tab == "custom":
                            if event.mod & pygame.KMOD_SHIFT:
                                self._redo_custom()
                            else:
                                self._undo_custom()
                        elif self.active_tab == "environment":
                            if event.mod & pygame.KMOD_SHIFT:
                                self._redo_world()
                            else:
                                self._undo_world()
                        else:
                            if event.mod & pygame.KMOD_SHIFT:
                                self._redo()
                            else:
                                self._undo()
                    if event.key == pygame.K_c and (event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META | pygame.KMOD_GUI)):
                        self._copy_selection()
                    if event.key == pygame.K_v and (event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META | pygame.KMOD_GUI)):
                        self._paste_selection()
                if event.type == pygame.MOUSEWHEEL:
                    if self.viewport_rect.collidepoint(pygame.mouse.get_pos()):
                        self.scale *= 1.0 + 0.1 * event.y
                if event.type == pygame.MOUSEBUTTONDOWN:
                    mods = pygame.key.get_mods()
                    shift = bool(mods & pygame.KMOD_SHIFT)
                    if event.button in (2, 3) and shift:
                        self.rotate_active = True
                        self.rotate_anchor = event.pos
                        self.rotate_start_angle = self.view_rotation
                    elif event.button in (2, 3):  # middle/right -> pan
                        self.pan_active = True
                        self.pan_start = event.pos
                    elif event.button == 1 and self.viewport_rect.collidepoint(event.pos):
                        self._handle_canvas_click(event.pos, start_drag=True)
                if event.type == pygame.MOUSEBUTTONUP:
                    if event.button in (2, 3):
                        self.pan_active = False
                        self.pan_start = None
                        if self.rotate_active:
                            self.rotate_active = False
                            self.rotate_anchor = None
                    if event.button == 1:
                        if self.mode == "draw_shape" and self.shape_start:
                            self._finalize_shape(self._s2w(event.pos))
                        if self.env_drawing:
                            self._finalize_env_stroke()
                        if self.bounds_mode and self.bounds_start:
                            self.bounds_preview = screen_to_world(
                                event.pos, self.viewport_rect, self.scale, self.offset, self.view_rotation
                            )
                            self._finalize_bounds()
                        if self.marquee_active:
                            self._finalize_marquee_selection()
                        if self.dragging:
                            self.dragging = False
                            self.drag_mode = None
                            self.drag_handle = None
                            self.drag_points_snapshot.clear()
                            self.drag_start_local = None
                            self.drag_scale_center = None
                            self.drag_scale_origin_vec = None
                        if self.dragging_device:
                            self.dragging_device = False
                            # finalize device move with a single rebuild for stability
                            self._rebuild_sim(preserve_selection=True)
                            self._populate_inspector_from_selection()
                if event.type == pygame.MOUSEMOTION:
                    self._handle_mouse_motion(event)
                self.manager.process_events(event)
                self._handle_ui_event(event)
            self.manager.update(dt)
            if self.hover_menu:
                self.hover_menu.update_hover(pygame.mouse.get_pos())
            self._draw()
        pygame.quit()

    def _handle_ui_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame_gui.UI_CONFIRMATION_DIALOG_CONFIRMED and self.pending_dialog:
            if self.pending_tab:
                # Save current tab then switch
                self._save_design(self.active_tab)
                self._apply_tab_switch(self.pending_tab)
                self.pending_tab = None
                action = None
                kind = None
                if self.pending_workspace_action:
                    action, kind = self.pending_workspace_action
                self.pending_workspace_action = None
                self.pending_dialog = None
                if action and kind:
                    self._perform_workspace_action(action, kind, allow_prompt=True)
                return
            if self.pending_workspace_action:
                action, kind = self.pending_workspace_action
                if kind in ("robot", "environment", "custom"):
                    self._save_design(kind)
                self.pending_workspace_action = None
                self.pending_dialog = None
                self._perform_workspace_action(action, kind, allow_prompt=True)
                return
            self.pending_dialog = None
            return
        if event.type == pygame_gui.UI_WINDOW_CLOSE and self.pending_dialog and event.ui_element == self.pending_dialog:
            # user closed without saving
            if self.pending_tab:
                self._apply_tab_switch(self.pending_tab)
                self.pending_tab = None
            self.pending_workspace_action = None
            self.pending_dialog = None
            return
        if event.type == pygame_gui.UI_WINDOW_CLOSE:
            if self.workspace_new_window and event.ui_element == self.workspace_new_window:
                self.workspace_new_window = None
                self.workspace_new_entry = None
                self.workspace_new_kind = None
            if self.workspace_save_as_window and event.ui_element == self.workspace_save_as_window:
                self.workspace_save_as_window = None
                self.workspace_save_as_entry = None
                self.workspace_save_as_kind = None
            if self.workspace_file_dialog and event.ui_element == self.workspace_file_dialog:
                self.workspace_file_dialog = None
                self.workspace_file_kind = None
                self.workspace_file_mode = None
            if self.device_import_dialog and event.ui_element == self.device_import_dialog:
                self.device_import_dialog = None
        if event.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
            if event.ui_element == self.dropdown:
                self.scenario_name = event.text if event.text != "<none>" else None
            elif event.ui_element == self.body_dropdown:
                self.body_name = event.text
        if event.type == pygame_gui.UI_FILE_DIALOG_PATH_PICKED:
            if self.workspace_file_dialog and event.ui_element == self.workspace_file_dialog:
                self._handle_workspace_file_pick(Path(event.text))
                self.workspace_file_dialog = None
                self.workspace_file_kind = None
                self.workspace_file_mode = None
            elif self.device_import_dialog and event.ui_element == self.device_import_dialog:
                self._handle_device_import(Path(event.text))
                self.device_import_dialog = None
            return
        if event.type == pygame_gui.UI_HORIZONTAL_SLIDER_MOVED:
            if self.brush_slider and event.ui_element == self.brush_slider:
                self._set_brush_thickness(float(getattr(event, "value", self.env_brush_thickness)))
                return
        if event.type == pygame_gui.UI_SELECTION_LIST_DOUBLE_CLICKED_SELECTION:
            # Support double-click-to-open without pressing OK in file dialogs.
            if (
                self.workspace_file_dialog
                and hasattr(self.workspace_file_dialog, "file_selection_list")
                and event.ui_element == self.workspace_file_dialog.file_selection_list
            ):
                base = Path(getattr(self.workspace_file_dialog, "current_directory_path", ""))
                target = (base / event.text).resolve()
                is_scenario_dir = self.workspace_file_kind == "scenario" and target.is_dir()
                if target.is_file() or is_scenario_dir:
                    picked = target
                    if is_scenario_dir:
                        desc = target / "scenario.json"
                        picked = desc if desc.exists() else target
                    self._handle_workspace_file_pick(picked)
                    try:
                        self.workspace_file_dialog.kill()
                    except Exception:
                        pass
                    self.workspace_file_dialog = None
                    self.workspace_file_kind = None
                    self.workspace_file_mode = None
                    return
            if (
                self.device_import_dialog
                and hasattr(self.device_import_dialog, "file_selection_list")
                and event.ui_element == self.device_import_dialog.file_selection_list
            ):
                base = Path(getattr(self.device_import_dialog, "current_directory_path", ""))
                target = (base / event.text).resolve()
                if target.is_file():
                    self._handle_device_import(target)
                    try:
                        self.device_import_dialog.kill()
                    except Exception:
                        pass
                    self.device_import_dialog = None
                    return
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            obj_ids = event.ui_element.object_ids if hasattr(event.ui_element, "object_ids") else []
            if obj_ids:
                last_id = obj_ids[-1]
                if last_id.endswith("new_asset_confirm"):
                    self._confirm_new_asset()
                    return
                if last_id.endswith("new_asset_cancel"):
                    self.workspace_new_window = None
                    self.workspace_new_entry = None
                    self.workspace_new_kind = None
                    return
                if last_id.endswith("save_as_confirm"):
                    self._confirm_save_as()
                    return
                if last_id.endswith("save_as_cancel"):
                    self.workspace_save_as_window = None
                    self.workspace_save_as_entry = None
                    self.workspace_save_as_kind = None
                    return
            if event.ui_element == self.btn_load:
                self._load_scenario()
            elif event.ui_element == self.btn_save:
                self._save_scenario()
            elif event.ui_element == self.btn_add_point:
                self._set_mode("add")
            elif event.ui_element == self.btn_move_point:
                self._set_mode("select")
            elif event.ui_element == self.btn_del_point:
                self._set_mode("delete")
            elif event.ui_element == self.btn_undo:
                self._undo()
            elif event.ui_element == self.btn_redo:
                self._redo()
            elif event.ui_element == self.btn_apply_device:
                self._apply_device_edit()
            elif event.ui_element == self.btn_delete_device:
                self._delete_selected_device()
            elif event.ui_element == self.btn_brush_mark:
                self._set_env_tool("mark")
            elif event.ui_element == self.btn_brush_wall:
                self._set_env_tool("wall")
            elif event.ui_element == self.btn_brush_off:
                self._set_env_tool("off")
            elif event.ui_element == self.btn_brush_clear:
                self._clear_env_drawings()
            elif event.ui_element == self.btn_brush_undo:
                self._undo_world()

    def _view_reset(self) -> None:
        self.offset = (0.0, 0.0)
        self.scale = 400.0
        self.status_hint = "View reset"

    def _view_reset_rotation(self) -> None:
        self.view_rotation = 0.0
        self.status_hint = "Rotation reset"

    def _view_toggle_grid(self) -> None:
        self.grid_enabled = not self.grid_enabled
        self.status_hint = "Grid on" if self.grid_enabled else "Grid off (clean view)"

    def _save_scenario(self, target_name: Optional[str] = None) -> None:
        if not (self.world_cfg and self.robot_cfg):
            self.status_hint = "Need robot and environment to save scenario"
            return
        brush_kind = self.env_tool if self.env_tool in ("mark", "wall") else "mark"
        self.world_cfg.designer_state = DesignerState(
            creation_context=self.creation_context,
            mode=self.mode,
            brush_kind=brush_kind,
            brush_thickness=self.env_brush_thickness,
            shape_tool=self.shape_tool,
        )
        name = target_name or self.scenario_name or "untitled_scenario"
        safe = "".join(c for c in name if c.isalnum() or c in ("_", "-")) or "untitled_scenario"
        scenario_path = self.scenario_root / safe
        scenario_path.mkdir(parents=True, exist_ok=True)

        # Load existing descriptor if present to preserve metadata/roster
        descriptor_path = scenario_path / "scenario.json"
        descriptor_data: Dict[str, object] = {}
        def _serialize(obj):
            if isinstance(obj, dict):
                return {k: _serialize(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [_serialize(v) for v in obj]
            if isinstance(obj, Path):
                return str(obj)
            if hasattr(obj, "__dict__"):
                return _serialize(vars(obj))
            return obj
        if descriptor_path.exists():
            try:
                with descriptor_path.open("r", encoding="utf-8") as f:
                    descriptor_data = json.load(f)
            except Exception:
                descriptor_data = {}
        if getattr(self, "scenario_descriptor", None):
            try:
                descriptor_data = _serialize(self.scenario_descriptor) or descriptor_data
            except Exception:
                pass

        env_ref = descriptor_data.get("environment") or descriptor_data.get("env") or "world.json"
        env_path = Path(env_ref)
        if not env_path.is_absolute():
            env_path = scenario_path / env_path
        env_path.parent.mkdir(parents=True, exist_ok=True)
        save_environment_design(env_path, self.world_cfg)

        robots_raw = [_serialize(r) for r in (descriptor_data.get("robots") or [])]
        if not robots_raw and descriptor_data.get("robot"):
            robots_raw = [{"ref": descriptor_data.get("robot"), "id": "robot"}]
        if not robots_raw:
            robots_raw = [{"ref": "robot.json", "id": self.active_robot_id or "robot"}]
        # pick target robot entry to update with current robot_cfg
        target_entry = next((r for r in robots_raw if r.get("id") == (self.active_robot_id or "robot")), None) or robots_raw[0]
        ref = target_entry.get("ref") or target_entry.get("robot") or "robot.json"
        robot_path = Path(ref)
        if not robot_path.is_absolute():
            robot_path = scenario_path / robot_path
        robot_path.parent.mkdir(parents=True, exist_ok=True)
        save_robot_design(robot_path, self.robot_cfg)
        target_entry["ref"] = ref if isinstance(ref, str) else robot_path.name
        target_entry["robot"] = target_entry["ref"]
        target_entry["id"] = target_entry.get("id") or (self.active_robot_id or "robot")
        target_entry["controller"] = getattr(self.robot_cfg, "controller_module", None)
        target_entry.setdefault("spawn_pose", getattr(self.robot_cfg, "spawn_pose", (0.0, 0.0, 0.0)))
        target_entry.setdefault("metadata", {})

        normalized_robots = []
        for entry in robots_raw:
            if not isinstance(entry, dict):
                entry = _serialize(entry) if entry else {}
            ref_val = entry.get("ref") or entry.get("robot") or "robot.json"
            normalized_robots.append(
                {
                    "id": entry.get("id") or "robot",
                    "ref": ref_val,
                    "robot": ref_val,
                    "controller": entry.get("controller"),
                    "spawn_pose": entry.get("spawn_pose") or entry.get("pose") or (0.0, 0.0, 0.0),
                    "role": entry.get("role"),
                    "metadata": entry.get("metadata") or {},
                }
            )
        robots_raw = normalized_robots

        env_ref_str = env_ref if isinstance(env_ref, str) else env_path.name
        descriptor_payload = {
            "id": descriptor_data.get("id") or safe,
            "name": descriptor_data.get("name") or safe,
            "description": descriptor_data.get("description"),
            "thumbnail": descriptor_data.get("thumbnail"),
            "help": descriptor_data.get("help"),
            "seed": descriptor_data.get("seed"),
            "metadata": descriptor_data.get("metadata") or {},
            "environment": env_ref_str,
            "robots": robots_raw,
        }
        try:
            with descriptor_path.open("w", encoding="utf-8") as f:
                json.dump(descriptor_payload, f, indent=2)
        except Exception as exc:
            print(f"[designer] failed to write descriptor: {exc}")

        # Normalize sim/scratch and update UI context
        self.scenario_name = safe
        self.scenario_descriptor = descriptor_payload
        self._refresh_scenarios_list()
        self._update_status_context()
        self.status_hint = f"Saved scenario {self.scenario_name}"

    # --- Environment drawing/bounds -------------------------------------
    def _set_env_tool(self, tool: str) -> None:
        if self.env_drawing and self.env_stroke_points:
            self._finalize_env_stroke()
        if self.active_tab != "environment":
            self._ensure_tab("environment")
            if self.pending_dialog:
                return
        self.env_tool = tool
        self.env_drawing = False
        self.env_stroke_points.clear()
        if tool == "off":
            self.status_hint = "Environment drawing off"
        elif tool == "wall":
            self.status_hint = "Drawing walls: click-drag to paint segments"
        else:
            self.status_hint = "Drawing marks: click-drag to paint"
        self._refresh_hover_menu()
        self._sync_paint_panel()

    def _sync_paint_panel(self) -> None:
        if not getattr(self, "paint_panel", None):
            return
        if self.env_tool in ("mark", "wall") and self.active_tab == "environment":
            self.paint_panel.show()
            if getattr(self, "paint_mode_label", None):
                self.paint_mode_label.set_text(f"Paint: {self.env_tool}")
            if getattr(self, "brush_slider", None):
                try:
                    self.brush_slider.set_current_value(self.env_brush_thickness)
                except Exception:
                    pass
            self._update_brush_label()
        else:
            self.paint_panel.hide()

    def _set_brush_thickness(self, thickness: float) -> None:
        self.env_brush_thickness = max(0.005, float(thickness))
        self.status_hint = f"Brush thickness {self.env_brush_thickness:.3f} m"
        self._update_brush_label()
        self._sync_paint_panel()
        self._refresh_hover_menu()

    def _clear_env_drawings(self) -> None:
        if self.active_tab != "environment":
            self._ensure_tab("environment")
            if self.pending_dialog:
                return
        if not self.world_cfg or not getattr(self.world_cfg, "drawings", None):
            return
        self._push_world_undo_state()
        self.world_cfg.drawings = []
        self._after_world_change()
        self.status_hint = "Cleared environment drawings"

    def _start_bounds_mode(self) -> None:
        if self.active_tab != "environment":
            self._ensure_tab("environment")
            if self.pending_dialog:
                return
        self.bounds_mode = True
        self.bounds_start = None
        self.bounds_preview = None
        self.status_hint = "Bounds: click-drag to set rectangle"
        self._refresh_hover_menu()

    def _clear_bounds(self) -> None:
        if self.active_tab != "environment":
            self._ensure_tab("environment")
            if self.pending_dialog:
                return
        if not self.world_cfg or not getattr(self.world_cfg, "bounds", None):
            return
        self._push_world_undo_state()
        self.world_cfg.bounds = None
        self._after_world_change()
        self.status_hint = "Bounds cleared"

    def _stroke_color(self, kind: str) -> Tuple[int, int, int]:
        if kind == "wall":
            return darken_color(self.theme["device_sensor"], 0.15)
        return self.theme["selection"]

    def _unique_shape_name(self, base: str, for_robot: bool) -> str:
        suffix = 1
        existing = set()
        if for_robot and self.robot_cfg:
            existing.update([b.name for b in self.robot_cfg.bodies])
        shapes = getattr(self.world_cfg, "shape_objects", []) or []
        existing.update([getattr(o, "name", "") for o in shapes])
        customs = getattr(self.world_cfg, "custom_objects", []) or []
        existing.update([getattr(o, "name", "") for o in customs])
        while True:
            candidate = f"{base}_{suffix}"
            if candidate not in existing:
                return candidate
            suffix += 1

    def _build_shape_body(self, start: Tuple[float, float], end: Tuple[float, float]) -> Optional[BodyConfig]:
        sx, sy = start
        ex, ey = end
        if self.shape_tool == "rect":
            minx, maxx = sorted([sx, ex])
            miny, maxy = sorted([sy, ey])
            if abs(maxx - minx) < 1e-4 or abs(maxy - miny) < 1e-4:
                return None
            pts = [(minx, miny), (minx, maxy), (maxx, maxy), (maxx, miny)]
        elif self.shape_tool == "triangle":
            pts = [(sx, sy), (ex, sy), (ex, ey)]
            if math.hypot(ex - sx, ey - sy) < 1e-4:
                return None
        else:  # line -> thin rectangle
            dx = ex - sx
            dy = ey - sy
            seg_len = math.hypot(dx, dy)
            if seg_len < 1e-4:
                return None
            nx = -dy / seg_len * (self.env_brush_thickness / 2.0)
            ny = dx / seg_len * (self.env_brush_thickness / 2.0)
            pts = [
                (sx + nx, sy + ny),
                (ex + nx, ey + ny),
                (ex - nx, ey - ny),
                (sx - nx, sy - ny),
            ]
        edges = [(i, (i + 1) % len(pts)) for i in range(len(pts))]
        name = self._unique_shape_name(self.shape_tool, self.creation_context == "robot")
        return BodyConfig(
            name=name,
            points=[(float(x), float(y)) for x, y in pts],
            edges=edges,
            pose=(0.0, 0.0, 0.0),
            can_move=self.creation_context == "robot",
            mass=1.0,
            inertia=1.0,
        )

    def _custom_dir(self) -> Path:
        return self._design_root("custom")

    def _save_custom_body(self, body_cfg: BodyConfig, name_override: Optional[str] = None) -> Optional[Path]:
        try:
            target_dir = self._custom_dir()
            target_dir.mkdir(parents=True, exist_ok=True)
            fname = (name_override or body_cfg.name) + ".json"
            target_path = target_dir / fname
            save_json(target_path, body_cfg)
            return target_path
        except Exception as exc:
            print(f"Failed to save custom object: {exc}")
            return None

    def _add_shape_object(self, body_cfg: BodyConfig) -> None:
        if not self.world_cfg:
            return
        if self.creation_context == "robot":
            self._push_undo_state()
            if self.robot_cfg:
                self.robot_cfg.bodies.append(body_cfg)
                self._after_state_change()
            return
        if self.creation_context == "custom":
            self._push_custom_undo()
            self.custom_active = CustomObjectConfig(name=body_cfg.name, body=body_cfg, kind="custom")
            self.custom_dirty = True
            return
        self._push_world_undo_state()
        wrapper = WorldObjectConfig(name=body_cfg.name, body=body_cfg)
        self.world_cfg.shape_objects.append(wrapper)  # type: ignore[arg-type]
        self._after_world_change()

    def _finalize_shape(self, end_point: Tuple[float, float]) -> None:
        if not self.shape_start:
            return
        body_cfg = self._build_shape_body(self.shape_start, end_point)
        self.shape_start = None
        self.shape_preview = None
        if not body_cfg:
            return
        self._add_shape_object(body_cfg)
        self.status_hint = f"Added {self.shape_tool} ({self.creation_context})"
        if self.creation_context == "custom":
            self.custom_dirty = True

    def _save_selection_as_custom(self) -> None:
        body_cfg = self._current_body_cfg()
        if not body_cfg:
            return
        clone = copy.deepcopy(body_cfg)
        clone.name = self._unique_shape_name(clone.name or "custom", False)
        self.custom_active = CustomObjectConfig(name=clone.name, body=clone, kind="custom")
        saved = self._save_custom_body(clone)
        if saved:
            self.custom_design_name = clone.name
            self.custom_dirty = False
            self.status_hint = f"Saved custom object to {saved.name}"

    def _import_custom_object(self) -> None:
        target_dir = self._custom_dir()
        if not target_dir.exists():
            self.status_hint = "No custom object folder yet"
            return
        json_files = sorted(target_dir.glob("*.json"))
        if not json_files:
            self.status_hint = "No custom objects to import"
            return
        path = json_files[0]
        try:
            asset = load_custom_asset(path)
            asset.name = self._unique_shape_name(asset.name, False)
            self.custom_active = asset
            self.custom_dirty = False
            self.custom_design_name = asset.name
            self.status_hint = f"Imported custom {path.stem}"
        except Exception as exc:
            self.status_hint = f"Import failed: {exc}"
    def _min_draw_spacing(self) -> float:
        return 0.01

    def _finalize_env_stroke(self) -> None:
        if not self.world_cfg or not self.env_stroke_points:
            self.env_drawing = False
            self.env_stroke_points.clear()
            return
        pts = self.env_stroke_points.copy()
        self.env_drawing = False
        self.env_stroke_points.clear()
        if len(pts) < 2:
            return
        self._push_world_undo_state()
        stroke = StrokeConfig(
            kind=self.env_tool if self.env_tool != "off" else "mark",
            thickness=self.env_brush_thickness,
            points=[(float(x), float(y)) for x, y in pts],
            color=self._stroke_color(self.env_tool),
        )
        self.world_cfg.drawings.append(stroke)
        self._after_world_change()
        self.status_hint = f"Added {stroke.kind} stroke ({len(stroke.points)} pts)"

    def _finalize_bounds(self) -> None:
        if not self.world_cfg or not self.bounds_start or not self.bounds_preview:
            self.bounds_mode = False
            self.bounds_start = None
            self.bounds_preview = None
            return
        x0, y0 = self.bounds_start
        x1, y1 = self.bounds_preview
        min_x, max_x = sorted([x0, x1])
        min_y, max_y = sorted([y0, y1])
        if max_x - min_x < 1e-4 or max_y - min_y < 1e-4:
            self.bounds_mode = False
            self.bounds_start = None
            self.bounds_preview = None
            return
        self._push_world_undo_state()
        self.world_cfg.bounds = EnvironmentBounds(min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y)
        self._after_world_change()
        self.bounds_mode = False
        self.bounds_start = None
        self.bounds_preview = None
        self.status_hint = f"Bounds set ({min_x:.2f},{min_y:.2f})–({max_x:.2f},{max_y:.2f})"

    def _current_body_cfg(self) -> Optional[BodyConfig]:
        self._ensure_robot_defaults()
        if not self.robot_cfg:
            return None
        if not self.body_name and self.robot_cfg.bodies:
            self.body_name = self.robot_cfg.bodies[0].name
        if not self.body_name:
            return None
        for b in self.robot_cfg.bodies:
            if b.name == self.body_name:
                return b
        return None

    def _body_pose(self, body_cfg: BodyConfig) -> Pose2D:
        spawn = self.robot_cfg.spawn_pose if self.robot_cfg else (0.0, 0.0, 0.0)
        return Pose2D(
            body_cfg.pose[0] + spawn[0],
            body_cfg.pose[1] + spawn[1],
            body_cfg.pose[2] + spawn[2],
        )

    def _handle_canvas_click(self, pos: Tuple[int, int], start_drag: bool = False) -> None:
        body_cfg = self._current_body_cfg()
        if not body_cfg and self.env_tool == "off" and not self.bounds_mode and self.mode != "draw_shape":
            self.status_hint = "No robot body selected. Add or select a body to edit."
            return
        mods = pygame.key.get_mods()
        shift = bool(mods & pygame.KMOD_SHIFT)
        marquee_mod = bool(mods & (pygame.KMOD_SHIFT | pygame.KMOD_META | pygame.KMOD_GUI))
        world_point = screen_to_world(pos, self.viewport_rect, self.scale, self.offset, self.view_rotation)
        self.hover_world = world_point
        if self.bounds_mode:
            if start_drag:
                self.bounds_start = world_point
                self.bounds_preview = world_point
            return
        if self.env_tool != "off" and self.active_tab == "environment":
            if start_drag:
                self.env_drawing = True
                self.env_stroke_points = [world_point]
            return
        if self.mode == "draw_shape":
            if start_drag:
                self.shape_start = world_point
                self.shape_preview = world_point
            return
        if self.mode == "add_device":
            dtype = str(self.pending_device_type or self._device_choice() or "motor")
            if dtype:
                self._push_undo_state()
                if not body_cfg:
                    self.status_hint = "Add a body before placing devices."
                    return
                placed = self._create_device_at_point(body_cfg, world_point, str(dtype))
                self._after_state_change()
                if placed:
                    self.selected_device = placed
                    self.selected_point = None
                    self._populate_inspector_from_selection()
                    self.status_hint = f"Placed {dtype} '{placed[1]}'"
                self._set_mode("select")
            return
        # Prefer device pick when in select mode
        if self.mode == "select":
            body_pose = self._body_pose(body_cfg) if body_cfg else None
            local_point = body_pose.inverse().transform_point(world_point) if body_pose else (0.0, 0.0)
            idx = self._nearest_vertex(body_cfg, local_point, thresh=0.03) if body_cfg else None
            # Scale handles take priority when dragging begins
            if start_drag and self.selected_points:
                hit = self._selection_handle_hit(body_cfg, pos)
                if hit:
                    handle_name, handle_local = hit
                    centroid = self._selection_centroid(body_cfg)
                    if centroid:
                        self._push_undo_state()
                        self.dragging = True
                        self.drag_mode = "scale"
                        self.drag_handle = handle_name
                        self.drag_points_snapshot = {idx: body_cfg.points[idx] for idx in self.selected_points}
                        self.drag_scale_center = centroid
                        self.drag_scale_origin_vec = (handle_local[0] - centroid[0], handle_local[1] - centroid[1])
                        return
            picked = self._pick_device(world_point)
            if picked:
                self.selected_device = picked
                self.selected_point = None
                self.selected_points.clear()
                self.dragging_device = start_drag
                if start_drag:
                    self._push_undo_state()
                self.status_hint = "Drag to reposition device; edit pose in inspector."
                self._populate_inspector_from_selection()
                return
            if start_drag and marquee_mod and idx is None:
                self.marquee_active = True
                self.marquee_start = world_point
                self.marquee_end = world_point
                self.selected_points.clear()
                self.selected_device = None
                return
        if not body_cfg:
            return
        body_pose = self._body_pose(body_cfg)
        local_point = body_pose.inverse().transform_point(world_point)
        if self.mode == "add":
            self._push_undo_state()
            body_cfg.points.append((float(local_point[0]), float(local_point[1])))
            body_cfg.edges = [(i, (i + 1) % len(body_cfg.points)) for i in range(len(body_cfg.points))]
            self._rebuild_sim()
        elif self.mode == "delete":
            idx = self._nearest_vertex(body_cfg, local_point, thresh=0.03)
            if idx is not None and len(body_cfg.points) > 3:
                self._push_undo_state()
                body_cfg.points.pop(idx)
                body_cfg.edges = [(i, (i + 1) % len(body_cfg.points)) for i in range(len(body_cfg.points))]
                self._rebuild_sim()
        else:  # select/move
            idx = self._nearest_vertex(body_cfg, local_point, thresh=0.03)
            if idx is not None:
                if shift:
                    if idx in self.selected_points:
                        self.selected_points.remove(idx)
                    else:
                        self.selected_points.add(idx)
                    self.selected_point = idx if self.selected_points else None
                else:
                    if idx in self.selected_points and len(self.selected_points) > 0:
                        # keep existing multi-selection when clicking an already-selected point
                        self.selected_point = idx
                    else:
                        self.selected_points = {idx}
                        self.selected_point = idx
                self.selected_device = None
                if start_drag:
                    self._push_undo_state()
                    self.dragging = True
                    self.drag_mode = "move"
                    self.drag_handle = None
                    self.drag_points_snapshot = {i: body_cfg.points[i] for i in self.selected_points}
                    self.drag_start_local = (float(local_point[0]), float(local_point[1]))

    def _handle_mouse_motion(self, event: pygame.event.Event) -> None:
        if self.rotate_active and self.rotate_anchor:
            dx = event.pos[0] - self.rotate_anchor[0]
            dy = event.pos[1] - self.rotate_anchor[1]
            self.view_rotation = self.rotate_start_angle + (dx - dy) * 0.005
            return
        if self.pan_active and self.pan_start:
            dx = (event.pos[0] - self.pan_start[0]) / self.scale
            dy = (event.pos[1] - self.pan_start[1]) / self.scale
            self.offset = (self.offset[0] - dx, self.offset[1] + dy)
            self.pan_start = event.pos
            return
        mouse_pos = event.pos
        inside = self.viewport_rect.collidepoint(mouse_pos)
        if not inside and not (self.dragging or self.dragging_device or self.env_drawing or self.bounds_mode or self.marquee_active):
            self.hover_point = None
            self.hover_device = None
            self.hover_world = None
            return
        # Allow dragging slightly outside the viewport
        clamped_pos = (
            max(self.viewport_rect.left, min(mouse_pos[0], self.viewport_rect.right)),
            max(self.viewport_rect.top, min(mouse_pos[1], self.viewport_rect.bottom)),
        )
        world_point = screen_to_world(clamped_pos, self.viewport_rect, self.scale, self.offset, self.view_rotation)
        self.hover_world = world_point
        if self.marquee_active and self.marquee_start:
            self.marquee_end = world_point
            return
        if self.env_drawing and self.active_tab == "environment":
            if self.env_stroke_points:
                last = self.env_stroke_points[-1]
                if math.hypot(world_point[0] - last[0], world_point[1] - last[1]) >= self._min_draw_spacing():
                    self.env_stroke_points.append(world_point)
            return
        if self.mode == "draw_shape" and self.shape_start:
            self.shape_preview = world_point
            return
        if self.bounds_mode and self.bounds_start:
            self.bounds_preview = world_point
            return
        body_cfg = self._current_body_cfg()
        if not body_cfg:
            return
        local_point = self._body_pose(body_cfg).inverse().transform_point(world_point)
        self.hover_point = self._nearest_vertex(body_cfg, local_point, thresh=0.03)
        self.hover_device = self._pick_device(world_point)
        if self.dragging:
            if self.drag_mode == "move" and self.drag_points_snapshot and self.drag_start_local:
                dx = float(local_point[0] - self.drag_start_local[0])
                dy = float(local_point[1] - self.drag_start_local[1])
                for idx, orig in self.drag_points_snapshot.items():
                    if 0 <= idx < len(body_cfg.points):
                        body_cfg.points[idx] = (orig[0] + dx, orig[1] + dy)
                body_cfg.edges = [(i, (i + 1) % len(body_cfg.points)) for i in range(len(body_cfg.points))]
                self._rebuild_sim(preserve_selection=True)
                return
            if (
                self.drag_mode == "scale"
                and self.drag_points_snapshot
                and self.drag_scale_center
                and self.drag_scale_origin_vec
            ):
                cx, cy = self.drag_scale_center
                vx = float(local_point[0] - cx)
                vy = float(local_point[1] - cy)
                ox, oy = self.drag_scale_origin_vec
                sx = vx / ox if abs(ox) > 1e-6 else 1.0
                sy = vy / oy if abs(oy) > 1e-6 else 1.0
                # Avoid collapsing/flip by clamping to small positive
                sx = sx if sx != 0 else 0.001
                sy = sy if sy != 0 else 0.001
                for idx, orig in self.drag_points_snapshot.items():
                    if 0 <= idx < len(body_cfg.points):
                        px, py = orig
                        nx = cx + (px - cx) * sx
                        ny = cy + (py - cy) * sy
                        body_cfg.points[idx] = (nx, ny)
                body_cfg.edges = [(i, (i + 1) % len(body_cfg.points)) for i in range(len(body_cfg.points))]
                self._rebuild_sim(preserve_selection=True)
                return
        if self.dragging_device and self.selected_device:
            self._move_device_to(self.selected_device, world_point)
            return

    def _nearest_vertex(self, body: BodyConfig, point: Tuple[float, float], thresh: float = 0.05) -> Optional[int]:
        best = None
        best_d = thresh
        for i, (x, y) in enumerate(body.points):
            d = ((x - point[0]) ** 2 + (y - point[1]) ** 2) ** 0.5
            if d < best_d:
                best_d = d
                best = i
        return best

    def _add_device(self) -> None:
        """Legacy quick-add: drop device at body origin."""
        body_cfg = self._current_body_cfg()
        if not body_cfg:
            return
        dtype = self._device_choice()
        self._push_undo_state()
        center_world = self._body_pose(body_cfg).transform_point((0.0, 0.0))
        self._create_device_at_point(body_cfg, center_world, dtype)
        self._after_state_change()

    def _draw(self) -> None:
        # cohesive viewport with consistent theme colors
        self.window_surface.fill(self.theme["bg"])
        pygame.draw.rect(self.window_surface, self.theme["viewport"], self.viewport_rect)
        pygame.draw.rect(self.window_surface, self.theme["viewport_border"], self.viewport_rect, 1)
        # Clip drawing to the viewport to avoid overlaying UI
        self.window_surface.set_clip(self.viewport_rect)
        if self.sim and self.active_tab != "custom":
            self._draw_world()
        if self.marquee_active and self.marquee_start and self.marquee_end:
            x0, y0 = self.marquee_start
            x1, y1 = self.marquee_end
            corners = [(x0, y0), (x0, y1), (x1, y1), (x1, y0)]
            scr = [world_to_screen(p, self.viewport_rect, self.scale, self.offset, self.view_rotation) for p in corners]
            overlay = pygame.Surface((self.viewport_rect.width, self.viewport_rect.height), pygame.SRCALPHA)
            shifted = [(sx - self.viewport_rect.x, sy - self.viewport_rect.y) for sx, sy in scr]
            pygame.draw.polygon(overlay, with_alpha(self.theme["selection_fill"], 50), shifted)
            pygame.draw.polygon(overlay, with_alpha(self.theme["selection"], 180), shifted, 2)
            self.window_surface.blit(overlay, self.viewport_rect.topleft)
        self.window_surface.set_clip(None)
        overlay_font = pygame.font.Font(pygame.font.get_default_font(), 14)
        help_lines = [
            "Left click: select/drag points or devices",
            "Right/Middle drag: pan  |  Wheel: zoom",
            "Devices: pick type from menu, then click canvas",
        ]
        for i, line in enumerate(help_lines):
            txt = overlay_font.render(line, True, self.theme["help_text"])
            self.window_surface.blit(txt, (self.viewport_rect.x + 8, self.viewport_rect.y + 8 + i * 18))
        # Scenario metadata overlay (top-right, hidden when absent)
        show_info = bool(self.scenario_name or self.scenario_descriptor or self.scenario_thumbnail)
        if show_info:
            info_font = pygame.font.Font(pygame.font.get_default_font(), 14)
            info_y = self.viewport_rect.y + 10
            thumb_w = 0
            thumb_x = self.viewport_rect.right - 12
            if self.scenario_thumbnail:
                thumb_rect = self.scenario_thumbnail.get_rect(topright=(thumb_x, info_y))
                self.window_surface.blit(self.scenario_thumbnail, thumb_rect)
                thumb_w = thumb_rect.width + 10
            info_x = self.viewport_rect.right - (thumb_w + 220)
            entry = self.scenario_lookup.get(self.scenario_name) if hasattr(self, "scenario_lookup") else None
            scenario_title = entry.name if entry else (self.scenario_name or "Scratch workspace")
            desc = self.scenario_description or ""
            roster = ""
            if self.loaded_robots:
                roster_ids = [getattr(r, "id", "robot") for r in self.loaded_robots]
                roster = "Robots: " + ", ".join(roster_ids)
                if self.active_robot_id:
                    roster += f" (editing: {self.active_robot_id})"
            self.window_surface.blit(info_font.render(str(scenario_title), True, self.theme["text_primary"]), (info_x, info_y))
            if desc:
                self.window_surface.blit(info_font.render(desc, True, self.theme["text_muted"]), (info_x, info_y + 18))
            if roster:
                self.window_surface.blit(info_font.render(roster, True, self.theme["help_text"]), (info_x, info_y + 36))
        font = pygame.font.Font(pygame.font.get_default_font(), 16)
        mode_label = f"Mode: {self.mode}"
        selection_label = "Selection: none"
        if self.selected_point is not None:
            selection_label = f"Selection: point {self.selected_point}"
        elif self.selected_device:
            selection_label = f"Selection: {self.selected_device[1]}"
        status = f"{mode_label} | {selection_label} | Scale: {self.scale:.1f} | Offset: ({self.offset[0]:.2f},{self.offset[1]:.2f})"
        if self.body_name:
            status += f" | Body: {self.body_name}"
        if self.robot_cfg:
            status += f" | Controller: {getattr(self.robot_cfg, 'controller_module', 'controller')}"
        status += f" | Context: {self.creation_context}"
        if self.env_tool != "off":
            status += f" | Draw: {self.env_tool} ({self.env_brush_thickness:.2f}m)"
        if self.mode == "draw_shape":
            status += f" | Shape: {self.shape_tool}"
        text_surf = font.render(status, True, self.theme["text_primary"])
        self.window_surface.blit(text_surf, (20, self.window_size[1] - 42))
        hint_surf = font.render(self.status_hint, True, self.theme["help_text"])
        self.window_surface.blit(hint_surf, (20, self.window_size[1] - 22))
        # mode badge
        badge = pygame.Surface((140, 24))
        badge.fill(self.theme["badge"])
        badge.blit(font.render(self.mode, True, self.theme["badge_text"]), (8, 4))
        self.window_surface.blit(badge, (self.window_size[0] - 170, self.window_size[1] - 30))
        self.manager.draw_ui(self.window_surface)
        if self.hover_menu:
            self.hover_menu.draw(self.window_surface)
        pygame.display.update()

    def _draw_environment(self) -> None:
        rot = getattr(self, "view_rotation", 0.0)
        # Only render environment overlays on env/custom tabs
        if self.active_tab not in ("environment", "custom"):
            return
        if self.active_tab == "environment" and self.world_cfg:
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
                pygame.draw.polygon(
                    self.window_surface, darken_color(self.theme["viewport_border"], 0.15), pts, max(1, int(0.02 * self.scale))
                )
            strokes = getattr(self.world_cfg, "drawings", []) or []
            for stroke in strokes:
                if not getattr(stroke, "points", None) or len(stroke.points) < 2:
                    continue
                color = tuple(getattr(stroke, "color", self._stroke_color("mark")))
                pts = [world_to_screen(p, self.viewport_rect, self.scale, self.offset, rot) for p in stroke.points]
                width = max(1, int(max(1.0, stroke.thickness * self.scale)))
                pygame.draw.lines(self.window_surface, color, False, pts, width)
                if getattr(stroke, "kind", "mark") == "wall":
                    pygame.draw.lines(self.window_surface, darken_color(color, 0.25), False, pts, 1)
            if self.env_drawing and self.env_stroke_points:
                pts = self.env_stroke_points.copy()
                if self.hover_world:
                    pts.append(self.hover_world)
                scr = [world_to_screen(p, self.viewport_rect, self.scale, self.offset, rot) for p in pts]
                pygame.draw.lines(self.window_surface, self.theme["selection"], False, scr, max(1, int(self.env_brush_thickness * self.scale)))
            if self.bounds_mode and self.bounds_start and self.bounds_preview:
                x0, y0 = self.bounds_start
                x1, y1 = self.bounds_preview
                corners = [(x0, y0), (x0, y1), (x1, y1), (x1, y0)]
                scr = [world_to_screen(c, self.viewport_rect, self.scale, self.offset, rot) for c in corners]
                pygame.draw.polygon(self.window_surface, self.theme["selection"], scr, 1)
        if self.mode == "draw_shape" and self.shape_start and self.shape_preview:
            preview_body = self._build_shape_body(self.shape_start, self.shape_preview)
            if preview_body:
                pts = [world_to_screen(p, self.viewport_rect, self.scale, self.offset, rot) for p in preview_body.points]
                if len(pts) >= 2:
                    pygame.draw.polygon(self.window_surface, self.theme["selection"], pts, 2)
        if self.active_tab == "custom" and self.custom_active:
            body = self.custom_active.body
            pts = [world_to_screen(p, self.viewport_rect, self.scale, self.offset, rot) for p in body.points]
            if len(pts) >= 3:
                fill = self.theme.get("selection_fill", (150, 180, 240))
                pygame.draw.polygon(self.window_surface, fill, pts, 0)
                pygame.draw.polygon(self.window_surface, self.theme.get("body_outline", (60, 80, 120)), pts, 2)

    def _draw_world(self) -> None:
        assert self.sim
        # grid
        if self.grid_enabled:
            self._draw_grid()
        self._draw_environment()
        for body in self.sim.bodies.values():
            color = getattr(body.material, "custom", {}).get("color", None) or self.theme.get("selection_fill", (150, 165, 210))
            outline = self.theme.get("body_outline", darken_color(color, 0.2))
            highlight = lighten_color(color, 0.14)
            if isinstance(body.shape, Polygon):
                draw_polygon(
                    self.window_surface,
                    self.viewport_rect,
                    body.shape,
                    color,
                    self.scale,
                    self.offset,
                    outline=outline,
                    highlight=highlight,
                    outline_width=2,
                    rotation=self.view_rotation,
                    pose=body.pose,
                )
                verts = body.shape._world_vertices(body.pose)
                for idx, v in enumerate(verts):
                    p = world_to_screen(v, self.viewport_rect, self.scale, self.offset, self.view_rotation)
                    radius = 5
                    color_point = lighten_color(self.theme["body_outline"], 0.6)
                    if self.hover_point == idx:
                        color_point = lighten_color(self.theme["selection_fill"], 0.3)
                        radius = 7
                    if idx in self.selected_points or self.selected_point == idx:
                        color_point = self.theme["selection"]
                        radius = 7
                    pygame.draw.circle(self.window_surface, color_point, p, radius)
        # selection bounding box and handles
        body_cfg = self._current_body_cfg()
        if body_cfg and self.selected_points:
            bbox_local = self._selection_bbox_local(body_cfg)
            if bbox_local:
                body_pose = self._body_pose(body_cfg)
                minx, miny, maxx, maxy = bbox_local
                corners = [
                    (minx, miny),
                    (minx, maxy),
                    (maxx, maxy),
                    (maxx, miny),
                ]
                screen_pts = [world_to_screen(body_pose.transform_point(c), self.viewport_rect, self.scale, self.offset, self.view_rotation) for c in corners]
                pygame.draw.polygon(self.window_surface, self.theme["selection"], screen_pts, 1)
                handles = self._selection_handles(body_cfg)
                for rect in handles.values():
                    pygame.draw.rect(self.window_surface, self.theme["handle_fill"], rect)
                    pygame.draw.rect(self.window_surface, self.theme["handle_border"], rect, 1)
        # hovered crosshair for alignment
        if self.hover_world and self.viewport_rect.collidepoint(pygame.mouse.get_pos()):
            hx, hy = world_to_screen(self.hover_world, self.viewport_rect, self.scale, self.offset, self.view_rotation)
            pygame.draw.line(self.window_surface, self.theme["hover_cross"], (hx - 8, hy), (hx + 8, hy), 1)
            pygame.draw.line(self.window_surface, self.theme["hover_cross"], (hx, hy - 8), (hx, hy + 8), 1)
            pygame.draw.circle(self.window_surface, darken_color(self.theme["hover_cross"], 0.15), (hx, hy), 2)
        # device visualization with hover/selection cues
        for motor in self.sim.motors.values():
            parent = motor.parent
            if not parent:
                continue
            pose = parent.pose.compose(motor.mount_pose)
            start = world_to_screen((pose.x, pose.y), self.viewport_rect, self.scale, self.offset, self.view_rotation)
            length = 0.08
            dir_vec = (math.cos(pose.theta), math.sin(pose.theta))
            end = world_to_screen(
                (pose.x + dir_vec[0] * length, pose.y + dir_vec[1] * length), self.viewport_rect, self.scale, self.offset, self.view_rotation
            )
            active = self.selected_device == ("actuator", motor.name)
            hovered = self.hover_device == ("actuator", motor.name)
            base_color = self.theme["device_motor"]
            color = base_color
            if active:
                color = lighten_color(base_color, 0.35)
            elif hovered:
                color = lighten_color(base_color, 0.18)
            tire_color = darken_color(color, 0.25)
            rim_color = lighten_color(color, 0.2)
            radius_px = max(6, int(self.scale * 0.025))
            pygame.draw.circle(self.window_surface, tire_color, start, radius_px)
            pygame.draw.circle(self.window_surface, rim_color, start, radius_px, 2)
            pygame.draw.circle(self.window_surface, lighten_color(color, 0.35), start, max(3, radius_px // 2))
            # direction arrow
            pygame.draw.line(self.window_surface, color, start, end, 3 if active or hovered else 2)
            arrow_vec = pygame.math.Vector2(end[0] - start[0], end[1] - start[1])
            if arrow_vec.length() > 0:
                arrow_vec.scale_to_length(10)
                left = (end[0] - arrow_vec.x + arrow_vec.y * 0.35, end[1] - arrow_vec.y - arrow_vec.x * 0.35)
                right = (end[0] - arrow_vec.x - arrow_vec.y * 0.35, end[1] - arrow_vec.y + arrow_vec.x * 0.35)
                pygame.draw.polygon(self.window_surface, color, [end, left, right])
        for sensor in self.sim.sensors.values():
            parent = sensor.parent
            if not parent:
                continue
            spose = parent.pose.compose(sensor.mount_pose)
            base = world_to_screen((spose.x, spose.y), self.viewport_rect, self.scale, self.offset, self.view_rotation)
            active = self.selected_device == ("sensor", sensor.name)
            hovered = self.hover_device == ("sensor", sensor.name)
            color = self.theme["device_sensor"]
            if active:
                color = lighten_color(color, 0.35)
            elif hovered:
                color = lighten_color(color, 0.2)
            pygame.draw.circle(self.window_surface, darken_color(color, 0.2), base, 6 if (active or hovered) else 5)
            pygame.draw.circle(self.window_surface, color, base, 4)
            tag = getattr(sensor, "visual_tag", "")
            rng = 0.2 if tag in ("sensor.distance",) else 0.12
            dir_vec = (math.cos(spose.theta), math.sin(spose.theta))
            end = world_to_screen(
                (spose.x + dir_vec[0] * rng, spose.y + dir_vec[1] * rng), self.viewport_rect, self.scale, self.offset, self.view_rotation
            )
            pygame.draw.line(self.window_surface, color, base, end, 2)
            # intuitive glyphs per sensor type
            if tag in ("sensor.distance",):
                left_dir = pygame.math.Vector2(dir_vec).rotate(14)
                right_dir = pygame.math.Vector2(dir_vec).rotate(-14)
                left_end = world_to_screen(
                    (spose.x + left_dir.x * rng, spose.y + left_dir.y * rng), self.viewport_rect, self.scale, self.offset, self.view_rotation
                )
                right_end = world_to_screen(
                    (spose.x + right_dir.x * rng, spose.y + right_dir.y * rng), self.viewport_rect, self.scale, self.offset, self.view_rotation
                )
                cone = pygame.Surface((self.viewport_rect.width, self.viewport_rect.height), pygame.SRCALPHA)
                pygame.draw.polygon(
                    cone,
                    with_alpha(color, 70),
                    [
                        (base[0] - self.viewport_rect.x, base[1] - self.viewport_rect.y),
                        (left_end[0] - self.viewport_rect.x, left_end[1] - self.viewport_rect.y),
                        (right_end[0] - self.viewport_rect.x, right_end[1] - self.viewport_rect.y),
                    ],
                )
                self.window_surface.blit(cone, self.viewport_rect.topleft)
                pygame.draw.line(self.window_surface, color, base, left_end, 1)
                pygame.draw.line(self.window_surface, color, base, right_end, 1)
            elif tag in ("sensor.line", "sensor.line_array"):
                side = (-dir_vec[1], dir_vec[0])
                bar_half = max(3, int(self.scale * 0.01))
                offsets = getattr(sensor, "lateral_offsets", None)
                offset_list = offsets if isinstance(offsets, list) and offsets else [0.0]
                for dx in offset_list:
                    px = spose.x + dir_vec[0] * 0.02 + side[0] * dx
                    py = spose.y + dir_vec[1] * 0.02 + side[1] * dx
                    p = world_to_screen((px, py), self.viewport_rect, self.scale, self.offset, self.view_rotation)
                    pygame.draw.line(
                        self.window_surface,
                        darken_color(color, 0.1),
                        (p[0] - bar_half, p[1]),
                        (p[0] + bar_half, p[1]),
                        3,
                    )
            elif tag in ("sensor.imu", "sensor.encoder"):
                ring_r = max(6, int(self.scale * 0.018))
                pygame.draw.circle(self.window_surface, color, base, ring_r, 2)
                pygame.draw.line(self.window_surface, darken_color(color, 0.15), (base[0] - ring_r, base[1]), (base[0] + ring_r, base[1]), 1)
                pygame.draw.line(self.window_surface, darken_color(color, 0.15), (base[0], base[1] - ring_r), (base[0], base[1] + ring_r), 1)
        # ghost preview for device placement
        if self.mode == "add_device" and self.hover_world:
            pos = world_to_screen(self.hover_world, self.viewport_rect, self.scale, self.offset, self.view_rotation)
            pygame.draw.circle(self.window_surface, self.theme["selection"], pos, 7, 2)
            pygame.draw.line(self.window_surface, self.theme["selection"], (pos[0], pos[1] - 10), (pos[0], pos[1] + 10), 1)
            pygame.draw.line(self.window_surface, self.theme["selection"], (pos[0] - 10, pos[1]), (pos[0] + 10, pos[1]), 1)

    def _draw_grid(self) -> None:
        spacing = 0.1
        top_left_world = screen_to_world(self.viewport_rect.topleft, self.viewport_rect, self.scale, self.offset, self.view_rotation)
        bottom_right_world = screen_to_world(self.viewport_rect.bottomright, self.viewport_rect, self.scale, self.offset, self.view_rotation)
        min_x = int(min(top_left_world[0], bottom_right_world[0]) / spacing) - 1
        max_x = int(max(top_left_world[0], bottom_right_world[0]) / spacing) + 1
        min_y = int(min(top_left_world[1], bottom_right_world[1]) / spacing) - 1
        max_y = int(max(top_left_world[1], bottom_right_world[1]) / spacing) + 1
        for ix in range(min_x, max_x + 1):
            x_world = ix * spacing
            p1 = world_to_screen((x_world, min_y * spacing), self.viewport_rect, self.scale, self.offset, self.view_rotation)
            p2 = world_to_screen((x_world, max_y * spacing), self.viewport_rect, self.scale, self.offset, self.view_rotation)
            pygame.draw.line(self.window_surface, self.theme["grid_minor"], p1, p2, 1)
        for iy in range(min_y, max_y + 1):
            y_world = iy * spacing
            p1 = world_to_screen((min_x * spacing, y_world), self.viewport_rect, self.scale, self.offset, self.view_rotation)
            p2 = world_to_screen((max_x * spacing, y_world), self.viewport_rect, self.scale, self.offset, self.view_rotation)
            pygame.draw.line(self.window_surface, self.theme["grid_minor"], p1, p2, 1)

    def _undo(self) -> None:
        if not self.undo_stack:
            return
        prev = self.undo_stack.pop()
        if self.robot_cfg:
            self.redo_stack.append(copy.deepcopy(self.robot_cfg))
        self._restore_cfg(prev)

    def _redo(self) -> None:
        if not self.redo_stack:
            return
        nxt = self.redo_stack.pop()
        if self.robot_cfg:
            self.undo_stack.append(copy.deepcopy(self.robot_cfg))
        self._restore_cfg(nxt)


def main():
    app = DesignerApp()
    app.run()


if __name__ == "__main__":
    main()

