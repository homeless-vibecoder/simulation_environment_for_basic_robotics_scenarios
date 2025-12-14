# Backlog – 2025-12-09

## High
- [Designer-Followups] Add env drawing undo/redo to Cmd/Ctrl+Z and surface a clear draw-mode indicator near select/add/draw controls. Tests: keyboard undo/redo updates drawings; indicator toggles with env tool; manual draw multiple strokes without reselecting mode.
- [Runner-Help-Followups] Rework Capture UX: keep snapshot/log options in a nested hover panel (no default load list), move continue-from-snapshot into Run, and drop the top-row Load/Save snapshot buttons. Tests: capture menu serialization shows nested entries only; top bar lacks load/save snapshot buttons; Run menu exposes resume from snapshot.
- [Runner-Help-Followups] Remove dedicated reposition mode and Reset/Save spawn buttons; rely on drag + snapshots. Tests: reposition_mode flag removed; dragging robot works without a mode toggle; UI no longer renders spawn buttons.

## Medium
- [Designer-Followups] Add shape primitives (rectangle/triangle) that become objects with editable properties; keep drawings rigid to the robot; allow storing/importing custom objects and a create-new scenario/file flow with robot/env/custom modes. Tests: create new scenario; add shape -> properties persist through save/load; custom object saved to disk and re-imported; mode switch cleanly scopes robot vs environment assets.
- [Designer-Followups / Visual-Polish] Bind shift+drag for camera/environment rotation and expose a small control to reset rotation. Tests: shift+drag rotates view; reset returns to 0°; drawings and robot stay aligned after rotation.
- [Runner-Help-Followups] Ensure IMU/state display shows numeric values with labels and rounding (no raw set/dict). Tests: simulated IMU reading renders yaw/accel numbers to 2 decimals; generic sensor fallback avoids showing "set" strings.
- [Content-Scenarios] Expand help overlay structure: add quick how-to summaries vs deeper sections, include a small controller example, clearer logging definition, and plan a supportive/analysis view stub for future work. Tests: serialize_help_topics includes new sections; manual check for spacing/bullets; optional snapshot of supportive-view config once implemented.
- [Content-Scenarios] Add scenario thumbnails/one-line descriptions to Runner/Designer selection so new curated setups are discoverable. Tests: dropdown/hover shows description per scenario; selecting updates status text/help; list stays in sync when scenarios are added.
- [Core/Config] Add unit coverage and docs for Optional dataclass parsing (e.g., bounds) and the new `line_array` sensor type so schema/loader behavior stays clear. Tests: loader round-trip with Optional dataclass passes; docs mention supported sensor types including line_array.
