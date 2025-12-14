"""Reference motor/actuator implementations."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional

from low_level_mechanics.world import Pose2D, World
from low_level_mechanics.entities import SimObject

from .base import Motor
from .presets import WHEEL_PRESETS, WheelMotorPreset


def _apply_impulse(body: SimObject, impulse: tuple[float, float], contact_point: tuple[float, float]) -> None:
    """Apply an impulse at a world point, updating linear and angular velocity."""
    if not body.can_move or body.state.mass <= 0:
        return
    inv_mass = 1.0 / max(body.state.mass, 1e-9)
    inv_inertia = 0.0 if body.state.moment_of_inertia <= 0 else 1.0 / body.state.moment_of_inertia
    rx = contact_point[0] - body.pose.x
    ry = contact_point[1] - body.pose.y
    jx, jy = impulse
    vx, vy = body.state.linear_velocity
    body.state.linear_velocity = (vx + jx * inv_mass, vy + jy * inv_mass)
    body.state.angular_velocity += (rx * jy - ry * jx) * inv_inertia


def _contact_velocity(body: SimObject, contact_point: tuple[float, float]) -> tuple[float, float]:
    """Compute the velocity of a world-space contact point on the body."""
    vx, vy = body.state.linear_velocity
    omega = body.state.angular_velocity
    rx = contact_point[0] - body.pose.x
    ry = contact_point[1] - body.pose.y
    return (vx - omega * ry, vy + omega * rx)


def _inv_mass_term(body: SimObject, contact_point: tuple[float, float], axis: tuple[float, float]) -> float:
    """Effective inverse mass along an axis at a contact point (2D rigid body)."""
    inv_mass = 0.0 if not body.can_move or body.state.mass <= 0 else 1.0 / body.state.mass
    inv_inertia = 0.0 if body.state.moment_of_inertia <= 0 else 1.0 / body.state.moment_of_inertia
    rx = contact_point[0] - body.pose.x
    ry = contact_point[1] - body.pose.y
    r_cross_n = rx * axis[1] - ry * axis[0]
    return inv_mass + (r_cross_n * r_cross_n) * inv_inertia


def _solve_wheel_traction(
    body: SimObject,
    contact_point: tuple[float, float],
    forward: tuple[float, float],
    preferred_speed: float,
    drive_impulse_cap: float,
    *,
    mu_long: float,
    mu_lat: float,
    normal_load: float,
    lateral_damping: float,
    dt: float,
) -> "TractionReport":
    """Track a preferred tangential speed with friction/traction-limited impulses."""
    preferred_speed = float(preferred_speed)
    if not body.can_move:
        return TractionReport(
            step=None,
            slip_ratio=0.0,
            lateral_slip=0.0,
            wheel_speed=preferred_speed,
            preferred_speed=preferred_speed,
            contact_speed=0.0,
            contact_speed_after=0.0,
            desired_longitudinal_impulse=0.0,
            applied_longitudinal_impulse=0.0,
            applied_lateral_impulse=0.0,
            normal_load=normal_load,
        )
    normal_load = max(normal_load, 0.0)
    lateral_damping = _clamp(lateral_damping, 0.0, 1.0)
    lateral = (-forward[1], forward[0])
    max_long_impulse = max(0.0, abs(mu_long) * normal_load * dt)
    max_lat_impulse = max(0.0, abs(mu_lat) * normal_load * dt)
    drive_cap = max(0.0, abs(drive_impulse_cap))

    vcx, vcy = _contact_velocity(body, contact_point)
    v_long = vcx * forward[0] + vcy * forward[1]
    v_lat = vcx * lateral[0] + vcy * lateral[1]
    slip_denom = max(abs(preferred_speed), abs(v_long), 0.05)
    slip_ratio = (preferred_speed - v_long) / slip_denom

    # Lateral slip correction (constraint-like)
    j_lat = 0.0
    if max_lat_impulse > 0.0 and abs(v_lat) > 1e-6:
        inv_mass_lat = _inv_mass_term(body, contact_point, lateral)
        if inv_mass_lat > 1e-9:
            target_j_lat = -v_lat / inv_mass_lat
            target_j_lat *= (1.0 - lateral_damping)
            j_lat = _clamp(target_j_lat, -max_lat_impulse, max_lat_impulse)
            _apply_impulse(body, (lateral[0] * j_lat, lateral[1] * j_lat), contact_point)

    # Longitudinal drive toward preferred speed with traction + drive caps
    inv_mass_long = _inv_mass_term(body, contact_point, forward)
    desired_impulse = 0.0
    j_drive = 0.0
    if inv_mass_long > 1e-9:
        desired_impulse = (preferred_speed - v_long) / inv_mass_long
        long_limit = max_long_impulse
        if max_long_impulse > 0.0 and max_lat_impulse > 0.0:
            lat_ratio = min(1.0, abs(j_lat) / (max_lat_impulse + 1e-9))
            long_limit = max_long_impulse * max(0.0, 1.0 - 0.5 * lat_ratio)
        if drive_cap > 0.0:
            long_limit = min(long_limit, drive_cap) if long_limit > 0.0 else drive_cap
        if long_limit > 0.0:
            j_drive = _clamp(desired_impulse, -long_limit, long_limit)
            if j_drive != 0.0:
                _apply_impulse(body, (forward[0] * j_drive, forward[1] * j_drive), contact_point)

    v_post_long = _contact_velocity(body, contact_point)
    v_post = v_post_long[0] * forward[0] + v_post_long[1] * forward[1]

    return TractionReport(
        step=None,
        slip_ratio=slip_ratio,
        lateral_slip=v_lat,
        wheel_speed=preferred_speed,
        preferred_speed=preferred_speed,
        contact_speed=v_long,
        contact_speed_after=v_post,
        desired_longitudinal_impulse=desired_impulse,
        applied_longitudinal_impulse=j_drive,
        applied_lateral_impulse=j_lat,
        normal_load=normal_load,
    )


@dataclass
class TractionReport:
    """Telemetry for a wheel traction evaluation."""

    step: Optional[int]
    slip_ratio: float
    lateral_slip: float
    wheel_speed: float
    preferred_speed: float
    contact_speed: float
    contact_speed_after: float
    desired_longitudinal_impulse: float
    applied_longitudinal_impulse: float
    applied_lateral_impulse: float
    normal_load: float


class WheelMotor(Motor):
    """Applies a longitudinal force along the wheel's heading with traction limits."""

    def __init__(
        self,
        name: str,
        *,
        mount_pose: Pose2D | None = None,
        max_force: float = 2.0,
        mu_long: float = 0.9,
        mu_lat: float = 0.8,
        g_equiv: float = 9.81,
        normal_force: float | None = None,
        lateral_damping: float = 0.25,
        wheel_count: int = 2,
        wheel_radius: float = 0.03,
        response_time: float = 0.05,
        max_wheel_omega: float = 40.0,
    ) -> None:
        super().__init__(name, mount_pose=mount_pose, max_command=1.0)
        self.max_force = max_force
        self.mu_long = mu_long
        self.mu_lat = mu_lat
        self.g_equiv = g_equiv
        self.normal_force = normal_force
        self.lateral_damping = lateral_damping
        self.wheel_count = max(1, wheel_count)
        self.wheel_radius = wheel_radius
        self.response_time = max(response_time, 1e-4)
        self.max_wheel_omega = max_wheel_omega
        self.angular_speed = 0.0
        self.last_report: Optional[TractionReport] = None

    def _apply(self, value: float, world: World, dt: float) -> None:
        if not self.parent or not self.parent.can_move:
            return
        pose = self.parent.pose.compose(self.mount_pose)
        direction = (math.cos(pose.theta), math.sin(pose.theta))
        normal_load = self.normal_force
        if normal_load is None:
            normal_load = self.parent.state.mass * self.g_equiv / float(max(self.wheel_count, 1))
        blend = min(1.0, dt / self.response_time)
        target_omega = value * self.max_wheel_omega
        self.angular_speed += (target_omega - self.angular_speed) * blend
        wheel_speed = self.angular_speed * self.wheel_radius
        drive_impulse_cap = abs(self.max_force) * dt
        report = _solve_wheel_traction(
            self.parent,
            (pose.x, pose.y),
            direction,
            wheel_speed,
            drive_impulse_cap,
            mu_long=self.mu_long,
            mu_lat=self.mu_lat,
            normal_load=normal_load,
            lateral_damping=self.lateral_damping,
            dt=dt,
        )
        traction_ratio = 0.0
        if abs(report.desired_longitudinal_impulse) > 1e-9:
            traction_ratio = min(1.0, abs(report.applied_longitudinal_impulse) / abs(report.desired_longitudinal_impulse))
        ground_omega = report.contact_speed_after / max(self.wheel_radius, 1e-6)
        self.angular_speed = self.angular_speed * (1.0 - 0.4 * traction_ratio) + ground_omega * (0.4 * traction_ratio)
        report.step = getattr(world, "step_index", None)
        self.last_report = report

    def as_dict(self):
        data = super().as_dict()
        data.update({
            "max_force": self.max_force,
            "mu_long": self.mu_long,
            "mu_lat": self.mu_lat,
            "g_equiv": self.g_equiv,
            "normal_force": self.normal_force,
            "lateral_damping": self.lateral_damping,
            "wheel_count": self.wheel_count,
            "wheel_radius": self.wheel_radius,
            "response_time": self.response_time,
            "max_wheel_omega": self.max_wheel_omega,
        })
        return data

    @property
    def visual_tag(self) -> str:
        return "motor.wheel"

    def visual_state(self):
        if not self.parent:
            return None
        return {
            "command": self.last_command,
            "max_force": self.max_force,
            "detail": "force",
        }


