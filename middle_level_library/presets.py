"""Named presets for sensors and motors to match real hardware profiles."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from low_level_mechanics.world import Pose2D

from .base import NoiseProfile


@dataclass(frozen=True)
class LineSensorPreset:
    name: str
    max_signal: float
    noise: NoiseProfile
    update_rate_hz: float
    spacing: float
    count: int


@dataclass(frozen=True)
class DistanceSensorPreset:
    name: str
    max_range: float
    step: float
    noise: NoiseProfile
    update_rate_hz: float


@dataclass(frozen=True)
class WheelMotorPreset:
    name: str
    wheel_radius: float
    max_torque: float
    gear_ratio: float
    motor_inertia: float
    response_time: float
    traction_coeff: float
    max_command: float
    mu_long: float = 0.9
    mu_lat: float = 0.8
    g_equiv: float = 9.81
    normal_force: float | None = None
    lateral_damping: float = 0.25
    wheel_count: int = 2


LINE_SENSOR_PRESETS: Dict[str, LineSensorPreset] = {
    "line_basic": LineSensorPreset(
        name="line_basic",
        max_signal=1.0,
        noise=NoiseProfile(std_dev=0.02),
        update_rate_hz=60.0,
        spacing=0.02,
        count=5,
    ),
}

DISTANCE_SENSOR_PRESETS: Dict[str, DistanceSensorPreset] = {
    "range_short": DistanceSensorPreset(
        name="range_short",
        max_range=1.5,
        step=0.01,
        noise=NoiseProfile(std_dev=0.01),
        update_rate_hz=40.0,
    ),
}

WHEEL_PRESETS: Dict[str, WheelMotorPreset] = {
    "wheel_small": WheelMotorPreset(
        name="wheel_small",
        wheel_radius=0.03,
        max_torque=0.45,
        gear_ratio=1.0,
        motor_inertia=0.002,
        response_time=0.05,
        traction_coeff=0.9,
        max_command=1.0,
        mu_long=0.9,
        mu_lat=0.8,
        g_equiv=9.81,
        normal_force=None,
        lateral_damping=0.25,
        wheel_count=2,
    ),
}
