# Physics Simulator – Multi-Resolution Overview

This document explains how the simulation stack works, from a high-level view down to implementation details. It is structured so you can skim the overview, dive into subsystem summaries, and then read detailed mechanics as needed.

---

## 1) High-Level Overview

- **Purpose:** A 2D top‑down simulator for small robots. It models rigid bodies, simple joints, collisions, and devices (motors/sensors) to run controllers inside interactive apps (`runner.py`, `designer.py`) or headless.
- **Core loop:** Each `Simulator.step(dt)` performs sensor reads → controller tick → integrate bodies → solve joints → resolve contacts → advance time.
- **Top-down defaults:** Gravity is zeroed for bird’s‑eye use; terrain can be disabled for an empty plane. Stability clamps prevent runaway velocities and teleporting.
- **Configuration:** Scenarios load from JSON (`world.json`, `robot.json`) into dataclasses (`WorldConfig`, `RobotConfig`, etc.). Apps add the project root to `sys.path` and hot-reload controllers.

---

## 2) Subsystem Summaries (Semi-Detailed)

### 2.1 Data + Config
- `core/config.py` defines `WorldConfig` (timestep, gravity, terrain), `RobotConfig` (bodies, joints, actuators, sensors), and helpers for JSON load/save.
- `core/persistence.py` (via `load_scenario`) reads scenario JSONs into configs, then the app constructs a `Simulator`.

### 2.2 World Geometry and Bodies
- Shapes: Convex polygons and circles (`low_level_mechanics/geometry.py`) with SAT-based intersection and collision manifolds (normal, penetration, contact point).
- Entities: `SimObject` + `DynamicState` (`entities.py`) hold pose, velocities, mass/inertia, and pending forces/torques. Integration is semi-implicit Euler with pose advancement.

### 2.3 Simulator Core
- Located in `core/simulator.py`. Owns bodies, joints, sensors, motors, controller, RNG, and step time.
- Loading: Builds terrain bodies (optional), robot bodies, joints, devices; sets `dt` and gravity (zeroed by default for top-down).
- Step pipeline:
  1) Read sensors (respecting sensor update rates).
  2) Call controller `step/update` with sensor readings and `dt`.
  3) Integrate bodies (gravity → damping → velocity clamps → integrate → pose sanitize).
  4) Solve joints (XPBD-style distance constraints with capped correction).
  5) Resolve contacts (manifold-based impulses + positional correction with clamps and friction).
  6) Record last commands/readings; advance time/step index; sanity-check displacement.
- Safety rails: NaN checks, linear/angular speed clamps, max step translation clamp, capped penetration corrections, restitution/friction clamping.

### 2.4 Devices (Motors/Sensors)
- Motors: `middle_level_library/motors.py` (wheel force or detailed torque model). Motors mount with a pose relative to the parent body and apply forces at the mount point.
- Sensors: `middle_level_library/sensors.py` (line, distance ray-march, IMU, encoder) using parent pose composition and world sampling.
- Base abstractions: `MountedComponent`, `Motor`, `Sensor` (`middle_level_library/base.py`), providing mount pose composition and update cadence.

### 2.5 Apps and Entry Points
- `apps/runner.py`: Interactive runner; loads scenario, steps the simulator at fixed `dt`, shows UI panels, hot-reloads controller, supports empty-world/zero‑g flags.
- `apps/designer.py`: Editor for world/robot configs and device placement.
- `app.py`: Minimal milestone app using the same simulator.

---

## 3) Detailed Mechanics

### 3.1 Poses and Transforms
- `Pose2D` (`world.py`): translation (x, y) and rotation (theta). Provides `transform_point`, `compose` (parent ∘ child), `inverse`, and tuple/dict helpers.
- Mounting: Sensor/motor/world points are computed via `parent.pose.compose(mount_pose)`; joints use anchors transformed by each body pose.

### 3.2 Integration
- Forces/torques accumulate per step via `apply_force`/`apply_torque`.
- In `_integrate_bodies(dt)`:
  - Gravity applied (zero for top-down).
  - Damping: linear and angular multiplied by tunable factors.
  - Velocity clamps: linear speed and angular speed capped; NaNs reset to zero.
  - Integrator: `DynamicState.advance_pose` moves pose by `v * dt` and rotates by `omega * dt`.
  - Pose sanity: invalid poses reset.
  - Impulses cleared each step.

### 3.3 Joints (XPBD-style distance constraint)
- For each joint: compute anchor world positions, distance error to target (often 0 for rigid/hinge anchor).
- Compute inverse masses, compliance, and update `lambda` with capped correction to avoid overshoot.
- Apply positional corrections proportionally to inverse masses; clamp max correction per step.

### 3.4 Contacts
- Broad-phase via pairwise shapes (small counts). Manifold from `collision_manifold` gives normal, penetration, contact point.
- Positional correction: Baumgarte-like, with percent, slop, and max correction clamps.
- Impulse resolution:
  - Normal impulse with clamped restitution (0–1), skipping separating contacts.
  - Friction: Coulomb clamp `jt ∈ [-μ|j|, μ|j|]` along tangent.
  - Post-impulse velocity sanitization.

