"""Ensure components register with SimObjects and expose visual_state data."""
from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from low_level_mechanics.world import World, Pose2D
from low_level_mechanics.geometry import Circle, Polygon
from low_level_mechanics.entities import SimObject
from low_level_mechanics.materials import MaterialProperties
from middle_level_library.sensors import LineSensorArray, DistanceSensor, IMUSensor
from middle_level_library.motors import DifferentialDrive

WORLD_HALF_WIDTH = 0.6
WORLD_HALF_HEIGHT = 0.6

def _build_world() -> tuple[World, SimObject]:
    world = World(name="component_check", random_seed=7, default_dt=0.05)
    floor = SimObject(
        name="floor",
        pose=Pose2D(0.0, 0.0, 0.0),
        shape=Polygon(
            [
                (-WORLD_HALF_WIDTH, -WORLD_HALF_HEIGHT),
                (WORLD_HALF_WIDTH, -WORLD_HALF_HEIGHT),
                (WORLD_HALF_WIDTH, WORLD_HALF_HEIGHT),
                (-WORLD_HALF_WIDTH, WORLD_HALF_HEIGHT),
            ]
        ),
        material=MaterialProperties(),
    )
    world.add_object(floor)
    line = SimObject(
        name="test_line",
        pose=Pose2D(0.0, 0.0, 0.0),
        shape=Polygon(
            [
                (-0.05, -0.6),
                (0.05, -0.6),
                (0.05, 0.6),
                (-0.05, 0.6),
            ]
        ),
        material=MaterialProperties(field_signals={"line_intensity": 1.0}),
    )
    world.add_object(line)
    wall = SimObject(
        name="wall",
        pose=Pose2D(0.4, 0.0, 0.0),
        shape=Polygon(
            [
                (-0.05, -0.2),
                (0.05, -0.2),
                (0.05, 0.2),
                (-0.05, 0.2),
            ]
        ),
        material=MaterialProperties(custom={"color": (120, 120, 160)}),
    )
    world.add_object(wall)
    robot = SimObject(
        name="bot",
        pose=Pose2D(0.0, 0.0, 0.0),
        shape=Circle(radius=0.1),
        material=MaterialProperties(friction=0.6),
        can_move=True,
    )
    world.add_object(robot)
    return world, robot


def run() -> bool:
    world, robot = _build_world()
    drive = DifferentialDrive(wheel_base=0.24, max_force=3.0)
    drive.attach(robot)
    line = LineSensorArray(name="line_array", mount_pose=Pose2D(0.0, 0.0, 0.0))
    line.attach(robot)
    ranger = DistanceSensor(name="distance", mount_pose=Pose2D(0.0, 0.0, 0.0))
    ranger.attach(robot)
    imu = IMUSensor(name="imu")
    imu.attach(robot)

    expected_components = 5  # 2 motors + 3 sensors
    component_count_ok = len(robot.components) == expected_components

    dt = world.default_dt
    drive.command(0.8, -0.2, world, dt)
    line.read(world, dt)
    ranger.read(world, dt)
    imu.read(world, dt)

    line_state = line.visual_state() or {}
    distance_state = ranger.visual_state() or {}
    imu_state = imu.visual_state() or {}
    motor_state = drive.left.visual_state() or {}

    states_ok = all(
        [
            len(line_state.get("points", [])) == line.preset.count,
            len(line_state.get("values", [])) == line.preset.count,
            "start" in distance_state and "end" in distance_state,
            "lin" in imu_state and "ang" in imu_state,
            abs(motor_state.get("command", 0.0) - 0.8) < 1e-6,
        ]
    )

    passed = component_count_ok and states_ok
    print(
        "Component visual state test: components={} states={} -> {}".format(
            len(robot.components),
            "OK" if states_ok else "ERR",
            "PASS" if passed else "FAIL",
        )
    )
    return passed


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
