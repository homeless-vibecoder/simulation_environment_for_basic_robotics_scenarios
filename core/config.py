"""Data models and JSON helpers for sim scenarios."""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, get_type_hints, get_origin, get_args

PoseTuple = Tuple[float, float, float]
Point = Tuple[float, float]
Edge = Tuple[int, int]


@dataclass
class MaterialConfig:
    color: Tuple[int, int, int] = (180, 180, 180)
    roughness: float = 0.5
    friction: float = 0.8
    traction: float | None = None
    restitution: float = 0.1
    reflect_line: float = 0.5
    reflect_distance: float = 0.5
    thickness: float = 0.02
    custom: Dict[str, object] = field(default_factory=dict)


@dataclass
class StrokeConfig:
    kind: str = "mark"  # "mark" (visual) | "wall" (collision)
    thickness: float = 0.05
    points: List[Point] = field(default_factory=list)
    color: Tuple[int, int, int] = (140, 180, 240)


@dataclass
class DesignerState:
    """Lightweight persisted UI state for the designer."""

    creation_context: str = "robot"  # robot | environment | custom
    mode: str = "select"  # select | add | delete | draw | draw_shape | add_device
    brush_kind: str = "mark"
    brush_thickness: float = 0.05
    shape_tool: str = "rect"  # rect | triangle | line


@dataclass
class EnvironmentBounds:
    min_x: float = -1.0
    min_y: float = -1.0
    max_x: float = 1.0
    max_y: float = 1.0


@dataclass
class BodyConfig:
    name: str
    points: List[Point]
    edges: List[Edge]
    pose: PoseTuple = (0.0, 0.0, 0.0)
    can_move: bool = True
    mass: float = 1.0
    inertia: float = 1.0
    material: MaterialConfig = field(default_factory=MaterialConfig)


@dataclass
class JointConfig:
    name: str
    parent: str
    child: str
    type: str = "rigid"  # rigid | hinge
    anchor_parent: Point = (0.0, 0.0)
    anchor_child: Point = (0.0, 0.0)
    lower_limit: float = 0.0
    upper_limit: float = 0.0
    stiffness: float = 1000.0
    damping: float = 10.0


@dataclass
class ActuatorConfig:
    name: str
    type: str  # "motor"
    body: str
    mount_pose: PoseTuple = (0.0, 0.0, 0.0)
    params: Dict[str, object] = field(default_factory=dict)


@dataclass
class SensorConfig:
    name: str
    type: str  # "distance" | "line" | "encoder" | "imu"
    body: str
    mount_pose: PoseTuple = (0.0, 0.0, 0.0)
    params: Dict[str, object] = field(default_factory=dict)


@dataclass
class MeasurementConfig:
    name: str
    signal: str  # e.g., "wheel_speed", "sensor.line_left"
    body: Optional[str] = None
    window: float = 5.0


@dataclass
class RobotConfig:
    spawn_pose: PoseTuple = (0.0, 0.0, 0.0)
    bodies: List[BodyConfig] = field(default_factory=list)
    joints: List[JointConfig] = field(default_factory=list)
    actuators: List[ActuatorConfig] = field(default_factory=list)
    sensors: List[SensorConfig] = field(default_factory=list)
    measurements: List[MeasurementConfig] = field(default_factory=list)
    controller_module: str = "controller"


@dataclass
class ScenarioRobotRef:
    """Descriptor entry for a robot asset used in a scenario."""

    ref: str
    id: str = "robot"
    spawn_pose: PoseTuple = (0.0, 0.0, 0.0)
    spawn_provided: bool = False
    controller: Optional[str] = None
    role: Optional[str] = None
    metadata: Dict[str, object] = field(default_factory=dict)


@dataclass
class ScenarioDescriptor:
    """Parsed scenario.json describing environment/robots and metadata."""

    id: str
    name: str
    environment: str
    robots: List[ScenarioRobotRef]
    description: Optional[str] = None
    thumbnail: Optional[str] = None
    help: Optional[str] = None
    seed: Optional[int] = None
    metadata: Dict[str, object] = field(default_factory=dict)


