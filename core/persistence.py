"""File I/O helpers for scenarios and snapshots."""
from __future__ import annotations

from pathlib import Path
import json
from typing import Dict, Tuple, List, Optional

from .config import (
    EnvironmentBounds,
    WorldConfig,
    RobotConfig,
    SnapshotState,
    BodyConfig,
    WorldObjectConfig,
    CustomObjectConfig,
    DesignerState,
    ScenarioDescriptor,
    ScenarioRobotRef,
    ScenarioRobot,
    ScenarioLoadResult,
    ScenarioSummary,
    load_json,
    save_json,
)


def _resolve_asset(base: Path, ref: str) -> Path:
    """Resolve an asset reference relative to the scenario folder or repository root."""
    if not ref:
        return base
    ref_path = Path(ref)
    if ref_path.is_absolute():
        return ref_path
    # First try relative to scenario directory
    candidate = (base / ref_path).resolve()
    if candidate.exists():
        return candidate
    # Then try relative to repo root (scenario_dir/..)
    repo_root = base.parent
    candidate = (repo_root / ref_path).resolve()
    if candidate.exists():
        return candidate
    # Fall back to original reference (may raise later)
    return ref_path.resolve()


def _coerce_pose(value) -> Tuple[float, float, float]:
    if not value:
        return (0.0, 0.0, 0.0)
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return (float(value[0]), float(value[1]), float(value[2]))
    raise ValueError(f"spawn_pose must be length-3 sequence, got {value}")


def _parse_robot_refs(data: dict, default_robot_ref: Optional[str]) -> List[ScenarioRobotRef]:
    robots_raw = data.get("robots") or []
    refs: List[ScenarioRobotRef] = []
    if robots_raw:
        for idx, entry in enumerate(robots_raw):
            ref = entry.get("ref") or entry.get("robot")
            if not ref:
                continue
            ident = entry.get("id") or entry.get("name") or f"robot_{idx+1}"
            spawn_provided = False
            spawn_val = None
            for key in ("spawn_pose", "spawn", "pose"):
                if key in entry:
                    spawn_provided = True
                    spawn_val = entry.get(key)
                    break
            spawn = _coerce_pose(spawn_val) if spawn_provided else (0.0, 0.0, 0.0)
            refs.append(
                ScenarioRobotRef(
                    ref=ref,
                    id=ident,
                    spawn_pose=spawn,
                    spawn_provided=spawn_provided,
                    controller=entry.get("controller"),
                    role=entry.get("role"),
                    metadata=dict(entry.get("metadata") or {}),
                )
            )
    elif default_robot_ref:
        refs.append(
            ScenarioRobotRef(
                ref=default_robot_ref,
                id="robot",
                spawn_pose=(0.0, 0.0, 0.0),
                spawn_provided=False,
                controller=data.get("controller"),
                role=None,
                metadata={},
            )
        )
    return refs


def load_scenario_descriptor(path: Path) -> ScenarioDescriptor:
    """Read scenario.json if present; otherwise synthesize a descriptor for legacy pairs."""
    descriptor_path = path / "scenario.json"
    if descriptor_path.exists():
        with descriptor_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        env_ref = data.get("environment") or data.get("env")
        robot_ref = data.get("robot")
        if not env_ref:
            raise ValueError(f"scenario.json missing 'environment': {descriptor_path}")
        robots = _parse_robot_refs(data, robot_ref)
        if not robots:
            raise ValueError(f"scenario.json missing 'robot' or 'robots' entries: {descriptor_path}")
        ident = data.get("id") or path.name
        name = data.get("name") or ident
        return ScenarioDescriptor(
            id=str(ident),
            name=str(name),
            environment=str(env_ref),
            robots=robots,
            description=data.get("description"),
            thumbnail=data.get("thumbnail"),
            help=data.get("help"),
            seed=data.get("seed"),
            metadata=dict(data.get("metadata") or {}),
        )

    # Legacy world/robot pair fallback
    world_file = path / "world.json"
    robot_file = path / "robot.json"
    if not (world_file.exists() and robot_file.exists()):
        raise FileNotFoundError(f"No scenario.json or world/robot pair found under {path}")
    ident = path.name
    robot_ref = robot_file.name
    robots = _parse_robot_refs({"controller": None}, robot_ref)
    return ScenarioDescriptor(
        id=str(ident),
        name=str(ident),
        environment=world_file.name,
        robots=robots,
        description=None,
        thumbnail=None,
        help=None,
        seed=None,
        metadata={},
    )


def load_scenario_summary(path: Path) -> dict:
    """Return lightweight descriptor info for UI listing."""
    desc = load_scenario_descriptor(path)
    thumb_path = None
    if desc.thumbnail:
        resolved = _resolve_asset(path, desc.thumbnail)
        if resolved.exists():
            thumb_path = resolved
    return ScenarioSummary(
        id=desc.id,
        name=desc.name,
        description=desc.description,
        thumbnail=thumb_path,
        path=path,
    )


