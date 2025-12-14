# Agent 3: Designer & Feature Expansion (full story)

## Scope and desired outcome
Expand the designer with an environment drawing mode (paint-like floor/wall drawing), environment bounds, smoother snapshot flows, and utilities that reduce friction when working with controllers and logs. Provide a CSV plotter window and a way to pick control algorithm files to load/swap. Add optional camera rotation (shift+drag) and robot rotation. Keep UI consistent with existing patterns and avoid regressing current save/load behavior.

## Inputs to review first
- User intent in `plan.md` (Dec 8 plan, feature section 166-188) and `planning_the_gui.md` for UI hints.
- Designer code: `apps/designer.py`, `apps/shared_ui.py`; persistence: `core/persistence.py`; config: `core/config.py`.
- Snapshots/log handling: relevant parts of `apps/runner.py`, `runner_layout.json`, and any CSV/log usage in `demos/`.

## Tasks
- Environment drawing mode:
  - Add a paint-like tool to draw floor marks and walls; allow choosing brush type (visual-only vs solid wall) and thickness.
  - Allow environment bounds definition (rectangular boundary) to keep the robot within region; persist with other designer data.
- Snapshot flows:
  - Keep quick-save; add "save as" with user-provided name and a dropdown/hover menu to load from available snapshots in the snapshots folder.
  - Preserve robustness of existing hover tabs (do not close instantly); menu should feel mac-like dropdowns similar to current options.
- Control algorithm picker:
  - Provide file-picker or dropdown to choose among control algorithm files; make it discoverable from designer (and ensure runner can consume selection via existing mechanisms if applicable).
- Log plotter window:
  - Allow selecting a `.csv` log and opening a plotting/analysis window; aim for quick visualization of key columns.
- Camera/robot rotation:
  - Add shift+drag to rotate camera view; optionally allow shift+drag on the robot to rotate it for setup.

## Verification (automated + manual)
- Add deterministic saves for designer state (including new drawings/bounds) and assert serialization in tests (consider adding to `verification_suite/` or a new designer-focused test file).
- For snapshot menus, add a test that enumerates available snapshots and ensures menu generation matches expectations.
- For plotter, add a tiny sample CSV and a test that validates parsing and plotting pipeline (can check computed series, not pixels).
- Manual checklist: draw a wall and a visual mark; set bounds; save as named snapshot and reload from dropdown; pick a controller file; open a CSV and view plotted data; rotate camera with shift+drag.

## Implementation notes
- Reuse existing UI patterns/styles from `shared_ui.py` to stay consistent.
- Keep persistence formats stable; add versioning or backward-compatible defaults if schemas change.
- Make new interactions discoverable but not intrusive; prefer menus/hover tabs over extra always-visible buttons.

## Outputs/deliverables
- Implemented drawing mode, bounds, snapshot save/load dropdown, controller picker, CSV plotter window, and camera/robot rotation.
- Deterministic serialization/tests for new designer state and snapshot menus; sample CSV test for plotter pipeline.
- Short README/update describing features, how to access them, and how they were validated (include the manual checklist).