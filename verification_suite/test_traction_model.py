"""Tests for traction-aware wheel dynamics and slip handling."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Tuple

SIM_ENV_ROOT = Path(__file__).resolve().parents[1]
if str(SIM_ENV_ROOT) not in sys.path:
    sys.path.insert(0, str(SIM_ENV_ROOT))

def _ensure_pygame_stub() -> None:
    """Provide a minimal pygame stub so tests run headless."""
    try:
        import pygame  # type: ignore  # noqa: F401
        return
    except ImportError:
        import types

        stub = types.SimpleNamespace()
        stub.init = lambda *a, **k: None
        stub.display = types.SimpleNamespace(
            set_caption=lambda *a, **k: None,
            set_mode=lambda *a, **k: None,
        )
        stub.font = types.SimpleNamespace(
            SysFont=lambda *a, **k: types.SimpleNamespace(render=lambda *a, **k: None)
        )
        stub.time = types.SimpleNamespace(
            Clock=lambda *a, **k: types.SimpleNamespace(tick=lambda *a, **k: None)
        )
        stub.event = types.SimpleNamespace(get=lambda: [])
        stub.QUIT = 0
        stub.MOUSEBUTTONDOWN = 1
        stub.MOUSEBUTTONUP = 2
        stub.MOUSEMOTION = 3
        stub.K_LSHIFT = 0
        stub.KMOD_SHIFT = 0
        stub.key = types.SimpleNamespace(get_mods=lambda: 0, get_pressed=lambda: [])
        stub.draw = types.SimpleNamespace(circle=lambda *a, **k: None, line=lambda *a, **k: None, polygon=lambda *a, **k: None)
        stub.mouse = types.SimpleNamespace(get_pos=lambda: (0, 0))
        sys.modules["pygame"] = stub
        sys.modules["pygame.freetype"] = stub


_ensure_pygame_stub()

from low_level_mechanics.world import World, Pose2D
from low_level_mechanics.entities import SimObject, DynamicState
from low_level_mechanics.geometry import Circle
from low_level_mechanics.materials import MaterialProperties
from middle_level_library.motors import WheelMotor, DifferentialDrive
from core.config import ActuatorConfig, BodyConfig, MaterialConfig, RobotConfig, WorldConfig
from core.simulator import Simulator


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "traction_trace.json"


def _make_world(mass: float = 1.5, dt: float = 0.02) -> Tuple[World, SimObject]:
    world = World(name="traction_world", random_seed=7, default_dt=dt)
    robot = SimObject(
        name="bot",
        pose=Pose2D(0.0, 0.0, 0.0),
        shape=Circle(radius=0.1),
        material=MaterialProperties(friction=0.9, traction=0.9),
        can_move=True,
        dynamic_state=DynamicState(mass=mass, moment_of_inertia=0.2),
    )
    world.add_object(robot)
    return world, robot


def _round_trace(trace: List[Dict[str, object]]) -> List[Dict[str, object]]:
    def _round_val(v):
        if isinstance(v, float):
            return round(v, 6)
        if isinstance(v, (tuple, list)):
            return [_round_val(x) for x in v]
        if isinstance(v, dict):
            return {k: _round_val(val) for k, val in v.items()}
        return v

    return [_round_val(entry) for entry in trace]


def check_longitudinal_no_slip() -> Tuple[bool, str]:
    world, robot = _make_world(mass=1.4, dt=0.02)
    motor = WheelMotor(
        name="drive",
        mount_pose=Pose2D(0.0, 0.1, 0.0),
        max_force=2.8,
        mu_long=1.2,
        mu_lat=1.0,
        wheel_radius=0.05,
        max_wheel_omega=30.0,
        response_time=0.05,
        wheel_count=1,
    )
    motor.attach(robot)

    for _ in range(60):
        motor.command(0.5, world, world.default_dt)
        world.step()

    speed = math.hypot(*robot.state.linear_velocity)
    report = motor.last_report
    target_speed = motor.angular_speed * motor.wheel_radius
    within_target = abs(speed - target_speed) < 0.12
    passed = bool(report) and abs(report.slip_ratio) < 0.1 and within_target
    msg = (
        f"no-slip: speed={speed:.3f}, target={target_speed:.3f}, "
        f"slip={report.slip_ratio if report else None}"
    )
    return passed, msg


def check_slip_when_overdriven() -> Tuple[bool, str]:
    world, robot = _make_world(mass=1.6, dt=0.02)
    motor = WheelMotor(
        name="drive",
        mount_pose=Pose2D(0.0, 0.0, 0.0),
        max_force=3.0,
        mu_long=0.25,
        mu_lat=0.6,
        wheel_radius=0.05,
        max_wheel_omega=35.0,
        response_time=0.02,
        wheel_count=1,
    )
    motor.attach(robot)

    for _ in range(12):
        motor.command(1.0, world, world.default_dt)
        world.step()

    report = motor.last_report
    normal_load = robot.state.mass * 9.81
    limit = motor.mu_long * normal_load * world.default_dt
    applied = report.applied_longitudinal_impulse if report else 0.0
    slip_ratio = report.slip_ratio if report else 0.0
    contact_after = report.contact_speed_after if report else 0.0
    wheel_speed = report.wheel_speed if report else 0.0
    capped_velocity = contact_after < wheel_speed if report else False
    passed = bool(report) and applied <= limit + 1e-5 and slip_ratio > 0.25 and capped_velocity
    msg = (
        f"overdrive: applied={applied:.5f} (limit={limit:.5f}), slip={slip_ratio:.3f}, "
        f"contact_after={contact_after:.4f}, wheel_speed={wheel_speed:.4f}"
    )
    return passed, msg


def check_lateral_slip_bounded() -> Tuple[bool, str]:
    world, robot = _make_world(mass=1.0, dt=0.02)
    drive = DifferentialDrive(wheel_base=0.22, max_force=2.5, mu_long=1.0, mu_lat=1.0, wheel_radius=0.05)
    drive.attach(robot)

    for _ in range(40):
        drive.command(0.4, 0.4, world, world.default_dt)
        world.step()

    left_report = drive.left.last_report
    right_report = drive.right.last_report
    lateral = max(abs(left_report.lateral_slip if left_report else 0.0), abs(right_report.lateral_slip if right_report else 0.0))
    passed = lateral < 0.02
    msg = f"lateral bounded: max_lat_slip={lateral:.4f}"
    return passed, msg


def check_locked_vs_spin() -> Tuple[bool, str]:
    world, robot = _make_world(mass=1.2, dt=0.02)
    left = WheelMotor(
        name="left",
        mount_pose=Pose2D(0.0, 0.1, 0.0),
        max_force=2.2,
        mu_long=0.8,
        mu_lat=0.9,
        wheel_radius=0.05,
        wheel_count=1,
    )
    right = WheelMotor(
        name="right",
        mount_pose=Pose2D(0.0, -0.1, 0.0),
        max_force=2.2,
        mu_long=0.8,
        mu_lat=0.9,
        wheel_radius=0.05,
        wheel_count=1,
    )
    left.attach(robot)
    right.attach(robot)

    for _ in range(30):
        left.command(0.0, world, world.default_dt)
        right.command(0.9, world, world.default_dt)
        world.step()

    ang_vel = robot.state.angular_velocity
    slip_right = right.last_report.slip_ratio if right.last_report else 0.0
    passed = ang_vel > 0.05 and slip_right > 0.1
    msg = f"one-wheel spin: ang_vel={ang_vel:.3f}, slip_right={slip_right:.3f}"
    return passed, msg


def _build_trace() -> List[Dict[str, object]]:
    world_cfg = WorldConfig(name="trace_world", seed=11, timestep=0.01)
    body_cfg = BodyConfig(
        name="chassis",
        points=[(-0.12, -0.08), (0.12, -0.08), (0.12, 0.08), (-0.12, 0.08)],
        edges=[(0, 1), (1, 2), (2, 3), (3, 0)],
        mass=1.1,
        inertia=0.08,
        material=MaterialConfig(friction=0.9, restitution=0.05),
    )
    actuators = [
        ActuatorConfig(
            name="left_motor",
            type="motor",
            body="chassis",
            mount_pose=(0.0, 0.08, 0.0),
            params={"max_force": 2.4, "wheel_radius": 0.04, "wheel_count": 2, "max_wheel_omega": 35.0},
        ),
        ActuatorConfig(
            name="right_motor",
            type="motor",
            body="chassis",
            mount_pose=(0.0, -0.08, 0.0),
            params={"max_force": 2.4, "wheel_radius": 0.04, "wheel_count": 2, "max_wheel_omega": 35.0},
        ),
    ]
    robot_cfg = RobotConfig(
        spawn_pose=(0.0, 0.0, 0.0),
        bodies=[body_cfg],
        joints=[],
        actuators=actuators,
        sensors=[],
        measurements=[],
        controller_module="controller",
    )
    sim = Simulator()
    sim.load(SIM_ENV_ROOT / "verification_suite", world_cfg, robot_cfg, ignore_terrain=True)
    sim.enable_trace_logging(True)

    commands = [(0.35, 0.35), (0.35, 0.15), (0.0, 0.4)]
    for left_cmd, right_cmd in commands:
        sim.motors["left_motor"].command(left_cmd, sim, sim.dt)
        sim.motors["right_motor"].command(right_cmd, sim, sim.dt)
        sim.step(sim.dt)
    return _round_trace(sim.export_trace_log())


def check_trace_regression() -> Tuple[bool, str]:
    actual = _build_trace()
    try:
        expected = json.loads(FIXTURE_PATH.read_text())
    except FileNotFoundError:
        return False, "trace fixture missing"
    passed = actual == expected
    return passed, "trace regression" if passed else "trace mismatch"


def run() -> bool:
    checks = [
        ("longitudinal_no_slip", check_longitudinal_no_slip),
        ("overdrive_slip", check_slip_when_overdriven),
        ("lateral_bounded", check_lateral_slip_bounded),
        ("one_wheel_spin", check_locked_vs_spin),
        ("trace_regression", check_trace_regression),
    ]
    results = []
    for name, fn in checks:
        passed, msg = fn()
        status = "PASS" if passed else "FAIL"
        print(f"{name}: {status} ({msg})")
        results.append(passed)
    return all(results)


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
