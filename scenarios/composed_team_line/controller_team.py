"""Shared line-follow controller that works with prefixed multi-robot names."""
from __future__ import annotations

from typing import Any, Dict, Iterable


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


class Controller:
    def __init__(self, sim) -> None:
        self.sim = sim
        self.robot_id = getattr(self, "robot_id", None)
        self.base_speed = 0.4
        self.turn_gain = 1.3
        self.dampen = 0.85

    def step(self, sensors: Dict[str, Any], dt: float) -> None:
        line_key = self._name("line_array")
        dist_key = self._name("front_distance")
        line_vals = sensors.get(line_key) or sensors.get("line_array") or [0.0, 0.0, 0.0, 0.0, 0.0]
        if isinstance(line_vals, (int, float)):
            line_vals = [float(line_vals)]
        front = float(sensors.get(dist_key, sensors.get("front_distance", 1.5)) or 1.5)
        error = self._weighted_error(line_vals)
        if front < 0.3:
            self.base_speed = 0.22
        else:
            self.base_speed = 0.42
        turn = self.turn_gain * error
        left_cmd = self.base_speed - turn
        right_cmd = self.base_speed + turn
        self._apply(left_cmd, right_cmd, dt)

    def _weighted_error(self, readings: Iterable[float]) -> float:
        vals = list(readings)
        if not vals:
            return 0.0
        mid = (len(vals) - 1) / 2.0
        weighted_sum = 0.0
        total = 0.0
        for idx, val in enumerate(vals):
            weight = idx - mid
            weighted_sum += weight * (val - 0.5)
            total += abs(weight)
        if total == 0.0:
            return 0.0
        return _clamp(weighted_sum / total, -1.0, 1.0) * self.dampen

    def _apply(self, left: float, right: float, dt: float) -> None:
        left_motor = self.sim.motors.get(self._name("left_motor")) or self.sim.motors.get("left_motor")
        right_motor = self.sim.motors.get(self._name("right_motor")) or self.sim.motors.get("right_motor")
        left = _clamp(left, -1.0, 1.0)
        right = _clamp(right, -1.0, 1.0)
        if left_motor:
            left_motor.command(left, self.sim, dt)
        if right_motor:
            right_motor.command(right, self.sim, dt)

    def _name(self, base: str) -> str:
        return f"{self.robot_id}/{base}" if self.robot_id else base
