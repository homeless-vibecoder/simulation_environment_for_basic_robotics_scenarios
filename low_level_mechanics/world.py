"""World- and transform-level primitives for the simulation environment."""
from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Dict, Iterable, Iterator, MutableMapping, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - only for static analyzers
    from .entities import SimObject


@dataclass(frozen=True)
class Pose2D:
    """A 2D pose with translation (meters) and rotation (radians)."""

    x: float
    y: float
    theta: float = 0.0

    def translated(self, dx: float = 0.0, dy: float = 0.0) -> "Pose2D":
        return Pose2D(self.x + dx, self.y + dy, self.theta)

    def rotated(self, dtheta: float) -> "Pose2D":
        return Pose2D(self.x, self.y, self.theta + dtheta)

    def transform_point(self, point: Tuple[float, float]) -> Tuple[float, float]:
        px, py = point
        cos_t = math.cos(self.theta)
        sin_t = math.sin(self.theta)
        return (
            self.x + cos_t * px - sin_t * py,
            self.y + sin_t * px + cos_t * py,
        )

    def compose(self, other: "Pose2D") -> "Pose2D":
        tx, ty = self.transform_point((other.x, other.y))
        return Pose2D(tx, ty, self.theta + other.theta)

    def inverse(self) -> "Pose2D":
        cos_t = math.cos(self.theta)
        sin_t = math.sin(self.theta)
        ix = -self.x * cos_t - self.y * sin_t
        iy = self.x * sin_t - self.y * cos_t
        return Pose2D(ix, iy, -self.theta)

    def as_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.theta)

    def as_dict(self) -> Dict[str, float]:
        return {"x": self.x, "y": self.y, "theta": self.theta}


@dataclass(frozen=True)
class Transform2D:
    """Convenience wrapper for repeatedly applying the same transform."""

    translation: Tuple[float, float] = (0.0, 0.0)
    rotation: float = 0.0

    @classmethod
    def between(cls, a: Pose2D, b: Pose2D) -> "Transform2D":
        delta = a.inverse().compose(b)
        return cls(translation=(delta.x, delta.y), rotation=delta.theta)

    @classmethod
    def from_pose(cls, pose: Pose2D) -> "Transform2D":
        return cls(translation=(pose.x, pose.y), rotation=pose.theta)

    def apply_to_point(self, point: Tuple[float, float]) -> Tuple[float, float]:
        cos_t = math.cos(self.rotation)
        sin_t = math.sin(self.rotation)
        x, y = point
        tx, ty = self.translation
        return (
            tx + cos_t * x - sin_t * y,
            ty + sin_t * x + cos_t * y,
        )

    def apply_to_pose(self, pose: Pose2D) -> Pose2D:
        x, y = self.apply_to_point((pose.x, pose.y))
        return Pose2D(x, y, pose.theta + self.rotation)


class World:
    """Owns simulation objects and deterministic randomness."""

    def __init__(
        self,
        *,
        name: str = "world",
        random_seed: Optional[int] = None,
        default_dt: float = 0.02,
        metadata: Optional[MutableMapping[str, object]] = None,
    ) -> None:
        self.name = name
        self.default_dt = default_dt
        self._objects: Dict[str, "SimObject"] = {}
        self.time: float = 0.0
        self.step_index: int = 0
        self.random_seed = random_seed
        self._rng = random.Random(random_seed)
        self.metadata: MutableMapping[str, object] = metadata or {}

    @property
    def rng(self) -> random.Random:
        return self._rng

    def add_object(self, obj: "SimObject", *, overwrite: bool = False) -> None:
        if obj.name in self._objects and not overwrite:
            raise ValueError(f"Object '{obj.name}' already exists in world {self.name}.")
        if obj.name in self._objects and overwrite:
            self._objects[obj.name].on_removed_from_world()
        self._objects[obj.name] = obj
        obj.on_added_to_world(self)

    def remove_object(self, name: str) -> None:
        obj = self._objects.pop(name)
        obj.on_removed_from_world()

    def get_object(self, name: str) -> "SimObject":
        return self._objects[name]

    def iter_objects(self) -> Iterator["SimObject"]:
        return iter(self._objects.values())

    def step(self, dt: Optional[float] = None) -> None:
        dt = self.default_dt if dt is None else dt
        prev_poses = {name: obj.pose for name, obj in self._objects.items()}
        for obj in self._objects.values():
            obj.integrate(dt)
        self._resolve_collisions(prev_poses)
        self.time += dt
        self.step_index += 1

    def reseed(self, seed: Optional[int]) -> None:
        self.random_seed = seed
        self._rng = random.Random(seed)

    def summary(self) -> str:
        names = ", ".join(self._objects.keys()) or "<empty>"
        return f"World(name={self.name}, time={self.time:.3f}, objects=[{names}])"

    def snapshot_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "time": self.time,
            "step": self.step_index,
            "objects": [obj.as_dict() for obj in self._objects.values()],
            "metadata": dict(self.metadata),
        }

    def __len__(self) -> int:
        return len(self._objects)

    def __iter__(self) -> Iterable["SimObject"]:
        return self.iter_objects()

    # --- Collision helpers -------------------------------------------------

    def _resolve_collisions(self, prev_poses: Dict[str, Pose2D]) -> None:
        solids = [obj for obj in self._objects.values() if self._object_is_solid(obj)]
        if not solids:
            return
        for name, obj in self._objects.items():
            if not obj.can_move:
                continue
            prev_pose = prev_poses.get(name)
            if prev_pose is None:
                continue
            for solid in solids:
                if solid is obj:
                    continue
                if not obj.shape.intersects(solid.shape, obj.pose, solid.pose):
                    continue
                self._rewind_to_contact(obj, prev_pose, solid)
                obj.state.linear_velocity = (0.0, 0.0)
                obj.state.angular_velocity = 0.0
                break

    @staticmethod
    def _object_is_solid(obj: "SimObject") -> bool:
        metadata = getattr(obj, "metadata", {}) or {}
        metadata_flag = metadata.get("solid") or metadata.get("collidable")
        material = getattr(obj, "material", None)
        custom = getattr(material, "custom", {}) if material and hasattr(material, "custom") else {}
        material_flag = custom.get("solid") or custom.get("collidable")
        return bool(metadata_flag or material_flag)

    def _rewind_to_contact(self, obj: "SimObject", prev_pose: Pose2D, solid: "SimObject") -> None:
        start = prev_pose
        end = obj.pose
        if not obj.shape.intersects(solid.shape, end, solid.pose):
            return
        low = 0.0
        high = 1.0
        for _ in range(12):
            mid = 0.5 * (low + high)
            test_pose = self._lerp_pose(start, end, mid)
            if obj.shape.intersects(solid.shape, test_pose, solid.pose):
                high = mid
            else:
                low = mid
        obj.set_pose(self._lerp_pose(start, end, low))

    @staticmethod
    def _lerp_pose(start: Pose2D, end: Pose2D, alpha: float) -> Pose2D:
        alpha = max(0.0, min(1.0, alpha))
        dx = end.x - start.x
        dy = end.y - start.y
        dtheta = (end.theta - start.theta + math.pi) % (2 * math.pi) - math.pi
        return Pose2D(start.x + dx * alpha, start.y + dy * alpha, start.theta + dtheta * alpha)
