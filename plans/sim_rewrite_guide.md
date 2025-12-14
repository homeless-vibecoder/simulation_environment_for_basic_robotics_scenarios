# Simulation Environment Rewrite Guide

Purpose: blueprint for rebuilding `simulation_environment` from scratch with a file-first architecture, verifiable controller-to-robot linkage, and cleaner designer/runner UX. This document is written so an AI agent (or human) can recreate a cleaner environment in a new folder without relying on legacy coupling.

## Goals and principles
- Treat every project file the same: robot, environment, scenario, or custom part share one schema and can be composed/imported.
- Decouple engine from UI; runner/designer are clients of a headless simulation API.
- Controllers are explicitly bound to robots and proven to drive them (tests must fail if code is missing or disconnected).
- Keep UX paint-like and file-first: open/create/save anywhere; double-click selects; save-as everywhere.
- Prefer clarity and testability over performance; simulations are 2D top-down.

## Proposed repo layout (new folder)
- `core/` — headless engine
  - `project_store.py` — load/save/validate project JSON; import/merge helpers.
  - `geometry.py` — shapes, transforms, intersection helpers (bbox, convex hull, broadphase culling).
  - `physics.py` — mass/inertia, friction, traction/slip model, integrator.
  - `devices/` — motor, wheel, imu, distance, encoders, custom device base.
  - `kinematics.py` — diff-drive and other drivetrains; converts motor outputs to chassis motion.
  - `simulation.py` — simulation loop, time-step control, event hooks, deterministic seeds.
  - `controller_runtime.py` — code packaging, hot-reload, per-robot controller binding.
  - `logging.py` — signal registry, sampling, CSV export, hooks for plotting.
  - `snapshots.py` — serialize/restore simulation state.
- `ui/designer/` — file-first editor client (can stay Pygame/Qt/other, but talks to engine via API).
- `ui/runner/` — scenario runner client with code tabs, plotting, snapshots, reposition, help.
- `assets/` — templates (robots, environments, scenarios, controllers).
- `tests/` — unit + integration + UI smoke.
- `docs/` — short user how-tos (runner, designer, controllers).

## Unified project schema (JSON)
Top-level shape:
```json
{
  "kind": "robot | environment | scenario | custom",
  "version": "1.0",
  "metadata": { "name": "", "description": "", "tags": [], "created": "", "updated": "" },
  "components": {
    "geometry": [...],
    "materials": {...},
    "devices": [...],
    "controllers": [...],
    "connections": [...],
    "assets": {...},
    "notes": "...",
    "help": "short hints for UI"
  },
  "compose": { "imports": [ { "path": "relative/or/url", "include": ["geometry","devices","controllers","materials"] } ] }
}
```

Key component shapes:
- `geometry`: list of objects with `id`, `type` (`polygon`, `circle`), `points` (relative), `pose` (x,y,theta), `visual` (color, stroke), `physics` (mass, friction, restitution, blockage flags), `can_move` bool, `bounds_hint` (bbox/triangle).
- `materials`: named presets for friction/traction/reflectivity to reuse across geometry.
- `devices`: each device has `id`, `kind` (`motor`, `wheel`, `imu`, `range`, `custom`), `pose`, `params` (max_torque, radius, noise, latency), `io` bindings (e.g., which wheel a motor drives).
- `controllers`: for robots only; list with `id`, `entry` (module/function names), `tabs` (imports/init/step/helpers/help), `metadata` (author, version), `doc` (inline help text to show in UI).
- `connections`: constraints/anchors (rigidity, joints) used by physics; optional for simple rigid builds.
- `assets`: references to sprites/textures or UI-only visuals.
- `compose`: imports merge by concatenating geometry/devices/materials and binding by ID; collisions on ID must be resolved explicitly by importer (designer prompts).

Storage layout suggestion:
- `projects/robots/*.json`
- `projects/environments/*.json`
- `projects/scenarios/*.json`
- `projects/custom/*.json`
- `controllers/*.py` (generated from tabs) with stable naming tied to project metadata.

