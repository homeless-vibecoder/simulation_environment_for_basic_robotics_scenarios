# Agent QC: Auditor & Gap Finder (execute; auto-update backlog)

## Role and goal
Act as an independent auditor. Read the latest feedback in `plan.md` lines 205-246 and prior charters. Identify misses, regressions, unclear UX, and unaddressed requests across designer, runner/help, visuals, and content. Produce a concise report and a prioritized fix list with suggested owners, and **write them to files** so no human triage is needed. Apply only low-risk clarifications/label/copy/layout tweaks yourself; leave larger work to follow-up agents via the backlog.

## Inputs to review
- Feedback: `plan.md` lines 205-246 (designer undo/draw modes, custom objects, separation of robot/env/custom, snapshot/log hierarchy, IMU display, help organization and clarity, controller explanations, logging definitions, supportive code view idea).
- Current code/state: `apps/designer.py`, `apps/runner.py`, `apps/help_content.py`, `apps/shared_ui.py`, `runner_layout.json`.
- Existing charters: `agent-help-ux.md`, `agent-designer-features.md`, `agent-visual-polish.md`, follow-up charters.

## Tasks
- Map requirements vs. current behavior: derive a checklist from feedback and earlier charters.
- Inspect code/UX (read or run) to spot gaps: undo/draw cues, brush picker, shapes-as-objects, custom object creation/import, robot/env/custom separation, snapshot/log nesting, reposition mode, IMU numbers, help copy structure, controller API clarity, logging definitions, supportive/analysis view ideas.
- Document findings with evidence.
- Write outputs to disk (no human copy/paste):
  - `plans/qc-report.md`: findings, evidence, and quick notes on impact.
  - `plans/backlog.md`: prioritized fix list with suggested owners (Designer-Followups, Runner-Help-Followups, Content-Scenarios, Visual-Polish/Help), and proposed tests/checks per item.
- Optional low-risk fixes: apply trivial textual/spacing/label/help-content clarifications that are very unlikely to break behavior. Otherwise leave for follow-up agents.

## Verification approach
- Recommend minimal deterministic checks (UI config/help-topic snapshots, presence/absence of controls) and quick manual checks to confirm fixes once implemented. Note them in `plans/backlog.md` alongside tasks.

## Outputs
- Updated `plans/qc-report.md` and `plans/backlog.md` (created if missing).
- Optional small clarifications in code/help/UI if low-risk.
- Suggested tests/checks for downstream agents.

## Notes
- Do not wait for approval; execute after drafting your brief plan in your own output.
- Avoid broad refactors; keep runtime behavior stable. If you change code/help, keep it minimal and deterministic.
