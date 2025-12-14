# AI Agents: Simulation Environment Workstream

This folder contains self-contained charters for multiple AI agents. Each file tells the full story so you can reference it directly in a prompt without extra context. Agents now draft a brief plan in their output and then execute without waiting for human approval. The QC agent writes reports/backlog so you don’t have to triage manually.

## Files
- `agent-qc.md` — auditor to compare code/UX vs feedback (plan.md 205-246) and prior charters; writes `plans/qc-report.md` and `plans/backlog.md` with prioritized fixes and suggested owners; may apply low-risk clarifications.
- `agent-designer-followups.md` — implements designer-specific feedback (undo, draw modes, shapes as objects, custom objects, mode separation, rotation, advanced view) and updates tests/docs; appends new gaps to backlog if found.
- `agent-runner-help-followups.md` — implements runner/help feedback (snapshot/log hierarchy, mode cleanup, IMU display, help structure/clarity, controller/logging explanations) and updates tests/docs; appends new gaps to backlog if found.
- `agent-content-scenarios.md` — adds curated environments/robots/scenarios and lightweight checks; appends new gaps to backlog if found.

Legacy/phase-1 charters (reference if needed):
- `agent-help-ux.md` — in-app help + runner UX overhaul.
- `agent-physics.md` — traction-aware physics and validation.
- `agent-designer-features.md` — designer expansions: drawing, bounds, plotter, snapshots, file picker.
- `agent-visual-polish.md` — visual/UI polish and menu cleanup.

## Execution order (updated)
1) QC/Auditor (creates `qc-report.md` + `backlog.md`)
2) Runner/Help follow-ups and Designer follow-ups (parallel if coordination is clear)
3) Visual polish (as needed from new issues)
4) Content/Scenarios
5) Physics (as needed from earlier scope)

## Human checkpoints (minimal but can be skipped if desired)
- Approve help/UX copy and menu layout choices if you want review.
- Approve physics tolerances if physics work resumes.
- Approve scope/UX for designer additions if you want review.
- Approve scenario/content scope/naming if you want review.

## Verification expectations (all agents)
- Add/extend automated checks where feasible (unit/property tests, seeded/deterministic UI state snapshots, CSV/log diffs).
- Include a short manual checklist tailored to the change.
- Record before/after evidence when UI changes (screenshots or structured descriptions of the layout/state).

## Deliverables (all agents)
- Code changes + tests.
- A short README/update in the codebase explaining what changed, how to use it, and how it was validated.
- Notes on known limitations or follow-ups (or append to backlog).

## How to use these charters
- Work from the relevant agent file alone; it restates the problem, inputs to read, tasks, verification, and outputs.
- Keep changes incremental and keep existing behaviors stable unless explicitly replaced.
- Prefer deterministic hooks and seeds to make validation reliable.
