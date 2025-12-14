"""Lane-biased generic controller that works for multi-robot runs."""
from __future__ import annotations

from typing import Any, Dict, Iterable


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


class Controller:
    def __init__(self, sim) -> None:
        self.sim = sim
        self.robot_id = getattr(self, "robot_id", None)
        # Small bias per robot to keep them from overlapping.
        self.bias = 0.06 if (self.robot_id or "").endswith("o") else -0.06
        self.base_speed = 0.38
        self.turn_gain = 1.2

    def step(self, sensors: Dict[str, Any], dt: float) -> None:
        line_vals = sensors.get(self._name("line_array")) or sensors.get("line_array")
        error = self._weighted_error(line_vals) if line_vals is not None else 0.0
        turn = self.turn_gain * error + self.bias
        left_cmd = self.base_speed - turn
        right_cmd = self.base_speed + turn
        self._apply(left_cmd, right_cmd, dt)

    def _weighted_error(self, readings: Iterable[float]) -> float:
        vals = list(readings) if isinstance(readings, (list, tuple)) else [float(readings)]
        if not vals:
            return 0.0
        mid = (len(vals) - 1) / 2.0
        weighted_sum = 0.0
        total = 0.0
        for idx, val in enumerate(vals):
            weight = idx - mid
            weighted_sum += weight * (float(val) - 0.5)
            total += abs(weight)
        if total == 0.0:
            return 0.0
        return _clamp(weighted_sum / total, -1.0, 1.0)

    def _apply(self, left: float, right: float, dt: float) -> None:
        left_motor = self.sim.motors.get(self._name("left_motor")) or self.sim.motors.get("left_motor")
        right_motor = self.sim.motors.get(self._name("right_motor")) or self.sim.motors.get("right_motor")
        left = _clamp(left, -0.9, 0.9)
        right = _clamp(right, -0.9, 0.9)
        if left_motor:
            left_motor.command(left, self.sim, dt)
        if right_motor:
            right_motor.command(right, self.sim, dt)

    def _name(self, base: str) -> str:
        return f"{self.robot_id}/{base}" if self.robot_id else base
