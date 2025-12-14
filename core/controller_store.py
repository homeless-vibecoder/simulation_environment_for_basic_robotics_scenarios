"""Controller storage and compilation helpers.

Controllers are stored as structured JSON files under `controllers/` with
sectioned code (imports/init/step/helpers) plus optional help/meta. This module
builds runnable Python code from those sections and writes a generated module
that the simulator can import.
"""
from __future__ import annotations

import ast
import json
import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


CONTROLLER_DIRNAME = "controllers"
CONTROLLER_SUFFIX = ".controller.json"
GENERATED_DIRNAME = ".generated_controllers"


DEFAULT_SECTIONS = {
    "imports": "# Add optional imports here (e.g., math)\n",
    "init": "# Runs once when the controller is created\n# self.sim and self.robot_id are available\nself.state = {}\n",
    "step": "# Called every timestep\n# sensors: dict of sensor readings\n# dt: timestep (seconds)\n# Example: read a sensor safely\n# dist = sensors.get('front_distance')\n# if dist is not None:\n#     pass\n",
    "helpers": "# Optional helper methods (indent like class methods)\n",
}

DEFAULT_HELP = (
    "imports: optional modules/constants\n"
    "__init__: set up state; self.sim and self.robot_id available\n"
    "step(sensors, dt): runs every timestep; return None\n"
    "helpers: optional class methods/utilities\n"
)


@dataclass
class ControllerDefinition:
    """Structured controller representation."""

    name: str
    sections: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_SECTIONS))
    help: str = DEFAULT_HELP
    meta: Dict[str, object] = field(default_factory=dict)
    version: int = 1

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "sections": self.sections,
            "help": self.help,
            "meta": self.meta,
            "version": self.version,
        }

    @classmethod
    def from_json(cls, name: str, data: dict) -> "ControllerDefinition":
        return cls(
            name=name,
            sections=dict(DEFAULT_SECTIONS | (data.get("sections") or {})),
            help=data.get("help", DEFAULT_HELP),
            meta=dict(data.get("meta") or {}),
            version=int(data.get("version", 1)),
        )


def controller_path(base: Path, module_name: str) -> Path:
    return base / CONTROLLER_DIRNAME / f"{module_name}{CONTROLLER_SUFFIX}"


def generated_path(base: Path, module_name: str) -> Path:
    return base / GENERATED_DIRNAME / f"{module_name}.py"


def list_controllers(base: Path) -> List[str]:
    """Return available controller module names (without suffix)."""
    folder = base / CONTROLLER_DIRNAME
    if not folder.exists():
        return []
    names: List[str] = []
    for path in folder.glob(f"*{CONTROLLER_SUFFIX}"):
        if not path.is_file():
            continue
        name = path.name.removesuffix(CONTROLLER_SUFFIX)
        names.append(name)
    return sorted(set(names))


def _extract_method_body(source: str, class_name: str, method_name: str) -> str:
    try:
        module = ast.parse(source)
    except Exception:
        return ""
    for node in module.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name == method_name:
                    segment = ast.get_source_segment(source, child) or ""
                    lines = segment.splitlines()
                    body_lines = []
                    for line in lines[1:]:
                        body_lines.append(line[4:] if line.startswith("    ") else line)
                    return "\n".join(body_lines).strip()
    return ""


def _extract_helpers(source: str, class_name: str) -> str:
    try:
        module = ast.parse(source)
    except Exception:
        return ""
    helpers: List[str] = []
    for node in module.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name not in ("__init__", "step"):
                    segment = ast.get_source_segment(source, child) or ""
                    helpers.append(textwrap.dedent(segment))
    return "\n\n".join(helpers).strip() + ("\n" if helpers else "")


def _extract_imports(source: str) -> str:
    imports: List[str] = []
    try:
        module = ast.parse(source)
    except Exception:
        return ""
    for node in module.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            segment = ast.get_source_segment(source, node) or ""
            imports.append(segment)
    return "\n".join(imports).strip() + ("\n" if imports else "")


