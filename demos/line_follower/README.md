# Line Follower Demo

This modular demo showcases how to compose a robot from reusable components and keep the controller logic separate from the simulator.

## Layout
- `robot.py` — provides `spawn_robot()` which returns a fully assembled line-follower robot (motors, sensors, IMU).
- `controller.py` — contains `LineFollowerController`, the entry point students edit to change behavior.
- `run_demo.py` — builds the world, spawns the robot, wires the controller, and launches the visualizer.

## Run it
```bash
cd /Users/irakli/Desktop/Polished_projects_for_Github/RBE_IQP/simulation_environment/demos/line_follower
python3 run_demo.py
```

## Manual control
Prefer to drive the robot yourself? Launch the manual variant:
```bash
cd /Users/irakli/Desktop/Polished_projects_for_Github/RBE_IQP/simulation_environment/demos/line_follower
python3 run_manual_demo.py
```
- `W`/`UP` accelerates forward, `S`/`DOWN` reverses.
- `A`/`LEFT` rotates left, `D`/`RIGHT` rotates right.
- `SHIFT` gives a short boost while held, `CTRL` acts as an instant brake.
- Tap `Q` to slow the base speed or `E` to speed it back up; the change applies to both drive and turning rates.
- Release all keys to leave the robot stationary.

## Customize
- Import `spawn_robot` in your own scenario to reuse the hardware definition.
- Swap in different presets from `middle_level_library.presets` for sensors or motors.
- Edit `controller.py` to experiment with new control laws without touching the simulation harness.

## Visualizer tips
- Wheel motors render as small orange capsules with a green/red arrow showing their drive direction (always visible, so you can distinguish left/right motors at a glance).
- Sensors use blue diamond/triangle glyphs that stay on-screen while `V` is enabled, making it easy to spot line arrays vs. distance sensors.
- `V` toggles component icons (on by default) if you want an uncluttered view.
- `B` overlays sensor footprints (line array samples, distance beams) for deeper debugging.
- `N` displays numeric readouts (sensor values, IMU velocities) next to each component.
