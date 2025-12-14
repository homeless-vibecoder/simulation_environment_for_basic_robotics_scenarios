# Low-Level Mechanics

This package provides deterministic, dependency-light building blocks for 2D robotics simulations.  It focuses on clean data models and introspection so higher-level robot and sensor logic can be layered on later.

## Goals
- Keep the primitives small, explicit, and easy to test.
- Encode enough metadata (poses, materials, interaction traits) so future sensor/motor modules can query the world without intrusive refactors.
- Make it easy to inspect any state (via serialization helpers and diagnostics utilities) for debugging-heavy teaching scenarios.

## Module overview
| Module | Responsibility |
| --- | --- |
| `world.py` | Coordinate frames, transforms, and the `World` container that owns simulation state and deterministic seeding. |
| `geometry.py` | Shape primitives (circle, polygon) plus bounding-volume helpers for coarse collision checks. |
| `materials.py` | Material traits such as friction, reflectivity, traction tags, or custom field emitters. |
| `entities.py` | The `SimObject` model tying pose, geometry, and material traits together, including hooks for motion and interactions. |
| `diagnostics.py` | Lightweight logging helpers to snapshot world/object state for visualization or troubleshooting. |

## Future layers
- **Robot cores**: chassis builders, constraint solvers, and actuator interfaces sitting on top of `SimObject`.
- **Sensors & motors**: catalogs that instantiate realistic bundles (latency, noise, field sensitivities) using the materials/geometry data described here.
- **Visualization**: thin GUI/CLI tools that consume diagnostics snapshots to show true vs sensed values.

Each future layer should depend on these primitives rather than introducing new ad-hoc structures. For example, a line-sensor catalog entry can describe its footprint entirely via `Pose2D` and `Shape2D`, while controller templates should derive their debugging overlays from `SnapshotLogger`.

## Quick example
```python
from low_level_mechanics.world import World, Pose2D
from low_level_mechanics.geometry import Circle
from low_level_mechanics.materials import MaterialProperties
from low_level_mechanics.entities import SimObject

world = World(random_seed=7)
robot = SimObject(
    name="robot",
    pose=Pose2D(0.0, 0.0, 0.0),
    shape=Circle(radius=0.2),
    material=MaterialProperties(friction=0.6, reflectivity=0.4),
)
world.add_object(robot)
print(world.summary())
```
