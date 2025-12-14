"""Simple wall-aware controller for the mouse maze competition."""
from __future__ import annotations

from typing import Any, Dict


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


class Controller:
    def __init__(self, sim) -> None:
        self.sim = sim
        self.robot_id = getattr(self, "robot_id", None)
        self.bias = 0.15 if self.robot_id == "red" else -0.15
        self.speed = 0.55

    def step(self, sensors: Dict[str, Any], dt: float) -> None:
        front = self._sensor("front_distance", sensors, default=1.5)
        imu = sensors.get(self._name("imu")) or sensors.get("imu") or {}
        heading = float(imu.get("yaw", 0.0)) if isinstance(imu, dict) else 0.0
        steer = 0.0
        # steer away from walls if too close
        if front < 0.25:
            steer -= 0.5
        steer += self.bias
        # light heading damp
        steer -= heading * 0.1
        left = self.speed - steer
        right = self.speed + steer
        self._apply(left, right, dt)

    def _sensor(self, base: str, sensors: Dict[str, Any], default: float) -> float:
        key = self._name(base)
        return float(sensors.get(key, sensors.get(base, default)) or default)

    def _apply(self, left: float, right: float, dt: float) -> None:
        left_motor = self.sim.motors.get(self._name("left_motor")) or self.sim.motors.get("left_motor")
        right_motor = self.sim.motors.get(self._name("right_motor")) or self.sim.motors.get("right_motor")
        left_motor and left_motor.command(_clamp(left, -1.0, 1.0), self.sim, dt)
        right_motor and right_motor.command(_clamp(right, -1.0, 1.0), self.sim, dt)

    def _name(self, base: str) -> str:
        return f"{self.robot_id}/{base}" if self.robot_id else base
