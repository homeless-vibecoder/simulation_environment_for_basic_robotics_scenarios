# Simulation environment (milestone 1)

Quick-start
- Install deps: `pip install pygame pygame_gui`.
- Runner (for coding/playback): `python apps/runner.py`
  - Pick a scenario from the dropdown (looks in `scenarios/`).
  - Use the hover menu: Run > Play/Pause/Step, Run > Resume from snapshot, Capture > Snapshots/Logging (nested).
  - Drag the robot directly in the viewport to reposition; no separate mode toggle.
  - Edit `controller.py` in Code; Save + Reload to apply.
- Designer (for geometry/devices/custom assets): `python apps/designer.py`
  - Use the hover menu Workspace to New/Open/Save/Save As robot/env/custom/scenario with explicit names (files go to `designs/` or `scenarios/<name>`).
  - Tabs (Robot / Environment / Custom) reflect the active datatype; the status bar shows the current file.
  - Robot tab: edit bodies/devices; Environment tab: draw marks/walls/bounds; Custom tab: craft custom shapes/assets.
  - Shift+drag rotates the view; Cmd/Ctrl+Z / Shift+Cmd/Ctrl+Z undo/redo within the active tab.
  - Export full scenarios only when you choose Export; otherwise robot/env/custom saves live under `designs/`.

Controls (hover menu)
- Run: Play/Pause, Step, Resume from snapshot (recent + load from file).
- Capture: Snapshots (quick/save-as) and Logging (start/stop, export, plotter, rate/duration).
- View: grid/motor arrows/path trace toggles; Panels: show/hide Code/State/Logs/Console/Plot.
- Help: structured topics with summaries + deeper sections.

Code editor
- Right-side panel is a minimal text editor for `scenarios/generic/controller.py` (supports typing, backspace, newline, tab).
- Use Save code to persist and reload without restarting the app.

Robot designer (minimal draft)
- Select a body from the dropdown; click “Add point,” then click in the viewport to append a vertex (convex or non-convex).
- Save robot writes updated `robot.json` (edges are re-closed automatically).

Viewport
- Runner: draws world/robot polygons; wheel arrows show motor commands.
- Designer: shows polygons and vertices; zoom with +/-; pan with arrow keys; click to add/move/delete vertices when a mode is active.

Data layout
- `scenarios/<name>/world.json` – terrain/track, physics settings.
- `scenarios/<name>/robot.json` – bodies, sensors/motors, controller module name.
- `scenarios/<name>/controller.py` – student code (hot-reloaded).
- `scenarios/<name>/snapshots/` – saved states (include controller state).
- `designs/robots|environments|custom/` – per-tab designer saves (isolated).

Notes
- Solver uses XPBD-style joint correction + impulse contacts with reasonable defaults (dt ~1/120s).
- Generic devices: distance, line, IMU, encoder sensors; wheel motors with force limit.

Wheel traction (top-down, zero-g world)
- Traction uses a virtual normal load so you can reason about mass: `N = normal_force` or `mass * g_equiv / wheel_count` (defaults g_equiv=9.81, wheel_count=2).
- Longitudinal drive is capped by `mu_long * N`; lateral slip is constrained with `mu_lat * N` and a small damping term to avoid oscillation.
- Configure per motor via actuator params: `mu_long`, `mu_lat`, `g_equiv`, `normal_force` (optional override), `lateral_damping`, `wheel_count`, `wheel_radius`, `max_force` (or `preset` + `detailed=True` for torque models).
- If `wheel_count` is omitted, the simulator auto-counts wheel motors on the same body and splits the virtual normal load equally. Set `wheel_count` or `normal_force` explicitly to override.
- Physical units: meters, seconds, kg. E.g., a 0.5 kg robot with two wheels gets ~2.45 N of normal load per wheel by default.

