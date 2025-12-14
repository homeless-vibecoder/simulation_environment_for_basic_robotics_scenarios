"""Deterministic checks for runner help/menu specs."""
from __future__ import annotations

import json
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from apps.help_content import serialize_help_topics, serialize_capture_menu


def run() -> bool:
    topics = serialize_help_topics()
    ids = {t["id"] for t in topics}
    required = {"quickstart", "controllers", "required-fns", "sensors-motors", "simulation", "logging-snapshots"}
    assert required.issubset(ids), f"Missing help topics: {required - ids}"
    assert len(ids) == len(topics), "Duplicate help topic ids"
    assert all(t["title"] for t in topics), "All topics need titles"
    assert all(any("Summary" in line for line in t["lines"]) for t in topics), "Each topic needs a summary line"

    capture = serialize_capture_menu()
    labels = set(capture.get("capture_labels", []))
    structure = capture.get("capture_structure", {})
    assert labels == {"Snapshots", "Logging"}, f"Unexpected capture labels: {labels}"
    assert "Snapshots" in structure and structure["Snapshots"] == ["Quick snapshot", "Save snapshot as..."]
    logging_items = structure.get("Logging", [])
    for item in ["Start/Stop logging", "Export log", "Open CSV plotter"]:
        assert item in logging_items, f"Missing logging item: {item}"
    rounding = capture.get("rounding_digits")
    assert rounding in (2, 3), f"Unexpected rounding digits: {rounding}"

    snapshot_path = Path(__file__).resolve().parent / "runner_help_snapshot.json"
    with snapshot_path.open("r", encoding="utf-8") as f:
        snapshot = json.load(f)
    assert snapshot["help_topics"] == topics, "Help topics drifted from snapshot"
    assert set(snapshot["capture_labels"]) == labels, "Capture labels drifted from snapshot"
    assert snapshot.get("capture_structure") == structure, "Capture structure drifted from snapshot"
    assert snapshot["rounding_digits"] == rounding, "Rounding digits drifted from snapshot"

    print("Runner help topics:", ids)
    print("Capture labels:", sorted(labels))
    print("Rounding digits:", rounding)
    print("PASS")
    return True


if __name__ == "__main__":
    run()
