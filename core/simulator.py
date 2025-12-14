"""High-level simulator with XPBD-style joints and impulse contacts."""
from __future__ import annotations

from dataclasses import dataclass
import copy
import json
import importlib
import math
import sys
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple
import random
import traceback

from low_level_mechanics.entities import DynamicState, SimObject
from low_level_mechanics.geometry import (
    Circle,
    Polygon,
    collision_manifold,
)
from low_level_mechanics.materials import MaterialProperties
from low_level_mechanics.world import Pose2D

from middle_level_library.motors import WheelMotor, WheelMotorDetailed
from middle_level_library.sensors import DistanceSensor, LineSensor, LineSensorArray, IMUSensor, EncoderSensor
from middle_level_library.base import Sensor

from .config import (
    ActuatorConfig,
    BodyConfig,
    JointConfig,
    MaterialConfig,
    RobotConfig,
    SensorConfig,
    SnapshotState,
    WorldConfig,
    Point,
    PoseTuple,
    StrokeConfig,
    EnvironmentBounds,
    ScenarioLoadResult,
    ScenarioRobot,
)
from .controller_store import ensure_compiled_controller


def _pose_from_tuple(p: PoseTuple) -> Pose2D:
    return Pose2D(p[0], p[1], p[2])


def _material_from_config(cfg) -> MaterialProperties:
    field_signals: Dict[str, float] = {}
    if getattr(cfg, "custom", None) and "line_intensity" in cfg.custom:
        field_signals["line_intensity"] = float(cfg.custom["line_intensity"])
    traction_value = getattr(cfg, "traction", None)
    if traction_value is None:
        traction_value = cfg.friction
    return MaterialProperties(
        friction=cfg.friction,
        restitution=cfg.restitution,
        reflectivity=cfg.reflect_line,
        traction=traction_value,
        field_signals=field_signals,
        custom={
            "reflect_distance": cfg.reflect_distance,
            "roughness": cfg.roughness,
            "thickness": cfg.thickness,
            "color": tuple(cfg.color),
        },
    )


@dataclass
class JointRuntime:
    cfg: JointConfig
    # XPBD params
    compliance: float = 0.0
    damping: float = 0.01
    lambda_accum: float = 0.0


