"""Manual-control variant of the line follower demo."""
from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

import pygame

from low_level_mechanics.world import World
from low_level_mechanics.visualizer import Visualizer, OverlayData, OverlaySegment

from demos.line_follower.manual_controller import ManualCommand, ManualDifferentialController
from demos.line_follower.robot import spawn_robot
from demos.line_follower.run_demo import WORLD_HALF_HEIGHT, WORLD_HALF_WIDTH, build_world


def run_manual_demo() -> None:
    world = build_world()
    _add_wall(world)
    ctx = spawn_robot()
    world.add_object(ctx.robot)

    controller = ManualDifferentialController()
    viz = Visualizer(
        window_size=(960, 660),
        pixels_per_meter=280.0,
        follow_robot=ctx.robot.name,
        rotate_with_robot=False,
    )
    viz.show_components = True
    viz.show_sensor_details = True

    def step_callback(world: World, dt: float) -> None:
        pressed = pygame.key.get_pressed()
        command = controller.command_from_keys(pressed)
        ctx.drive.command(command.left, command.right, world, dt)
        if command.hold_position:
            ctx.robot.state.linear_velocity = (0.0, 0.0)
            ctx.robot.state.angular_velocity = 0.0
        _sample_sensors(ctx, world, dt)

    def overlay_provider(world: World) -> OverlayData:
        data = OverlayData()
        _append_arena_bounds(data)
        return data

    instructions = (
        "W / Up: drive forward",
        "S / Down: reverse",
        "A / Left: turn left",
        "D / Right: turn right",
        "Ctrl: brake   Shift: boost",
        "Q/E: decrease/increase base speed",
    )

    viz.run(
        world,
        step_callback=step_callback,
        overlay_provider=overlay_provider,
        instructions=instructions,
    )


def _append_arena_bounds(data: OverlayData) -> None:
    corners = [
        (-WORLD_HALF_WIDTH, -WORLD_HALF_HEIGHT),
        (WORLD_HALF_WIDTH, -WORLD_HALF_HEIGHT),
        (WORLD_HALF_WIDTH, WORLD_HALF_HEIGHT),
        (-WORLD_HALF_WIDTH, WORLD_HALF_HEIGHT),
    ]
    for start, end in zip(corners, corners[1:] + corners[:1]):
        data.segments.append(OverlaySegment(start=start, end=end, color=(230, 230, 230)))


def _sample_sensors(ctx, world: World, dt: float) -> None:
    line_reading = ctx.line_sensor.read(world, dt)
    if line_reading:
        ctx.state["line_values"] = line_reading.value
    distance = ctx.range_sensor.read(world, dt)
    if distance:
        ctx.state["range"] = distance.value
        ctx.state["range_hit"] = distance.metadata.get("hit", False)
    ctx.imu.read(world, dt)


def _add_wall(world: World) -> None:
    from low_level_mechanics.entities import SimObject
    from low_level_mechanics.geometry import Polygon
    from low_level_mechanics.materials import MaterialProperties
    from low_level_mechanics.world import Pose2D

    wall = SimObject(
        name="test_wall",
        pose=Pose2D(0.0, 0.6, 0.0),
        shape=Polygon(
            [
                (-0.4, -0.02),
                (0.4, -0.02),
                (0.4, 0.02),
                (-0.4, 0.02),
            ]
        ),
        material=MaterialProperties(custom={"color": (200, 100, 60)}),
        metadata={"solid": True},
    )
    world.add_object(wall)


if __name__ == "__main__":
    run_manual_demo()

