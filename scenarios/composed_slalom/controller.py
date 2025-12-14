"""Oscillating controller for slalom posts with a safety slowdown."""
from __future__ import annotations

import math
from typing import Dict, Any


class Controller:
    def __init__(self, sim) -> None:
        self.sim = sim
        self.phase = 0.0
        self.base_speed = 0.65
        self.turn_amplitude = 0.35

    def step(self, sensors: Dict[str, Any], dt: float) -> None:
        front = float(sensors.get("front_distance", 1.5) or 1.5)
        right = float(sensors.get("right_distance", 1.5) or 1.5)

        # Advance the oscillation for the slalom weave.
        self.phase += dt * 1.2
        turn = math.sin(self.phase)

        speed = self.base_speed
        if front < 0.45 or right < 0.25:
            speed = 0.35
            turn += 0.4  # nudge left when boxed in

        left_cmd = speed - self.turn_amplitude * turn
        right_cmd = speed + self.turn_amplitude * turn
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
        return {"phase": self.phase}

    def set_state(self, state):
        self.phase = float(state.get("phase", self.phase))