def migrate_from_py(base: Path, module_name: str) -> Optional[ControllerDefinition]:
    """Best-effort migration from legacy controller.py into sections."""
    legacy_path = base / f"{module_name}.py"
    if not legacy_path.exists():
        return None
    source = legacy_path.read_text(encoding="utf-8")
    sections = dict(DEFAULT_SECTIONS)
    sections["imports"] = _extract_imports(source) or sections["imports"]
    init_body = _extract_method_body(source, "Controller", "__init__")
    step_body = _extract_method_body(source, "Controller", "step")
    helpers = _extract_helpers(source, "Controller")
    if init_body:
        sections["init"] = init_body + ("\n" if not init_body.endswith("\n") else "")
    if step_body:
        sections["step"] = step_body + ("\n" if not step_body.endswith("\n") else "")
    if helpers:
        sections["helpers"] = helpers
    help_text = DEFAULT_HELP + "\n(migrated from legacy controller.py)"
    return ControllerDefinition(name=module_name, sections=sections, help=help_text)


def load_controller_definition(base: Path, module_name: str) -> ControllerDefinition:
    path = controller_path(base, module_name)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return ControllerDefinition.from_json(module_name, data)
    migrated = migrate_from_py(base, module_name)
    if migrated:
        return migrated
    return ControllerDefinition(name=module_name)


def save_controller_definition(base: Path, module_name: str, definition: ControllerDefinition, *, backup: bool = True) -> Path:
    """Persist controller JSON; returns path."""
    path = controller_path(base, module_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    if backup and path.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = path.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        path.rename(backup_dir / f"{module_name}_{ts}{CONTROLLER_SUFFIX}")
    path.write_text(json.dumps(definition.to_json(), indent=2), encoding="utf-8")
    return path


def build_controller_code(definition: ControllerDefinition) -> str:
    """Assemble runnable Python source from sectioned definition."""
    sections = definition.sections or {}
    imports = sections.get("imports", "").rstrip()
    init_body = sections.get("init", "").rstrip() or "pass"
    step_body = sections.get("step", "").rstrip() or "pass"
    helpers = sections.get("helpers", "").rstrip()

    def indent_block(block: str, level: int = 1) -> str:
        return textwrap.indent(block + ("\n" if not block.endswith("\n") else ""), "    " * level)

    parts = [
        "# Auto-generated from controller JSON; edit via runner UI\n",
        f"# Controller: {definition.name}\n",
    ]
    if imports:
        parts.append(imports + "\n\n")
    parts.append("class Controller:\n")
    parts.append(indent_block("def __init__(self, sim):\n    self.sim = sim\n    self.robot_id = getattr(sim, 'robot_ids', ['robot'])[0]\n" + indent_block(init_body, 0), 1))
    parts.append("\n")
    parts.append(indent_block("def step(self, sensors, dt: float):\n" + indent_block(step_body, 0), 1))
    if helpers:
        parts.append("\n")
        # Helpers are expected to be full method definitions, already indented to class scope.
        parts.append(indent_block(helpers.rstrip() + ("\n" if not helpers.endswith("\n") else "")))
    parts.append("\n")
    return "".join(parts)


def ensure_compiled_controller(base: Path, module_name: str) -> Tuple[Optional[Path], Path]:
    """Return path to a Python module for the controller, generating if needed."""
    json_path = controller_path(base, module_name)
    if json_path.exists():
        definition = load_controller_definition(base, module_name)
        code = build_controller_code(definition)
        out_dir = base / GENERATED_DIRNAME
        out_dir.mkdir(parents=True, exist_ok=True)
        py_path = out_dir / f"{module_name}.py"
        py_path.write_text(code, encoding="utf-8")
        return py_path, out_dir
    legacy_path = base / f"{module_name}.py"
    if legacy_path.exists():
        return legacy_path, base
    return None, base