def list_environment_assets(base: Path) -> List[Path]:
    """List available environment JSON assets under assets/environments."""
    env_dir = base / "assets" / "environments"
    if not env_dir.exists():
        return []
    return sorted(p for p in env_dir.glob("*.json") if p.is_file())


def list_robot_assets(base: Path) -> List[Path]:
    """List available robot JSON assets under assets/robots."""
    robot_dir = base / "assets" / "robots"
    if not robot_dir.exists():
        return []
    return sorted(p for p in robot_dir.glob("*.json") if p.is_file())


def list_scenario_summaries(base: Path) -> List[ScenarioSummary]:
    """Return shallow summaries for all detectable scenarios under a folder."""
    if not base.exists():
        return []
    summaries: List[ScenarioSummary] = []
    for entry in base.iterdir():
        if not entry.is_dir():
            continue
        has_pair = (entry / "world.json").exists() and (entry / "robot.json").exists()
        has_descriptor = (entry / "scenario.json").exists()
        if not (has_pair or has_descriptor):
            continue
        try:
            summaries.append(load_scenario_summary(entry))
        except Exception:
            continue
    return sorted(summaries, key=lambda s: s.id)


def load_scenario(path: Path, *, spawn_overrides: Optional[Dict[str, Tuple[float, float, float]]] = None) -> ScenarioLoadResult:
    """Load a scenario descriptor plus its environment/robots."""
    descriptor = load_scenario_descriptor(path)
    env_path = _resolve_asset(path, descriptor.environment)
    world_cfg = load_environment_design(env_path)
    if descriptor.seed is not None and getattr(world_cfg, "seed", None) is None:
        world_cfg.seed = descriptor.seed
    robots: List[ScenarioRobot] = []
    for idx, ref in enumerate(descriptor.robots):
        robot_path = _resolve_asset(path, ref.ref)
        robot_cfg = load_robot_design(robot_path)
        override_pose = spawn_overrides.get(ref.id) if spawn_overrides else None
        if override_pose is not None:
            spawn_pose = _coerce_pose(override_pose)
        elif getattr(ref, "spawn_provided", False):
            spawn_pose = _coerce_pose(getattr(ref, "spawn_pose", (0.0, 0.0, 0.0)))
        else:
            # Fall back to the robot asset's own spawn if the descriptor omitted one.
            spawn_pose = _coerce_pose(getattr(robot_cfg, "spawn_pose", (0.0, 0.0, 0.0)))
        robot_cfg.spawn_pose = spawn_pose
        controller_module = ref.controller or getattr(robot_cfg, "controller_module", None) or "controller"
        robot_cfg.controller_module = controller_module
        _normalize_robot(robot_cfg)
        robots.append(
            ScenarioRobot(
                id=ref.id or f"robot_{idx+1}",
                config=robot_cfg,
                spawn_pose=spawn_pose,
                controller=controller_module,
                role=ref.role,
                metadata=ref.metadata,
                path=robot_path,
            )
        )
    if not robots:
        # Should not happen, but guard for safety
        robot_cfg = load_robot_design(path / "robot.json")
        _normalize_robot(robot_cfg)
        robots.append(
            ScenarioRobot(
                id="robot",
                config=robot_cfg,
                spawn_pose=robot_cfg.spawn_pose,
                controller=robot_cfg.controller_module,
                role=None,
                metadata={},
                path=path / "robot.json",
            )
        )
    return ScenarioLoadResult(descriptor=descriptor, world=world_cfg, robots=robots, scenario_path=path)


def save_scenario(path: Path, world_cfg: WorldConfig, robot_cfg: RobotConfig) -> None:
    _normalize_world(world_cfg)
    _normalize_robot(robot_cfg)
    save_json(path / "world.json", world_cfg)
    save_json(path / "robot.json", robot_cfg)


def save_snapshot(path: Path, snap: SnapshotState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "time": snap.time,
                "step": snap.step,
                "bodies": snap.bodies,
                "controller_state": snap.controller_state,
            },
            f,
            indent=2,
        )


def load_snapshot(path: Path) -> SnapshotState:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return SnapshotState(
        time=data.get("time", 0.0),
        step=data.get("step", 0),
        bodies=data.get("bodies", {}),
        controller_state=data.get("controller_state"),
    )


