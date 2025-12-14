GUI plan — first draft (will iterate heavily)

Goals
- Run each scenario once; students edit code/robot inside GUI without restarting.
- Save all GUI edits back to files (robot designs, code, scenario settings).
- Make pieces modular: simulation core stays headless; UI swaps easily.

Target use cases (initial)
- Robot designer: drag/shape frame, set joints (rigid/hinge/loose), add constraints, place motors/sensors, name them for code use.
- Scenario runner (e.g., line follower): students edit controller code, see live variables, replay runs, and troubleshoot.

Architecture sketch
- Core sim: tick-based, UI-agnostic API (reset, step, get_state, set_state), deterministic with a seed.
- Renderer/viewport: pygame surface; support pan/zoom, selection highlights.
- UI widgets: prefer pygame + pygame_gui overlay (keeps single process, quick to bolt on).
- State bridge: command queue from UI to sim (play/pause/step, reload code, add part); sim publishes snapshots for viewport + inspector.
- Hot reload: each robot controller is its own module; on “Run/Upload”, write buffer to disk and importlib.reload; optionally reset robot state.
- Persistence: scenario folders (e.g., `scenarios/line_follower/`) hold `world.json` (layout), `robot.json` (parts), `controller.py` (student code), `replay/` logs.

Key features to surface in UI
- Transport: play/pause/step, time-scale slider, restart, seed entry, replay controls.
- Robot design: palette of primitives (body segments, wheels, caster), joints, constraints; drag/drop with ghost preview; property inspector (mass, size, limits, sensor ranges); option to place points and connect edges to form polygon bodies (convex or non-convex).
- Sensors/motors: add/remove, set fields (name, port/id, range, noise, saturation); color-coded indicators on canvas.
- Code editor tab: multiline editor, load/save, run/upload button, error panel; optional variable watch list and simple printf log view.
- Replay/troubleshoot: record actions + seed; scrub timeline; show sensor traces; mark exceptions and collisions.
- Snapshots: on pause (or any time), save a world snapshot to a JSON file; list snapshots in a browser panel; allow “load snapshot as starting point”, “duplicate”, and “delete”. Keep snapshot metadata (timestamp, sim time, note).
- Sensors/motors: ship a library of realistic presets (e.g., line sensor, IR/ultrasonic rangefinder, wheel encoder, gyro/IMU, DC motor, servo). Each preset has tuned parameters (noise, latency, saturation, drift, failure rate, power/torque, acceleration limits, backlash). Students mostly pick presets; advanced tuning UI can be minimal but available. Aim for believable behavior, even if the GUI surface stays simple.
- Display/customization:
  - Let students choose which values/overlays are visible and persist that preference (per scenario/user).
  - Keep the main viewport uncluttered; offer optional in-place cues (e.g., wheel arrows showing direction/force, sensor frustums/ranges).
  - Provide a “measurements layer” on the robot: users can attach measurement points/probes (e.g., motor speed, torque, sensor reading at location) and toggle their visibility.
  - Support opening data views in separate panels/windows (plots/logs) instead of drawing everything on the game window.

MVP cut (small first step)
- Line-follower scenario only.
- Single robot, fixed body; allow adding sensors (line sensors, distance) and motors via UI.
- Transport controls + code editor with hot reload + error display.
- Save/load to scenario folder (JSON for robot config, .py for controller).

Risks/considerations
- Need guardrails for student code (time budget per tick, try/except with tracebacks surfaced in UI).
- Keep deterministic mode for reproducible teaching moments; allow “record + replay”.
- Avoid coupling UI to sim internals so headless grading/testing still works.

Open questions for you
- Storage format OK as JSON+py per scenario, or prefer another layout?
- Is pygame + pygame_gui acceptable, or do you prefer a web UI (React/Monaco) talking to the sim?
- Should robot designer include arbitrary polygon bodies, or is a small set of parametric shapes enough for now?
- Do we need multi-robot support in the first milestone, or is one robot sufficient?

