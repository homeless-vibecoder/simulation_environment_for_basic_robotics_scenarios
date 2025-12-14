# Basic Low-Level Mechanics Demo

This standalone demo exercises the primitives defined in `low_level_mechanics` together with the new `middle_level_library` sensors and motors.

## What it does
- Builds a tiny 2D world with a floor, a magnetic line marker, and a lightweight robot chassis.
- Mounts a differential-drive module plus a line sensor array and a distance sensor from `middle_level_library`.
- Runs a simple line-following controller based on the sensor readings while visualizing everything through the built-in Pygame viewer, including world boundaries and sensor overlays.

## Running it
Requires Python 3 and `pygame` (`pip install pygame` if needed).

```bash
cd /Users/irakli/Desktop/Polished_projects_for_Github/RBE_IQP/simulation_environment/demos/basic_demo
python3 demo.py
```

Controls inside the viewer:
- `SPACE` — toggle play/pause
- `RIGHT` or `.` — single-step when paused
- `TAB` — cycle which robot the camera follows
- `1` / `2` — switch between world view and follow view
- `[` / `]` — zoom out / zoom in
- `R` — toggle rotation-aligned follow camera
- `V` — toggle component icons (motors/sensors)
- `B` — toggle detailed sensor overlays
- `N` — toggle numeric readouts
- `H` — show/hide on-screen controls
- `Q` / `ESC` / window close — exit

Feel free to delete the entire `demos/` directory once you have inspected the output—the core mechanics live exclusively under `low_level_mechanics/`.