def _normalize_world(world_cfg: WorldConfig) -> None:
    """Ensure world config fields stay deterministic when saving."""
    # Normalize bounds ordering
    if getattr(world_cfg, "bounds", None):
        b = world_cfg.bounds
        assert b
        min_x = min(b.min_x, b.max_x)
        max_x = max(b.min_x, b.max_x)
        min_y = min(b.min_y, b.max_y)
        max_y = max(b.min_y, b.max_y)
        world_cfg.bounds = EnvironmentBounds(min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y)
    # Normalize drawings (sort + clamp small negative thickness)
    drawings = getattr(world_cfg, "drawings", []) or []
    normalized = []
    for d in drawings:
        pts = [(float(p[0]), float(p[1])) for p in d.points]
        normalized.append(
            type(d)(
                kind=str(getattr(d, "kind", "mark")),
                thickness=max(1e-4, float(getattr(d, "thickness", 0.05))),
                points=pts,
                color=tuple(getattr(d, "color", (140, 180, 240))),
            )
        )
    world_cfg.drawings = sorted(
        normalized,
        key=lambda s: (
            s.kind,
            round(s.thickness, 6),
            len(s.points),
            [(round(p[0], 6), round(p[1], 6)) for p in s.points],
        ),
    )
    # Normalize shape objects (static or decorative geometry)
    shape_objects = getattr(world_cfg, "shape_objects", []) or []
    norm_shapes: list[WorldObjectConfig] = []
    for obj in shape_objects:
        body = getattr(obj, "body", None)
        if not body:
            continue
        pts = [(float(p[0]), float(p[1])) for p in body.points]
        edges = [(int(a), int(b)) for a, b in body.edges]
        norm_body = BodyConfig(
            name=str(body.name),
            points=pts,
            edges=edges,
            pose=tuple(float(v) for v in body.pose),
            can_move=bool(getattr(body, "can_move", False)),
            mass=float(getattr(body, "mass", 1.0)),
            inertia=float(getattr(body, "inertia", 1.0)),
            material=body.material,  # already dataclass
        )
        norm_shapes.append(WorldObjectConfig(name=str(obj.name), body=norm_body))
    world_cfg.shape_objects = sorted(norm_shapes, key=lambda o: o.name)
    # Normalize custom objects (metadata + geometry)
    custom_objects = getattr(world_cfg, "custom_objects", []) or []
    norm_customs: list[CustomObjectConfig] = []
    for obj in custom_objects:
        body = getattr(obj, "body", None)
        if not body:
            continue
        pts = [(float(p[0]), float(p[1])) for p in body.points]
        edges = [(int(a), int(b)) for a, b in body.edges]
        norm_body = BodyConfig(
            name=str(body.name),
            points=pts,
            edges=edges,
            pose=tuple(float(v) for v in body.pose),
            can_move=bool(getattr(body, "can_move", False)),
            mass=float(getattr(body, "mass", 1.0)),
            inertia=float(getattr(body, "inertia", 1.0)),
            material=body.material,
        )
        norm_customs.append(
            CustomObjectConfig(
                name=str(getattr(obj, "name", body.name)),
                body=norm_body,
                kind=str(getattr(obj, "kind", "custom")),
                metadata=dict(getattr(obj, "metadata", {}) or {}),
            )
        )
    world_cfg.custom_objects = sorted(norm_customs, key=lambda o: o.name)
    # Normalize designer state to keep numeric values stable
    ds = getattr(world_cfg, "designer_state", None) or DesignerState()
    ds.brush_thickness = max(1e-4, float(getattr(ds, "brush_thickness", 0.05)))
    if getattr(ds, "brush_kind", "") not in ("mark", "wall"):
        ds.brush_kind = "mark"
    if getattr(ds, "shape_tool", "") not in ("rect", "triangle", "line"):
        ds.shape_tool = "rect"
    if getattr(ds, "creation_context", "") not in ("robot", "environment", "custom"):
        ds.creation_context = "robot"
    world_cfg.designer_state = ds


def _normalize_robot(robot_cfg: RobotConfig) -> None:
    """Keep device ordering stable for deterministic saves."""
    # Ensure at least one body exists to avoid downstream None crashes.
    if not getattr(robot_cfg, "bodies", None):
        robot_cfg.bodies = [
            BodyConfig(
                name="body",
                points=[(0.1, -0.06), (0.1, 0.06), (-0.08, 0.06), (-0.08, -0.06)],
                edges=[(0, 1), (1, 2), (2, 3), (3, 0)],
                pose=(0.0, 0.0, 0.0),
                can_move=True,
            )
        ]
    robot_cfg.actuators = sorted(robot_cfg.actuators, key=lambda a: a.name)
    robot_cfg.sensors = sorted(robot_cfg.sensors, key=lambda s: s.name)
    robot_cfg.bodies = sorted(robot_cfg.bodies, key=lambda b: b.name)


# --- Design helpers (robot/env/custom) ---------------------------------------
def save_robot_design(path: Path, robot_cfg: RobotConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _normalize_robot(robot_cfg)
    save_json(path, robot_cfg)


def load_robot_design(path: Path) -> RobotConfig:
    robot = load_json(path, RobotConfig)
    _normalize_robot(robot)
    return robot


def save_environment_design(path: Path, world_cfg: WorldConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _normalize_world(world_cfg)
    save_json(path, world_cfg)


def load_environment_design(path: Path) -> WorldConfig:
    return load_json(path, WorldConfig)


def save_custom_asset(path: Path, asset: CustomObjectConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    save_json(path, asset)


def load_custom_asset(path: Path) -> CustomObjectConfig:
    return load_json(path, CustomObjectConfig)