Decisions (round 1, from discussion)
- Storage: JSON (+ controller .py) per scenario is fine; keep it simple.
- UI stack: favor local pygame + pygame_gui for now (fast to ship, offline-friendly). Web UI is possible later but slower to build/deploy; keep sim core UI-agnostic so a web front-end remains an option.
- Robot designer: start lean—parametric shapes (rect/tri/circle wheels/body) plus user-drawn polygons by placing points and connecting edges (allowing convex or non-convex), hinge/rigid joints, basic constraints.
- Multi-robot: defer; single robot per scenario for milestone 1. Architect so adding more robots later is just adding multiple controllers and a tab/switcher.

Next planning steps
- Lock minimal file layout: e.g., `scenarios/<name>/world.json`, `robot.json`, `controller.py`, optional `replay/`, `snapshots/`.
- Sketch GUI panels: transport, palette, inspector, code editor, log/errors, replay strip.
- Define sim core API surface we need (reset, step, get_state snapshot, apply_state, load/save robot config).
- Decide minimal properties exposed in inspector (body size/mass, joint type/limits, sensor range/noise, motor limits).
- Confirm how “save from GUI” maps back to files (JSON for config, overwrite controller.py on upload).
- Design snapshot UX: snapshot list with metadata, buttons (load/set-as-start, duplicate, delete), and a “save snapshot” action available when paused.
- Define preset library and exposed tunables per type (sensors: noise, range, latency, reliability; motors: torque curve, accel, stall behavior, backlash, failure/noise).
- Candidate real-world–ish presets to mirror (target milestone 2 for specificity; milestone 1 uses generic “motor”, “distance”, “line”, “encoder”, “IMU” types):
  - Line sensor: Pololu QTR-8RC strip (per-sensor noise, response time, saturation).
  - Distance: HC-SR04 ultrasonic (cone angle, min range dead zone, latency/jitter, dropout rate).
  - Short-range IR: Sharp GP2Y0A21 (nonlinear range response, noise, latency).
  - IMU: MPU-6050 6DOF (gyro bias drift, accel noise, sample latency).
  - Wheel encoder: simple optical encoder (counts per rev, missed pulses at high speed).
  - DC gearmotor: small 6–12V (stall torque/current, free-run speed, torque-speed curve, accel limit/inertia, brownout risk).
  - Servo: hobby micro servo SG90-class (angle limits, speed, positional overshoot/backlash, stall).
- Measurement/analysis toolbox (prebuilt widgets students can drop in):
  - Time-series logger/plot for any signal (sensor, motor speed/torque, pose), with autoscale and export.
  - Simple processing options: moving average/low-pass, high-pass, threshold events, line-of-best-fit on windowed data.
  - Comparison view: plot two signals together or diff them.
  - Snapshot markers on plots (tie to sim snapshots/replay timeline).
  - Optional separate window/panel for plots to avoid clutter; quick toggle buttons on viewport to show/hide probes and arrows.

Milestones (plan to stage features; architect for easy extension)
- Milestone 1 (foundations): solid physics feel, cleaner low_level_mechanics structure, GUI basics (run/pause/step, code editor in separate window/tab, saving/loading controller.py; robot designer with rectangles and user-drawn polygons from points/edges, allowing convex and non-convex cycles; attach motors/sensors, basic measurement probes/time logger), snapshots, generic device types (generic motor, generic distance/line sensor, generic encoder/IMU), save/load configs. Keep code structured so advanced analysis/replay can drop in later.
- Milestone 2 (advanced troubleshooting + richer devices): detailed recording, replay scrub, rich analysis widgets (filters, comparisons, overlays), broader body shapes and multi-robot if needed, plus a wider library of specific sensor/motor models.

Physics/structure
- Improve/tune physics realism (friction, restitution, motor dynamics) as part of milestone 1.
- Simplify low_level_mechanics: separate independent parts (geometry, collision, dynamics, actuators) to reduce coupling and make future additions cleaner.

