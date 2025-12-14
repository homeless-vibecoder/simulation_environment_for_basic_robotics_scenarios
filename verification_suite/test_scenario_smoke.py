"""Deterministic load/run smoke tests for curated scenarios."""
from __future__ import annotations

import math
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from core import Simulator, load_scenario  # noqa: E402

SCENARIOS = [
    "bounded_maze",
    "slalom_field",
    "tight_corridor",
    "line_loop",
    "composed_generic",
    "composed_slalom",
    "composed_team_line",
    "composed_slalom_duo",
    "mouse_maze_competition",
    "composed_generic_duo",
    "composed_generic_trio",
]
STEPS = 180


def _finite_pose(body) -> bool:
    pose = body.pose
    lin_v = body.state.linear_velocity
    ang_v = body.state.angular_velocity
    return all(
        math.isfinite(v)
        for v in (
            pose.x,
            pose.y,
            pose.theta,
            lin_v[0],
            lin_v[1],
            ang_v,
        )
    )


def run_scenario(name: str) -> bool:
    scenario_path = BASE / "scenarios" / name
    scenario = load_scenario(scenario_path)
    roster_ids = {r.id for r in scenario.robots}
    sim = Simulator()
    sim.load(scenario_path, scenario.world, robots=scenario.robots, top_down=True)
    for _ in range(STEPS):
        sim.step()
    bodies_ok = all(_finite_pose(body) for body in sim.bodies.values())
    ctrl_ok = sim.last_controller_error is None and not getattr(sim, "last_controller_errors", {})
    phys_ok = sim.last_physics_warning is None
    seen_ids = set(sim.motor_owners.values()) if getattr(sim, "motor_owners", None) else set()
    roster_ok = (not roster_ids) or roster_ids.issubset(seen_ids)
    sim_ids = set(getattr(sim, "robot_ids", []) or [])
    id_match = not roster_ids or roster_ids == sim_ids
    return bodies_ok and ctrl_ok and phys_ok and roster_ok and id_match


def run() -> bool:
    results = {}
    all_ok = True
    for name in SCENARIOS:
        ok = run_scenario(name)
        results[name] = ok
        all_ok = all_ok and ok
    for name, status in results.items():
        print(f"[{name}] {'PASS' if status else 'FAIL'}")
    return all_ok


def test_scenarios_smoke() -> None:
    assert run()


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
