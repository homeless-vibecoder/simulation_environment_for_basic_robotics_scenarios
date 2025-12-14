"""Regression check for bounded_maze stability and bounds adherence."""
from __future__ import annotations

import math
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from core import Simulator, load_scenario  # noqa: E402


def test_bounded_maze_stays_within_bounds():
    scenario_path = BASE / "scenarios" / "bounded_maze"
    world_cfg, robot_cfg = load_scenario(scenario_path)
    sim = Simulator()
    sim.load(scenario_path, world_cfg, robot_cfg, top_down=True)

    assert world_cfg.bounds is not None, "bounded_maze should define bounds"
    b = world_cfg.bounds
    margin = 0.12  # small slack to account for robot footprint and wall thickness

    for _ in range(600):
        sim.step()
        pose = next(iter(sim.bodies.values())).pose
        assert b.min_x - margin <= pose.x <= b.max_x + margin
        assert b.min_y - margin <= pose.y <= b.max_y + margin
        assert math.isfinite(pose.theta)
        lin_v = next(iter(sim.bodies.values())).state.linear_velocity
        ang_v = next(iter(sim.bodies.values())).state.angular_velocity
        assert all(math.isfinite(v) for v in (lin_v[0], lin_v[1], ang_v))
        assert sim.last_controller_error is None
        assert sim.last_physics_warning is None

