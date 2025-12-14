"""Check that symmetric wheel forces translate without spinning."""
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
from middle_level_library.motors import DifferentialDrive


def run() -> bool:
    world = World(name="translation_test", random_seed=1, default_dt=0.05)
    robot = SimObject(
        name="bot",
        pose=Pose2D(0.0, 0.0, 0.0),
        shape=Circle(radius=0.1),
        material=MaterialProperties(friction=0.6),
        can_move=True,
        dynamic_state=DynamicState(mass=2.0, moment_of_inertia=0.25),
    )
    world.add_object(robot)

    drive = DifferentialDrive(wheel_base=0.24, max_force=3.0, detailed=False)
    drive.attach(robot)

    for _ in range(40):
        drive.command(0.8, 0.8, world, world.default_dt)
        world.step()

    vx, vy = robot.state.linear_velocity
    ang = robot.state.angular_velocity
    passed = vx > 0.1 and abs(ang) < 0.01
    print(
        f"Differential drive translation: vx={vx:.3f}, ang={ang:.3f} -> {'PASS' if passed else 'FAIL'}"
    )
    return passed


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
