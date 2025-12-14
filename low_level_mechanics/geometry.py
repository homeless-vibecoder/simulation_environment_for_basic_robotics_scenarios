"""Shape primitives and lightweight collision helpers."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import List, Optional, Sequence, Tuple

from .world import Pose2D

Point2D = Tuple[float, float]


@dataclass(frozen=True)
class BoundingBox:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def intersects(self, other: "BoundingBox") -> bool:
        return not (
            self.max_x < other.min_x
            or self.min_x > other.max_x
            or self.max_y < other.min_y
            or self.min_y > other.max_y
        )

    def expand(self, margin: float) -> "BoundingBox":
        return BoundingBox(
            self.min_x - margin,
            self.min_y - margin,
            self.max_x + margin,
            self.max_y + margin,
        )


class Shape2D:
    """Base class for simple 2D shapes."""

    def area(self) -> float:  # pragma: no cover - interface only
        raise NotImplementedError

    def bounding_box(self, pose: Pose2D | None = None) -> BoundingBox:
        raise NotImplementedError

    def contains_point(self, point: Point2D, pose: Pose2D | None = None) -> bool:
        raise NotImplementedError

    def intersects(self, other: "Shape2D", pose_self: Pose2D, pose_other: Pose2D) -> bool:
        bbox_self = self.bounding_box(pose_self)
        bbox_other = other.bounding_box(pose_other)
        if not bbox_self.intersects(bbox_other):
            return False
        if isinstance(self, Circle) and isinstance(other, Circle):
            return _circle_vs_circle(self, pose_self, other, pose_other)
        if isinstance(self, Circle) and isinstance(other, Polygon):
            return _circle_vs_polygon(self, pose_self, other, pose_other)
        if isinstance(self, Polygon) and isinstance(other, Circle):
            return _circle_vs_polygon(other, pose_other, self, pose_self)
        if isinstance(self, Polygon) and isinstance(other, Polygon):
            return _polygon_vs_polygon(self, pose_self, other, pose_other)
        # Fallback to bounding boxes.
        return True


@dataclass(frozen=True)
class Circle(Shape2D):
    radius: float

    def area(self) -> float:
        return math.pi * self.radius**2

    def bounding_box(self, pose: Pose2D | None = None) -> BoundingBox:
        cx = pose.x if pose else 0.0
        cy = pose.y if pose else 0.0
        r = self.radius
        return BoundingBox(cx - r, cy - r, cx + r, cy + r)

    def contains_point(self, point: Point2D, pose: Pose2D | None = None) -> bool:
        cx = pose.x if pose else 0.0
        cy = pose.y if pose else 0.0
        px, py = point
        return (px - cx) ** 2 + (py - cy) ** 2 <= self.radius**2


@dataclass(frozen=True)
class Polygon(Shape2D):
    """Convex polygon represented by a list of vertices in local coordinates."""

    vertices: Sequence[Point2D]

    def __post_init__(self) -> None:
        if len(self.vertices) < 3:
            raise ValueError("Polygon requires at least three vertices")

    def area(self) -> float:
        area = 0.0
        pts = self.vertices
        for i in range(len(pts)):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % len(pts)]
            area += x1 * y2 - x2 * y1
        return abs(area) * 0.5

    def _world_vertices(self, pose: Pose2D | None) -> List[Point2D]:
        if pose is None:
            return list(self.vertices)
        return [pose.transform_point(v) for v in self.vertices]

    def bounding_box(self, pose: Pose2D | None = None) -> BoundingBox:
        verts = self._world_vertices(pose)
        xs = [v[0] for v in verts]
        ys = [v[1] for v in verts]
        return BoundingBox(min(xs), min(ys), max(xs), max(ys))

    def contains_point(self, point: Point2D, pose: Pose2D | None = None) -> bool:
        local_point = point
        if pose is not None:
            inv = pose.inverse()
            local_point = inv.transform_point(point)
        winding = 0
        px, py = local_point
        pts = self.vertices
        for i in range(len(pts)):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % len(pts)]
            if y1 <= py < y2 or y2 <= py < y1:
                x_cross = x1 + (py - y1) * (x2 - x1) / (y2 - y1 + 1e-12)
                if px < x_cross:
                    winding ^= 1
        return winding == 1


def _circle_vs_circle(a: Circle, pose_a: Pose2D, b: Circle, pose_b: Pose2D) -> bool:
    dx = pose_a.x - pose_b.x
    dy = pose_a.y - pose_b.y
    radius_sum = a.radius + b.radius
    return dx * dx + dy * dy <= radius_sum * radius_sum


def _circle_vs_polygon(circle: Circle, pose_circle: Pose2D, polygon: Polygon, pose_polygon: Pose2D) -> bool:
    world_verts = polygon._world_vertices(pose_polygon)
    # Check if polygon contains circle center.
    if polygon.contains_point((pose_circle.x, pose_circle.y), pose_polygon):
        return True
    # Check distance to edges.
    for i in range(len(world_verts)):
        start = world_verts[i]
        end = world_verts[(i + 1) % len(world_verts)]
        if _distance_point_to_segment((pose_circle.x, pose_circle.y), start, end) <= circle.radius:
            return True
    return False


def _polygon_vs_polygon(a: Polygon, pose_a: Pose2D, b: Polygon, pose_b: Pose2D) -> bool:
    verts_a = a._world_vertices(pose_a)
    verts_b = b._world_vertices(pose_b)
    return _sat_overlap(verts_a, verts_b) and _sat_overlap(verts_b, verts_a)


def _sat_overlap(verts_a: List[Point2D], verts_b: List[Point2D]) -> bool:
    for i in range(len(verts_a)):
        x1, y1 = verts_a[i]
        x2, y2 = verts_a[(i + 1) % len(verts_a)]
        edge_x = x2 - x1
        edge_y = y2 - y1
        normal = (-edge_y, edge_x)
        min_a, max_a = _project(normal, verts_a)
        min_b, max_b = _project(normal, verts_b)
        if max_a < min_b or max_b < min_a:
            return False
    return True


def _project(axis: Point2D, verts: List[Point2D]) -> Tuple[float, float]:
    ax, ay = axis
    length = math.hypot(ax, ay) or 1.0
    ax /= length
    ay /= length
    dots = [vx * ax + vy * ay for vx, vy in verts]
    return min(dots), max(dots)


def _distance_point_to_segment(point: Point2D, start: Point2D, end: Point2D) -> float:
    px, py = point
    sx, sy = start
    ex, ey = end
    dx = ex - sx
    dy = ey - sy
    if dx == 0 and dy == 0:
        return math.hypot(px - sx, py - sy)
    t = ((px - sx) * dx + (py - sy) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    proj_x = sx + t * dx
    proj_y = sy + t * dy
    return math.hypot(px - proj_x, py - proj_y)


@dataclass(frozen=True)
class CollisionManifold:
    """Lightweight contact info for impulse/position solvers."""

    normal: Point2D
    penetration: float
    contact_point: Point2D


def collision_manifold(
    shape_a: Shape2D, pose_a: Pose2D, shape_b: Shape2D, pose_b: Pose2D
) -> Optional[CollisionManifold]:
    """Compute a simple manifold (normal points from A to B)."""
    if isinstance(shape_a, Circle) and isinstance(shape_b, Circle):
        return _circle_vs_circle_manifold(shape_a, pose_a, shape_b, pose_b)
    if isinstance(shape_a, Circle) and isinstance(shape_b, Polygon):
        return _circle_vs_polygon_manifold(shape_a, pose_a, shape_b, pose_b)
    if isinstance(shape_a, Polygon) and isinstance(shape_b, Circle):
        manifold = _circle_vs_polygon_manifold(shape_b, pose_b, shape_a, pose_a)
        if manifold:
            n = manifold.normal
            return CollisionManifold(normal=(-n[0], -n[1]), penetration=manifold.penetration, contact_point=manifold.contact_point)
        return None
    if isinstance(shape_a, Polygon) and isinstance(shape_b, Polygon):
        return _polygon_vs_polygon_manifold(shape_a, pose_a, shape_b, pose_b)
    return None


def _circle_vs_circle_manifold(a: Circle, pose_a: Pose2D, b: Circle, pose_b: Pose2D) -> Optional[CollisionManifold]:
    dx = pose_b.x - pose_a.x
    dy = pose_b.y - pose_a.y
    dist_sq = dx * dx + dy * dy
    radius_sum = a.radius + b.radius
    if dist_sq >= radius_sum * radius_sum:
        return None
    dist = math.sqrt(dist_sq) if dist_sq > 1e-12 else 0.0
    penetration = radius_sum - dist
    if dist > 1e-6:
        normal = (dx / dist, dy / dist)
        contact = (pose_a.x + normal[0] * a.radius, pose_a.y + normal[1] * a.radius)
    else:
        normal = (1.0, 0.0)
        contact = (pose_a.x, pose_a.y)
    return CollisionManifold(normal=normal, penetration=penetration, contact_point=contact)


def _circle_vs_polygon_manifold(circle: Circle, pose_circle: Pose2D, polygon: Polygon, pose_polygon: Pose2D) -> Optional[CollisionManifold]:
    world_verts = polygon._world_vertices(pose_polygon)
    center = (pose_circle.x, pose_circle.y)
    closest_dist = float("inf")
    closest_point = None
    # Check vertices
    for vx, vy in world_verts:
        d = math.hypot(center[0] - vx, center[1] - vy)
        if d < closest_dist:
            closest_dist = d
            closest_point = (vx, vy)
    # Check edges
    for i in range(len(world_verts)):
        start = world_verts[i]
        end = world_verts[(i + 1) % len(world_verts)]
        d = _distance_point_to_segment(center, start, end)
        if d < closest_dist:
            closest_dist = d
            # project center to edge
            sx, sy = start
            ex, ey = end
            dx = ex - sx
            dy = ey - sy
            if dx == 0 and dy == 0:
                proj = start
            else:
                t = ((center[0] - sx) * dx + (center[1] - sy) * dy) / (dx * dx + dy * dy)
                t = max(0.0, min(1.0, t))
                proj = (sx + t * dx, sy + t * dy)
            closest_point = proj
    penetration = circle.radius - closest_dist
    if penetration <= 0.0 or closest_point is None:
        return None
    nx = center[0] - closest_point[0]
    ny = center[1] - closest_point[1]
    norm_len = math.hypot(nx, ny) or 1.0
    normal = (nx / norm_len, ny / norm_len)
    contact = closest_point
    return CollisionManifold(normal=normal, penetration=penetration, contact_point=contact)


def _polygon_vs_polygon_manifold(a: Polygon, pose_a: Pose2D, b: Polygon, pose_b: Pose2D) -> Optional[CollisionManifold]:
    verts_a = a._world_vertices(pose_a)
    verts_b = b._world_vertices(pose_b)
    penetration = float("inf")
    best_axis = None
    best_point = None

    def _check_axes(verts1, verts2, current_penetration, current_axis, current_point):
        pen = current_penetration
        axis = current_axis
        point = current_point
        for i in range(len(verts1)):
            x1, y1 = verts1[i]
            x2, y2 = verts1[(i + 1) % len(verts1)]
            edge_x = x2 - x1
            edge_y = y2 - y1
            normal = (-edge_y, edge_x)
            min1, max1 = _project(normal, verts1)
            min2, max2 = _project(normal, verts2)
            overlap = min(max1, max2) - max(min1, min2)
            if overlap <= 0:
                return None, None, None
            if overlap < pen:
                pen = overlap
                length = math.hypot(*normal) or 1.0
                axis = (normal[0] / length, normal[1] / length)
                point = verts1[i]
        return pen, axis, point

    penetration, best_axis, best_point = _check_axes(verts_a, verts_b, penetration, best_axis, best_point)
    if best_axis is None:
        return None
    penetration, best_axis, best_point = _check_axes(verts_b, verts_a, penetration, best_axis, best_point)
    if best_axis is None:
        return None
    # normal from A to B: ensure direction points from A to B
    center_a = _centroid(verts_a)
    center_b = _centroid(verts_b)
    dir_ab = (center_b[0] - center_a[0], center_b[1] - center_a[1])
    if best_axis[0] * dir_ab[0] + best_axis[1] * dir_ab[1] < 0:
        best_axis = (-best_axis[0], -best_axis[1])
    contact = best_point if best_point is not None else center_a
    return CollisionManifold(normal=best_axis, penetration=penetration, contact_point=contact)


def _centroid(verts: List[Point2D]) -> Point2D:
    if not verts:
        return (0.0, 0.0)
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


__all__ = [
    "Shape2D",
    "Circle",
    "Polygon",
    "BoundingBox",
    "CollisionManifold",
    "collision_manifold",
]
