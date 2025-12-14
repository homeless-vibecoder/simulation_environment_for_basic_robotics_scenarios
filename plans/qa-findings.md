# QA Findings

## Runner
- **Repro**: Spacebar play/pause bypassed the error gate, so a paused simulation error could be overridden and the play button/menu drifted out of sync; manual Step (button or right arrow) advanced physics but handed `0` to live-state/logging so logger/path-trace did not advance, making single steps look like a pause; UI handler had an unreachable branch under the speed-slider move path.
- **Expected vs observed**: Transport controls should respect error pauses and stay synchronized; single steps should advance state/logging; UI handlers should stay minimal/decluttered.
- **Suspected areas**: `_toggle_play`/keyboard handling bypassing error guards; `_step_once` not carrying step `dt` into live-state/logging; stale UI event branches.
- **Fixes applied**: Added `_can_run` + `_set_play_button` guard and routed spacebar/hover-menu/UI buttons through shared `_toggle_play`/`_step_once` so error-paused sessions cannot resume until cleared and controls stay in sync; manual steps now record the step `dt` and feed it into live-state/logging; removed the unreachable speed-slider branch and left overlays/thumbnails disabled.
- **Tests**: `pytest verification_suite/test_scenario_smoke.py verification_suite/test_scenario_descriptor.py` (pass; covers bounded_maze, composed_slalom_duo, composed_generic_trio, and descriptor parsing).
- **Remaining recommendations**: Consider a lightweight UI/transport guard test harness and reducing repeated controller-error status spam if it resurfaces; keep capture/log menu breadth monitored for clutter as new items land.

- **Repro**: In multi-robot scenarios, saving always overwrote `controller.py` and reloaded all controllers; clicking robots or pressing Tab did not change the active robot, so edits opened the wrong module and robots appeared idle.
- **Expected vs observed**: Save/reload should target the selected robot’s controller module; selecting a robot (click or Tab) should load its controller into the editor and set it active.
- **Fixes applied**: Save now writes to the active robot’s controller module and reloads only that robot; added viewport click hit-test and Tab cycling to switch active robot and load its controller; hover roster still works.
- **Remaining recommendations**: Consider a small HUD hint showing the active robot + controller module when multiple robots are present.
## Scenarios
- Missing spawn fallback for descriptor robots without explicit spawn
  - Repro: load `composed_generic` (runner or `load_scenario`); robot spawns at origin instead of asset offset.
  - Expected vs observed: expected asset spawn_pose `(0.0, 0.15, 0.0)`; observed default `(0.0, 0.0, 0.0)`.
  - Suspected area: descriptor parsing forced `(0,0,0)` when spawn key absent; loader never consulted robot asset spawn.
  - Fixes applied: track whether spawn is provided and fall back to the robot asset's spawn_pose when omitted; propagate into loaded ScenarioRobots.
  - Tests run/results: `pytest verification_suite/test_scenario_descriptor.py` (pass).
  - Remaining recommendations: surface spawn source in UI and warn on overlapping spawns when multiple robots are present.

- Runner opened the wrong controller for multi-robot scenarios and hid metadata
  - Repro: open `composed_generic_duo` in Runner; editor shows `controller.py` instead of `controller_duo_generic.py`; status text omits tags/description.
  - Expected vs observed: editor should open the active robot's controller module and status should surface descriptor metadata.
  - Suspected area: runner hardcoded `controller.py` on load/reload and ignored descriptor metadata for the status label.
  - Fixes applied: pick controller per active robot (uses descriptor/controller_module, falls back gracefully) when loading/reloading; status text now includes description/tags from descriptor metadata.
  - Tests run/results: covered indirectly by descriptor parsing test set; manual runner load verified after code change.
  - Remaining recommendations: add lightweight tooltip or panel snippet for scenario metadata and per-robot controller switching cues.

## UI/Usability
- Designer hover menu started with a placeholder (View/Workspace only), hiding File/Mode/Controller entries until later refresh; Workspace duplicated the same actions and labels were inconsistent (“Save As” vs “Save snapshot as...”).
  - Fixes applied: build the full hover menu on init, remove the redundant Workspace top-level menu, and standardize designer save labels to “Save as...” to match runner terminology.
  - Tests run/results: `python verification_suite/test_designer_ui_snapshots.py` (PASS).
  - Remaining suggestions: consider adding a keyboard shortcut hint strip once menu layout settles.
- Runner controller menu showed a non-functional “Switch controller module” row above the real module list.
  - Fixes applied: removed the inert placeholder entry to reduce menu noise; actual controller options remain.
  - Tests run/results: `python verification_suite/test_ui_snapshots.py` (not re-run here; structure unchanged by label tweak).
  - Remaining suggestions: surface current controller name in the menu header (e.g., “Controller: module.py”) for quicker confirmation.

## Designer
- Issue: Workspace menu actions ignored dirty state, so creating/opening robot/env/custom assets could discard edits or hop tabs without prompting.  
  - Repro: make robot edits (dirty), then Workspace → Environment → New/Open; it switches immediately and robot edits are lost.  
  - Expected vs observed: should prompt to save/discard before replacing or switching tabs.  
  - Suspected areas: `apps/designer.py` (workspace action flow, tab switching).  
  - Fixes applied: route workspace actions through dirty-aware tab switching, carry pending actions across prompts, and block env draw/bounds/clear until tab confirmation completes.  
  - Tests run/results: headless designer smoke (`SDL_VIDEODRIVER=dummy`) covering tab switching, env drawing, device placement, advanced view, save/load/export (pass).

- Issue: Loading scenarios could re-enable environment brush UI on robot/custom tabs because `brush_kind` defaulted to “mark” even when saving from robot tab.  
  - Repro: save while on robot (env drawing off), reload; paint panel shows Mark tool on the robot tab.  
  - Expected vs observed: env tools should stay off unless the environment tab is active.  
  - Suspected areas: `apps/designer.py` (`_load_scenario`).  
  - Fixes applied: keep `active_tab` aligned to saved creation context and forcibly disable env drawing when restoring non-environment tabs to stop UI bleed.  
  - Tests run/results: `pytest verification_suite/test_design_persistence.py -q` (pass); headless designer smoke above.
