"""Manual keyboard controller for the line follower robot."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Sequence, Tuple

try:  # pragma: no cover - pygame availability depends on host
    import pygame
except ImportError as exc:  # pragma: no cover
    raise ImportError("manual_controller requires pygame to read keyboard state.") from exc


def _default_keymap() -> Dict[str, Tuple[int, ...]]:
    return {
        "forward": (pygame.K_w, pygame.K_UP),
        "backward": (pygame.K_s, pygame.K_DOWN),
        "left": (pygame.K_a, pygame.K_LEFT),
        "right": (pygame.K_d, pygame.K_RIGHT),
        "boost": (pygame.K_LSHIFT, pygame.K_RSHIFT),
        "brake": (pygame.K_LCTRL, pygame.K_RCTRL),
        "faster": (pygame.K_e,),
        "slower": (pygame.K_q,),
    }


@dataclass(frozen=True)
class ManualCommand:
    left: float
    right: float
    hold_position: bool


@dataclass
class ManualDifferentialController:
    """Translate keyboard input into differential wheel commands."""

    max_speed: float = 0.25
    turn_speed: float = 0.4
    boost_multiplier: float = 1.4
    speed_scale: float = 0.5
    min_speed_scale: float = 0.2
    max_speed_scale: float = 1.0
    keymap: Dict[str, Tuple[int, ...]] = field(default_factory=_default_keymap)
    _edge_cache: Dict[str, bool] = field(default_factory=dict, init=False, repr=False)

    def command_from_keys(self, pressed: Sequence[bool]) -> ManualCommand:
        """Return wheel commands plus whether to hold position."""
        self._update_speed_scale(pressed)

        throttle = 0.0
        if self._any_pressed(pressed, "forward"):
            throttle += 1.0
        if self._any_pressed(pressed, "backward"):
            throttle -= 1.0

        turn = 0.0
        if self._any_pressed(pressed, "left"):
            turn += 1.0
        if self._any_pressed(pressed, "right"):
            turn -= 1.0

        if self._any_pressed(pressed, "brake"):
            return ManualCommand(0.0, 0.0, True)

        boost = self.boost_multiplier if self._any_pressed(pressed, "boost") else 1.0
        linear = throttle * (self.max_speed * self.speed_scale) * boost
        angular = turn * (self.turn_speed * self.speed_scale)

        left = _clamp(linear - angular)
        right = _clamp(linear + angular)
        hold = throttle == 0.0 and turn == 0.0
        return ManualCommand(left, right, hold)

    def _any_pressed(self, pressed: Sequence[bool], action: str) -> bool:
        keys = self.keymap.get(action, ())
        return any(pressed[key] for key in keys)

    def _update_speed_scale(self, pressed: Sequence[bool]) -> None:
        if self._edge_triggered(pressed, "faster"):
            self.speed_scale = min(self.max_speed_scale, self.speed_scale + 0.1)
        if self._edge_triggered(pressed, "slower"):
            self.speed_scale = max(self.min_speed_scale, self.speed_scale - 0.1)

    def _edge_triggered(self, pressed: Sequence[bool], action: str) -> bool:
        current = self._any_pressed(pressed, action)
        previous = self._edge_cache.get(action, False)
        self._edge_cache[action] = current
        return current and not previous


def _clamp(value: float, limit: float = 1.0) -> float:
    return max(-limit, min(limit, value))


__all__ = ["ManualDifferentialController", "ManualCommand"]

