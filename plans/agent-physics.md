# Agent 2: Physics & Traction Fidelity (full story)

## Scope and desired outcome
Diagnose and fix the current wheel/traction model. Today motion is force-only and ignores tire traction/slip; wheel spin vs body velocity can mismatch with no modeled slip. Implement a traction-aware model so commanded wheel speeds translate into realistic motion, including slip when traction is exceeded. Provide validation (tests + instrumentation) that demonstrates correctness and prevents regressions.

## Inputs to review first
- User intent in `plan.md` (Dec 8 plan, physics section 161-165).
- Physics core: `core/simulator.py`, `low_level_mechanics/*` (geometry, materials, world, entities), `middle_level_library/motors.py`, `middle_level_library/robots.py`, `verification_suite/` existing physics tests.
- Demos to understand expectations: `demos/` and `proper_line_follower/` behaviors.

## Tasks
- Map current motion path: how wheel commands become forces/velocities. Identify where traction is ignored.
- Design a traction-aware wheel model (keep it lightweight):
  - Tie wheel angular velocity to desired tangential velocity; compute slip ratio and lateral slip.
  - Apply traction limits (longitudinal + lateral) based on material/friction params; cap forces/torques accordingly.
  - Ensure energy/momentum are consistent (no free acceleration when traction is insufficient).
- Implement with minimal API disruption; add friction/traction parameters with sensible defaults.
- Instrumentation: add optional CSV/JSON logging hook that records per-step wheel command, slip ratio, applied force, resulting body velocity/pose for deterministic seeds.

## Verification (automated + manual)
- Extend `verification_suite/` with numeric/property tests:
  - Commanded wheel speeds vs resulting body speed within tolerance when traction is sufficient.
  - When commanded speed exceeds traction, slip ratio is non-zero and applied velocity is limited.
  - Lateral slip stays bounded when straight-line commands are issued.
  - Regression seed: run a short deterministic scenario and assert on serialized trace (pose/velocity/forces) to catch future regressions.
- Consider a simple analytical case (e.g., one wheel locked, one spinning) and assert qualitative outcomes.
- Manual checklist: run a short sim with moderate traction and with intentionally low traction; observe expected slip/limited acceleration and stable stopping.

## Implementation notes
- Keep performance reasonable; prefer per-step closed-form calculations over expensive solvers.
- Default behavior should feel similar or better for existing demos; avoid breaking public APIs.
- Document new parameters and defaults.

## Outputs/deliverables
- Traction-aware motion implementation with sensible defaults.
- Instrumentation hook for per-step wheel/force/slip logging.
- Added/updated automated tests covering slip and bounded motion.
- Short README/update explaining the model, parameters, how to run the tests, and validation evidence (including the deterministic trace).