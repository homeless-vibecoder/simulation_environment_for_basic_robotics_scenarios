"""Deterministic snapshot for designer hover menu labels/structure."""
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

from apps.designer import DesignerApp  # noqa: E402


def _serialize_entry(entry: dict) -> dict:
    node = {"label": str(entry.get("label"))}
    children = entry.get("children")
    if isinstance(children, list):
        node["children"] = [_serialize_entry(child) for child in children]
    if entry.get("checked") is not None:
        node["has_check"] = True
    return node


def _snapshot_menu(app: DesignerApp) -> list[dict]:
    app._refresh_hover_menu()
    if not app.hover_menu:
        return []
    return [{"menu": label, "items": [_serialize_entry(e) for e in entries]} for label, entries in app.hover_menu.menus]


def _find_menu(snapshot: list[dict], name: str) -> dict:
    return next((m for m in snapshot if m.get("menu") == name), {})


def _labels(menu: dict) -> list[str]:
    return [item.get("label") for item in menu.get("items", [])]


def run() -> bool:
    app = DesignerApp()
    menu_snapshot = _snapshot_menu(app)

    print(json.dumps({"menus": menu_snapshot}, indent=2))

    # Clean up pygame to avoid leaking handles when invoked as a script
    pygame.quit()

    top_labels = [m.get("menu") for m in menu_snapshot]
    assert "Workspace" not in top_labels, "Workspace menu should be merged into File"

    file_menu = _find_menu(menu_snapshot, "File")
    file_items = file_menu.get("items", [])
    robot_entry = next((item for item in file_items if item.get("label") == "Robot"), {})
    robot_children = robot_entry.get("children", [])
    robot_labels = [child.get("label") for child in robot_children]
    assert "Save as..." in robot_labels, "Robot file menu should expose Save as..."

    controller_menu = _find_menu(menu_snapshot, "Controller")
    controller_items = _labels(controller_menu)
    assert controller_items, "Controller menu should list modules or placeholders"

    print("Designer UI snapshot PASS")
    return True


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
