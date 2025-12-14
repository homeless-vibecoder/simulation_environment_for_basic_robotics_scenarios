"""Batch evaluation harness for line-follower controllers."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SIM_ROOT = Path(__file__).resolve().parents[2]
for root in (PROJECT_ROOT, SIM_ROOT):
    root_str = str(root)
    if root_str not in sys.path:  # pragma: no cover - path wiring
        sys.path.insert(0, root_str)

from proper_line_follower import (
    BinaryLineBangBangController,
    LineFollowerRobot,
    create_robot,
    create_track_world,
    list_robot_presets,
    list_track_presets,
    default_track_entry_pose,
)


@dataclass(frozen=True)
class Scenario:
    track: str
    robot: str
    duration: float = 25.0


def user_controller_factory() -> Callable[[LineFollowerRobot, object, float], None]:
    """Edit this function to plug in your own controller."""
    return BinaryLineBangBangController()


def main() -> None:
    scenarios = _default_scenarios()
    results = []
    for scenario in scenarios:
        print(f"Running {scenario.track} / {scenario.robot} ...")
        score = _run_scenario(scenario, user_controller_factory())
        results.append((scenario, score))
    _print_summary(results)


def _run_scenario(scenario: Scenario, controller: Callable[[LineFollowerRobot, object, float], None]) -> dict:
    world, spec = create_track_world(scenario.track)
    start_pose = default_track_entry_pose(spec)
    robot = create_robot(scenario.robot, name=f"{scenario.robot}_{scenario.track}", pose=start_pose)
    world.add_object(robot.robot)
    dt = world.default_dt
    steps = int(scenario.duration / dt)
    lost_steps = 0
    for _ in range(steps):
        controller(robot, world, dt)
        bits = robot.read_line_bits(world, dt)
        if bits == (0, 0) or bits == (None, None):
            lost_steps += 1
        robot.distance_sensor.read(world, dt)
        robot.imu.read(world, dt)
        world.step(dt)
    adherence = 1.0 - (lost_steps / max(1, steps))
    return {
        "adherence": round(adherence, 3),
        "lost_steps": lost_steps,
        "total_steps": steps,
    }


def _default_scenarios() -> Sequence[Scenario]:
    presets = list(zip(list_track_presets(), list_robot_presets()))
    if not presets:
        return [Scenario(track="oval_loop", robot="edge_dual")]
    scenarios: List[Scenario] = []
    for track_name in list_track_presets():
        for robot_name in list_robot_presets():
            scenarios.append(Scenario(track=track_name, robot=robot_name, duration=20.0))
    return scenarios[:6]  # keep it short by default


def _print_summary(results: Iterable[tuple[Scenario, dict]]) -> None:
    print("\nEvaluation summary:")
    for scenario, metrics in results:
        print(
            f"- {scenario.track:>10s} / {scenario.robot:<12s} "
            f"adherence={metrics['adherence']:.2f} "
            f"(lost {metrics['lost_steps']} of {metrics['total_steps']} steps)"
        )


if __name__ == "__main__":
    main()

