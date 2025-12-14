# Auto-generated from controller JSON; edit via runner UI
# Controller: controller
from __future__ import annotations
from typing import Dict, Any, Iterable

class Controller:
    def __init__(self, sim):
        self.sim = sim
        self.robot_id = getattr(sim, 'robot_ids', ['robot'])[0]
    self.sim = sim
        self.base_speed = 0.45
        self.turn_gain = 1.4
        self.dampen = 0.9

    def step(self, sensors, dt: float):
       line_vals = sensors.get("line_array") or [0.0, 0.0, 0.0, 0.0, 0.0]
        if isinstance(line_vals, (int, float)):
            line_vals = [float(line_vals)]
        front = float(sensors.get("front_distance", 1.5) or 1.5)
        error = self._weighted_error(line_vals)
        if front < 0.3:
            self.base_speed = 0.25
        else:
            self.base_speed =  0.45

        turn = self.turn_gain * error
        left_cmd = self.base_speed - turn
        right_cmd = self.base_speed + turn
        self.base_speed = 0.1
        self._apply(left_cmd, right_cmd, dt)
    #    self.right_motor.command(-1, self.sim, dt)

    motor = self.sim.motors.get('left_motor')
    motor.command(-0.1, self.sim, dt)

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
            left_motor = self.sim.motors.get("left_motor")
            right_motor = self.sim.motors.get("right_motor")
            left = _clamp(left, -1.0, 1.0)
            right = _clamp(right, -1.0, 1.0)
            if left_motor:
                left_motor.command(left, self.sim, dt)
            if right_motor:
                right_motor.command(right, self.sim, dt)

    def get_state(self):
            return {"base_speed": self.base_speed}

    def set_state(self, state):
            self.base_speed = float(state.get("base_speed", self.base_speed))

