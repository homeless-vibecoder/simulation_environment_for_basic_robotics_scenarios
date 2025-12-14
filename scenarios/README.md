# Scenario Library (curated)

## Current scenarios
- `bounded_maze`: Bounded maze with left-hand wall follower robot; distance sensors front/left/right; bounds keep robot inside; sample log saved under `logs/bounded_maze_sample.json`.
- `slalom_field`: Zig-zag posts with oscillating gait; open bounds; safety slowdown on close hits; sample log `logs/slalom_field_sample.json`.
- `tight_corridor`: Narrow S-bend corridor tuned for distance centering; logs in `logs/tight_corridor_sample.json`.
- `line_loop`: Closed rectangular line track with line-array follower and optional front range guard; log at `logs/line_loop_sample.json`.
- `composed_generic`: Uses shared assets (`assets/environments/generic_world.json`, `assets/robots/generic_robot.json`) plus its own controller.
- `composed_slalom`: Uses shared assets (`assets/environments/slalom_world.json`, `assets/robots/slalom_robot.json`) plus its own controller.
- `composed_team_line`: Multi-robot descriptor example; two generic robots share `assets/environments/generic_world.json` with a shared `controller_team.py`.
- `composed_slalom_duo`: Two slalom robots on `assets/environments/slalom_world.json` with `controller_duo.py`.
- `mouse_maze_competition`: Seeded head-to-head race in `assets/environments/mouse_maze_world.json`; two generic robots with `controller_mouse.py`; sample trace at `logs/trace_sample.json`.
- `composed_generic_duo`: Descriptor-only; two generic robots with mild lane bias on `generic_world.json` using `controller_duo_generic.py`.
- `composed_generic_trio`: Three generic robots on the same course, spaced out for smoke checks; also uses `controller_duo_generic.py`.

## scenario.json schema (descriptor)
Descriptors live beside each scenario and replace ad-hoc world/robot pairs. They remain backward-compatible with legacy `world.json` + `robot.json` by synthesizing a descriptor automatically.

```json
{
  "id": "mouse_maze_competition",          // scenario id (defaults to folder name)
  "name": "Mouse Maze Competition",        // human-readable name
  "description": "short text",             // optional
  "thumbnail": "thumbnail.png",            // optional PNG in the scenario folder
  "help": "help.md",                       // optional help asset
  "environment": "../assets/environments/mouse_maze_world.json",
  "seed": 1337,                            // optional; overrides world seed if missing
  "robots": [
    {
      "id": "blue",                        // robot identifier (used for namespacing)
      "ref": "../assets/robots/generic_robot.json",
      "spawn_pose": [-0.95, -0.75, 0.0],    // world coordinates (meters, yaw radians)
      "controller": "controller_mouse",     // optional module override
      "role": "lane_bottom",                // optional metadata
      "metadata": {}
    }
  ]
}
```

Notes:
- Spawn poses are always world-frame (meters, yaw in radians) relative to the environment origin.
- `robots` supports N robots; bodies/devices are namespaced when multiple robots are present.
- Per-robot controllers: set `controller` on a robot entry to override the default `controller_module` in the robot asset.
- Thumbnails: place a small PNG in the scenario folder (e.g., `thumbnail.png`). Runner/Designer will display it if present; assets can also reference a shared thumbnail elsewhere via relative path.
- Legacy pairs still load: `world.json` + `robot.json` are wrapped into a descriptor at load time.

## Loading and discovery
- Runner/Designer list scenarios via `apps.shared_ui.list_scenarios`, which now surfaces descriptions and thumbnails.
- Controllers live beside each scenario and hot-reload when Runner reloads code. Per-robot controller overrides are supported through `robots[].controller`.

## Asset reuse
- Shared assets stay under `assets/environments/` and `assets/robots/`. Descriptor-based scenarios reference them via relative paths, keeping environments/robots reusable across scenarios.