Validation:
- `project_store.py` validates `kind`, required component fields, referential integrity (devices reference geometry IDs, controllers reference device IDs), and import resolution.
- Provide CLI: `python -m core.project_store validate projects/robots/foo.json`.

## Engine architecture
- **Data flow** per tick: read inputs (controllers -> motor commands) → kinematics → physics integration (traction/slip + collisions) → device updates → logging → render hooks.
- **Geometry/collision**: use bounding boxes/triangles for broadphase; convex polygon intersection for narrow phase; interactions only when intersecting.
- **Physics**: traction model compares commanded wheel surface speed vs actual chassis speed to compute slip force; friction, damping, restitution configurable per material.
- **Devices**: motors produce torque; wheels map to chassis via kinematics; sensors (imu, range, encoders) read from physics state with noise/latency params.
- **Controller runtime**: loads controller tabs, assembles into a module, enforces contract (must expose `Controller` with `__init__(self, robot, world)` and `step(self, dt)`), injects device APIs, and hot-reloads on file change.
- **Snapshots**: serialize geometry poses, velocities, device states, controller state (optional), and RNG seed to allow deterministic resume.
- **Headless API**: `Simulation` object with `load_project`, `add_robot`, `add_environment`, `run(dt, steps)`, `set_controller(robot_id, controller_spec)`, `snapshot()`, `restore()`, and `hooks` for UI.

## Controller contract and code tabs
- Tabs: `imports`, `init` (setup), `step` (per tick), `helpers`, `help/notes`.
- Code packager writes a generated module (e.g., `controllers/<robot_name>__<id>.py`) assembled in that order plus a header with metadata/help text.
- Required class signature:
  ```python
  class Controller:
      def __init__(self, robot, world, logger):
          # robot exposes devices by id; world exposes read-only environment API
          ...
      def step(self, dt):
          # set motor commands here
          ...
  ```
- Binding: robot project references `controller.id`; engine ensures exactly one active controller per robot (or explicit none). Simulation raises if controller missing or fails to step.
- Hot reload: when runner edits tabs, packager rewrites module and engine reloads between ticks (with state reset or preserved by policy).
- Help export: `help/notes` tab populates runner Help; also render a “what functions are required” quick summary.
- Example minimal tabs (logical layout, not actual file):
  - Imports: `import math`
  - Init: set PID gains, cache device handles.
  - Step: read sensors, compute motor speeds, set outputs.
  - Helpers: utility funcs.
  - Help: short explanation + available device IDs.

## Designer experience (spec)
- Start screen: open/create project (robot/environment/scenario/custom); recent list; file chooser with save-as; double-click opens; no hidden coupling between types.
- Modes: Robot mode, Environment mode, Scenario mode, Custom part mode; each uses same schema editor with context-specific presets.
- Canvas: paint-like draw (pen, line, rect, polygon), snap/align, rotate/translate; undo/redo (Ctrl/Cmd+Z/Y); selection with resize/rotate handles; shift+drag rotates.
- Devices panel: add from library or import from file; attach to geometry; device properties editable; controllers attach as placeholders.
- Properties panel: geometry visual/material/physics; blockage flags; reflectivity for sensors.
- Composition: import other project files into current (merge UI); show conflicts and allow rename.
- Export: save, save-as, export template; always choose folder; remove redundant scenario/robot tabs.
- Reliability: drawing walls/objects must not crash; empty-canvas creation always works.

## Runner experience (spec)
- Loads scenario project (env + robots + controllers). Supports multi-robot.
- Code pane split into tabs: Imports, Init, Step, Helpers, Help/Notes; each shows purpose; edits bind to selected robot only.
- Controls: play/pause/step; drag robot to reposition; optional save-as snapshot and load; reset to snapshot; no separate “reposition mode.”
- View toggles: grid, motor arrows, sensor readings (rounded to 2–3 decimals), path trace.
- Logging: pick signals, rate, duration; CSV export; quick plotter window for CSVs.
- Capture: snapshot load/save in nested menu; avoid defaulting to single file.
- Help: structured outline (controller API, device list with examples, simulation overview, file layout, how to swap controllers).
- IMU display shows numbers (rounded); remove unused/unclear buttons; remove “format code” if not needed.

