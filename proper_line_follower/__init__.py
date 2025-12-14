"""Reusable track, robot, and controller utilities for line-follower demos."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure sibling packages (low_level_mechanics, middle_level_library, etc.)
# are importable even when this package is imported as
# `simulation_environment.proper_line_follower`.
_SIM_ROOT = Path(__file__).resolve().parents[1]
if str(_SIM_ROOT) not in sys.path:  # pragma: no cover - import-time wiring
    sys.path.insert(0, str(_SIM_ROOT))

from .tracks.library import (
    TrackSpec,
    create_track_world,
    get_track_spec,
    list_track_presets,
    default_track_entry_pose,
)
from .robots.library import (
    LineFollowerRobot,
    RobotSpec,
    create_robot,
    list_robot_presets,
)
from .controllers.bang_bang import BinaryLineBangBangController

__all__ = [
    "TrackSpec",
    "RobotSpec",
    "LineFollowerRobot",
    "create_track_world",
    "create_robot",
    "get_track_spec",
    "list_track_presets",
    "list_robot_presets",
    "BinaryLineBangBangController",
    "default_track_entry_pose",
]

