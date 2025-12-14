# Agent Content-Scenarios: Curated environments/robots/demos (execute)

## Role and goal
Create a small, polished library of environments, robots, and scenarios so users have content to explore beyond the UI. Provide ready-to-run examples with light documentation and basic load/behavior checks. Draft a short plan in your output, then execute without waiting for approval.

## Inputs to review
- Existing demos: `demos/` and `proper_line_follower/` for patterns.
- Config/persistence: `core/config.py`, `core/persistence.py`, `scenarios/` layout.
- UI affordances for selection: `apps/runner.py`, `apps/designer.py` (how environments/robots are loaded today).
- Feedback context: overall goal to add more content; keep consistent with recent UX changes.
- Backlog (if present): `plans/backlog.md` tasks tagged for content/scenarios.

## Tasks (suggested initial scope)
- Add 3–5 scenarios with variety (e.g., maze/walls with bounds; open field with noise; tight corridor; slalom cones; line-following variation) and matching robots (differing sensors/actuators).
- Provide environment/robot definitions and snapshots where appropriate; ensure bounds are set when relevant.
- Add sample logs for at least one scenario and a short description of expected behavior.
- Wire scenarios to be discoverable (e.g., via existing selection menus) without disrupting current flows.

## Verification
- Deterministic load/run smoke tests: each scenario loads; robot spawns; a short scripted run completes without errors; key state fields remain finite.
- Validate snapshots/config schemas remain backward-compatible; include minimal schema/version note if needed.
- Manual checklist: load each scenario, start/stop run, observe expected layout/robot, open sample log if provided.

## Outputs
- New scenarios/environments/robots and any supporting assets/snapshots/logs.
- Light docs/readme per scenario set: what it is, how to load/run, expected behavior.
- Simple automated checks for load/smoke, plus notes on compatibility.
- If new gaps arise, append to `plans/backlog.md` with owner and proposed verification.