## Testing and verification
- Unit tests:
  - `project_store`: validates schema, detects missing controllers/devices, resolves imports.
  - `physics`: traction/slip response, friction, restitution.
  - `kinematics`: diff-drive motion vs motor commands.
  - `devices`: sensor readings with noise/latency; motor torque application.
  - `controller_runtime`: missing/invalid controllers raise; hot-reload rebuilds module.
- Integration tests:
  - Load robot + controller → step → motor commands change pose (guards against “code not connected” per plan.md 286-293).
  - Multi-robot scenario runs without interference; controllers isolated.
  - Snapshots save/restore same pose and controller state.
  - Logging produces CSV with expected headers/rows.
- UI smoke (designer/runner) via snapshots or scripted UI harness:
  - Open/create/save-as flows work for all kinds.
  - Code tabs visible and editable; help pane populated.
  - Drag-to-reposition works; snapshots menu nests correctly.
  - Drawing tools do not crash; undo/redo works.
- Regression tests:
  - If controller file is deleted or blank, runner refuses to run and surfaces an error.
  - Removing controller binding makes robot idle (expected), and test asserts that.

## Migration notes
- Fresh start is allowed; reuse legacy assets only after manual vetting.
- Provide a one-time converter (optional): map old robot/env JSON into new schema; warn on unsupported fields.
- Keep a small curated set of legacy examples rewritten into the new format as templates.

## AI agent build prompt (drop-in)
Copy-paste for agents to rebuild in a clean folder:

```
You are tasked with creating a new 2D robotics simulation environment (top-down) with a file-first architecture. Use Python and the existing desktop stack (e.g., Pygame) but keep the engine headless and UI as a client.

Goals:
- Unified project JSON schema for robot/environment/scenario/custom; composable imports; file-first open/save-as.
- Engine domains: geometry/collision, physics with traction/slip, kinematics (diff-drive), devices (motors, sensors), simulation loop, snapshots, logging.
- Controllers: tabbed code (imports/init/step/helpers/help) assembled into a module; Controller class with __init__(robot, world, logger) and step(dt); bound to robots; hot-reload; help text exported to UI.
- Designer: paint-like draw with undo/redo; modes for robot/environment/scenario/custom; device library/import; attach controllers; import/merge other projects; save-as everywhere; double-click to open.
- Runner: load scenario, multi-robot support, code tabs per robot, drag-to-reposition, snapshot save/load, logging with CSV and quick plotting, view toggles, rounded displays, structured help.
- Verification: tests to ensure controllers actually drive robots, project schema validates, physics/kinematics sane, multi-robot works, snapshots/logging, and UI flows (open/save/code tabs/reposition).

Suggested layout:
- core/: project_store.py, geometry.py, physics.py, kinematics.py, devices/, simulation.py, controller_runtime.py, logging.py, snapshots.py
- ui/designer/ and ui/runner/ as thin clients using the engine API
- assets/ templates; tests/ for unit/integration/UI smoke; docs/ for user guides.

Deliverables:
- Implement the core modules and schema validation.
- Implement designer/runner clients with the behaviors above.
- Provide starter templates (robots/environments/scenarios/controllers).
- Add tests per the verification list; fail if controller is missing or not wired (guards against old bug where code edits did nothing).
- Include short user docs (runner, designer, controllers) referencing the help tab content.
```

## Next steps when implementing
- Start with `project_store` and schema validation.
- Build controller packager/runtime and a minimal diff-drive example robot to prove controller wiring.
- Add physics/kinematics core; then logging/snapshots.
- Stub designer/runner UI using engine API; iterate on UX polish after functionality passes smoke tests.
- Keep tests green as features land.
