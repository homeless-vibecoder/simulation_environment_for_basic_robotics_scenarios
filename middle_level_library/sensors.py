"""Reference sensor implementations built on top of low-level mechanics."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, List, Optional

from low_level_mechanics.world import Pose2D, World
from low_level_mechanics.entities import SimObject

from .base import NoiseProfile, Sensor, SensorReading
from .presets import LINE_SENSOR_PRESETS, LineSensorPreset, DISTANCE_SENSOR_PRESETS, DistanceSensorPreset


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _sample_line_intensity(world: World, point: tuple[float, float]) -> float:
    for obj in world:
        intensity = obj.material_field("line_intensity", 0.0)
        if intensity <= 0.0:
            continue
        if obj.shape.contains_point(point, obj.pose):
            return intensity
    return 0.0


class LineSensor(Sensor):
    """Single reflectance-style sensor that responds to line_intensity fields."""

    def __init__(
        self,
        name: str,
        *,
        preset: str = "line_basic",
        mount_pose: Pose2D | None = None,
    ) -> None:
        preset_info = LINE_SENSOR_PRESETS[preset]
        super().__init__(
            name,
            mount_pose=mount_pose,
            update_rate_hz=preset_info.update_rate_hz,
            noise=preset_info.noise,
        )
        self.preset = preset_info

    def read(self, world: World, dt: float) -> Optional[SensorReading]:
        if not self.parent or not self.should_update(dt):
            return None
        pose = self.world_pose()
        point = (pose.x, pose.y)
        signal = _sample_line_intensity(world, point)
        normalized = _clamp(signal / self.preset.max_signal + self.noise.sample(world), 0.0, 1.0)
        reading = SensorReading(
            name=self.name,
            value=normalized,
            timestamp=world.time,
            metadata={"raw": signal, "preset": self.preset.name},
        )
        self._last_reading = reading
        return reading

    @property
    def visual_tag(self) -> str:
        return "sensor.line"

    def visual_state(self) -> Optional[dict]:
        if not self.parent:
            return None
        reading = self.last_reading.value if self.last_reading else None
        pose = self.world_pose()
        return {
            "value": reading,
            "point": (pose.x, pose.y),
        }


class LineSensorArray(Sensor):
    """Multiple line sensors arranged horizontally around the mount pose."""

    def __init__(
        self,
        name: str,
        *,
        preset: str = "line_basic",
        mount_pose: Pose2D | None = None,
    ) -> None:
        preset_info = LINE_SENSOR_PRESETS[preset]
        super().__init__(
            name,
            mount_pose=mount_pose,
            update_rate_hz=preset_info.update_rate_hz,
            noise=preset_info.noise,
        )
        self.preset = preset_info
        offsets = [
            Pose2D((i - (self.preset.count - 1) / 2) * self.preset.spacing, 0.0, 0.0)
            for i in range(self.preset.count)
        ]
        self._offsets = offsets

    def read(self, world: World, dt: float) -> Optional[SensorReading]:
        if not self.parent or not self.should_update(dt):
            return None
        points = self.sample_points_world()
        values: List[float] = []
        for point in points:
            signal = _sample_line_intensity(world, point)
            normalized = _clamp(signal / self.preset.max_signal + self.noise.sample(world), 0.0, 1.0)
            values.append(normalized)
        reading = SensorReading(
            name=self.name,
            value=values,
            timestamp=world.time,
            metadata={"count": self.preset.count, "preset": self.preset.name},
        )
        self._last_reading = reading
        return reading

    @property
    def lateral_offsets(self) -> List[float]:
        return [offset.x for offset in self._offsets]

    def sample_points_world(self) -> List[tuple[float, float]]:
        if not self.parent:
            return []
        base_pose = self.parent.pose.compose(self.mount_pose)
        points: List[tuple[float, float]] = []
        for offset in self._offsets:
            pose = base_pose.compose(offset)
            points.append((pose.x, pose.y))
        return points

    @property
    def visual_tag(self) -> str:
        return "sensor.line_array"

    def visual_state(self) -> Optional[dict]:
        if not self.parent:
            return None
        reading = self.last_reading.value if self.last_reading else [0.0 for _ in self._offsets]
        points = self.sample_points_world()
        return {
            "points": points,
            "values": reading,
        }


class DistanceSensor(Sensor):
    """Simple ray-marching distance sensor for demos."""

    def __init__(
        self,
        name: str,
        *,
        preset: str = "range_short",
        mount_pose: Pose2D | None = None,
    ) -> None:
        preset_info = DISTANCE_SENSOR_PRESETS[preset]
        super().__init__(
            name,
            mount_pose=mount_pose,
            update_rate_hz=preset_info.update_rate_hz,
            noise=preset_info.noise,
        )
        self.preset = preset_info

    def read(self, world: World, dt: float) -> Optional[SensorReading]:
        if not self.parent or not self.should_update(dt):
            return None
        pose = self.world_pose()
        direction = (math.cos(pose.theta), math.sin(pose.theta))
        hit_distance = self._ray_march(world, (pose.x, pose.y), direction)
        value = self.preset.max_range if hit_distance is None else hit_distance
        value += self.noise.sample(world)
        value = _clamp(value, 0.0, self.preset.max_range)
        reading = SensorReading(
            name=self.name,
            value=value,
            timestamp=world.time,
            metadata={"hit": hit_distance is not None, "preset": self.preset.name},
        )
        self._last_reading = reading
        return reading

    def _ray_march(
        self,
        world: World,
        origin: tuple[float, float],
        direction: tuple[float, float],
    ) -> Optional[float]:
        distance = 0.0
        while distance <= self.preset.max_range:
            sample_point = (
                origin[0] + direction[0] * distance,
                origin[1] + direction[1] * distance,
            )
            for obj in world:
                if obj.shape.contains_point(sample_point, obj.pose):
                    if obj is self.parent:
                        continue
                    return distance
            distance += self.preset.step
        return None

    @property
    def visual_tag(self) -> str:
        return "sensor.distance"

    def visual_state(self) -> Optional[dict]:
        if not self.parent:
            return None
        pose = self.world_pose()
        direction = (math.cos(pose.theta), math.sin(pose.theta))
        reading = self.last_reading
        distance = reading.value if reading else self.preset.max_range
        end = (pose.x + direction[0] * distance, pose.y + direction[1] * distance)
        hit = reading.metadata.get("hit", False) if reading else False
        return {
            "start": (pose.x, pose.y),
            "end": end,
            "distance": distance,
            "hit": hit,
        }


class IMUSensor(Sensor):
    """Reports linear/Angular velocity readings from the parent."""

    def __init__(
        self,
        name: str,
        *,
        noise: Optional[NoiseProfile] = None,
        update_rate_hz: float = 200.0,
    ) -> None:
        super().__init__(
            name,
            mount_pose=Pose2D(0.0, 0.0, 0.0),
            update_rate_hz=update_rate_hz,
            noise=noise or NoiseProfile(std_dev=0.005),
        )

    def read(self, world: World, dt: float) -> Optional[SensorReading]:
        if not self.parent or not self.should_update(dt):
            return None
        vx, vy = self.parent.state.linear_velocity
        omega = self.parent.state.angular_velocity
        noisy_vx = vx + self.noise.sample(world)
        noisy_vy = vy + self.noise.sample(world)
        noisy_omega = omega + self.noise.sample(world)
        reading = SensorReading(
            name=self.name,
            value={"lin": (noisy_vx, noisy_vy), "ang": noisy_omega},
            timestamp=world.time,
        )
        self._last_reading = reading
        return reading

    @property
    def visual_tag(self) -> str:
        return "sensor.imu"

    def visual_state(self) -> Optional[dict]:
        if not self.parent:
            return None
        reading = self.last_reading.value if self.last_reading else {"lin": (0.0, 0.0), "ang": 0.0}
        return reading


class EncoderSensor(Sensor):
    """Reports angular velocity of the parent body."""

    def __init__(
        self,
        name: str,
        *,
        noise: Optional[NoiseProfile] = None,
        update_rate_hz: float = 200.0,
    ) -> None:
        super().__init__(
            name,
            mount_pose=Pose2D(0.0, 0.0, 0.0),
            update_rate_hz=update_rate_hz,
            noise=noise or NoiseProfile(std_dev=0.001),
        )

    def read(self, world: World, dt: float) -> Optional[SensorReading]:
        if not self.parent or not self.should_update(dt):
            return None
        omega = self.parent.state.angular_velocity
        noisy_omega = omega + self.noise.sample(world)
        reading = SensorReading(
            name=self.name,
            value=noisy_omega,
            timestamp=world.time,
        )
        self._last_reading = reading
        return reading

    @property
    def visual_tag(self) -> str:
        return "sensor.encoder"

    def visual_state(self) -> Optional[dict]:
        return {"omega": self.last_reading.value if self.last_reading else 0.0}
