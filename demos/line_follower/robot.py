"""Robot definition for the line follower demo."""
from __future__ import annotations

from low_level_mechanics.world import Pose2D
from middle_level_library.robots import DemoLineFollower


ROBOT_FACTORY = DemoLineFollower()


def spawn_robot(name: str = "scout", pose: Pose2D | None = None):
    pose = pose or Pose2D(-0.9, 0.1, 0.0)
    return ROBOT_FACTORY.create(name=name, pose=pose)
