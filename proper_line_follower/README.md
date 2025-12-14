# Proper Line Follower Suite

Reusable tracks, robots, and controller templates for quickly prototyping line-follower assignments. The goal is to let you import a preset design, write a control function, and immediately exercise it on multiple tracks.

## Package layout

```
proper_line_follower/
├── tracks/        # Floor + black-line presets (oval, chicane, double-S, …)
├── robots/        # Differential-drive robots with binary line sensors
├── controllers/   # Reference controllers (e.g., bang-bang)
└── demos/         # Manual driver, autonomous template, batch harness
```

Everything is plain Python—no command-line flags. Edit the module-level constants if you want to switch presets.

## Tracks

Use `proper_line_follower.list_track_presets()` to inspect available names:

```python
from proper_line_follower import create_track_world, list_track_presets

print(list_track_presets())  # ['chicane_loop', 'double_s', 'oval_loop']
world, spec = create_track_world("double_s")
```

Each track is defined by a white rectangular floor plus a thin black loop (MaterialProperties carries `line_intensity = 1.0`). You can add your own track by extending `proper_line_follower/tracks/library.py`.

## Robots

Robots expose two binary line sensors (left/right) plus an IMU and range sensor:

```python
from proper_line_follower import (
    create_track_world,
    create_robot,
    default_track_entry_pose,
    list_robot_presets,
)

print(list_robot_presets())  # ['edge_dual', 'forward_probe', 'wide_body']
world, spec = create_track_world("double_s")
robot = create_robot("forward_probe", pose=default_track_entry_pose(spec))
world.add_object(robot.robot)  # attach to your world
```

Call `robot.read_line_bits(world, dt)` each step to get `(left_bit, right_bit)` where each entry is `0`, `1`, or `None` if that sensor skipped an update.

## Controllers

`BinaryLineBangBangController` demonstrates the classic two-bit strategy:

```python
from proper_line_follower import BinaryLineBangBangController

controller = BinaryLineBangBangController(forward_speed=0.2, turn_speed=0.35)

def step(world, dt):
    controller(robot, world, dt)
    world.step(dt)
```

Implement your own controller by following the same signature: `(robot, world, dt) -> None`. You have full access to the robot’s sensors via `robot.state`.

## Demos

- `python3 simulation_environment/proper_line_follower/demos/run_manual.py`  
  Drive with WASD/arrow keys (reuses the shared manual controller).

- `python3 simulation_environment/proper_line_follower/demos/run_auto_template.py`  
  Runs the bang-bang controller. Edit the constants or drop in your own controller.

- `python3 simulation_environment/proper_line_follower/demos/eval_harness.py`  
  Batch-runs your controller (edit `user_controller_factory`) across several track/robot combos and prints a quick adherence score.

## Typical workflow

1. **Pick a preset**  
   ```python
   world, spec = create_track_world("chicane_loop")
   robot = create_robot("wide_body", pose=default_track_entry_pose(spec))
   world.add_object(robot.robot)
   ```

2. **Write your controller**  
   Accept `(robot, world, dt)` arguments, read sensor bits, and command `robot.drive`.

3. **Run locally**  
   Use the manual or auto demo as a starting point. Swap in your controller and track/robot names.

4. **Evaluate**  
   Edit `proper_line_follower/demos/eval_harness.py` to construct your controller, then run the harness to see how it performs on multiple scenarios.

## Extending

- Add new tracks by registering additional `TrackSpec` entries.
- Define new robot layouts by adding `RobotSpec` instances and tweaking sensor offsets or drive parameters.
- Create more sophisticated controllers (PID, state-estimation based, etc.) and share them via the `controllers/` package.

This package deliberately avoids any CLI/argparse plumbing to keep it notebook- and script-friendly—simply import the pieces you need and start experimenting. Have fun building smarter line followers!

