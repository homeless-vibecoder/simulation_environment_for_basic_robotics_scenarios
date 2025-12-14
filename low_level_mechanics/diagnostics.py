"""Diagnostics utilities for capturing world/object state."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .world import World


@dataclass
class Snapshot:
    """Serializable representation of a world's state at a time step."""

    time: float
    step: int
    objects: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)
    tag: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        payload = {
            "time": self.time,
            "step": self.step,
            "objects": self.objects,
            "metadata": dict(self.metadata),
        }
        if self.tag is not None:
            payload["tag"] = self.tag
        return payload


class SnapshotLogger:
    """Collects snapshots for later visualization or debugging."""

    def __init__(self) -> None:
        self._snapshots: List[Snapshot] = []

    def record(
        self,
        world: World,
        *,
        tag: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Snapshot:
        data = world.snapshot_dict()
        metadata = dict(data.get("metadata", {}))
        if extra_metadata:
            metadata.update(extra_metadata)
        snapshot = Snapshot(
            time=data["time"],
            step=data["step"],
            objects=data["objects"],
            metadata=metadata,
            tag=tag,
        )
        self._snapshots.append(snapshot)
        return snapshot

    def export(self) -> List[Dict[str, Any]]:
        return [snap.as_dict() for snap in self._snapshots]

    def clear(self) -> None:
        self._snapshots.clear()

    def __len__(self) -> int:
        return len(self._snapshots)

    def __iter__(self):  # pragma: no cover - trivial delegator
        return iter(self._snapshots)


__all__ = ["Snapshot", "SnapshotLogger"]
