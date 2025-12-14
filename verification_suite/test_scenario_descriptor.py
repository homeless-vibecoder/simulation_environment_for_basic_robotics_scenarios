from __future__ import annotations

from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[1]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from core import load_scenario, list_environment_assets, list_robot_assets
from core.persistence import load_scenario_summary


def test_descriptor_parses_multi_robot() -> None:
    scenario = load_scenario(BASE / "scenarios" / "composed_team_line")
    assert scenario.descriptor.environment.endswith("generic_world.json")
    assert scenario.descriptor.thumbnail == "thumbnail.png"
    assert len(scenario.robots) == 2
    ids = {r.id for r in scenario.robots}
    assert {"alpha", "bravo"}.issubset(ids)
    assert all(r.config.spawn_pose for r in scenario.robots)


def test_descriptor_legacy_pair_still_loads() -> None:
    scenario = load_scenario(BASE / "scenarios" / "bounded_maze")
    assert scenario.descriptor.id == "bounded_maze"
    assert len(scenario.robots) == 1
    assert scenario.robots[0].config.controller_module


def test_descriptor_optional_fields_and_summary() -> None:
    scenario_path = BASE / "scenarios" / "composed_generic_duo"
    scenario = load_scenario(scenario_path)
    desc = scenario.descriptor
    assert desc.description
    assert desc.thumbnail == "thumbnail.png"
    assert desc.environment.endswith("generic_world.json")
    assert all(r.spawn_pose for r in desc.robots)
    summary = load_scenario_summary(scenario_path)
    assert summary.thumbnail is not None
    assert summary.name == desc.name


def test_spawn_defaults_to_asset_spawn_when_descriptor_omits_spawn() -> None:
    scenario = load_scenario(BASE / "scenarios" / "composed_generic")
    assert scenario.robots
    # composed_generic descriptor omits spawn; should reuse the asset spawn_pose.
    assert scenario.robots[0].config.spawn_pose == (0.0, 0.15, 0.0)


def test_multi_robot_controllers_resolved() -> None:
    scenario = load_scenario(BASE / "scenarios" / "composed_generic_duo")
    ids = [r.id for r in scenario.robots]
    assert {"alpha", "bravo"}.issubset(ids)
    controllers = {r.id: r.config.controller_module for r in scenario.robots}
    assert controllers.get("alpha") == "controller_duo_generic"
    assert controllers.get("bravo") == "controller_duo_generic"
    # spawn positions should reflect descriptor values, not default zeros
    alpha = next(r for r in scenario.robots if r.id == "alpha")
    bravo = next(r for r in scenario.robots if r.id == "bravo")
    assert alpha.config.spawn_pose == (-0.45, -0.28, 0.0)
    assert bravo.config.spawn_pose == (-0.45, 0.28, 0.0)


def test_asset_helpers_list_shared_content() -> None:
    envs = list_environment_assets(BASE)
    robots = list_robot_assets(BASE)
    assert any(p.name == "generic_world.json" for p in envs)
    assert any(p.name == "generic_robot.json" for p in robots)