class WheelMotorDetailed(Motor):
    """Wheel model that converts commands into torque/speed with traction limits."""

    def __init__(
        self,
        name: str,
        preset: str = "wheel_small",
        *,
        mount_pose: Pose2D | None = None,
    ) -> None:
        preset_info = WHEEL_PRESETS[preset]
        super().__init__(name, mount_pose=mount_pose, max_command=preset_info.max_command)
        self.preset = preset_info
        self.angular_speed = 0.0
        self.last_report: Optional[TractionReport] = None

    def _apply(self, value: float, world: World, dt: float) -> None:
        if not self.parent or not self.parent.can_move:
            return
        torque = self.preset.max_torque * value
        heading = self.parent.pose.compose(self.mount_pose)
        direction = (math.cos(heading.theta), math.sin(heading.theta))
        normal_load = self.preset.normal_force
        if normal_load is None:
            normal_load = self.parent.state.mass * self.preset.g_equiv / float(max(self.preset.wheel_count, 1))
        wheel_speed = self.angular_speed * self.preset.wheel_radius
        drive_impulse_cap = abs(self.preset.max_torque * self.preset.gear_ratio / self.preset.wheel_radius) * dt
        report = _solve_wheel_traction(
            self.parent,
            (heading.x, heading.y),
            direction,
            wheel_speed,
            drive_impulse_cap,
            mu_long=self.preset.mu_long,
            mu_lat=self.preset.mu_lat,
            normal_load=normal_load,
            lateral_damping=self.preset.lateral_damping,
            dt=dt,
        )
        reaction_torque = 0.0
        if dt > 0:
            reaction_torque = (report.applied_longitudinal_impulse / dt) * self.preset.wheel_radius / max(self.preset.gear_ratio, 1e-6)
        net_torque = torque - reaction_torque
        self.angular_speed += (net_torque / max(self.preset.motor_inertia, 1e-6)) * dt
        self.angular_speed = _clamp(self.angular_speed, -100.0, 100.0)
        traction_ratio = 0.0
        if abs(report.desired_longitudinal_impulse) > 1e-9:
            traction_ratio = min(1.0, abs(report.applied_longitudinal_impulse) / abs(report.desired_longitudinal_impulse))
        ground_omega = report.contact_speed_after / max(self.preset.wheel_radius, 1e-6)
        self.angular_speed = self.angular_speed * (1.0 - 0.3 * traction_ratio) + ground_omega * (0.3 * traction_ratio)
        report.step = getattr(world, "step_index", None)
        self.last_report = report

    def as_dict(self):
        data = super().as_dict()
        data.update({
            "preset": self.preset.name,
            "wheel_radius": self.preset.wheel_radius,
            "max_torque": self.preset.max_torque,
            "mu_long": self.preset.mu_long,
            "mu_lat": self.preset.mu_lat,
            "g_equiv": self.preset.g_equiv,
            "normal_force": self.preset.normal_force,
            "lateral_damping": self.preset.lateral_damping,
            "wheel_count": self.preset.wheel_count,
        })
        return data

    @property
    def visual_tag(self) -> str:
        return "motor.wheel"

    def visual_state(self):
        if not self.parent:
            return None
        return {
            "command": self.last_command,
            "max_torque": self.preset.max_torque,
            "wheel_radius": self.preset.wheel_radius,
            "angular_speed": self.angular_speed,
            "detail": "torque",
        }


