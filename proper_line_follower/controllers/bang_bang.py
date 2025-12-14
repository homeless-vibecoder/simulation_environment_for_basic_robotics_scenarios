"""Reference binary-sensor controller for quick experiments."""
from __future__ import annotations

from dataclasses import dataclass

from low_level_mechanics.world import World

from ..robots.library import LineFollowerRobot


@dataclass
class BinaryLineBangBangController:
    """LED-style bang-bang controller with gentler cruise and recovery search."""

    forward_speed: float = 0.16
    turn_speed: float = 0.5
    search_turn: float = 0.45
    edge_speed_scale: float = 0.45
    lost_speed_scale: float = 0.3

    def __call__(self, robot: LineFollowerRobot, world: World, dt: float) -> None:
        left_raw, right_raw = robot.read_line_bits(world, dt)
        left_bit = self._resolve_bit(robot, left_raw, "left_line")
        right_bit = self._resolve_bit(robot, right_raw, "right_line")

        speed_scale = 1.0
        turn = 0.0
        if left_bit == 1 and right_bit == 0:
            turn = self.turn_speed  # drifted left, steer counter-clockwise
            speed_scale = self.edge_speed_scale
            robot.state["last_seen_side"] = 1
        elif right_bit == 1 and left_bit == 0:
            turn = -self.turn_speed  # drifted right, steer clockwise
            speed_scale = self.edge_speed_scale
            robot.state["last_seen_side"] = -1
        elif left_bit == 1 and right_bit == 1:
            turn = 0.0  # centered on the line, keep straight
        else:
            # Lost the line: slow down and bias search towards last steering command.
            last_side = robot.state.get("last_seen_side", 1)
            turn = self.search_turn if last_side >= 0 else -self.search_turn
            speed_scale = self.lost_speed_scale

        forward = self.forward_speed * speed_scale
        robot.state["last_turn"] = turn
        left_cmd = _clamp(forward - turn)
        right_cmd = _clamp(forward + turn)
        robot.drive.command(left_cmd, right_cmd, world, dt)

    @staticmethod
    def _resolve_bit(robot: LineFollowerRobot, reading: int | None, key: str) -> int | None:
        if reading is not None:
            return reading
        return robot.state.get(key)


def _clamp(value: float, limit: float = 1.0) -> float:
    return max(-limit, min(limit, value))


__all__ = ["BinaryLineBangBangController"]

