"""Wall-following controller for the bounded maze scenario."""
from __future__ import annotations

from typing import Dict, Any


class Controller:
    def __init__(self, sim) -> None:
        self.sim = sim
        self.base_speed = 0.55
        self.turn_gain = 0.9
        self.avoid_gain = 0.8

    def step(self, sensors: Dict[str, Any], dt: float) -> None:
        front = float(sensors.get("front_distance", 1.5) or 1.5)
        left = float(sensors.get("left_distance", 1.0) or 1.0)
        right = float(sensors.get("right_distance", 1.0) or 1.0)

        left_cmd = self.base_speed
        right_cmd = self.base_speed

        # Avoid front collisions first.
        if front < 0.35:
            left_cmd = -0.15
            right_cmd = self.base_speed + self.avoid_gain
        else:
            # Bias toward left-hand wall following.
            error = left - right
            correction = self.turn_gain * error
            left_cmd = self.base_speed + correction
            right_cmd = self.base_speed - correction

        self._apply(left_cmd, right_cmd, dt)

    def _apply(self, left: float, right: float, dt: float) -> None:
        left_motor = self.sim.motors.get("left_motor")
        right_motor = self.sim.motors.get("right_motor")
        left = max(-1.0, min(1.0, left))
        right = max(-1.0, min(1.0, right))
        if left_motor:
            left_motor.command(left, self.sim, dt)
        if right_motor:
            right_motor.command(right, self.sim, dt)

    def get_state(self):
        return {"base_speed": self.base_speed}

    def set_state(self, state):
        self.base_speed = float(state.get("base_speed", self.base_speed))