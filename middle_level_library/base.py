"""Common abstractions for sensors and motors."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import random
from typing import Any, Dict, Optional

from low_level_mechanics.world import Pose2D, World
from low_level_mechanics.entities import SimObject


@dataclass
class NoiseProfile:
    """Simple Gaussian + bias noise model."""

    bias: float = 0.0
    std_dev: float = 0.0
    seed: Optional[int] = None

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def sample(self, world: World | None = None) -> float:
        if self.std_dev == 0.0:
            return self.bias
        rng = world.rng if world is not None else self._rng
        return self.bias + rng.gauss(0.0, self.std_dev)


@dataclass
class SensorReading:
    name: str
    value: Any
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class MountedComponent:
    """Base class for things that mount onto a SimObject."""

    def __init__(self, name: str, mount_pose: Pose2D | None = None) -> None:
        self.name = name
        self.mount_pose = mount_pose or Pose2D(0.0, 0.0, 0.0)
        self.parent: Optional[SimObject] = None

    def attach(self, parent: SimObject) -> None:
        if self.parent is parent:
            return
        self.detach()
        self.parent = parent
        if hasattr(parent, "register_component"):
            parent.register_component(self)

    def detach(self) -> None:
        if self.parent and hasattr(self.parent, "unregister_component"):
            self.parent.unregister_component(self)
        self.parent = None

    def world_pose(self) -> Pose2D:
        if self.parent is None:
            return self.mount_pose
        return self.parent.pose.compose(self.mount_pose)

    @property
    def visual_tag(self) -> Optional[str]:
        return None

    def visual_state(self) -> Optional[Dict[str, Any]]:
        return None


class Sensor(MountedComponent):
    """Base sensor interface."""

    def __init__(
        self,
        name: str,
        *,
        mount_pose: Pose2D | None = None,
        update_rate_hz: float = 50.0,
        latency: float = 0.0,
        noise: Optional[NoiseProfile] = None,
    ) -> None:
        super().__init__(name, mount_pose)
        self.update_period = 1.0 / update_rate_hz if update_rate_hz > 0 else 0.0
        self.latency = latency
        self.noise = noise or NoiseProfile()
        self._time_since_update = 0.0
        self._last_reading: Optional[SensorReading] = None

    def should_update(self, dt: float) -> bool:
        if self.update_period == 0.0:
            return True
        self._time_since_update += dt
        if self._time_since_update >= self.update_period:
            self._time_since_update = 0.0
            return True
        return False

    def read(self, world: World, dt: float) -> Optional[SensorReading]:  # pragma: no cover - interface
        raise NotImplementedError

    @property
    def last_reading(self) -> Optional[SensorReading]:
        return self._last_reading


class Motor(MountedComponent):
    """Base motor/actuator interface."""

    def __init__(
        self,
        name: str,
        *,
        mount_pose: Pose2D | None = None,
        max_command: float = 1.0,
    ) -> None:
        super().__init__(name, mount_pose)
        self.max_command = max_command
        self._last_command: float = 0.0
        self.last_report = None
        self._last_report_step: Optional[int] = None

    def command(self, value: float, world: World, dt: float) -> None:
        value = max(-self.max_command, min(self.max_command, value))
        self._last_command = value
        self._apply(value, world, dt)

    def _apply(self, value: float, world: World, dt: float) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "max_command": self.max_command,
            "last_command": self._last_command,
            "mount_pose": self.mount_pose.as_dict(),
            "parent": self.parent.name if self.parent else None,
        }

    @property
    def last_command(self) -> float:
        return self._last_command
