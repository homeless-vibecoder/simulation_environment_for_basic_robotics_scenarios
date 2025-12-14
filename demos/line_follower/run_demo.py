"""Line follower demo using modular robot + controller."""
from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from low_level_mechanics.world import World, Pose2D
from low_level_mechanics.geometry import Circle, Polygon
from low_level_mechanics.entities import SimObject, DynamicState
from low_level_mechanics.materials import MaterialProperties
from low_level_mechanics.visualizer import Visualizer, OverlayData, OverlayPoint, OverlaySegment

from demos.line_follower.robot import spawn_robot
from demos.line_follower.controller import LineFollowerController

WORLD_HALF_WIDTH = 1.5
WORLD_HALF_HEIGHT = 1.0


def build_world() -> World:
    world = World(name="line_demo", random_seed=123, default_dt=0.05)
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
        material=MaterialProperties(custom={"color": (50, 70, 120)}),
    )
    world.add_object(floor)

    line_marker = SimObject(
        name="line_marker",
        pose=Pose2D(0.4, 0.0, 0.0),
        shape=Polygon(
            [
                (-0.04, -0.7),
                (0.04, -0.7),
                (0.04, 0.7),
                (-0.04, 0.7),
            ]
        ),
        material=MaterialProperties(field_signals={"line_intensity": 1.0}, custom={"color": "black"}),
    )
    world.add_object(line_marker)
    return world


def run_demo() -> None:
    world = build_world()
    ctx = spawn_robot()
    world.add_object(ctx.robot)

    controller = LineFollowerController()
    viz = Visualizer(window_size=(960, 660), pixels_per_meter=280.0, follow_robot=ctx.robot.name)
    viz.show_components = True
    viz.show_sensor_details = True

    def step_callback(world: World, dt: float) -> None:
        controller(ctx, world, dt)

    def overlay_provider(world: World) -> OverlayData:
        data = OverlayData()
        corners = [
            (-WORLD_HALF_WIDTH, -WORLD_HALF_HEIGHT),
            (WORLD_HALF_WIDTH, -WORLD_HALF_HEIGHT),
            (WORLD_HALF_WIDTH, WORLD_HALF_HEIGHT),
            (-WORLD_HALF_WIDTH, WORLD_HALF_HEIGHT),
        ]
        for start, end in zip(corners, corners[1:] + corners[:1]):
            data.segments.append(OverlaySegment(start=start, end=end, color=(230, 230, 230)))
        return data

    instructions = (
        "Edit demos/line_follower/controller.py to change behavior.",
        "Import demos.line_follower.robot.spawn_robot elsewhere for reuse.",
    )

    viz.run(world, step_callback=step_callback, overlay_provider=overlay_provider, instructions=instructions)


if __name__ == "__main__":
    run_demo()