Robot body shapes
- Start with rectangles and user-defined polygons (convex or non-convex) built from placed points and chosen connections/edges; hinge/rigid joints for attachments. Store point/edge lists for persistence.

Clarifications to settle
- Are parametric shapes enough for the first designer (rect bodies + wheel/caster + simple arm segment)?
- Any must-have sensors/motors in milestone 1 (line sensor, distance/IR, encoder, gyro)?
- Is replay (record + scrub) part of the first milestone, or second?

Constraints/solver approach (to choose)
- Options:
  - Lagrange multipliers (iterative impulse/Gauss-Seidel) for constraints/joints; stable with proper mass/inertia, aligns with many 2D engines.
  - XPBD-style position projection for joints/contacts; good stability with larger timesteps, simpler parameterization (compliance).
  - Hybrid: velocity-based solver for contacts/friction, XPBD for joints/limits.
- Goal: keep it simple/robust for milestone 1; pick one path and avoid over-engineering. Decision: XPBD for joints/limits + impulse solver for contacts/friction. This is stable, fast enough, and straightforward to tune for teaching scenarios.
- Tuning defaults (reasonable starting points):
  - Fixed internal timestep ~1/120s; render at display rate with interpolation if needed.
  - Solver iterations: 8–12 for contacts; 4–8 for joints (XPBD); adjust if jitter appears.
  - XPBD: per-constraint compliance and damping with sensible defaults (e.g., moderately stiff, lightly damped); expose at most a single “stiffness” slider in UI later.
  - Impulse solver: warm-start cached impulses to reduce jitter; clamp impulses to avoid explosions.
  - Collision: decompose non-convex polygons internally before contact generation; store original point/edge data for persistence/UI.
  - Damping: modest linear/angular damping to tame energy gain; default friction and restitution values that “just work” (e.g., mu_static ~0.8, mu_dynamic ~0.6, restitution ~0.1–0.2 for teaching scenarios).

Materials/properties (keep useful but not over-elaborate)
- Render/appearance: color/albedo; optional roughness; sensor reflectivity per modality (line vs. distance/IR), and a “reflect chance” for probabilistic returns.
- Physics interaction: static/dynamic friction, restitution, damping; mass/inertia already in physics component.
- Sensor interaction: per-sensor-type reflectivity/absorption; optional noise modifier.
- Optional: thickness for distance/occlusion checks (can default).

Snapshot content
- Include controller state in snapshots (milestone 1) so rewinding and rerunning resumes code state as well as physics (poses/velocities).

Data model / file layout (draft)
- Objects/entities have: `id`, `type`, `name`, `transform` (pos, rot, optional center offset), `tags`, and a set of components.
- Components (separable to keep things clean):
  - Physics: mass, inertia, static/dynamic friction, restitution, linear/angular damping, is_static, collision layer/mask.
  - Shape: polygon defined by `points` (local coords) and `edges` (indices) to allow convex or non-convex; cached AABB. (For physics we may decompose internally, but we store the original point/edge set.)
  - Material/render: color, reflectivity/albedo, sensor_reflectivity per sensor type (e.g., line vs. distance), optional texture id.
  - Joints/constraints: parent_id, child_id, type (hinge/rigid/slider), anchor(s), limits, stiffness/damping, break force.
  - Actuator: type (generic motor/servo), mount (body_id, local_pose), params (max_torque, free_speed, torque-speed curve ref, accel limit, stall current, gearbox ratio, efficiency).
  - Sensor: type (generic distance/line/encoder/IMU), mount (body_id, local_pose), params (range/FOV, noise, latency, dropout, bias drift, response curve, sample rate).
  - Measurement probe: signal source (e.g., wheel_angular_vel, sensor reading), optional attach pose, log window length, enabled flag.
  - Custom props: free-form key/values to extend later.
