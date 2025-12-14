"""Core low-level mechanics package for 2D robotics simulations."""

from .world import World, Pose2D, Transform2D
from .geometry import Circle, Polygon, Shape2D
from .materials import MaterialProperties
from .entities import SimObject, DynamicState
from .diagnostics import SnapshotLogger, Snapshot
from .visualizer import Visualizer, OverlayPoint, OverlaySegment, OverlayData

__all__ = [
    "World",
    "Pose2D",
    "Transform2D",
    "Circle",
    "Polygon",
    "Shape2D",
    "MaterialProperties",
    "SimObject",
    "DynamicState",
    "SnapshotLogger",
    "Snapshot",
    "Visualizer",
    "OverlayPoint",
    "OverlaySegment",
    "OverlayData",
]
