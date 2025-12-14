"""Robot blueprints and controller hooks."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from low_level_mechanics.world import World, Pose2D
from low_level_mechanics.entities import SimObject, DynamicState
from low_level_mechanics.geometry import Circle
from low_level_mechanics.materials import MaterialProperties

from .sensors import LineSensorArray, DistanceSensor, IMUSensor
from .motors import DifferentialDrive

ControllerFn = Callable[["RobotContext", World, float], None]


@dataclass
class RobotContext:
    robot: SimObject
    line_sensor: LineSensorArray
    range_sensor: DistanceSensor
    imu: IMUSensor
    drive: DifferentialDrive
    state: dict = field(default_factory=dict)


class DemoLineFollower:
    """Factory for a line-following robot + controller slot."""

    def __init__(
        self,
        *,
        line_preset: str = "line_basic",
        range_preset: str = "range_short",
        wheel_preset: str = "wheel_small",
        wheel_base: float = 0.24,
        radius: float = 0.12,
    ) -> None:
        self.line_preset = line_preset
        self.range_preset = range_preset
        self.wheel_preset = wheel_preset
        self.wheel_base = wheel_base
        self.radius = radius

    def create(self, name: str, pose: Pose2D) -> RobotContext:
        robot = SimObject(
            name=name,
            pose=pose,
            shape=Circle(radius=self.radius),
            material=MaterialProperties(friction=0.6, reflectivity=0.2, custom={"role": "line_follower"}),
            can_move=True,
            dynamic_state=DynamicState(
                linear_velocity=(0.0, 0.0),
                angular_velocity=0.0,
                mass=1.7,
                moment_of_inertia=0.06,
            ),
        )
        line = LineSensorArray(
            name=f"{name}_line",
            preset=self.line_preset,
            mount_pose=Pose2D(self.radius + 0.02, 0.0, 0.0),
        )
        distance = DistanceSensor(
            name=f"{name}_range",
            preset=self.range_preset,
            mount_pose=Pose2D(self.radius + 0.02, 0.0, 0.0),
        )
        imu = IMUSensor(name=f"{name}_imu")
        drive = DifferentialDrive(wheel_base=self.wheel_base, detailed=True, preset=self.wheel_preset)

        for component in (line, distance, imu):
            component.attach(robot)
        drive.attach(robot)

        return RobotContext(robot=robot, line_sensor=line, range_sensor=distance, imu=imu, drive=drive)
