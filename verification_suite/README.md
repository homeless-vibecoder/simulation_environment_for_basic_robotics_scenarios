# Verification Suite

Self-contained scripts that sanity-check the current physics and sensor stack. Run each from this directory with: python3 <script>.py. They only import the reusable packages so the core code stays untouched.

| Script | Purpose | Expected Output |
| --- | --- | --- |
| test_wheel_rotation.py | Applies a single off-center wheel force and ensures the chassis develops angular velocity. | Prints ang_vel magnitude (>0.01) plus PASS. |
| test_diff_drive_translation.py | Uses symmetric wheel commands to verify forward translation with near-zero spin. | Prints vx>0.1, ang≈0 and PASS. |
| test_sensors.py | Checks that line and distance sensors respond correctly to simple scenes. | Shows near-1.0 line reading on the stripe, <0.2 off stripe, close-range hit <0.9, and clear >1.0, ending with PASS. |
| test_component_outputs.py | Verifies components register with the robot and expose visual_state payloads (points, rays, commands). | Reports component count match and states=OK -> PASS. |
| test_ui_snapshots.py | Captures hover menu/device snapshots and checks rounding helper output. | Prints JSON payload and PASS when menu + rounding look good. |
| test_traction_model.py | Validates traction-aware wheel model, slip ratio limits, overdrive behavior, and regression trace. | Prints PASS for no-slip, overdrive slip, bounded lateral, one-wheel spin, and trace regression. |

Add more scripts here as coverage expands (e.g., IMU noise checks).

## Traction logging and manual checks
- Enable per-step traces in scripts or apps with `sim.enable_trace_logging(True)` and persist with `sim.save_trace_log(Path("trace.json"))`. Trace entries include wheel command, slip ratio, preferred/contact speed, applied longitudinal/lateral impulses/forces, and body pose/velocity.
- Moderate-traction check: run a straight drive (e.g., commands ~0.4–0.5) on a frictional surface; expect slip ratio near zero and body speed close to wheel tangential speed.
- Low-traction check: lower `mu_long`/`mu_lat` (e.g., 0.2–0.3) and drive at high command; expect non-zero slip ratio, capped applied force, and slower-than-commanded body speed. Compare traces to confirm acceleration is limited and lateral slip remains bounded.
