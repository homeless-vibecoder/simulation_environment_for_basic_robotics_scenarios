"""Template autonomous demo for proper line follower robots."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SIM_ROOT = Path(__file__).resolve().parents[2]
for root in (PROJECT_ROOT, SIM_ROOT):
    root_str = str(root)
    if root_str not in sys.path:  # pragma: no cover - path wiring
        sys.path.insert(0, root_str)

from low_level_mechanics.world import World
from low_level_mechanics.visualizer import OverlayData, OverlaySegment, Visualizer

from proper_line_follower import (
    BinaryLineBangBangController,
    create_robot,
    create_track_world,
    default_track_entry_pose,
)

TRACK_NAME = "chicane_loop"
ROBOT_PRESET = "forward_probe"


def main() -> None:
    world, spec = create_track_world(TRACK_NAME)
    start_pose = default_track_entry_pose(spec)
    robot = create_robot(ROBOT_PRESET, name="auto_bot", pose=start_pose)
    world.add_object(robot.robot)

    controller = BinaryLineBangBangController()
    viz = Visualizer(
        window_size=(1080, 720),
        pixels_per_meter=320.0,
        follow_robot=robot.robot.name,
        rotate_with_robot=False,
    )
    viz.show_components = True
    viz.show_sensor_details = True
    viz.show_numeric_labels = False

    def step_callback(world: World, dt: float) -> None:
        controller(robot, world, dt)
        robot.distance_sensor.read(world, dt)
        robot.imu.read(world, dt)

    instructions = (
        f"Track preset: {spec.name}",
        f"Robot preset: {ROBOT_PRESET}",
        "Edit BinaryLineBangBangController for custom logic.",
        "Swap TRACK_NAME/ROBOT_PRESET constants to try other combos.",
    )

    viz.run(
        world,
        step_callback=step_callback,
        overlay_provider=lambda w: _outline_track(spec),
        instructions=instructions,
    )


def _outline_track(spec) -> OverlayData:
    data = OverlayData()
    corners = [
        (-spec.floor_half_width, -spec.floor_half_height),
        (spec.floor_half_width, -spec.floor_half_height),
        (spec.floor_half_width, spec.floor_half_height),
        (-spec.floor_half_width, spec.floor_half_height),
    ]
    for start, end in zip(corners, corners[1:] + corners[:1]):
        data.segments.append(OverlaySegment(start=start, end=end, color=(220, 220, 220)))
    return data


if __name__ == "__main__":
    main()

