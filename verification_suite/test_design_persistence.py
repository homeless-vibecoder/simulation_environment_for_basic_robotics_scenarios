"""Verify designer design save/load helpers for robot, environment, custom assets."""
from __future__ import annotations

from pathlib import Path

from core.config import BodyConfig, WorldConfig, RobotConfig, CustomObjectConfig, MaterialConfig
from core.persistence import (
    save_robot_design,
    load_robot_design,
    save_environment_design,
    load_environment_design,
    save_custom_asset,
    load_custom_asset,
    save_scenario,
    load_scenario,
)


def _tmp(tmp_path: Path, name: str) -> Path:
    return tmp_path / f"{name}.json"


def test_robot_design_roundtrip(tmp_path: Path) -> None:
    robot = RobotConfig(
        bodies=[
            BodyConfig(
                name="base",
                points=[(0.0, 0.0), (0.2, 0.0), (0.2, 0.1), (0.0, 0.1)],
                edges=[(0, 1), (1, 2), (2, 3), (3, 0)],
            )
        ]
    )
    path = _tmp(tmp_path, "robot")
    save_robot_design(path, robot)
    loaded = load_robot_design(path)
    assert len(loaded.bodies) == 1
    assert loaded.bodies[0].name == "base"
    assert [tuple(p) for p in loaded.bodies[0].points] == [tuple(p) for p in robot.bodies[0].points]


def test_robot_design_inserts_default_body_when_empty(tmp_path: Path) -> None:
    robot = RobotConfig()
    path = _tmp(tmp_path, "robot_empty")
    save_robot_design(path, robot)
    loaded = load_robot_design(path)
    assert len(loaded.bodies) >= 1
    assert loaded.bodies[0].points, "default body should define geometry"


def test_environment_design_roundtrip(tmp_path: Path) -> None:
    world = WorldConfig(drawings=[], bounds=None, metadata={"note": "env"})
    path = _tmp(tmp_path, "env")
    save_environment_design(path, world)
    loaded = load_environment_design(path)
    assert loaded.metadata.get("note") == "env"
    assert loaded.drawings == []


def test_custom_asset_roundtrip(tmp_path: Path) -> None:
    body = BodyConfig(
        name="custom_body",
        points=[(0.0, 0.0), (0.1, 0.0), (0.1, 0.1)],
        edges=[(0, 1), (1, 2), (2, 0)],
        material=MaterialConfig(color=(10, 20, 30)),
    )
    asset = CustomObjectConfig(name="custom_asset", body=body, kind="custom", metadata={"tag": "test"})
    path = _tmp(tmp_path, "custom")
    save_custom_asset(path, asset)
    loaded = load_custom_asset(path)
    assert loaded.name == "custom_asset"
    assert [tuple(p) for p in loaded.body.points] == [tuple(p) for p in body.points]
    assert loaded.metadata.get("tag") == "test"


def test_scenario_creation_roundtrip(tmp_path: Path) -> None:
    scenario_dir = tmp_path / "demo_scenario"
    scenario_dir.mkdir()
    world = WorldConfig()
    robot = RobotConfig(
        bodies=[
            BodyConfig(
                name="base",
                points=[(0.0, 0.0), (0.2, 0.0), (0.2, 0.1), (0.0, 0.1)],
                edges=[(0, 1), (1, 2), (2, 3), (3, 0)],
            )
        ]
    )
    save_scenario(scenario_dir, world, robot)
    loaded = load_scenario(scenario_dir)
    assert loaded.world is not None
    assert loaded.robots, "scenario should contain at least one robot"
    assert loaded.robots[0].config.bodies, "robot should have bodies after load"
