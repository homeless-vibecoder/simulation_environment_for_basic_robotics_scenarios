"""Pre-built track specifications and helpers for the proper line follower suite."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, Iterable, List, Sequence, Tuple

from low_level_mechanics.entities import SimObject
from low_level_mechanics.geometry import Polygon
from low_level_mechanics.materials import MaterialProperties
from low_level_mechanics.world import Pose2D, World

Color = Tuple[int, int, int]
Point = Tuple[float, float]


@dataclass(frozen=True)
class TrackSpec:
    name: str
    floor_half_width: float
    floor_half_height: float
    path: Sequence[Point]
    line_width: float = 0.08
    floor_color: Color = (245, 245, 245)
    line_color: Color = (25, 25, 25)
    floor_friction: float = 1.2


TRACK_PRESETS: Dict[str, TrackSpec] = {
    "oval_loop": TrackSpec(
        name="oval_loop",
        floor_half_width=1.6,
        floor_half_height=1.1,
        path=[
            (-1.0, -0.4),
            (-0.5, -0.85),
            (0.4, -0.9),
            (1.05, -0.3),
            (1.0, 0.45),
            (0.35, 0.95),
            (-0.55, 0.85),
            (-1.05, 0.25),
        ],
    ),
    "chicane_loop": TrackSpec(
        name="chicane_loop",
        floor_half_width=1.7,
        floor_half_height=1.2,
        path=[
            (-1.2, -0.3),
            (-0.4, -0.9),
            (0.15, -0.45),
            (0.65, -0.8),
            (1.1, -0.15),
            (0.5, 0.15),
            (1.0, 0.8),
            (0.2, 0.9),
            (-0.3, 0.4),
            (-0.8, 0.85),
            (-1.25, 0.2),
        ],
        line_width=0.07,
    ),
    "double_s": TrackSpec(
        name="double_s",
        floor_half_width=1.8,
        floor_half_height=1.3,
        path=[
            (-1.2, -0.8),
            (-0.6, -0.3),
            (-0.1, -0.85),
            (0.55, -0.35),
            (1.2, -0.7),
            (1.25, 0.2),
            (0.65, 0.8),
            (0.0, 0.3),
            (-0.55, 0.85),
            (-1.3, 0.25),
        ],
        line_width=0.09,
    ),
}


def list_track_presets() -> List[str]:
    return sorted(TRACK_PRESETS.keys())


def get_track_spec(name: str) -> TrackSpec:
    try:
        return TRACK_PRESETS[name]
    except KeyError as exc:  # pragma: no cover - defensive
        raise KeyError(f"Unknown track preset '{name}'. Available: {list_track_presets()}") from exc


def create_track_world(
    track_name: str = "oval_loop",
    *,
    random_seed: int | None = 123,
    default_dt: float = 0.02,
) -> Tuple[World, TrackSpec]:
    spec = get_track_spec(track_name)
    world = World(name=f"proper_{spec.name}", random_seed=random_seed, default_dt=default_dt)
    for obj in build_track_objects(spec):
        world.add_object(obj)
    return world, spec


def build_track_objects(spec: TrackSpec) -> Iterable[SimObject]:
    yield _build_floor(spec)
    for index, segment in enumerate(_iter_segments(spec.path)):
        vertices = _segment_vertices(segment[0], segment[1], spec.line_width)
        if not vertices:
            continue
        strip = SimObject(
            name=f"{spec.name}_line_{index}",
            pose=Pose2D(0.0, 0.0, 0.0),
            shape=Polygon(vertices),
            material=MaterialProperties(
                friction=max(spec.floor_friction, 1.1),
                reflectivity=0.2,
                field_signals={"line_intensity": 1.0},
                custom={"color": spec.line_color},
            ),
            metadata={"color": spec.line_color},
        )
        yield strip


def _build_floor(spec: TrackSpec) -> SimObject:
    w = spec.floor_half_width
    h = spec.floor_half_height
    floor_shape = Polygon([(-w, -h), (w, -h), (w, h), (-w, h)])
    return SimObject(
        name=f"{spec.name}_floor",
        pose=Pose2D(0.0, 0.0, 0.0),
        shape=floor_shape,
        material=MaterialProperties(friction=spec.floor_friction, custom={"color": spec.floor_color}),
        metadata={"color": spec.floor_color},
    )


def _iter_segments(points: Sequence[Point]) -> Iterable[Tuple[Point, Point]]:
    if len(points) < 2:
        return
    for i in range(len(points)):
        start = points[i]
        end = points[(i + 1) % len(points)]
        yield start, end


def _segment_vertices(p0: Point, p1: Point, width: float) -> List[Point]:
    dx = p1[0] - p0[0]
    dy = p1[1] - p0[1]
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return []
    nx = -dy / length
    ny = dx / length
    half = width / 2.0
    offset = (nx * half, ny * half)
    return [
        (p0[0] + offset[0], p0[1] + offset[1]),
        (p1[0] + offset[0], p1[1] + offset[1]),
        (p1[0] - offset[0], p1[1] - offset[1]),
        (p0[0] - offset[0], p0[1] - offset[1]),
    ]


def default_track_entry_pose(spec: TrackSpec, back_offset: float = 0.18) -> Pose2D:
    """Return a pose aligned with the longest straight segment of a track."""
    segment = _longest_segment(spec.path)
    if segment is None:
        # Fall back to placing the robot on the left edge facing right.
        return Pose2D(-spec.floor_half_width + back_offset, 0.0, 0.0)
    start, next_pt = segment
    heading = math.atan2(next_pt[1] - start[1], next_pt[0] - start[0])
    x = start[0] - math.cos(heading) * back_offset
    y = start[1] - math.sin(heading) * back_offset
    return Pose2D(x, y, heading)


def _longest_segment(points: Sequence[Point]) -> Tuple[Point, Point] | None:
    longest: Tuple[Point, Point] | None = None
    max_length = -1.0
    for start, end in _iter_segments(points):
        length = math.hypot(end[0] - start[0], end[1] - start[1])
        if length > max_length:
            max_length = length
            longest = (start, end)
    return longest


__all__ = [
    "TrackSpec",
    "TRACK_PRESETS",
    "list_track_presets",
    "get_track_spec",
    "create_track_world",
    "build_track_objects",
    "default_track_entry_pose",
]

