"""Controller logic for the line follower demo."""
from __future__ import annotations

from typing import List

from low_level_mechanics.world import World

from middle_level_library.robots import RobotContext


class LineFollowerController:
    def __init__(self) -> None:
        self.base_speed = 0.05
        self.kp = 0.8

    def __call__(self, ctx: RobotContext, world: World, dt: float) -> None:
        reading = ctx.line_sensor.read(world, dt)
        if reading:
            ctx.state["line_values"] = reading.value
        distance = ctx.range_sensor.read(world, dt)
        if distance:
            ctx.state["range"] = distance.value
            ctx.state["range_hit"] = distance.metadata.get("hit", False)
        ctx.imu.read(world, dt)

        values = ctx.state.get("line_values", [0.0 for _ in ctx.line_sensor.lateral_offsets])
        error = _compute_line_error(values, ctx.line_sensor.lateral_offsets)
        correction = self.kp * error
        correction = self.base_speed
        left = _clamp(self.base_speed - correction, 0.1)
        right = _clamp(self.base_speed + correction, 0.1)
        ctx.drive.command(left, right, world, dt)


def _compute_line_error(values: List[float], offsets: List[float]) -> float:
    if not values or not offsets or len(values) != len(offsets):
        return 0.0
    weighted = sum(offset * value for offset, value in zip(offsets, values))
    total = sum(values) or 1.0
    return weighted / total


def _clamp(value: float, limit: float = 1.0) -> float:
    return max(-limit, min(limit, value))