class Simulator:
    """Owns world state, robot, devices, and stepping."""

    def __init__(self) -> None:
        self.world_cfg: Optional[WorldConfig] = None
        self.robot_cfg: Optional[RobotConfig] = None  # primary robot for legacy paths
        self.dt: float = 1.0 / 120.0
        self.gravity: Tuple[float, float] = (0.0, -9.81)
        self.time: float = 0.0
        self.step_index: int = 0
        self.bodies: Dict[str, SimObject] = {}
        self.joints: List[JointRuntime] = []
        self.sensors: Dict[str, Sensor] = {}
        self.motors: Dict[str, WheelMotor] = {}
        self.controller_module: Optional[object] = None  # primary controller
        self.controller_instance: Optional[object] = None  # primary controller
        self.controller_state: Optional[dict] = None
        self.controller_modules: Dict[str, object] = {}
        self.controller_instances: Dict[str, object] = {}
        self.scenario_path: Optional[Path] = None
        self._rng = random.Random()
        self.last_controller_error: Optional[str] = None
        self.last_controller_errors: Dict[str, str] = {}
        self.last_sensor_readings: Dict[str, object] = {}
        self.last_sensor_readings_by_robot: Dict[str, Dict[str, object]] = {}
        self.last_motor_commands: Dict[str, float] = {}
        self.last_motor_commands_by_robot: Dict[str, Dict[str, float]] = {}
        self.last_physics_warning: Optional[str] = None
        self.robot_ids: List[str] = []
        self.robot_roles: Dict[str, Optional[str]] = {}
        self.robot_spawn: Dict[str, PoseTuple] = {}
        self.robot_configs: Dict[str, RobotConfig] = {}
        self.sensor_owners: Dict[str, str] = {}
        self.motor_owners: Dict[str, str] = {}
        # Tunables for stability
        self.linear_damping: float = 0.995
        self.angular_damping: float = 0.995
        self.max_linear_speed: float = 15.0
        self.max_angular_speed: float = 40.0
        self.contact_correction_percent: float = 0.25
        self.contact_slop: float = 0.002
        self.max_penetration_correction: float = 0.05
        self.max_step_translation: float = 0.5
        self.debug_checks: bool = False
        # Optional per-step trace logging
        self.trace_enabled: bool = False
        self.trace_log: List[Dict[str, object]] = []
        self.trace_callback: Optional[Callable[[Dict[str, object]], None]] = None

    # --- Loading ---------------------------------------------------------
    def load(
        self,
        scenario_path: Path,
        world_cfg: WorldConfig,
        robot_cfg: Optional[RobotConfig] = None,
        *,
        robots: Optional[List[ScenarioRobot]] = None,
        spawn_overrides: Optional[Dict[str, PoseTuple]] = None,
        top_down: bool = True,
        ignore_terrain: bool = False,
    ) -> None:
        self.scenario_path = scenario_path
        self.world_cfg = world_cfg
        self.dt = world_cfg.timestep
        # Top-down view: disable gravity unless explicitly requested otherwise.
        self.gravity = (0.0, 0.0) if top_down else world_cfg.gravity
        self.time = 0.0
        self.step_index = 0
        self._rng = random.Random(world_cfg.seed)
        self.last_controller_error = None
        self.last_controller_errors = {}
        self.last_physics_warning = None
        self.bodies.clear()
        self.joints.clear()
        self.sensors.clear()
        self.motors.clear()
        self.controller_instances.clear()
        self.controller_modules.clear()
        self.robot_ids = []
        self.robot_roles = {}
        self.robot_spawn = {}
        self.robot_configs = {}
        self.sensor_owners = {}
        self.motor_owners = {}
        self.last_sensor_readings = {}
        self.last_sensor_readings_by_robot = {}
        self.last_motor_commands = {}
        self.last_motor_commands_by_robot = {}
        # Reset stability tunables per load; tighten step clamp for multi-robot to reduce tunneling and penetrations.
        self.max_step_translation = 0.5
        self.contact_correction_percent = 0.25
        # Terrain/objects
        if not ignore_terrain:
            for obj in world_cfg.terrain:
                sim_obj = self._make_body(obj.body)
                sim_obj.can_move = False
                self.bodies[obj.name] = sim_obj
        self._inject_environment(world_cfg)
        # Robot(s)
        robot_list: List[ScenarioRobot] = robots if robots is not None else []
        if not robot_list and robot_cfg is not None:
            robot_list = [
                ScenarioRobot(
                    id="robot",
                    config=robot_cfg,
                    spawn_pose=getattr(robot_cfg, "spawn_pose", (0.0, 0.0, 0.0)),
                    controller=getattr(robot_cfg, "controller_module", "controller"),
                    role=None,
                    metadata={},
                    path=None,
                )
            ]
        multi = len(robot_list) > 1
        if multi and self.max_step_translation > 0.25:
            self.max_step_translation = 0.25
        for idx, robot in enumerate(robot_list):
            robot_id = robot.id or f"robot_{idx+1}"
            spawn_pose = spawn_overrides.get(robot_id) if spawn_overrides else robot.spawn_pose
            prepared_cfg = self._prepare_robot_config(
                robot_id, robot.config, spawn_pose or robot.spawn_pose, prefix_names=multi
            )
            self.robot_ids.append(robot_id)
            self.robot_roles[robot_id] = robot.role
            self.robot_spawn[robot_id] = prepared_cfg.spawn_pose
            self.robot_configs[robot_id] = prepared_cfg
            if idx == 0:
                self.robot_cfg = prepared_cfg  # legacy primary
                self.controller_module = prepared_cfg.controller_module
                self.controller_instance = None
            # Bodies
            for body_cfg in prepared_cfg.bodies:
                sim_obj = self._make_body(body_cfg, spawn_pose=prepared_cfg.spawn_pose)
                self.bodies[body_cfg.name] = sim_obj
            # Joints
            for joint_cfg in prepared_cfg.joints:
                self.joints.append(JointRuntime(cfg=joint_cfg))
            # Devices
            for act_cfg in prepared_cfg.actuators:
                self._attach_actuator(act_cfg, robot_id)
            for sensor_cfg in prepared_cfg.sensors:
                self._attach_sensor(sensor_cfg, robot_id)
            self._load_controller_for_robot(robot_id, prepared_cfg.controller_module, scenario_path)
        if len(self.robot_spawn) > 1:
            ids = list(self.robot_spawn.items())
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    (id_a, pose_a) = ids[i]
                    (id_b, pose_b) = ids[j]
                    dist = math.hypot(pose_a[0] - pose_b[0], pose_a[1] - pose_b[1])
                    if dist < 0.05:
                        warning = f"spawn overlap between {id_a} and {id_b} (d={dist:.3f} m)"
                        self.last_physics_warning = warning
                        if self.debug_checks:
                            print(f"[sim][warn] {warning}")

    def _make_body(self, body_cfg: BodyConfig, spawn_pose: Optional[PoseTuple] = None) -> SimObject:
        points = body_cfg.points
        shape = Polygon(points)
        pose_tuple = (
            body_cfg.pose[0] + (spawn_pose[0] if spawn_pose else 0.0),
            body_cfg.pose[1] + (spawn_pose[1] if spawn_pose else 0.0),
            body_cfg.pose[2] + (spawn_pose[2] if spawn_pose else 0.0),
        )
        pose = _pose_from_tuple(pose_tuple)
        material = _material_from_config(body_cfg.material)
        state = DynamicState(mass=body_cfg.mass, moment_of_inertia=body_cfg.inertia)
        sim_obj = SimObject(
            name=body_cfg.name,
            pose=pose,
            shape=shape,
            material=material,
            can_move=body_cfg.can_move,
            dynamic_state=state,
        )
        return sim_obj

    def _attach_actuator(self, cfg: ActuatorConfig, robot_id: str) -> None:
        parent = self.bodies.get(cfg.body)
        if not parent:
            raise ValueError(f"Actuator parent body '{cfg.body}' not found")
        mount = _pose_from_tuple(cfg.mount_pose)
        params = cfg.params or {}
        # Auto-detect how many wheel motors are on this body for equal load sharing
        wheel_count = params.get("wheel_count")
        if wheel_count is None:
            wheel_count = 1 + sum(
                1
                for m in self.motors.values()
                if getattr(m, "parent", None) is parent and isinstance(m, (WheelMotor, WheelMotorDetailed))
            )
        if params.get("detailed"):
            motor = WheelMotorDetailed(
                cfg.name,
                preset=params.get("preset", "wheel_small"),
                mount_pose=mount,
            )
        else:
            material_mu = getattr(parent.material, "traction", None)
            mu_fallback = getattr(parent.material, "friction", 0.9)
            mu_long = float(params.get("mu_long", material_mu if material_mu is not None else mu_fallback))
            mu_lat = float(params.get("mu_lat", mu_fallback))
            motor = WheelMotor(
                cfg.name,
                mount_pose=mount,
                max_force=float(params.get("max_force", 2.0)),
                mu_long=mu_long,
                mu_lat=mu_lat,
                g_equiv=float(params.get("g_equiv", 9.81)),
                normal_force=float(params["normal_force"]) if "normal_force" in params else None,
                lateral_damping=float(params.get("lateral_damping", 0.25)),
                wheel_count=int(wheel_count),
                wheel_radius=float(params.get("wheel_radius", 0.03)),
                response_time=float(params.get("response_time", 0.05)),
                max_wheel_omega=float(params.get("max_wheel_omega", 40.0)),
            )
        motor.attach(parent)
        self.motors[cfg.name] = motor
        self.motor_owners[cfg.name] = robot_id

    def _attach_sensor(self, cfg: SensorConfig, robot_id: str) -> None:
        parent = self.bodies.get(cfg.body)
        if not parent:
            raise ValueError(f"Sensor parent body '{cfg.body}' not found")
        mount = _pose_from_tuple(cfg.mount_pose)
        sensor: Sensor
        if cfg.type == "distance":
            sensor = DistanceSensor(cfg.name, mount_pose=mount, preset=cfg.params.get("preset", "range_short"))
        elif cfg.type == "line":
            sensor = LineSensor(cfg.name, mount_pose=mount, preset=cfg.params.get("preset", "line_basic"))
        elif cfg.type == "line_array":
            sensor = LineSensorArray(cfg.name, mount_pose=mount, preset=cfg.params.get("preset", "line_basic"))
        elif cfg.type == "imu":
            sensor = IMUSensor(cfg.name)
        elif cfg.type == "encoder":
            sensor = EncoderSensor(cfg.name)
        else:
            raise ValueError(f"Unsupported sensor type '{cfg.type}'")
        sensor.attach(parent)
        self.sensors[cfg.name] = sensor
        self.sensor_owners[cfg.name] = robot_id

    def _load_controller_for_robot(
        self, robot_id: str, module_name: str, scenario_path: Path, keep_previous: bool = False
    ) -> None:
        controller_path, module_dir = ensure_compiled_controller(scenario_path, module_name)
        if not controller_path or not controller_path.exists():
            if not keep_previous:
                self.controller_modules.pop(robot_id, None)
                self.controller_instances.pop(robot_id, None)
                if robot_id == (self.robot_ids[0] if self.robot_ids else "robot"):
                    self.controller_module = None
                    self.controller_instance = None
            missing_name = f"{module_name}.controller.json" if (scenario_path / "controllers").exists() else f"{module_name}.py"
            self._record_controller_error(robot_id, f"Controller file not found: {missing_name}")
            return
        prev_module = self.controller_modules.get(robot_id) if keep_previous else None
        prev_instance = self.controller_instances.get(robot_id) if keep_previous else None
        sys.path.insert(0, str(module_dir))
        try:
            if module_name in sys.modules:
                del sys.modules[module_name]
            module_obj = importlib.import_module(module_name)
            self.controller_modules[robot_id] = module_obj
            RobotController = getattr(module_obj, "Controller", None)
            instance = RobotController(self) if RobotController else None
            if instance is not None and not hasattr(instance, "robot_id"):
                try:
                    setattr(instance, "robot_id", robot_id)
                except Exception:
                    pass
            self.controller_instances[robot_id] = instance
            if robot_id == (self.robot_ids[0] if self.robot_ids else "robot"):
                self.controller_module = module_obj
                self.controller_instance = instance
            self._record_controller_error(robot_id, None)
        except Exception:
            self._record_controller_error(robot_id, traceback.format_exc())
            if keep_previous:
                if prev_module is not None:
                    self.controller_modules[robot_id] = prev_module
                if prev_instance is not None:
                    self.controller_instances[robot_id] = prev_instance
                if robot_id == (self.robot_ids[0] if self.robot_ids else "robot"):
                    self.controller_module = prev_module
                    self.controller_instance = prev_instance
            else:
                self.controller_modules.pop(robot_id, None)
                self.controller_instances.pop(robot_id, None)
                if robot_id == (self.robot_ids[0] if self.robot_ids else "robot"):
                    self.controller_module = None
                    self.controller_instance = None
        finally:
            if sys.path and sys.path[0] == str(module_dir):
                sys.path.pop(0)

    def _load_controller(self, module_name: str, scenario_path: Path, keep_previous: bool = False) -> None:
        """Backward-compatible helper for single-robot callers."""
        primary_id = self.robot_ids[0] if self.robot_ids else "robot"
        self._load_controller_for_robot(primary_id, module_name, scenario_path, keep_previous=keep_previous)

    def _record_controller_error(self, robot_id: str, message: Optional[str]) -> None:
        if message:
            self.last_controller_errors[robot_id] = message
        else:
            self.last_controller_errors.pop(robot_id, None)
        self.last_controller_error = next(iter(self.last_controller_errors.values())) if self.last_controller_errors else None

    # --- Environment helpers ---------------------------------------------
    def _inject_environment(self, world_cfg: WorldConfig) -> None:
        drawings = getattr(world_cfg, "drawings", []) or []
        bounds = getattr(world_cfg, "bounds", None)
        for cfg in self._bound_body_configs(bounds):
            sim_obj = self._make_body(cfg)
            sim_obj.can_move = False
            self.bodies[cfg.name] = sim_obj
        for cfg in self._stroke_body_configs(drawings):
            sim_obj = self._make_body(cfg)
            sim_obj.can_move = False
            self.bodies[cfg.name] = sim_obj
        for obj in getattr(world_cfg, "shape_objects", []) or []:
            cfg = getattr(obj, "body", None)
            if not cfg:
                continue
            sim_obj = self._make_body(cfg)
            sim_obj.can_move = False
            self.bodies[cfg.name] = sim_obj
        for obj in getattr(world_cfg, "custom_objects", []) or []:
            cfg = getattr(obj, "body", None)
            if not cfg:
                continue
            sim_obj = self._make_body(cfg)
            sim_obj.can_move = False
            self.bodies[cfg.name] = sim_obj

    def _prepare_robot_config(
        self, robot_id: str, robot_cfg: RobotConfig, spawn_pose: PoseTuple, *, prefix_names: bool
    ) -> RobotConfig:
        cfg = copy.deepcopy(robot_cfg)
        cfg.spawn_pose = spawn_pose
        if not getattr(cfg, "controller_module", None):
            cfg.controller_module = "controller"
        if not prefix_names:
            return cfg
        prefix = f"{robot_id}/"
        body_map = {}
        for body in cfg.bodies:
            old_name = body.name
            new_name = prefix + old_name
            body_map[old_name] = new_name
            body.name = new_name
        for joint in cfg.joints:
            joint.parent = body_map.get(joint.parent, joint.parent)
            joint.child = body_map.get(joint.child, joint.child)
        for act in cfg.actuators:
            act.body = body_map.get(act.body, act.body)
            act.name = prefix + act.name
        for sensor in cfg.sensors:
            sensor.body = body_map.get(sensor.body, sensor.body)
            sensor.name = prefix + sensor.name
        for meas in cfg.measurements:
            if meas.body:
                meas.body = body_map.get(meas.body, meas.body)
            meas.name = prefix + meas.name
            # signal may reference sensor; leave unchanged unless clearly namespaced
        return cfg

    def _make_static_body_cfg(
        self, name: str, points: List[Point], color: Tuple[int, int, int] = (120, 140, 160)
    ) -> BodyConfig:
        edges = [(i, (i + 1) % len(points)) for i in range(len(points))]
        mat = MaterialConfig(
            color=color,
            friction=0.9,
            restitution=0.05,
            reflect_line=0.5,
            reflect_distance=0.5,
            roughness=0.7,
            thickness=0.04,
            custom={"color": color},
        )
        return BodyConfig(
            name=name,
            points=points,
            edges=edges,
            pose=(0.0, 0.0, 0.0),
            can_move=False,
            mass=10.0,
            inertia=10.0,
            material=mat,
        )

    def _bound_body_configs(self, bounds: Optional[EnvironmentBounds]) -> List[BodyConfig]:
        if not bounds:
            return []
        min_x, max_x = bounds.min_x, bounds.max_x
        min_y, max_y = bounds.min_y, bounds.max_y
        thickness = 0.05
        half = thickness / 2.0
        walls = [
            (
                [
                    (min_x - half, min_y - half),
                    (max_x + half, min_y - half),
                    (max_x + half, min_y + half),
                    (min_x - half, min_y + half),
                ],
                "env_bound_bottom",
            ),
            (
                [
                    (min_x - half, max_y - half),
                    (max_x + half, max_y - half),
                    (max_x + half, max_y + half),
                    (min_x - half, max_y + half),
                ],
                "env_bound_top",
            ),
            (
                [
                    (min_x - half, min_y - half),
                    (min_x + half, min_y - half),
                    (min_x + half, max_y + half),
                    (min_x - half, max_y + half),
                ],
                "env_bound_left",
            ),
            (
                [
                    (max_x - half, min_y - half),
                    (max_x + half, min_y - half),
                    (max_x + half, max_y + half),
                    (max_x - half, max_y + half),
                ],
                "env_bound_right",
            ),
        ]
        return [self._make_static_body_cfg(name, pts, color=(90, 120, 170)) for pts, name in walls]

    def _stroke_body_configs(self, drawings: Iterable[StrokeConfig]) -> List[BodyConfig]:
        configs: List[BodyConfig] = []
        seg_idx = 0
        for stroke in drawings:
            if getattr(stroke, "kind", "mark") != "wall":
                continue
            pts = list(getattr(stroke, "points", []) or [])
            if len(pts) < 2:
                continue
            thickness = max(1e-4, float(getattr(stroke, "thickness", 0.05)))
            color = tuple(getattr(stroke, "color", (160, 160, 180)))
            for i in range(len(pts) - 1):
                p0 = pts[i]
                p1 = pts[i + 1]
                dx = p1[0] - p0[0]
                dy = p1[1] - p0[1]
                seg_len = math.hypot(dx, dy)
                if seg_len < 1e-6:
                    continue
                nx = -dy / seg_len * (thickness / 2.0)
                ny = dx / seg_len * (thickness / 2.0)
                rect = [
                    (p0[0] + nx, p0[1] + ny),
                    (p1[0] + nx, p1[1] + ny),
                    (p1[0] - nx, p1[1] - ny),
                    (p0[0] - nx, p0[1] - ny),
                ]
                configs.append(self._make_static_body_cfg(f"env_wall_{seg_idx}", rect, color=color))
                seg_idx += 1
        return configs

    # --- Stepping --------------------------------------------------------
    def step(self, dt: Optional[float] = None) -> None:
        if dt is None:
            dt = self.dt
        self.last_physics_warning = None
        prev_poses = {name: body.pose for name, body in self.bodies.items()}
        # Sensors read before controller
        sensor_readings = self._update_sensors(dt)
        self.last_sensor_readings = sensor_readings
        # Controller update
        self._tick_controller(sensor_readings, dt)
        # Integrate with gravity
        self._integrate_bodies(dt)
        # Solve joints
        self._solve_joints(dt)
        # Contacts
        self._solve_contacts(dt)
        self._check_step_sanity(prev_poses, dt)
        self.last_motor_commands = {name: getattr(motor, "last_command", 0.0) for name, motor in self.motors.items()}
        motor_map: Dict[str, Dict[str, float]] = {}
        for name, cmd in self.last_motor_commands.items():
            owner = self.motor_owners.get(name)
            if owner:
                motor_map.setdefault(owner, {})[name] = cmd
        self.last_motor_commands_by_robot = motor_map
        if self.trace_enabled:
            self._record_trace(dt)
        self.time += dt
        self.step_index += 1

    def enable_trace_logging(
        self,
        enabled: bool = True,
        callback: Optional[Callable[[Dict[str, object]], None]] = None,
        *,
        clear_existing: bool = True,
    ) -> None:
        """Toggle per-step trace capture; optional callback for streaming."""
        self.trace_enabled = enabled
        self.trace_callback = callback
        if clear_existing:
            self.trace_log.clear()

    def export_trace_log(self) -> List[Dict[str, object]]:
        return list(self.trace_log)

    def clear_trace_log(self) -> None:
        self.trace_log.clear()

    def save_trace_log(self, path: Path) -> None:
        """Persist the current trace log to disk as JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.trace_log, f, indent=2)

    def _update_sensors(self, dt: float) -> Dict[str, object]:
        readings: Dict[str, object] = {}
        per_robot: Dict[str, Dict[str, object]] = {rid: {} for rid in self.robot_ids}
        for name, sensor in self.sensors.items():
            reading = sensor.read(self, dt)  # type: ignore[arg-type]
            if reading:
                readings[name] = reading.value
                owner = self.sensor_owners.get(name)
                if owner:
                    per_robot.setdefault(owner, {})[name] = reading.value
        self.last_sensor_readings_by_robot = per_robot
        return readings

    def _tick_controller(self, sensor_readings: Dict[str, object], dt: float) -> None:
        if not self.robot_ids:
            return
        for rid in self.robot_ids:
            ctrl = self.controller_instances.get(rid) if self.controller_instances else self.controller_instance
            if not ctrl:
                continue
            tick_fn = getattr(ctrl, "step", None) or getattr(ctrl, "update", None)
            if not tick_fn:
                continue
            if self.last_controller_errors.get(rid):
                continue
            per_robot_readings = self.last_sensor_readings_by_robot.get(rid, sensor_readings)
            try:
                tick_fn(per_robot_readings, dt)
            except Exception:
                self._record_controller_error(rid, traceback.format_exc())

    # --- Safety and clamping helpers ------------------------------------
    def _flag_warning(self, message: str) -> None:
        self.last_physics_warning = message
        if self.debug_checks:
            print(f"[sim][warn] {message}")

    def _sanitize_velocity(self, body: SimObject) -> None:
        vx, vy = body.state.linear_velocity
        omega = body.state.angular_velocity
        if not all(math.isfinite(v) for v in (vx, vy)):
            body.state.linear_velocity = (0.0, 0.0)
            self._flag_warning(f"{body.name}: reset invalid linear velocity")
            vx, vy = body.state.linear_velocity
        if not math.isfinite(omega):
            body.state.angular_velocity = 0.0
            self._flag_warning(f"{body.name}: reset invalid angular velocity")
            omega = 0.0
        speed = math.hypot(vx, vy)
        if self.max_linear_speed > 0.0 and speed > self.max_linear_speed:
            scale = self.max_linear_speed / max(speed, 1e-9)
            body.state.linear_velocity = (vx * scale, vy * scale)
            self._flag_warning(f"{body.name}: clamped linear speed to {self.max_linear_speed:.2f} m/s")
        if self.max_angular_speed > 0.0 and abs(omega) > self.max_angular_speed:
            body.state.angular_velocity = math.copysign(self.max_angular_speed, omega)
            self._flag_warning(f"{body.name}: clamped angular speed to {self.max_angular_speed:.2f} rad/s")

    def _sanitize_pose(self, body: SimObject) -> None:
        pose = body.pose
        if not all(math.isfinite(v) for v in (pose.x, pose.y, pose.theta)):
            body.pose = Pose2D(0.0, 0.0, 0.0)
            self._flag_warning(f"{body.name}: reset pose due to invalid values")

    def _check_step_sanity(self, prev_poses: Dict[str, Pose2D], dt: float) -> None:
        if self.max_step_translation <= 0.0:
            return
        limit = self.max_step_translation
        for name, body in self.bodies.items():
            if not body.can_move:
                continue
            prev = prev_poses.get(name)
            if not prev:
                continue
            dx = body.pose.x - prev.x
            dy = body.pose.y - prev.y
            dist = math.hypot(dx, dy)
            if not math.isfinite(dist):
                self._flag_warning(f"{name}: invalid step distance; resetting pose")
                body.pose = prev
                continue
            if dist > limit:
                self._flag_warning(f"{name}: large step {dist:.3f} m (dt={dt:.4f}) clamped")
                if dist > 1e-9:
                    scale = limit / dist
                    body.pose = Pose2D(prev.x + dx * scale, prev.y + dy * scale, body.pose.theta)
                else:
                    body.pose = prev

    def _record_trace(self, dt: float) -> None:
        entry: Dict[str, object] = {
            "step": self.step_index,
            "time": self.time,
            "dt": dt,
            "motors": {},
            "bodies": {},
        }
        robot_trace: Dict[str, Dict[str, object]] = {}
        for rid in self.robot_ids:
            robot_trace[rid] = {
                "spawn": self.robot_spawn.get(rid),
                "role": self.robot_roles.get(rid),
                "controller_error": self.last_controller_errors.get(rid),
                "motors": {},
                "sensors": self.last_sensor_readings_by_robot.get(rid, {}),
                "pose": None,
            }
        for name, motor in self.motors.items():
            report = getattr(motor, "last_report", None)
            entry["motors"][name] = {
                "command": getattr(motor, "last_command", 0.0),
                "slip_ratio": getattr(report, "slip_ratio", None) if report else None,
                "lateral_slip": getattr(report, "lateral_slip", None) if report else None,
                "wheel_speed": getattr(report, "wheel_speed", None) if report else None,
                "preferred_speed": getattr(report, "preferred_speed", None) if report else None,
                "contact_speed": getattr(report, "contact_speed", None) if report else None,
                "contact_speed_after": getattr(report, "contact_speed_after", None) if report else None,
                "applied_longitudinal_impulse": getattr(report, "applied_longitudinal_impulse", None) if report else None,
                "applied_lateral_impulse": getattr(report, "applied_lateral_impulse", None) if report else None,
                "applied_longitudinal_force": (
                    getattr(report, "applied_longitudinal_impulse", 0.0) / dt if report and dt > 0 else None
                ),
                "applied_lateral_force": (
                    getattr(report, "applied_lateral_impulse", 0.0) / dt if report and dt > 0 else None
                ),
                "normal_load": getattr(report, "normal_load", None) if report else None,
                "step": getattr(report, "step", None) if report else None,
            }
            owner = self.motor_owners.get(name)
            if owner and owner in robot_trace:
                robot_trace[owner].setdefault("motors", {})[name] = entry["motors"][name]
        for name, body in self.bodies.items():
            entry["bodies"][name] = {
                "pose": body.pose.as_dict(),
                "lin_vel": body.state.linear_velocity,
                "ang_vel": body.state.angular_velocity,
            }
        for rid, info in robot_trace.items():
            cfg = self.robot_configs.get(rid)
            if cfg and getattr(cfg, "bodies", None):
                root_name = cfg.bodies[0].name
                body = self.bodies.get(root_name)
                if body:
                    info["pose"] = body.pose.as_dict()
        entry["robots"] = robot_trace
        entry["warnings"] = {
            "physics": self.last_physics_warning,
            "controllers": dict(self.last_controller_errors),
        }
        self.trace_log.append(entry)
        if self.trace_callback:
            self.trace_callback(entry)

    def _integrate_bodies(self, dt: float) -> None:
        gx, gy = self.gravity
        for body in self.bodies.values():
            if not body.can_move or body.state.mass <= 0:
                body.clear_impulses()
                continue
            # gravity
            body.apply_force((gx * body.state.mass, gy * body.state.mass))
            # simple damping
            vx, vy = body.state.linear_velocity
            body.state.linear_velocity = (vx * self.linear_damping, vy * self.linear_damping)
            body.state.angular_velocity *= self.angular_damping
            self._sanitize_velocity(body)
            body.integrate(dt)
            self._sanitize_pose(body)

    def _solve_joints(self, dt: float) -> None:
        # Minimal XPBD distance constraint for hinge anchors (if any)
        for jr in self.joints:
            parent = self.bodies.get(jr.cfg.parent)
            child = self.bodies.get(jr.cfg.child)
            if not parent or not child or not parent.can_move and not child.can_move:
                continue
            pa = parent.pose.transform_point(jr.cfg.anchor_parent)
            pb = child.pose.transform_point(jr.cfg.anchor_child)
            dx = pb[0] - pa[0]
            dy = pb[1] - pa[1]
            dist = math.hypot(dx, dy)
            target = jr.cfg.upper_limit if jr.cfg.lower_limit == jr.cfg.upper_limit else 0.0
            error = dist - target
            if abs(error) < 1e-5:
                continue
            n = (dx / (dist + 1e-6), dy / (dist + 1e-6))
            inv_mass_a = 0.0 if not parent.can_move else 1.0 / max(parent.state.mass, 1e-6)
            inv_mass_b = 0.0 if not child.can_move else 1.0 / max(child.state.mass, 1e-6)
            w = inv_mass_a + inv_mass_b
            if w == 0:
                continue
            alpha = 1.0 / (jr.compliance + 1e-9)
            dlambda = -(error) * alpha / (w + alpha * dt * dt)
            if not math.isfinite(dlambda):
                continue
            jr.lambda_accum += dlambda
            correction = max(-self.max_penetration_correction, min(self.max_penetration_correction, dlambda))
            if parent.can_move:
                parent.pose = parent.pose.translated(-n[0] * correction * inv_mass_a, -n[1] * correction * inv_mass_a)
            if child.can_move:
                child.pose = child.pose.translated(n[0] * correction * inv_mass_b, n[1] * correction * inv_mass_b)

    def _solve_contacts(self, dt: float) -> None:
        names = list(self.bodies.keys())
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a = self.bodies[names[i]]
                b = self.bodies[names[j]]
                if not (a.can_move or b.can_move):
                    continue
                manifold = collision_manifold(a.shape, a.pose, b.shape, b.pose)
                if not manifold:
                    continue
                normal = manifold.normal
                penetration = manifold.penetration
                inv_mass_a = 0.0 if not a.can_move else 1.0 / max(a.state.mass, 1e-6)
                inv_mass_b = 0.0 if not b.can_move else 1.0 / max(b.state.mass, 1e-6)
                inv_mass_sum = inv_mass_a + inv_mass_b
                if inv_mass_sum == 0:
                    continue
                # positional correction (baumgarte-ish)
                percent = self.contact_correction_percent
                slop = self.contact_slop
                correction_mag = max(penetration - slop, 0.0) * percent / inv_mass_sum
                correction_mag = min(correction_mag, self.max_penetration_correction)
                if not math.isfinite(correction_mag):
                    continue
                correction = (normal[0] * correction_mag, normal[1] * correction_mag)
                if a.can_move:
                    a.pose = a.pose.translated(-correction[0] * inv_mass_a, -correction[1] * inv_mass_a)
                if b.can_move:
                    b.pose = b.pose.translated(correction[0] * inv_mass_b, correction[1] * inv_mass_b)
                # relative velocity
                rvx = a.state.linear_velocity[0] - b.state.linear_velocity[0]
                rvy = a.state.linear_velocity[1] - b.state.linear_velocity[1]
                vel_along_normal = rvx * normal[0] + rvy * normal[1]
                if vel_along_normal > 0 or not math.isfinite(vel_along_normal):
                    continue
                restitution = max(getattr(a.material, "restitution", 0.1), getattr(b.material, "restitution", 0.1))
                restitution = max(0.0, min(1.0, restitution))
                j = -(1 + restitution) * vel_along_normal
                j /= inv_mass_sum
                if not math.isfinite(j):
                    continue
                impulse = (j * normal[0], j * normal[1])
                if a.can_move:
                    a.state.linear_velocity = (
                        a.state.linear_velocity[0] - inv_mass_a * impulse[0],
                        a.state.linear_velocity[1] - inv_mass_a * impulse[1],
                    )
                if b.can_move:
                    b.state.linear_velocity = (
                        b.state.linear_velocity[0] + inv_mass_b * impulse[0],
                        b.state.linear_velocity[1] + inv_mass_b * impulse[1],
                    )
                # friction (Coulomb)
                rvx = a.state.linear_velocity[0] - b.state.linear_velocity[0]
                rvy = a.state.linear_velocity[1] - b.state.linear_velocity[1]
                tangent = (-normal[1], normal[0])
                vt = rvx * tangent[0] + rvy * tangent[1]
                jt = -vt / inv_mass_sum
                if not math.isfinite(jt):
                    continue
                mu = 0.5 * (getattr(a.material, "friction", 0.6) + getattr(b.material, "friction", 0.6))
                jt_limit = mu * abs(j)
                jt = max(-jt_limit, min(jt_limit, jt))
                t_impulse = (jt * tangent[0], jt * tangent[1])
                if a.can_move:
                    a.state.linear_velocity = (
                        a.state.linear_velocity[0] - inv_mass_a * t_impulse[0],
                        a.state.linear_velocity[1] - inv_mass_a * t_impulse[1],
                    )
                if b.can_move:
                    b.state.linear_velocity = (
                        b.state.linear_velocity[0] + inv_mass_b * t_impulse[0],
                        b.state.linear_velocity[1] + inv_mass_b * t_impulse[1],
                    )
                if a.can_move:
                    self._sanitize_velocity(a)
                if b.can_move:
                    self._sanitize_velocity(b)

    # --- Snapshot --------------------------------------------------------
    def snapshot(self) -> SnapshotState:
        body_state = {}
        for name, body in self.bodies.items():
            body_state[name] = {
                "pose": body.pose.as_dict(),
                "lin_vel": body.state.linear_velocity,
                "ang_vel": body.state.angular_velocity,
            }
        ctrl_state = None
        if self.controller_instance and hasattr(self.controller_instance, "get_state"):
            try:
                ctrl_state = self.controller_instance.get_state()
            except Exception:
                ctrl_state = None
        return SnapshotState(
            time=self.time,
            step=self.step_index,
            bodies=body_state,
            controller_state=ctrl_state,
        )

    def apply_snapshot(self, snap: SnapshotState) -> None:
        self.time = snap.time
        self.step_index = snap.step
        for name, s in snap.bodies.items():
            if name not in self.bodies:
                continue
            body = self.bodies[name]
            pose = s.get("pose", {})
            body.pose = Pose2D(pose.get("x", 0.0), pose.get("y", 0.0), pose.get("theta", 0.0))
            body.state.linear_velocity = tuple(s.get("lin_vel", (0.0, 0.0)))  # type: ignore
            body.state.angular_velocity = float(s.get("ang_vel", 0.0))
        if self.controller_instance and snap.controller_state and hasattr(self.controller_instance, "set_state"):
            try:
                self.controller_instance.set_state(snap.controller_state)
            except Exception:
                pass

    # --- Controller hot reload ------------------------------------------
    def reload_controller(self, robot_id: Optional[str] = None, *, keep_previous: bool = False) -> None:
        if not self.scenario_path:
            return
        targets = self.robot_ids if robot_id is None else [robot_id]
        for rid in targets:
            cfg = self.robot_configs.get(rid)
            if not cfg:
                continue
            self._load_controller_for_robot(rid, cfg.controller_module, self.scenario_path, keep_previous=keep_previous)

    def clear_controller_error(self, robot_id: Optional[str] = None) -> None:
        if robot_id is None:
            self.last_controller_errors.clear()
        else:
            self.last_controller_errors.pop(robot_id, None)
        self.last_controller_error = None if not self.last_controller_errors else next(iter(self.last_controller_errors.values()))

    # --- Robot pose helpers ----------------------------------------------
    def reposition_robot(
        self, spawn_pose: PoseTuple, zero_velocity: bool = True, set_as_spawn: bool = False, robot_id: Optional[str] = None
    ) -> None:
        """Move the selected robot bodies to a new spawn pose; optionally update default spawn."""
        rid = robot_id or (self.robot_ids[0] if self.robot_ids else None)
        if not rid:
            return
        cfg = self.robot_configs.get(rid) or self.robot_cfg
        if not cfg:
            return
        for body_cfg in cfg.bodies:
            body = self.bodies.get(body_cfg.name)
            if not body:
                continue
            pose_tuple = (
                body_cfg.pose[0] + spawn_pose[0],
                body_cfg.pose[1] + spawn_pose[1],
                body_cfg.pose[2] + spawn_pose[2],
            )
            body.pose = _pose_from_tuple(pose_tuple)
            if zero_velocity:
                body.state.linear_velocity = (0.0, 0.0)
                body.state.angular_velocity = 0.0
                body.clear_impulses()
        if set_as_spawn and cfg:
            cfg.spawn_pose = spawn_pose
        for jr in self.joints:
            jr.lambda_accum = 0.0

    def reset_to_spawn(self, robot_id: Optional[str] = None) -> None:
        """Return robot to the configured spawn pose and clear velocities."""
        rid = robot_id or (self.robot_ids[0] if self.robot_ids else None)
        cfg = self.robot_configs.get(rid) if rid else self.robot_cfg
        if not cfg:
            return
        self.reposition_robot(cfg.spawn_pose, zero_velocity=True, set_as_spawn=False, robot_id=rid)

    # --- Helpers for sensors expecting a world-like interface -----------
    def __iter__(self) -> Iterable[SimObject]:
        return iter(self.bodies.values())

    @property
    def rng(self) -> random.Random:
        return self._rng


