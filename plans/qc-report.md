# QC Report – 2025-12-09

## Designer
- Cmd/Ctrl+Z only targets robot edits; environment strokes rely on a separate menu undo, so drawing undo/redo is not keyboard-accessible. Impact: users cannot quickly recover drawing mistakes.
```
876:898:/Users/irakli/Desktop/Polished_projects_for_Github/RBE_IQP/simulation_environment/apps/designer.py
while self.running:
    ...
    if event.key == pygame.K_z and (event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META | pygame.KMOD_GUI)):
        if event.mod & pygame.KMOD_SHIFT:
            self._redo()
        else:
            self._undo()
```

- Drawing UX is limited to mark/wall strokes with brush thickness; no shape primitives, no way to treat drawings as objects, and no custom object storage/import. Impact: requested draw-as-object workflow and custom designs are missing.
```
318:336:/Users/irakli/Desktop/Polished_projects_for_Github/RBE_IQP/simulation_environment/apps/designer.py
env_entries: List[Dict[str, object]] = [
    {"label": "Draw mark", ...},
    {"label": "Draw wall", ...},
]
... Brush Thin/Medium/Thick ...
{"label": "Exit env drawing", ...},
{"label": "Clear drawings", ...},
{"label": "Set bounds (drag)", ...},
{"label": "Clear bounds", ...},
{"label": "Undo env", ...},
{"label": "Redo env", ...},
```

- Designer only loads existing scenarios; there is no create-new file flow, no explicit robot vs environment/custom mode separation, no advanced per-device view, and no camera/environment rotation binding (shift+drag). Impact: users cannot create new/custom assets or enter the advanced tuning view the feedback called for.
```
96:110:/Users/irakli/Desktop/Polished_projects_for_Github/RBE_IQP/simulation_environment/apps/designer.py
self.dropdown = pygame_gui.elements.UIDropDownMenu(
    options_list=self.scenario_names or ["<none>"],
    starting_option=self.scenario_name or "<none>",
    ...
)
self.btn_load = ... "Load"
self.btn_save = ... "Save"
```

## Runner / Capture
- Capture menu is flat and exposes snapshot loading and logger controls directly; top bar still shows Save/Load snapshot buttons. Feedback asked for hover->subitems and keeping specific snapshots out of the default view. Impact: cluttered capture UX and snapshot selection is still front-and-center.
```
194:199:/Users/irakli/Desktop/Polished_projects_for_Github/RBE_IQP/simulation_environment/apps/runner.py
self.btn_snap = ... "Save snapshot"
self.btn_load_snap = ... "Load snapshot"
```
```
1679:1717:/Users/irakli/Desktop/Polished_projects_for_Github/RBE_IQP/simulation_environment/apps/runner.py
snapshot_entries = ["Quick snapshot", "Save snapshot as...", "Load snapshot from file", ... latest list ]
logger_entries = ["Start/Stop logging", "Export log", ... rate/duration toggles]
self.hover_menu = HoverMenu([... ("Capture", capture_menu), ...])
```

- Reposition mode and Reset/Save spawn buttons remain, though feedback said to drop the dedicated reposition mode and redundant spawn controls. Impact: extra mode-switching friction.
```
238:245:/Users/irakli/Desktop/Polished_projects_for_Github/RBE_IQP/simulation_environment/apps/runner.py
self.btn_reposition_mode = pygame_gui.elements.UIButton(... "Reposition robot")
self.btn_reset_pose = pygame_gui.elements.UIButton(... "Reset to spawn")
self.btn_set_spawn = pygame_gui.elements.UIButton(... "Save as spawn")
```

- IMU readings still flow through generic live-state rendering; any non-numeric/tuple values fall back to raw string, which matches the report of IMU showing "set" instead of numbers. No IMU-specific labels/rounding beyond the generic formatter. Impact: unclear IMU display and missing rounding guarantee for that sensor.
```
1093:1100:/Users/irakli/Desktop/Polished_projects_for_Github/RBE_IQP/simulation_environment/apps/runner.py
motors = {name: getattr(motor, "last_command", 0.0) ...}
sensors = dict(getattr(self.sim, "last_sensor_readings", {}) or {})
self.live_state = {"motors": motors, "sensors": sensors, ...}
```
```
1043:1055:/Users/irakli/Desktop/Polished_projects_for_Github/RBE_IQP/simulation_environment/apps/runner.py
try:
    if isinstance(value, (list, tuple)):
        return "(" + ", ".join(self._fmt_value(v) for v in value) + ")"
    num = float(value)
except (TypeError, ValueError):
    return str(value)
```

## Help / Content
- Help overlay remains a single linear column (no quick-summary vs deeper sections or formatting changes) and lacks the supportive code/analysis view idea; controller and logging details were thin. Impact: users still get dense text with limited structure and no code visualization.
```
1792:1834:/Users/irakli/Desktop/Polished_projects_for_Github/RBE_IQP/simulation_environment/apps/runner.py
for line in topic.get("lines", []):
    lines.extend(self._wrap_text(...))
... self.window_surface.blit(font_body.render(line, True, ...))
```

- Small clarification applied (low-risk copy tweak) to help topics: added bullet-like summaries for controllers, required functions, sensors, logging definitions, and quick start.
```
12:54:/Users/irakli/Desktop/Polished_projects_for_Github/RBE_IQP/simulation_environment/apps/help_content.py
"Pick a scenario (Scenario > name > Load)."
... "Logging = recording selected motor:/sensor: signals to CSV at a chosen rate/duration."
```
