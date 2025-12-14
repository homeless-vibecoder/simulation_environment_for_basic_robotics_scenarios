"""Check that line and distance sensors respond to simple scenes."""
from __future__ import annotations

import sys
from pathlib import Path
import math

SIM_ENV_ROOT = Path(__file__).resolve().parents[1]
if str(SIM_ENV_ROOT) not in sys.path:
    sys.path.insert(0, str(SIM_ENV_ROOT))

from low_level_mechanics.world import World, Pose2D
from low_level_mechanics.geometry import Polygon, Circle
from low_level_mechanics.entities import SimObject
from low_level_mechanics.materials import MaterialProperties
from middle_level_library.sensors import LineSensor, DistanceSensor

WORLD_HALF_WIDTH = 1.0
WORLD_HALF_HEIGHT = 1.0
SENSOR_DT = 0.05


def create_world() -> World:
    world = World(name="sensor_test", random_seed=2, default_dt=0.02)
    line = SimObject(
        name="line",
        pose=Pose2D(0.0, 0.0, 0.0),
        shape=Polygon(
            [
                (-0.05, -0.25),
                (0.05, -0.25),
                (0.05, 0.25),
                (-0.05, 0.25),
            ]
        ),
        material=MaterialProperties(field_signals={"line_intensity": 1.0}, custom={"color": "black"}),
    )
    world.add_object(line)
    return world


def run() -> bool:
    world = create_world()
    robot = SimObject(
        name="sensor_mount",
        pose=Pose2D(0.0, 0.0, 0.0),
        shape=Circle(radius=0.05),
        material=MaterialProperties(),
    )
    world.add_object(robot)

    line_sensor = LineSensor(name="line_probe", preset="line_basic", mount_pose=Pose2D(0.0, 0.0, 0.0))
    line_sensor.attach(robot)
    reading_on_line = line_sensor.read(world, SENSOR_DT)

    robot.set_pose(Pose2D(0.3, 0.3, 0.0))
    reading_off_line = line_sensor.read(world, SENSOR_DT)

    range_sensor = DistanceSensor(name="range", preset="range_short", mount_pose=Pose2D(0.0, 0.0, 0.0))
    range_sensor.attach(robot)
    robot.set_pose(Pose2D(-0.8, 0.0, 0.0))
    range_on = range_sensor.read(world, SENSOR_DT)

    robot.set_pose(Pose2D(-0.8, 0.0, math.pi))
    range_off = range_sensor.read(world, SENSOR_DT)

    conditions = [
        reading_on_line and reading_on_line.value > 0.8,
        reading_off_line and reading_off_line.value < 0.2,
        range_on and range_on.value < 0.9,
        range_off and range_off.value > 1.0,
    ]
    passed = all(conditions)
    print(
        "Sensor test: line_on={:.2f}, line_off={:.2f}, range_hit={:.2f}, range_clear={:.2f} -> {}".format(
            reading_on_line.value if reading_on_line else -1.0,
            reading_off_line.value if reading_off_line else -1.0,
            range_on.value if range_on else -1.0,
            range_off.value if range_off else -1.0,
            "PASS" if passed else "FAIL",
        )
    )
    return passed


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
