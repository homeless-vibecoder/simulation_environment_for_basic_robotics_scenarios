"""Sanity check that an off-center motor induces rotation."""
from __future__ import annotations

import sys
from pathlib import Path

SIM_ENV_ROOT = Path(__file__).resolve().parents[1]
if str(SIM_ENV_ROOT) not in sys.path:
    sys.path.insert(0, str(SIM_ENV_ROOT))

from low_level_mechanics.world import World, Pose2D
from low_level_mechanics.entities import SimObject, DynamicState
from low_level_mechanics.geometry import Circle
from low_level_mechanics.materials import MaterialProperties
from middle_level_library.motors import WheelMotor


def run() -> bool:
    world = World(name="torque_test", random_seed=0, default_dt=0.05)
    robot = SimObject(
        name="bot",
        pose=Pose2D(0.0, 0.0, 0.0),
        shape=Circle(radius=0.1),
        material=MaterialProperties(friction=0.6),
        can_move=True,
        dynamic_state=DynamicState(mass=2.0, moment_of_inertia=0.2),
    )
    world.add_object(robot)

    motor = WheelMotor(name="thruster", mount_pose=Pose2D(0.0, 0.15, 0.0), max_force=4.0)
    motor.attach(robot)

    steps = 40
    for _ in range(steps):
        motor.command(1.0, world, world.default_dt)
        world.step()

    ang_vel = robot.state.angular_velocity
    passed = abs(ang_vel) > 0.01
    print(f"Single wheel rotation test: ang_vel={ang_vel:.3f} -> {'PASS' if passed else 'FAIL'}")
    return passed


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