@dataclass
class ScenarioSummary:
    """Lightweight UI summary for a scenario listing."""

    id: str
    name: str
    description: Optional[str]
    thumbnail: Optional[Path]
    path: Path


@dataclass
class ScenarioRobot:
    """Loaded robot config plus descriptor metadata."""

    id: str
    config: RobotConfig
    spawn_pose: PoseTuple
    controller: str
    role: Optional[str] = None
    metadata: Dict[str, object] = field(default_factory=dict)
    path: Optional[Path] = None


@dataclass
class ScenarioLoadResult:
    """Result of loading a scenario descriptor and its assets."""

    descriptor: ScenarioDescriptor
    world: WorldConfig
    robots: List[ScenarioRobot]
    scenario_path: Path

    def __iter__(self):
        """Allow legacy unpacking: world_cfg, primary_robot_cfg = load_scenario(...)."""
        primary_robot_cfg = self.robots[0].config if self.robots else None
        return iter((self.world, primary_robot_cfg))

    @property
    def primary_robot(self) -> Optional[RobotConfig]:
        return self.robots[0].config if self.robots else None


@dataclass
class WorldObjectConfig:
    name: str
    body: BodyConfig


@dataclass
class CustomObjectConfig:
    """Standalone custom asset that can be placed in robot or environment."""

    name: str
    body: BodyConfig
    kind: str = "custom"
    metadata: Dict[str, object] = field(default_factory=dict)


@dataclass
class WorldConfig:
    name: str = "world"
    seed: Optional[int] = None
    gravity: Tuple[float, float] = (0.0, 0.0)
    timestep: float = 1.0 / 120.0
    terrain: List[WorldObjectConfig] = field(default_factory=list)
    metadata: Dict[str, object] = field(default_factory=dict)
    drawings: List[StrokeConfig] = field(default_factory=list)
    bounds: Optional[EnvironmentBounds] = None
    shape_objects: List[WorldObjectConfig] = field(default_factory=list)
    custom_objects: List[CustomObjectConfig] = field(default_factory=list)
    designer_state: DesignerState = field(default_factory=DesignerState)


@dataclass
class SnapshotState:
    time: float
    step: int
    bodies: Dict[str, Dict[str, object]]
    controller_state: Optional[Dict[str, object]] = None


def _dataclass_from_dict(cls, data: Dict) -> object:
    field_types = get_type_hints(cls)
    kwargs = {}
    for key, value in data.items():
        expected = field_types.get(key)
        origin = get_origin(expected)
        if origin is list:
            inner = get_args(expected)[0]
            if hasattr(inner, "__dataclass_fields__"):
                kwargs[key] = [_dataclass_from_dict(inner, v) for v in value]
                continue
        if origin is not None:
            args = [a for a in get_args(expected) if a is not type(None)]
            if len(args) == 1 and hasattr(args[0], "__dataclass_fields__"):
                if value is None:
                    kwargs[key] = None
                else:
                    kwargs[key] = _dataclass_from_dict(args[0], value)
                continue
        if hasattr(expected, "__dataclass_fields__"):
            kwargs[key] = _dataclass_from_dict(expected, value)
        else:
            kwargs[key] = value
    return cls(**kwargs)


def load_json(path: Path, cls):
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return _dataclass_from_dict(cls, data)


def save_json(path: Path, obj) -> None:
    def _encode(o):
        if hasattr(o, "__dataclass_fields__"):
            return {k: _encode(v) for k, v in asdict(o).items()}
        if isinstance(o, (list, tuple)):
            return [_encode(v) for v in o]
        if isinstance(o, dict):
            return {k: _encode(v) for k, v in o.items()}
        return o

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(_encode(obj), f, indent=2)

