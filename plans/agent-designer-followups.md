# Agent Designer-Followups: Address new designer feedback (execute)

## Role and goal
Implement the designer-specific feedback from `plan.md` lines 205-221. Improve drawing UX, mode clarity, undo, shapes-as-objects, custom object authoring/import, and separation of robot vs environment vs custom creation. Draft a short plan in your output, then execute without waiting for approval.

## Inputs to review
- Feedback: `plan.md` lines 205-221.
- Current designer code: `apps/designer.py`, `apps/shared_ui.py`; persistence: `core/persistence.py`, `core/config.py`.
- Prior charter: `agent-designer-features.md` (ensure consistency and avoid regressions).
- Backlog (if present): `plans/backlog.md` tasks tagged for designer.

## Tasks
- Undo/redo: add cmd+Z undo (and redo if easy) for drawing/actions.
- Modes & clarity:
  - Make select/add/draw easy to switch; add visible state indicators.
  - Draw mode should persist like paint (no re-click for every stroke).
  - Add a brush picker UI panel when draw is active (brush type, thickness, wall vs visual paint).
- Shapes as objects: allow drawing shapes (rectangles, triangles, etc.) that become manipulable objects; ensure drawings stay attached to the robot when in robot design mode (rigid with connections).
- Modes for creation types: clear pathways/tabs for “Create robot”, “Create environment”, “Create custom”; custom mode can define new objects/classes (mass, properties), store them by name, and import from file.
- Custom objects: allow adding a new object file (not just picking existing) and importing stored customs.
- Advanced view: for devices/components (e.g., motor), offer an advanced/details view where parameters can be tuned; consider opening code/fields view.
- Rotation: enable shift+drag (or similar) to rotate environment/objects.

## Verification
- Deterministic serialization of designer state including shapes-as-objects, mode indicators, and custom objects; tests that load/save and assert structure.
- UI config snapshot test for mode toggles/brush picker presence when draw mode active.
- Manual checklist: switch modes, draw shapes without re-clicking, undo/redo works, shapes stay with robot, create/import custom object, rotate via shift+drag, open advanced view for a component.

## Outputs
- Implemented features above with persistence where applicable.
- Updated/added tests and a short README/update covering new designer UX, modes, and custom object handling.
- If new gaps arise, append to `plans/backlog.md` with owner and proposed verification.
