# Agent 1: Help & Runner UX (full story)

## Scope and desired outcome
Build an in-app help experience and clarify runner UX so a beginner can operate the simulator without reading source code. The help should explain: how to edit robot code, required functions (`step()`, `_apply()`), available sensors/motors and their APIs, how the simulation loop uses these functions, how to arrange files, and how to switch among control algorithms. Clean up the runner UI: convert cluttered buttons to clear menus/dropdowns, round displayed numbers, and present device info cleanly. Keep existing behaviors stable while making them understandable and easier to use.

## Inputs to review first
- User intent in `plan.md` (Dec 8 plan, priority section 145-193) and `planning_the_gui.md` for UX cues.
- Runner code and UI helpers: `apps/runner.py`, `apps/shared_ui.py`, `app.py`.
- Current device/state displays and menu structures: run the app if possible to see current layout (or read `runner_layout.json`).
- Existing verification suite for patterns: `verification_suite/` (tests may inspire deterministic checks).

## Tasks
- Design & build a help surface (menu item + modal/overlay/panel) that is easy to reach from runner. It must include:
  - How to edit robot code; where files live; how to add/delete control algorithms; how to pick which algorithm runs.
  - What functions are required (`step()`, `_apply()`, any hooks) and how the simulator calls them.
  - Sensors/motors overview: available devices, how to read/write them, basic examples.
  - Simulation overview: what “sim” means here; rough description of physics loop; how logs/snapshots work.
  - Navigation: quick-start section + links/anchors to deeper chapters so users can jump to the right part.
- Restructure runner controls for clarity:
  - Convert start logging/export log/snapshot controls into a coherent menu/dropdown so buttons don’t overlap.
  - Provide “load code”/“switch control algorithm” affordance (file picker or dropdown) in runner so users can swap controllers.
  - Improve snapshot UX: keep current quick-save but add discoverable menu entry for named saves and loading from folder.
  - Keep a clear options area; remove/relocate low-value items. Preserve hover-tab behavior for consistency.
- State/device presentation improvements:
  - Round numeric displays to 2–3 decimals where appropriate (IMU, velocities, readings).
  - Remove the extraneous “show device help” label and present devices as bullet/numbered lists with clear headers (e.g., “Available devices”). Use legible font sizing/weight for headers.
  - Keep existing helpful examples for device usage; extend if quick wins are obvious.
- UX hygiene:
  - Avoid redundant view controls that users can already do with the mouse; keep toggles that add value (e.g., motor arrows, readings). Make code/menu areas clearly labeled.
  - Ensure any new menus feel consistent with current style (hoverable options tabs).

## Implementation notes
- Keep changes minimal-risk: prefer reorganizing existing components before adding new ones.
- Make help content data-driven where possible (e.g., a structured help spec rendered into the UI) so it’s easy to maintain and test.
- Provide sane defaults and avoid breaking existing keyboard/mouse interactions.

## Verification (automated + manual)
- Add deterministic UI/state snapshots: serialize menu structure/help topics and numeric rounding settings into JSON and assert in tests (e.g., under `verification_suite/`).
- Add a lightweight test that checks help topics cover required chapters (controllers, functions, sensors/motors, simulation overview, file arrangement, switching algorithms).
- If possible, add a seeded run that captures log/snapshot menu config to ensure the dropdown/menu wiring stays stable.
- Manual checklist: open help; navigate to at least two chapters; switch control algorithms via the new affordance; trigger logging/export/snapshot via the menu; confirm rounded values and cleaned device list.

## Outputs/deliverables
- Implemented help UI + reorganized runner menus/logging/snapshots.
- Cleaned device/state presentation with rounded numbers and clearer lists.
- Automated checks for help/menu coverage and deterministic config snapshots.
- Short README/update summarizing what changed, how to use the help/menu features, and how validation was done (include quick manual checklist).