@dataclass
class DifferentialDrive:
    """Convenience wrapper around two wheel motors."""

    wheel_base: float = 0.18
    max_force: float = 2.0
    detailed: bool = False
    preset: str = "wheel_small"
    mu_long: float = 0.9
    mu_lat: float = 0.8
    wheel_radius: float = 0.03
    g_equiv: float = 9.81
    lateral_damping: float = 0.25
    response_time: float = 0.05
    max_wheel_omega: float = 40.0

    def __post_init__(self) -> None:
        half = self.wheel_base / 2
        motor_cls = WheelMotorDetailed if self.detailed else WheelMotor
        motor_kwargs = {"preset": self.preset} if self.detailed else {
            "max_force": self.max_force,
            "mu_long": self.mu_long,
            "mu_lat": self.mu_lat,
            "wheel_radius": self.wheel_radius,
            "g_equiv": self.g_equiv,
            "lateral_damping": self.lateral_damping,
            "response_time": self.response_time,
            "max_wheel_omega": self.max_wheel_omega,
        }
        self.left = motor_cls(
            name="left_wheel",
            mount_pose=Pose2D(0.0, half, 0.0),
            **motor_kwargs,
        )
        self.right = motor_cls(
            name="right_wheel",
            mount_pose=Pose2D(0.0, -half, 0.0),
            **motor_kwargs,
        )

    def attach(self, parent: SimObject) -> None:
        self.left.attach(parent)
        self.right.attach(parent)

    def command(self, left: float, right: float, world: World, dt: float) -> None:
        self.left.command(left, world, dt)
        self.right.command(right, world, dt)

    def as_dict(self) -> dict:
        return {
            "wheel_base": self.wheel_base,
            "left": self.left.as_dict(),
            "right": self.right.as_dict(),
        }


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))
