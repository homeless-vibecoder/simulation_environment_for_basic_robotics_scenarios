"""Entities tie geometry, materials, and motion together."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple, TYPE_CHECKING

from .geometry import BoundingBox, Shape2D
from .materials import MaterialProperties
from .world import Pose2D

if TYPE_CHECKING:  # pragma: no cover
    from .world import World

@dataclass
class DynamicState:
    """Minimal kinematic state for moving objects."""

    linear_velocity: Tuple[float, float] = (0.0, 0.0)
    angular_velocity: float = 0.0
    mass: float = 1.0
    moment_of_inertia: float = 1.0

    def advance_pose(self, pose: Pose2D, dt: float) -> Pose2D:
        vx, vy = self.linear_velocity
        new_pose = pose.translated(vx * dt, vy * dt)
        if self.angular_velocity:
            new_pose = new_pose.rotated(self.angular_velocity * dt)
        return new_pose


class SimObject:
    """Physical or logical object placed into the world."""

    def __init__(
        self,
        *,
        name: str,
        pose: Pose2D,
        shape: Shape2D,
        material: Optional[MaterialProperties] = None,
        can_move: bool = False,
        dynamic_state: Optional[DynamicState] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.name = name
        self.pose = pose
        self.shape = shape
        self.material = material or MaterialProperties()
        self.can_move = can_move
        self.state = dynamic_state or DynamicState()
        self.metadata: Dict[str, Any] = metadata or {}
        self.world: Optional["World"] = None
        self._pending_forces: List[Tuple[float, float]] = []
        self._pending_torque: float = 0.0
        self._components: List[Any] = []

    def on_added_to_world(self, world: Any) -> None:
        self.world = world

    def on_removed_from_world(self) -> None:
        self.world = None
        self._pending_forces.clear()
        self._pending_torque = 0.0
        for component in tuple(self._components):
            detach = getattr(component, "detach", None)
            if callable(detach):
                detach()

    def set_pose(self, pose: Pose2D) -> None:
        self.pose = pose

    def apply_force(
        self,
        force: Tuple[float, float],
        *,
        application_point: Optional[Tuple[float, float]] = None,
    ) -> None:
        """Apply a force, optionally at an offset to induce torque."""
        self._pending_forces.append(force)
        if application_point is not None:
            cx, cy = self.pose.x, self.pose.y
            rx = application_point[0] - cx
            ry = application_point[1] - cy
            torque = rx * force[1] - ry * force[0]
            self._pending_torque += torque

    def apply_torque(self, torque: float) -> None:
        self._pending_torque += torque

    def clear_impulses(self) -> None:
        self._pending_forces.clear()
        self._pending_torque = 0.0

    def integrate(self, dt: float) -> None:
        if not self.can_move:
            self.clear_impulses()
            return
        fx = sum(f[0] for f in self._pending_forces)
        fy = sum(f[1] for f in self._pending_forces)
        vx, vy = self.state.linear_velocity
        if self.state.mass > 0:
            vx += (fx / self.state.mass) * dt
            vy += (fy / self.state.mass) * dt
        self.state.linear_velocity = (vx, vy)
        if self.state.moment_of_inertia > 0:
            self.state.angular_velocity += (self._pending_torque / self.state.moment_of_inertia) * dt
        self.pose = self.state.advance_pose(self.pose, dt)
        self.clear_impulses()

    def register_component(self, component: Any) -> None:
        if component not in self._components:
            self._components.append(component)

    def unregister_component(self, component: Any) -> None:
        if component in self._components:
            self._components.remove(component)

    def iter_components(self) -> Iterable[Any]:
        return iter(self._components)

    @property
    def components(self) -> Tuple[Any, ...]:
        return tuple(self._components)

    def bounding_box(self) -> BoundingBox:
        return self.shape.bounding_box(self.pose)

    def overlaps_with(self, other: "SimObject") -> bool:
        return self.shape.intersects(other.shape, self.pose, other.pose)

    def material_field(self, field_name: str, default: float = 0.0) -> float:
        return self.material.field_value(field_name, default)

    def as_dict(self) -> Dict[str, Any]:
        bbox = self.bounding_box()
        return {
            "name": self.name,
            "pose": self.pose.as_dict(),
            "shape": type(self.shape).__name__,
            "material": self.material.as_dict(),
            "can_move": self.can_move,
            "state": {
                "linear_velocity": self.state.linear_velocity,
                "angular_velocity": self.state.angular_velocity,
            },
            "bbox": {
                "min_x": bbox.min_x,
                "min_y": bbox.min_y,
                "max_x": bbox.max_x,
                "max_y": bbox.max_y,
            },
            "metadata": dict(self.metadata),
        }


__all__ = ["SimObject", "DynamicState"]
