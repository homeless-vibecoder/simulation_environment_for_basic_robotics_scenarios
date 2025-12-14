"""Shared UI helpers for runner and designer apps."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple, Optional, Dict
import copy
import math

import pygame

from low_level_mechanics.geometry import Polygon
from core.persistence import list_scenario_summaries

# --- Palette & drawing helpers ---------------------------------------------


def _clamp_channel(x: float) -> int:
    return max(0, min(255, int(x)))


def blend_color(color: tuple[int, int, int], target: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return tuple(_clamp_channel(c + (target[i] - c) * t) for i, c in enumerate(color))


def lighten_color(color: tuple[int, int, int], amount: float = 0.15) -> tuple[int, int, int]:
    return blend_color(color, (255, 255, 255), amount)


def darken_color(color: tuple[int, int, int], amount: float = 0.15) -> tuple[int, int, int]:
    return blend_color(color, (0, 0, 0), amount)


def with_alpha(color: tuple[int, int, int], alpha: int) -> tuple[int, int, int, int]:
    return (color[0], color[1], color[2], max(0, min(255, alpha)))


DESIGNER_THEME: dict[str, tuple[int, int, int]] = {
    "bg": (20, 24, 28),
    "viewport": (14, 16, 22),
    "viewport_border": (92, 108, 132),
    "grid_major": (44, 48, 56),
    "grid_minor": (36, 36, 42),
    "body_outline": (44, 56, 74),
    "selection": (120, 200, 255),
    "selection_fill": (170, 205, 255),
    "handle_fill": (170, 210, 255),
    "handle_border": (40, 60, 90),
    "hover_cross": (90, 130, 190),
    "text_primary": (230, 234, 240),
    "text_muted": (190, 205, 220),
    "help_text": (180, 185, 195),
    "badge": (42, 58, 90),
    "badge_text": (240, 240, 240),
    "device_motor": (96, 210, 180),
    "device_sensor": (240, 208, 140),
}


@dataclass
class ScenarioListEntry:
    id: str
    name: str
    description: Optional[str]
    thumbnail: Optional[Path]
    path: Path


def list_scenarios(base_path: Path, *, with_metadata: bool = False) -> List[ScenarioListEntry | str]:
    """Return scenarios with optional metadata (description/thumbnail)."""
    names: List[ScenarioListEntry | str] = []
    if not base_path.exists():
        return names
    summaries = list_scenario_summaries(base_path)
    if with_metadata:
        for summary in summaries:
            names.append(
                ScenarioListEntry(
                    id=summary.id,
                    name=summary.name,
                    description=summary.description,
                    thumbnail=summary.thumbnail,
                    path=summary.path,
                )
            )
    else:
        names.extend([summary.id for summary in summaries])
    return sorted(names, key=lambda n: n.id if isinstance(n, ScenarioListEntry) else n)


def world_to_screen(
    point: Tuple[float, float],
    viewport: pygame.Rect,
    scale: float,
    offset: Tuple[float, float],
    rotation: float = 0.0,
) -> Tuple[int, int]:
    ox, oy = offset
    cx = viewport.x + viewport.width // 2
    cy = viewport.y + viewport.height // 2
    x, y = point[0] + ox, point[1] + oy
    if rotation:
        cos_r = math.cos(rotation)
        sin_r = math.sin(rotation)
        x, y = (x * cos_r - y * sin_r, x * sin_r + y * cos_r)
    return (int(cx + x * scale), int(cy - y * scale))


def screen_to_world(
    pos: Tuple[int, int],
    viewport: pygame.Rect,
    scale: float,
    offset: Tuple[float, float],
    rotation: float = 0.0,
) -> Tuple[float, float]:
    ox, oy = offset
    cx = viewport.x + viewport.width // 2
    cy = viewport.y + viewport.height // 2
    x = (pos[0] - cx) / scale - ox
    y = -(pos[1] - cy) / scale - oy
    if rotation:
        cos_r = math.cos(-rotation)
        sin_r = math.sin(-rotation)
        x, y = (x * cos_r - y * sin_r, x * sin_r + y * cos_r)
    return (x, y)


class HoverMenu:
    """Lightweight hover-to-open menu bar for pygame surfaces."""

    def __init__(
        self,
        menus: List[Tuple[str, List[Dict[str, object]]]],
        pos: Tuple[int, int] = (12, 8),
        font: Optional[pygame.font.Font] = None,
    ) -> None:
        self.menus = menus  # [(label, entries)], entry: {"label", "action", "checked"?}
        self.pos = pos
        self.font = font or pygame.font.Font(pygame.font.get_default_font(), 14)
        self.header_h = 24
        self.padding = 10
        self.open_menu: Optional[int] = None
        self.open_submenu: Optional[Tuple[int, int]] = None  # (menu_idx, entry_idx)
        self.header_rects: List[pygame.Rect] = []
        self.entry_rects: Dict[Tuple[int, int], pygame.Rect] = {}
        self.close_grace_ms = 160
        self._last_inside_ms: int = pygame.time.get_ticks()

    def _compute_headers(self) -> None:
        x, y = self.pos
        self.header_rects = []
        for label, _ in self.menus:
            w = self.font.size(label)[0] + self.padding * 2
            self.header_rects.append(pygame.Rect(x, y, w, self.header_h))
            x += w + 8

    def _menu_entries_rects(self, idx: int) -> List[pygame.Rect]:
        rects: List[pygame.Rect] = []
        if idx < 0 or idx >= len(self.menus):
            return rects
        header = self.header_rects[idx]
        entries = self.menus[idx][1]
        menu_w = max(self.font.size(e.get("label", ""))[0] + self.padding * 3 for e in entries) if entries else header.width
        x = header.x
        y = header.bottom  # eliminate hover gap
        rects = []
        for _ in entries:
            rects.append(pygame.Rect(x, y, menu_w, self.header_h))
            y += self.header_h  # tight stacking
        return rects

    def _submenu_entries_rects(self, menu_idx: int, entry_idx: int) -> List[pygame.Rect]:
        rects: List[pygame.Rect] = []
        if not self.header_rects:
            self._compute_headers()
        if menu_idx < 0 or menu_idx >= len(self.menus):
            return rects
        entries = self.menus[menu_idx][1]
        if entry_idx < 0 or entry_idx >= len(entries):
            return rects
        children = entries[entry_idx].get("children")
        if not isinstance(children, list) or not children:
            return rects
        parent_rects = self._menu_entries_rects(menu_idx)
        if entry_idx >= len(parent_rects):
            return rects
        parent = parent_rects[entry_idx]
        menu_w = max(self.font.size(c.get("label", ""))[0] + self.padding * 3 for c in children)
        x = parent.right - 2
        y = parent.y
        for _ in children:
            rects.append(pygame.Rect(x, y, menu_w, self.header_h))
            y += self.header_h
        return rects

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.header_rects:
            self._compute_headers()
        if event.type == pygame.MOUSEMOTION:
            # If hovering over a header, open it; if hovering over an open menu, keep it open.
            for i, rect in enumerate(self.header_rects):
                if rect.collidepoint(event.pos):
                    self.open_menu = i
                    self._last_inside_ms = pygame.time.get_ticks()
                    break
            if self.open_menu is not None:
                entry_rects = self._menu_entries_rects(self.open_menu)
                entries = self.menus[self.open_menu][1]
                hovered_child = None
                for rect in entry_rects:
                    if rect.collidepoint(event.pos):
                        self._last_inside_ms = pygame.time.get_ticks()
                        idx = entry_rects.index(rect)
                        hovered_child = idx if entries[idx].get("children") else None
                        break
                if hovered_child is not None:
                    self.open_submenu = (self.open_menu, hovered_child)
                sub_rects: List[pygame.Rect] = []
                if self.open_submenu:
                    sub_rects = self._submenu_entries_rects(*self.open_submenu)
                for rect in sub_rects:
                    if rect.collidepoint(event.pos):
                        self._last_inside_ms = pygame.time.get_ticks()
                        break
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Click in headers toggles open state
            for i, rect in enumerate(self.header_rects):
                if rect.collidepoint(event.pos):
                    self.open_menu = i if self.open_menu != i else None
                    self.open_submenu = None
                    if self.open_menu is not None:
                        self._last_inside_ms = pygame.time.get_ticks()
                    return True
            # Click in entries
            if self.open_menu is not None:
                entries = self.menus[self.open_menu][1]
                entry_rects = self._menu_entries_rects(self.open_menu)
                for j, rect in enumerate(entry_rects):
                    if rect.collidepoint(event.pos) and j < len(entries):
                        entry = entries[j]
                        if entry.get("children"):
                            self.open_submenu = (self.open_menu, j)
                            return True
                        action = entry.get("action")
                        if callable(action):
                            action()
                        self.open_menu = None
                        self.open_submenu = None
                        return True
                if self.open_submenu and self.open_submenu[0] == self.open_menu:
                    menu_idx, entry_idx = self.open_submenu
                    children = entries[entry_idx].get("children", [])
                    sub_rects = self._submenu_entries_rects(menu_idx, entry_idx)
                    for k, rect in enumerate(sub_rects):
                        if rect.collidepoint(event.pos) and k < len(children):
                            action = children[k].get("action")
                            if callable(action):
                                action()
                            self.open_menu = None
                            self.open_submenu = None
                            return True
                # Click away closes
                if not any(rect.collidepoint(event.pos) for rect in entry_rects) and not any(
                    rect.collidepoint(event.pos)
                    for rect in (self._submenu_entries_rects(*self.open_submenu) if self.open_submenu else [])
                ):
                    self.open_menu = None
                    self.open_submenu = None
        return False

    def update_hover(self, mouse_pos: Tuple[int, int]) -> None:
        if self.open_menu is None:
            return
        now = pygame.time.get_ticks()
        if not self.header_rects:
            self._compute_headers()
        in_header = any(rect.collidepoint(mouse_pos) for rect in self.header_rects)
        entry_rects = self._menu_entries_rects(self.open_menu)
        submenu_rects: List[pygame.Rect] = []
        if self.open_submenu and self.open_submenu[0] == self.open_menu:
            submenu_rects = self._submenu_entries_rects(*self.open_submenu)
        in_menu = any(rect.collidepoint(mouse_pos) for rect in entry_rects)
        in_submenu = any(rect.collidepoint(mouse_pos) for rect in submenu_rects)
        if in_header or in_menu or in_submenu:
            self._last_inside_ms = now
            return
        # Add a tolerance band below the header to reduce accidental closes while moving into the menu.
        header = self.header_rects[self.open_menu]
        menu_width = entry_rects[0].width if entry_rects else header.width
        band_left = min(header.x, entry_rects[0].x if entry_rects else header.x) - 8
        band_right = max(header.right, (entry_rects[0].x + menu_width) if entry_rects else header.right) + 8
        padded = pygame.Rect(band_left, header.bottom, band_right - band_left, self.header_h // 2 + 10)
        if padded.collidepoint(mouse_pos):
            self._last_inside_ms = now
            return
        if now - self._last_inside_ms > self.close_grace_ms:
            self.open_menu = None
            self.open_submenu = None

    def draw(self, surface: pygame.Surface) -> None:
        if not self.header_rects:
            self._compute_headers()
        self.entry_rects.clear()
        header_idle = darken_color(DESIGNER_THEME["viewport"], 0.02)
        header_active = lighten_color(header_idle, 0.08)
        header_outline = DESIGNER_THEME["viewport_border"]
        for i, rect in enumerate(self.header_rects):
            label = self.menus[i][0]
            active = self.open_menu == i
            bg = header_active if active else header_idle
            pygame.draw.rect(surface, bg, rect, border_radius=6)
            pygame.draw.rect(surface, header_outline, rect, 1, border_radius=6)
            surface.blit(self.font.render(label, True, DESIGNER_THEME["text_primary"]), (rect.x + self.padding - 2, rect.y + 4))
        if self.open_menu is None:
            return
        entries = self.menus[self.open_menu][1]
        entry_rects = self._menu_entries_rects(self.open_menu)
        entry_bg = darken_color(DESIGNER_THEME["viewport"], 0.06)
        entry_border = DESIGNER_THEME["viewport_border"]
        sub_bg = darken_color(DESIGNER_THEME["viewport"], 0.1)
        sub_border = darken_color(DESIGNER_THEME["viewport_border"], 0.05)
        check_color = DESIGNER_THEME["device_motor"]
        for j, rect in enumerate(entry_rects):
            entry = entries[j]
            label = entry.get("label", "")
            checked = False
            checker = entry.get("checked")
            if callable(checker):
                try:
                    checked = bool(checker())
                except Exception:
                    checked = False
            pygame.draw.rect(surface, entry_bg, rect, border_radius=6)
            pygame.draw.rect(surface, entry_border, rect, 1, border_radius=6)
            box = pygame.Rect(rect.x + self.padding - 2, rect.y + 6, 12, 12)
            if checked:
                pygame.draw.rect(surface, check_color, box.inflate(-2, -2))
            suffix = " ›" if entry.get("children") else ""
            surface.blit(
                self.font.render(label + suffix, True, DESIGNER_THEME["text_primary"]),
                (box.right + self.padding // 2, rect.y + 4),
            )
        if self.open_submenu and self.open_submenu[0] == self.open_menu:
            entries = self.menus[self.open_menu][1]
            parent_idx = self.open_submenu[1]
            if 0 <= parent_idx < len(entries):
                children = entries[parent_idx].get("children", [])
                sub_rects = self._submenu_entries_rects(self.open_menu, parent_idx)
                for k, rect in enumerate(sub_rects):
                    child = children[k]
                    label = child.get("label", "")
                    checked = False
                    checker = child.get("checked")
                    if callable(checker):
                        try:
                            checked = bool(checker())
                        except Exception:
                            checked = False
                    pygame.draw.rect(surface, sub_bg, rect, border_radius=6)
                    pygame.draw.rect(surface, sub_border, rect, 1, border_radius=6)
                    box = pygame.Rect(rect.x + self.padding - 2, rect.y + 6, 12, 12)
                    if checked:
                        pygame.draw.rect(surface, check_color, box.inflate(-2, -2))
                    surface.blit(
                        self.font.render(str(label), True, DESIGNER_THEME["text_primary"]),
                        (box.right + self.padding // 2, rect.y + 4),
                    )


def draw_polygon(
    surface: pygame.Surface,
    viewport: pygame.Rect,
    poly: Polygon,
    color: Tuple[int, int, int],
    scale: float,
    offset: Tuple[float, float],
    outline: Tuple[int, int, int] = (30, 30, 30),
    rotation: float = 0.0,
    pose=None,
    highlight: Tuple[int, int, int] | None = None,
    outline_width: int = 2,
) -> None:
    verts = poly._world_vertices(pose) if pose is not None else poly.vertices
    pts = [world_to_screen(v, viewport, scale, offset, rotation) for v in verts]
    if len(pts) >= 3:
        pygame.draw.polygon(surface, color, pts, 0)
        if highlight:
            pygame.draw.lines(surface, highlight, True, pts, max(1, outline_width - 1))
        pygame.draw.lines(surface, outline, True, pts, outline_width)


class SimpleTextEditor:
    """Tiny multi-line text editor."""

    def __init__(self, rect: pygame.Rect, font: pygame.font.Font, text: str = "") -> None:
        self.rect = rect
        self.font = font
        self.lines = text.splitlines() or [""]
        self.cursor = [0, 0]  # line, col
        self.has_focus = False
        self.gutter_width = 40
        self.line_height = self.font.get_height() + 2
        self.selection_anchor: Tuple[int, int] | None = None
        self.selection_focus: Tuple[int, int] | None = None
        self.clipboard_text: str = ""
        self.scroll_offset: int = 0
        self.is_dragging: bool = False
        self.history: List[Tuple[List[str], List[int], Tuple[int, int] | None, Tuple[int, int] | None]] = []
        self.future: List[Tuple[List[str], List[int], Tuple[int, int] | None, Tuple[int, int] | None]] = []
        self._push_history()
        # Optional system clipboard support
        try:
            pygame.scrap.init()
        except Exception:
            pass

    def set_text(self, text: str) -> None:
        self.lines = text.splitlines() or [""]
        self.cursor = [0, 0]
        self.selection_anchor = None
        self.selection_focus = None
        self.history.clear()
        self.future.clear()
        self._push_history()

    def text(self) -> str:
        return "\n".join(self.lines)

    def handle_event(self, event: pygame.event.Event) -> None:
        mods = getattr(event, "mod", 0)
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.has_focus = self.rect.collidepoint(event.pos)
            if self.has_focus:
                if event.button == 1:
                    if mods & pygame.KMOD_SHIFT and self.selection_anchor:
                        # extend existing selection
                        self.selection_focus = self._cursor_from_mouse(event.pos)
                        self.cursor = list(self.selection_focus)
                    else:
                        self.cursor = list(self._cursor_from_mouse(event.pos))
                        self.selection_anchor = tuple(self.cursor)
                        self.selection_focus = None
                    self.is_dragging = True
                    self._ensure_cursor_visible()
                elif event.button == 4:  # wheel up (some mice send as buttons)
                    self.scroll_offset = max(0, self.scroll_offset - 1)
                elif event.button == 5:  # wheel down
                    self.scroll_offset = min(max(0, len(self.lines) - 1), self.scroll_offset + 1)
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.is_dragging = False
        if event.type == pygame.MOUSEMOTION and self.is_dragging:
            if getattr(event, "buttons", (0, 0, 0))[0]:
                self.selection_focus = self._cursor_from_mouse(event.pos)
                self.cursor = list(self.selection_focus)
                self._ensure_cursor_visible()
        if not self.has_focus:
            return
        if event.type == pygame.MOUSEWHEEL and self.rect.collidepoint(pygame.mouse.get_pos()):
            self.scroll_offset = max(0, min(len(self.lines) - 1, self.scroll_offset - event.y))
        if event.type == pygame.KEYDOWN:
            mods = getattr(event, "mod", 0)
            ctrl = mods & (pygame.KMOD_CTRL | pygame.KMOD_META | pygame.KMOD_GUI)
            if ctrl and event.key == pygame.K_a:
                self._select_all()
            elif ctrl and event.key == pygame.K_c:
                self._copy_selection()
            elif ctrl and event.key == pygame.K_x:
                self._cut_selection()
            elif ctrl and event.key == pygame.K_v:
                self._paste_clipboard()
            elif ctrl and event.key == pygame.K_z:
                self._undo()
            elif ctrl and event.key == pygame.K_y:
                self._redo()
            elif event.key == pygame.K_BACKSPACE:
                if mods & (pygame.KMOD_META | pygame.KMOD_GUI):
                    self._delete_line()
                else:
                    self._backspace()
            elif event.key == pygame.K_RETURN:
                self._newline()
            elif event.key == pygame.K_TAB and (mods & pygame.KMOD_SHIFT):
                self._outdent()
            elif event.key == pygame.K_TAB:
                self._indent()
            elif event.key == pygame.K_LEFT:
                if mods & (pygame.KMOD_META | pygame.KMOD_GUI):
                    self._move_line_boundary(to_end=False, selecting=bool(mods & pygame.KMOD_SHIFT))
                else:
                    self._move_cursor(-1, 0, selecting=bool(mods & pygame.KMOD_SHIFT))
            elif event.key == pygame.K_RIGHT:
                if mods & (pygame.KMOD_META | pygame.KMOD_GUI):
                    self._move_line_boundary(to_end=True, selecting=bool(mods & pygame.KMOD_SHIFT))
                else:
                    self._move_cursor(1, 0, selecting=bool(mods & pygame.KMOD_SHIFT))
            elif event.key == pygame.K_UP:
                self._move_cursor(0, -1, selecting=bool(mods & pygame.KMOD_SHIFT))
            elif event.key == pygame.K_DOWN:
                self._move_cursor(0, 1, selecting=bool(mods & pygame.KMOD_SHIFT))
            elif event.key == pygame.K_HOME:
                self.cursor[1] = 0
                if mods & pygame.KMOD_SHIFT and self.selection_anchor is None:
                    self.selection_anchor = tuple(self.cursor)
                elif not (mods & pygame.KMOD_SHIFT):
                    self.selection_anchor = None
                    self.selection_focus = None
                self._ensure_cursor_visible()
            elif event.key == pygame.K_END:
                self.cursor[1] = len(self.lines[self.cursor[0]])
                if mods & pygame.KMOD_SHIFT and self.selection_anchor is None:
                    self.selection_anchor = tuple(self.cursor)
                elif not (mods & pygame.KMOD_SHIFT):
                    self.selection_anchor = None
                    self.selection_focus = None
                self._ensure_cursor_visible()
            elif event.unicode and not (mods & (pygame.KMOD_CTRL | pygame.KMOD_META | pygame.KMOD_GUI)):
                self._insert(event.unicode)

    def _insert(self, text: str) -> None:
        self._push_history()
        if self._has_selection():
            self._delete_selection()
        line = self.lines[self.cursor[0]]
        before = line[: self.cursor[1]]
        after = line[self.cursor[1] :]
        self.lines[self.cursor[0]] = before + text + after
        self.cursor[1] += len(text)
        self.selection_anchor = None
        self.selection_focus = None
        self._ensure_cursor_visible()

    def _newline(self) -> None:
        self._push_history()
        if self._has_selection():
            self._delete_selection()
        line = self.lines[self.cursor[0]]
        before = line[: self.cursor[1]]
        after = line[self.cursor[1] :]
        indent = self._leading_spaces(before)
        if before.rstrip().endswith(":"):
            indent += "    "
        self.lines[self.cursor[0]] = before
        self.lines.insert(self.cursor[0] + 1, indent + after)
        self.cursor = [self.cursor[0] + 1, len(indent)]
        self.selection_anchor = None
        self.selection_focus = None
        self._ensure_cursor_visible()

    def _backspace(self) -> None:
        if self.cursor == [0, 0] and not self._has_selection():
            return
        self._push_history()
        if self._has_selection():
            self._delete_selection()
            return
        line = self.lines[self.cursor[0]]
        if self.cursor[1] > 0:
            self.lines[self.cursor[0]] = line[: self.cursor[1] - 1] + line[self.cursor[1] :]
            self.cursor[1] -= 1
        else:
            prev_line = self.lines[self.cursor[0] - 1]
            self.cursor[1] = len(prev_line)
            self.lines[self.cursor[0] - 1] = prev_line + line
            del self.lines[self.cursor[0]]
            self.cursor[0] -= 1
        self.selection_anchor = None
        self.selection_focus = None
        self._ensure_cursor_visible()

    def _delete_line(self) -> None:
        """Delete the entire current line (Meta+Backspace)."""
        if not self.lines:
            return
        self._push_history()
        line_idx = self.cursor[0]
        if len(self.lines) == 1:
            self.lines = [""]
            self.cursor = [0, 0]
        else:
            del self.lines[line_idx]
            if line_idx >= len(self.lines):
                line_idx = len(self.lines) - 1
            self.cursor = [line_idx, 0]
        self.selection_anchor = None
        self.selection_focus = None
        self._ensure_cursor_visible()

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, (25, 25, 25), self.rect)
        pygame.draw.rect(surface, (70, 70, 70), self.rect, 1)
        x, y = self.rect.topleft
        gutter_color = (60, 70, 80)
        pygame.draw.rect(surface, (18, 18, 18), (x, y, self.gutter_width, self.rect.height))
        visible_lines = int(self.rect.height / self.line_height) + 1
        start_line = self.scroll_offset
        end_line = min(len(self.lines), start_line + visible_lines)
        sel = self._normalized_selection()
        for i in range(start_line, end_line):
            y_pos = y + (i - start_line) * self.line_height + 2
            if y_pos > self.rect.bottom:
                break
            gutter_txt = self.font.render(str(i + 1).rjust(3), True, gutter_color)
            surface.blit(gutter_txt, (x + 6, y_pos))
            line = self.lines[i]
            # selection highlight
            if sel and sel[0][0] <= i <= sel[1][0]:
                start_col = sel[0][1] if i == sel[0][0] else 0
                end_col = sel[1][1] if i == sel[1][0] else len(line)
                start_px = self.font.size(line[:start_col])[0]
                end_px = self.font.size(line[:end_col])[0]
                highlight_rect = pygame.Rect(
                    x + self.gutter_width + 6 + start_px, y_pos, max(2, end_px - start_px), self.line_height
                )
                pygame.draw.rect(surface, (40, 60, 90), highlight_rect)
            color = self._color_for_line(line)
            txt_surf = self.font.render(line, True, color)
            surface.blit(txt_surf, (x + self.gutter_width + 6, y_pos))
        if self.has_focus:
            cursor_line = self.cursor[0]
            cursor_col = self.cursor[1]
            cursor_y = y + (cursor_line - start_line) * self.line_height + 4
            cursor_x = x + self.gutter_width + 6 + self.font.size(self.lines[cursor_line][:cursor_col])[0]
            pygame.draw.line(
                surface, (240, 200, 120), (cursor_x, cursor_y), (cursor_x, cursor_y + self.line_height - 6), 2
            )

    def _move_cursor(self, dx: int, dy: int, selecting: bool = False) -> None:
        prev = tuple(self.cursor)
        line = self.cursor[0] + dy
        line = max(0, min(line, len(self.lines) - 1))
        col = self.cursor[1]
        line_len = len(self.lines[line])
        if dx < 0 and col == 0 and line > 0:
            line -= 1
            col = len(self.lines[line])
        elif dx > 0 and col >= line_len and line < len(self.lines) - 1:
            line += 1
            col = 0
        else:
            col = max(0, min(col + dx, line_len))
        self.cursor = [line, col]
        if selecting:
            if self.selection_anchor is None:
                self.selection_anchor = prev
            self.selection_focus = tuple(self.cursor)
        else:
            self.selection_anchor = None
            self.selection_focus = None
        self._ensure_cursor_visible()

    def _move_line_boundary(self, to_end: bool, selecting: bool) -> None:
        prev = tuple(self.cursor)
        line = self.cursor[0]
        if not self.lines:
            self.cursor = [0, 0]
        else:
            if to_end:
                self.cursor = [line, len(self.lines[line])]
            else:
                self.cursor = [line, 0]
        if selecting:
            if self.selection_anchor is None:
                self.selection_anchor = prev
            self.selection_focus = tuple(self.cursor)
        else:
            self.selection_anchor = None
            self.selection_focus = None
        self._ensure_cursor_visible()

    def _cursor_from_mouse(self, pos: Tuple[int, int]) -> Tuple[int, int]:
        x, y = pos
        rel_y = y - self.rect.y
        line_idx = self.scroll_offset + int(rel_y // self.line_height)
        line_idx = max(0, min(line_idx, len(self.lines) - 1))
        rel_x = x - self.rect.x - self.gutter_width - 6
        rel_x = max(0, rel_x)
        line = self.lines[line_idx]
        col = 0
        while col < len(line) and self.font.size(line[: col + 1])[0] < rel_x:
            col += 1
        return (line_idx, col)

    def _color_for_line(self, line: str) -> Tuple[int, int, int]:
        stripped = line.lstrip()
        if stripped.startswith("#"):
            return (120, 160, 200)
        if stripped.startswith(("def ", "class ", "import ", "from ", "return", "with ", "for ", "while ")):
            return (200, 210, 140)
        return (220, 220, 220)

    # --- Selection helpers ------------------------------------------------
    def _has_selection(self) -> bool:
        return self.selection_anchor is not None and self.selection_focus is not None and self.selection_anchor != self.selection_focus

    def _normalized_selection(self) -> Tuple[Tuple[int, int], Tuple[int, int]] | None:
        if not self._has_selection():
            return None
        a = self.selection_anchor
        b = self.selection_focus
        assert a and b
        if a < b:
            return (a, b)
        return (b, a)

    def _select_all(self) -> None:
        if not self.lines:
            return
        self.selection_anchor = (0, 0)
        self.selection_focus = (len(self.lines) - 1, len(self.lines[-1]))
        self.cursor = [self.selection_focus[0], self.selection_focus[1]]

    def _delete_selection(self) -> None:
        sel = self._normalized_selection()
        if not sel:
            return
        (l1, c1), (l2, c2) = sel
        if l1 == l2:
            line = self.lines[l1]
            self.lines[l1] = line[:c1] + line[c2:]
        else:
            head = self.lines[l1][:c1]
            tail = self.lines[l2][c2:]
            self.lines = self.lines[:l1] + [head + tail] + self.lines[l2 + 1 :]
        self.cursor = [l1, c1]
        self.selection_anchor = None
        self.selection_focus = None

    def _copy_selection(self) -> None:
        sel = self._normalized_selection()
        if not sel:
            return
        text = self._selection_text(sel)
        self._set_clipboard(text)

    def _cut_selection(self) -> None:
        if not self._has_selection():
            return
        self._copy_selection()
        self._push_history()
        self._delete_selection()

    def _paste_clipboard(self) -> None:
        text = self._get_clipboard()
        if text is None:
            text = self.clipboard_text
        if text is None:
            return
        self._push_history()
        if self._has_selection():
            self._delete_selection()
        lines = text.splitlines()
        if not lines:
            return
        line = self.lines[self.cursor[0]]
        before = line[: self.cursor[1]]
        after = line[self.cursor[1] :]
        if len(lines) == 1:
            self.lines[self.cursor[0]] = before + lines[0] + after
            self.cursor[1] += len(lines[0])
        else:
            new_lines = [before + lines[0]] + lines[1:-1] + [lines[-1] + after]
            self.lines = self.lines[: self.cursor[0]] + new_lines + self.lines[self.cursor[0] + 1 :]
            self.cursor = [self.cursor[0] + len(lines) - 1, len(lines[-1])]
        self.selection_anchor = None
        self.selection_focus = None

    def _selection_text(self, sel: Tuple[Tuple[int, int], Tuple[int, int]]) -> str:
        (l1, c1), (l2, c2) = sel
        if l1 == l2:
            return self.lines[l1][c1:c2]
        parts = [self.lines[l1][c1:]] + self.lines[l1 + 1 : l2] + [self.lines[l2][:c2]]
        return "\n".join(parts)

    def _set_clipboard(self, text: str) -> None:
        self.clipboard_text = text
        try:
            if pygame.scrap.get_init():
                pygame.scrap.put(pygame.SCRAP_TEXT, text.encode("utf-8"))
        except Exception:
            pass

    def _get_clipboard(self) -> str | None:
        try:
            if pygame.scrap.get_init():
                raw = pygame.scrap.get(pygame.SCRAP_TEXT)
                if raw:
                    return raw.decode("utf-8")
        except Exception:
            return None
        return None

    # --- Undo/redo --------------------------------------------------------
    def _push_history(self) -> None:
        snapshot = (copy.deepcopy(self.lines), list(self.cursor), self.selection_anchor, self.selection_focus)
        self.history.append(snapshot)
        if len(self.history) > 100:
            self.history.pop(0)
        self.future.clear()

    def _undo(self) -> None:
        if len(self.history) <= 1:
            return
        current = self.history.pop()
        self.future.append(current)
        prev = self.history[-1]
        self._restore_snapshot(prev)

    def _redo(self) -> None:
        if not self.future:
            return
        snap = self.future.pop()
        self.history.append(snap)
        self._restore_snapshot(snap)

    def _restore_snapshot(self, snap) -> None:
        lines, cursor, anchor, focus = snap
        self.lines = copy.deepcopy(lines)
        self.cursor = list(cursor)
        self.selection_anchor = anchor
        self.selection_focus = focus

    # --- Indent helpers ---------------------------------------------------
    def _indent(self) -> None:
        self._push_history()
        if self._has_selection():
            sel = self._normalized_selection()
            assert sel
            (l1, _), (l2, _) = sel
            for i in range(l1, l2 + 1):
                self.lines[i] = "    " + self.lines[i]
            self.cursor[0] = l2
            self.cursor[1] += 4
        else:
            line = self.lines[self.cursor[0]]
            self.lines[self.cursor[0]] = line[: self.cursor[1]] + "    " + line[self.cursor[1] :]
            self.cursor[1] += 4
        self.selection_anchor = None
        self.selection_focus = None
        self._ensure_cursor_visible()

    def _outdent(self) -> None:
        self._push_history()
        if self._has_selection():
            sel = self._normalized_selection()
            assert sel
            (l1, _), (l2, _) = sel
            for i in range(l1, l2 + 1):
                if self.lines[i].startswith("    "):
                    self.lines[i] = self.lines[i][4:]
            self.cursor[0] = l2
            self.cursor[1] = min(self.cursor[1], len(self.lines[self.cursor[0]]))
        else:
            line = self.lines[self.cursor[0]]
            if line.startswith("    "):
                self.lines[self.cursor[0]] = line[4:]
                self.cursor[1] = max(0, self.cursor[1] - 4)
        self.selection_anchor = None
        self.selection_focus = None
        self._ensure_cursor_visible()

    def _leading_spaces(self, text: str) -> str:
        spaces = 0
        for ch in text:
            if ch == " ":
                spaces += 1
            elif ch == "\t":
                spaces += 4
            else:
                break
        return " " * spaces

    def _ensure_cursor_visible(self) -> None:
        visible_lines = int(self.rect.height / self.line_height) + 1
        if self.cursor[0] < self.scroll_offset:
            self.scroll_offset = self.cursor[0]
        elif self.cursor[0] >= self.scroll_offset + visible_lines:
            self.scroll_offset = self.cursor[0] - visible_lines + 1
        self.scroll_offset = max(0, min(self.scroll_offset, max(0, len(self.lines) - 1)))