### 3.5 Sensors
- Line/array: sample `line_intensity` field of materials at world points.
- Distance: ray-march forward up to preset max range; ignores parent body.
- IMU/encoder: read linear/angular velocity with optional noise; respect update rates.
- Each sensor stores last reading and metadata (timestamp, preset).

### 3.6 Motors
- `WheelMotor`: tracks a preferred tangential speed (command → wheel omega → tangential speed) and applies impulses to drive the contact point toward that speed; impulses are clamped by motor authority and traction.
- `WheelMotorDetailed`: torque → angular speed with inertia and gear ratio; uses the same traction-aware tangential-speed solver, with reaction torque fed back into the motor.
- Wheel traction (top-down uses virtual load): normal load `N = normal_force` or `mass * g_equiv / wheel_count` (defaults g_equiv=9.81, wheel_count=2). Longitudinal impulses clamp to `mu_long * N`, lateral slip constrained with `mu_lat * N` and damping (`lateral_damping`) to avoid oscillation. Configure via actuator params or wheel presets (mu_long, mu_lat, g_equiv/normal_force, lateral_damping, wheel_count, wheel_radius, max_force/preset).
- Auto wheel-count: if `wheel_count` is omitted, the simulator counts wheel motors on the same body and splits the virtual normal load equally. Override by setting `wheel_count` or `normal_force`.
- `DifferentialDrive`: two wheels with base separation; commands left/right.

### 3.7 Controller Loop
- Controller module loaded from scenario folder (hot-reloadable). If a `Controller` class is present, `step(sensor_readings, dt)` is called each sim step.
- Errors captured and surfaced to UI; sim pauses or displays error logs.

### 3.8 Snapshots and Teleport Safety
- `snapshot()` exports time/step, body poses/velocities, optional controller state.
- `apply_snapshot()` restores poses/velocities and controller state if supported.
- Step sanity: max per-step translation clamp prevents teleporting; warnings recorded.

---

## 4) Configuration and Scenarios

- **World (`world.json`):** gravity (default 0,0 for top-down), timestep, optional terrain objects (each has a `BodyConfig`). For empty-plane runs, terrain is empty and gravity is zero.
- **Robot (`robot.json`):** bodies (polygon points, mass/inertia), joints, actuators (mount pose, params), sensors (mount pose, params), spawn pose, controller module.
- **Materials:** friction, restitution, reflectivity/line signals, roughness/thickness, and optional custom fields.
- **Runtime toggles:** In runner, `top_down_mode` and `force_empty_world` map to `Simulator.load(..., top_down=True, ignore_terrain=True)`.

---

## 5) Usage Notes and Tuning

- **Timestep:** Default `dt = 1/120`. Runner substeps clamp backlog to avoid spiral-of-death if the frame stalls.
- **Stability knobs (`Simulator`):** linear/angular damping, speed clamps, contact correction percent/slop/max penetration, max step translation.
- **Zero-G top-down:** Gravity forced to `(0,0)` for bird’s-eye; use nonzero gravity only if simulating vertical effects.
- **Empty world:** Skip terrain for isolation; add terrain only if you need lines/obstacles, but ensure materials are sensible (friction/restitution) to avoid bounce.
- **Sensors/mounts:** All mounts compose via body pose; check mount_pose units (meters, radians) to avoid apparent offsets.
- **Controllers:** Keep commands bounded (motors clamp), and watch for NaNs; errors are captured and shown in runner logs.
- **Logging and snapshots:** Runner supports logging signals and saving/restoring snapshots for debugging and regression checks.

---

## 6) File Map (Key Pieces)

- `core/simulator.py` — main simulation loop, joints, contacts, safety rails.
- `core/config.py` — dataclasses for world/robot/joints/actuators/sensors.
- `low_level_mechanics/geometry.py` — shapes, SAT collision, manifolds.
- `low_level_mechanics/entities.py` — SimObject, DynamicState, integration.
- `low_level_mechanics/materials.py` — friction/restitution/fields.
- `middle_level_library/motors.py` — wheel motors and differential drive.
- `middle_level_library/sensors.py` — line, distance, IMU, encoder sensors.
- `apps/runner.py` — interactive runner (top-down, empty-world toggles, UI).
- `apps/designer.py` — scenario editor for bodies/devices.
- `core/persistence.py` — scenario load/save helpers.
- `scenarios/*/world.json`, `robot.json` — scenario inputs.

---

## 7) Quick Start (Top-Down, Empty World)

1) Ensure scenario `world.json` has gravity `(0,0)` and empty `terrain`.
2) Run `apps/runner.py`; by default it loads with `top_down=True`, `ignore_terrain=True`.
3) Use the hover/panel menus to play/pause, step, reload code, and view panels (state, devices, logs, console).
4) Watch pose/velocity in the State panel; no gravity means the robot should only move when motors command forces.

---

## 8) Mental Model Cheat-Sheet

- **State:** Poses + velocities; forces/torques accumulate for one step.
- **Loop:** sense → control → integrate (with damping/clamps) → joints → contacts → advance time.
- **Contacts:** manifold → positional correction (clamped) + impulse + friction.
- **Joints:** XPBD distance constraint with capped correction.
- **Safety:** NaN guards, speed caps, step-distance cap.
- **Top-down:** gravity off; optional empty terrain for isolation.
