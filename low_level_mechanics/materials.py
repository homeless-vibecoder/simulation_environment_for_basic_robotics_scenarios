"""Material traits that describe how objects interact."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Mapping, MutableMapping, Optional, Set


@dataclass
class MaterialProperties:
    """Simple container for physical and signal-level attributes."""

    friction: float = 0.6
    restitution: float = 0.1
    reflectivity: float = 0.3
    traction: float = 0.6
    permeability_tags: Set[str] = field(default_factory=set)
    field_signals: MutableMapping[str, float] = field(default_factory=dict)
    custom: MutableMapping[str, object] = field(default_factory=dict)

    def field_value(self, field_name: str, default: float = 0.0) -> float:
        return float(self.field_signals.get(field_name, default))

    def allows(self, tag: str) -> bool:
        return tag in self.permeability_tags

    def with_overrides(
        self,
        *,
        friction: Optional[float] = None,
        restitution: Optional[float] = None,
        reflectivity: Optional[float] = None,
        traction: Optional[float] = None,
        permeability_tags: Optional[Set[str]] = None,
        field_signals: Optional[Mapping[str, float]] = None,
        custom: Optional[Mapping[str, object]] = None,
    ) -> "MaterialProperties":
        updated = MaterialProperties(
            friction=friction if friction is not None else self.friction,
            restitution=restitution if restitution is not None else self.restitution,
            reflectivity=reflectivity if reflectivity is not None else self.reflectivity,
            traction=traction if traction is not None else self.traction,
            permeability_tags=set(permeability_tags)
            if permeability_tags is not None
            else set(self.permeability_tags),
        )
        updated.field_signals.update(self.field_signals)
        if field_signals:
            updated.field_signals.update(field_signals)
        updated.custom.update(self.custom)
        if custom:
            updated.custom.update(custom)
        return updated

    def as_dict(self) -> Dict[str, object]:
        return {
            "friction": self.friction,
            "restitution": self.restitution,
            "reflectivity": self.reflectivity,
            "traction": self.traction,
            "permeability_tags": sorted(self.permeability_tags),
            "field_signals": dict(self.field_signals),
            "custom": dict(self.custom),
        }


__all__ = ["MaterialProperties"]