- World file (world.json): seed, gravity, timestep, terrain/track, obstacles (each as entity with components above), material presets.
- Robot file (robot.json): spawn transform; bodies[] (each an entity with shape/physics/material); joints/constraints[]; actuators[]; sensors[]; measurements[]; controller entry (module name).
- Snapshot file: serialized world + robot state at a moment (poses, velocities, controller state if needed), plus metadata.

--------------------------------------------------------------------------------
Usability gaps and mitigation plan

Current pain points
- Designer UI feels rough: unclear modes, bad/distracting visuals, device placement not obvious, buttons unclear, not everything works (e.g. placement of motor/sensor and configuration when designing robot - when placing a motor/sensor, it isn't trivial, there should be a menu that will help specify things e.g. direction of motor, etc.).
- Error handling: controller syntax/runtime errors can crash; need in-window reporting and isolation.
- General polish: need a systematic approach, not piecemeal fixes.

Proposed systematic approach
- Adopt a small design system: consistent colors, spacing, iconography, hover/active states for tools/modes; define a palette and component variants (button/toolbar/sidebar/status).
- Tighten input model: single “tool” state (select/move, add point, delete point), cursor change on hover, highlight of hovered element, status text + tooltips for all actions.
- Camera: standard pan (right/middle drag) + wheel zoom + reset view; optional grid toggle with subdued lines.
- Selection model: click to select point/edge/body; drag to move; Esc to clear; delete key to delete in delete mode.
- Devices placement: a compact “Add device” dropdown with ghost preview; visual icons/arrows/frustums drawn on canvas; selectable/movable after placement.
- Undo/redo: keep for geometry edits; extend to device add/remove.
- Error surface: wrap controller load/run in try/except, show errors in a non-crashing overlay (panel/log in runner) and keep sim running/pause on error.
- Scenario picker: standard open/reload buttons; show current scenario name prominently.
- Snapshots: simple list with “save latest” and “load latest” plus filenames in UI (later: list view).

Targeted next steps (Milestone 1.1 polish)
- Designer:
  - Fix point alignment regressions definitively: always convert screen→world→body-local using spawn+body pose; draw using posed vertices; add a crosshair at the hovered world point for debugging.
  - Improve mode visibility: toolbar buttons with toggle states and icons; cursor change per mode; on-canvas hint text.
  - Device visuals: draw motor icons/arrows and sensor frustums; add selection/hover highlighting for devices; allow reposition/delete via selection.
  - Grid and background: off by default; thin, low-contrast lines when enabled; remove stray horizontal line.
  - Status strip: show mode, selection (point index), zoom, offset, body name.
  - Undo/redo: extend to device add/remove.
- Runner:
  - Harden controller load/run: catch syntax/runtime errors, display in an on-screen panel, do not crash; pause on error until cleared; keep last good controller loaded.
  - Add a minimal error log window and a “clear errors” button.
  - Scenario picker retained; ensure hot-reload doesn’t reset sim unless requested.
- Shared polish tasks:
  - Define a color/spacing/token set; apply consistent padding/margins; reduce visual noise.
  - Add tooltips or a short “help” overlay showing controls (pan/zoom/modes).

Recent runner polish (Dec 7)
- Added collapsible sidebar tabs (Code / Devices / State / Logs) to declutter the viewport; sidebar can be hidden.
- View/options dropdown in-viewport: reset view, center on robot, toggle grid or motor arrows, and quick-entry to reposition mode.
- State tab: live motor/sensor values, selectable logger (choose signals, rate, duration), CSV export; logging pauses automatically on duration cap.
- Devices tab: compact controller hints and device list (API snippets stay in monospace overlay).
- Reposition tool: click-drag robot start pose; reset to spawn or save current pose as new spawn; pausing sim while moving to avoid glitches.
- View controls normalized: wheel zoom, middle/right-drag pan (direction fixed), grid overlay optional.

Longer-term (beyond 1.1)
- Property inspector for selected body/device (edit params in UI).
- Edge/segment selection and manipulation.
- Better file ops: save-as/duplicate scenario; snapshot list view.
- Deeper analysis/replay once core UX is solid.

