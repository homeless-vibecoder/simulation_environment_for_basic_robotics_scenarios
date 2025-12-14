"""Robot presets with binary line sensors for the proper line follower suite."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

from low_level_mechanics.entities import DynamicState, SimObject
from low_level_mechanics.geometry import Circle
from low_level_mechanics.materials import MaterialProperties
from low_level_mechanics.world import Pose2D, World

from middle_level_library.motors import DifferentialDrive
from middle_level_library.sensors import DistanceSensor, IMUSensor, LineSensor


@dataclass(frozen=True)
class RobotSpec:
    name: str
    radius: float
    wheel_base: float
    sensor_offsets: Sequence[Tuple[float, float]]
    sensor_preset: str = "line_basic"
    distance_preset: str = "range_short"
    detailed_drive: bool = False
    tire_friction: float = 1.4
    tire_traction: float = 1.0
    drive_max_force: float = 2.6
    mass: float = 1.0
    moment_of_inertia: float = 0.035


@dataclass
class LineFollowerRobot:
    robot: SimObject
    drive: DifferentialDrive
    left_sensor: "BinaryLineSensor"
    right_sensor: "BinaryLineSensor"
    distance_sensor: DistanceSensor
    imu: IMUSensor
    state: dict = field(default_factory=dict)

    def attach_components(self) -> None:
        for component in (self.left_sensor, self.right_sensor, self.distance_sensor, self.imu):
            component.attach(self.robot)
        self.drive.attach(self.robot)

    def read_line_bits(self, world: World, dt: float) -> Tuple[int | None, int | None]:
        left = self.left_sensor.read(world, dt)
        right = self.right_sensor.read(world, dt)
        left_bit = left.value if left else None
        right_bit = right.value if right else None
        if left_bit is not None:
            self.state["left_line"] = left_bit
        if right_bit is not None:
            self.state["right_line"] = right_bit
        return left_bit, right_bit


class BinaryLineSensor(LineSensor):
    """Line sensor that reports a binary 0/1 based on thresholding."""

    def __init__(
        self,
        name: str,
        *,
        threshold: float = 0.5,
        mount_pose: Pose2D | None = None,
        preset: str = "line_basic",
    ) -> None:
        super().__init__(name, mount_pose=mount_pose, preset=preset)
        self.threshold = threshold

    def read(self, world: World, dt: float):
        reading = super().read(world, dt)
        if reading is None:
            return None
        bit = 1 if reading.value >= self.threshold else 0
        reading.value = bit
        return reading


ROBOT_PRESETS: Dict[str, RobotSpec] = {
    "edge_dual": RobotSpec(
        name="edge_dual",
        radius=0.11,
        wheel_base=0.22,
        sensor_offsets=((0.13, 0.07), (0.13, -0.07)),
        tire_friction=1.6,
        tire_traction=1.25,
        drive_max_force=3.0,
        mass=0.65,
        moment_of_inertia=0.02,
    ),
    "forward_probe": RobotSpec(
        name="forward_probe",
        radius=0.12,
        wheel_base=0.24,
        sensor_offsets=((0.18, 0.08), (0.18, -0.08)),
        detailed_drive=True,
        tire_friction=1.5,
        tire_traction=1.15,
        drive_max_force=3.2,
        mass=0.85,
        moment_of_inertia=0.03,
    ),
    "wide_body": RobotSpec(
        name="wide_body",
        radius=0.14,
        wheel_base=0.28,
        sensor_offsets=((0.12, 0.1), (0.12, -0.1)),
        sensor_preset="line_basic",
        tire_friction=1.45,
        tire_traction=1.1,
        drive_max_force=3.1,
        mass=0.95,
        moment_of_inertia=0.028,
    ),
}


def list_robot_presets() -> List[str]:
    return sorted(ROBOT_PRESETS.keys())


def create_robot(
    spec_name: str = "edge_dual",
    *,
    name: str = "proper_bot",
    pose: Pose2D | None = None,
) -> LineFollowerRobot:
    spec = _get_robot_spec(spec_name)
    pose = pose or Pose2D(-spec.radius * 3.0, 0.0, 0.0)
    robot = SimObject(
        name=name,
        pose=pose,
        shape=Circle(radius=spec.radius),
        material=MaterialProperties(
            friction=spec.tire_friction,
            traction=spec.tire_traction,
            reflectivity=0.15,
            custom={"color": (200, 60, 80)},
        ),
        can_move=True,
        dynamic_state=DynamicState(
            linear_velocity=(0.0, 0.0),
            angular_velocity=0.0,
            mass=spec.mass,
            moment_of_inertia=spec.moment_of_inertia,
        ),
    )
    drive = DifferentialDrive(
        wheel_base=spec.wheel_base,
        detailed=spec.detailed_drive,
        max_force=spec.drive_max_force,
        mu_long=spec.tire_traction,
        mu_lat=spec.tire_friction,
    )
    left_sensor = BinaryLineSensor(
        name=f"{name}_line_left",
        mount_pose=Pose2D(spec.sensor_offsets[0][0], spec.sensor_offsets[0][1], 0.0),
        preset=spec.sensor_preset,
    )
    right_sensor = BinaryLineSensor(
        name=f"{name}_line_right",
        mount_pose=Pose2D(spec.sensor_offsets[1][0], spec.sensor_offsets[1][1], 0.0),
        preset=spec.sensor_preset,
    )
    distance_sensor = DistanceSensor(
        name=f"{name}_range",
        preset=spec.distance_preset,
        mount_pose=Pose2D(spec.radius + 0.02, 0.0, 0.0),
    )
    imu = IMUSensor(name=f"{name}_imu")
    robot_ctx = LineFollowerRobot(
        robot=robot,
        drive=drive,
        left_sensor=left_sensor,
        right_sensor=right_sensor,
        distance_sensor=distance_sensor,
        imu=imu,
    )
    robot_ctx.attach_components()
    return robot_ctx


def _get_robot_spec(name: str) -> RobotSpec:
    try:
        return ROBOT_PRESETS[name]
    except KeyError as exc:  # pragma: no cover - defensive
        raise KeyError(f"Unknown robot preset '{name}'. Available: {list_robot_presets()}") from exc


__all__ = [
    "BinaryLineSensor",
    "LineFollowerRobot",
    "RobotSpec",
    "ROBOT_PRESETS",
    "create_robot",
    "list_robot_presets",
]

