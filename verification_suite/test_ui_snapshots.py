"""Capture deterministic UI snapshots and rounding behavior."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


# Allow pygame to initialize without a real display
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

import pygame  # noqa: E402

from apps.runner import RunnerApp  # noqa: E402


def _snapshot_menu(app: RunnerApp) -> list[dict]:
    app._refresh_hover_menu()
    snapshot = []
    for label, entries in app.hover_menu.menus:  # type: ignore[assignment]
        snapshot.append({"menu": label, "items": [_serialize_entry(e) for e in entries]})
    return snapshot


def _serialize_entry(entry: dict) -> dict:
    node = {"label": str(entry.get("label"))}
    children = entry.get("children")
    if isinstance(children, list):
        node["children"] = [_serialize_entry(child) for child in children]
    if entry.get("checked") is not None:
        node["has_check"] = True
    return node


def _snapshot_devices(app: RunnerApp) -> dict:
    motors = sorted(app.sim.motors.keys()) if app.sim else []
    sensors = sorted(app.sim.sensors.keys()) if app.sim else []
    return {"motors": motors, "sensors": sensors}


def _check_rounding(app: RunnerApp) -> bool:
    samples = {
        "small": app._fmt_value(0.12399),
        "large": app._fmt_value(12.3456),
        "negative": app._fmt_value(-0.9876),
        "imu": app._fmt_value({"ang": 1.2345, "lin": (0.1111, -0.2222)}),
    }
    return samples == {
        "small": "0.124",
        "large": "12.35",
        "negative": "-0.988",
        "imu": "{ang: 1.23, lin: (0.11, -0.22)}",
    }


def run() -> bool:
    app = RunnerApp()
    menu_snapshot = _snapshot_menu(app)
    devices_snapshot = _snapshot_devices(app)
    rounding_ok = _check_rounding(app)

    payload = {
        "menus": menu_snapshot,
        "devices": devices_snapshot,
        "rounding": rounding_ok,
    }
    print(json.dumps(payload, indent=2))

    # Restore stdout/pygame so downstream scripts stay clean
    try:
        sys.stdout = app._orig_stdout
    finally:
        pygame.quit()

    capture_menu = next((m for m in menu_snapshot if m["menu"] == "Capture"), {})
    run_menu = next((m for m in menu_snapshot if m["menu"] == "Run"), {})
    view_menu = next((m for m in menu_snapshot if m["menu"] == "View"), {})

    def _labels(menu: dict) -> list[str]:
        return [item["label"] for item in menu.get("items", [])]

    capture_top = _labels(capture_menu)
    run_labels = _labels(run_menu)
    view_labels = _labels(view_menu)

    nested_ok = (
        capture_top == ["Snapshots", "Logging"]
        and any(child["label"] == "Resume from snapshot" and child.get("children") for child in run_menu.get("items", []))
        and all("Reposition" not in label for label in view_labels)
    )

    passed = bool(menu_snapshot) and rounding_ok and nested_ok
    print(f"UI snapshot + rounding test -> {'PASS' if passed else 'FAIL'}")
    return passed


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
