from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from .assets import find_worldbuilder_root
from .project import WorldBuilderProject, node_kind

_VERSION_PATTERNS = {
    "worldBuilder": re.compile(r'local\s+ModVersion\s*=\s*["\']([^"\']+)["\']'),
    "codewareRequired": re.compile(r'local\s+CodewareVersion\s*=\s*["\']([^"\']+)["\']'),
    "archiveXLRequired": re.compile(r'local\s+ArchiveXLVersion\s*=\s*["\']([^"\']+)["\']'),
}

_FINGERPRINT_FILES = (
    "modules/classes/editor/positionable.lua",
    "modules/classes/editor/positionableGroup.lua",
    "modules/classes/editor/spawnableElement.lua",
    "modules/utils/nodeRefRegistry.lua",
    "modules/utils/history.lua",
    "modules/ui/exportUI.lua",
)


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _extract_versions(root: Path) -> dict[str, str | None]:
    base_ui = root / "modules/ui/baseUI.lua"
    text = base_ui.read_text(encoding="utf-8", errors="replace") if base_ui.is_file() else ""
    out: dict[str, str | None] = {}
    for key, pattern in _VERSION_PATTERNS.items():
        match = pattern.search(text)
        out[key] = match.group(1) if match else None
    export_ui = root / "modules/ui/exportUI.lua"
    export_text = export_ui.read_text(encoding="utf-8", errors="replace") if export_ui.is_file() else ""
    match = re.search(r'local\s+minScriptVersion\s*=\s*["\']([^"\']+)["\']', export_text)
    out["exportScriptMinimum"] = match.group(1) if match else None
    return out


def _scan_module_paths(root: Path) -> tuple[set[str], set[str]]:
    editor: set[str] = set()
    spawn: set[str] = set()
    editor_dir = root / "modules/classes/editor"
    if editor_dir.is_dir():
        for path in editor_dir.rglob("*.lua"):
            text = path.read_text(encoding="utf-8", errors="replace")
            for match in re.finditer(r'o\.modulePath\s*=\s*["\']([^"\']+)["\']', text):
                value = match.group(1)
                if value.startswith("modules/classes/editor/"):
                    editor.add(value)
    spawn_dir = root / "modules/classes/spawn"
    if spawn_dir.is_dir():
        for path in spawn_dir.rglob("*.lua"):
            text = path.read_text(encoding="utf-8", errors="replace")
            for match in re.finditer(r'o\.modulePath\s*=\s*["\']([^"\']+)["\']', text):
                value = match.group(1)
                if not value.startswith("modules/classes/editor/"):
                    spawn.add(value)
    return editor, spawn


def scan_worldbuilder(world_builder_root: str | Path, project_file: str | Path | None = None) -> dict[str, Any]:
    root = find_worldbuilder_root(world_builder_root)
    versions = _extract_versions(root)
    editor_modules, spawn_modules = _scan_module_paths(root)
    features = {
        "randomizedGroups": (root / "modules/classes/editor/randomizedGroup.lua").is_file(),
        "scatteredGroups": (root / "modules/classes/editor/scatteredGroup.lua").is_file(),
        "splines": (root / "modules/classes/spawn/meta/spline.lua").is_file(),
        "splineMarkers": (root / "modules/classes/spawn/meta/splineMarker.lua").is_file(),
        "nodeRefRegistry": (root / "modules/utils/nodeRefRegistry.lua").is_file(),
        "history": (root / "modules/utils/history.lua").is_file(),
        "exporter": (root / "modules/ui/exportUI.lua").is_file(),
    }
    fingerprints = {
        rel: digest for rel in _FINGERPRINT_FILES if (digest := _sha256(root / rel)) is not None
    }
    result: dict[str, Any] = {
        "worldBuilderRoot": str(root),
        "versions": versions,
        "features": features,
        "editorModules": len(editor_modules),
        "spawnModules": len(spawn_modules),
        "fingerprints": fingerprints,
        "compatible": True,
        "issues": [],
    }

    if project_file is not None:
        project = WorldBuilderProject.load(project_file)
        unknown_editor: list[dict[str, str]] = []
        unknown_spawn: list[dict[str, str]] = []
        for entry in project.iter_nodes():
            kind = node_kind(entry.node)
            if kind == "group":
                module = str(entry.node.get("modulePath", ""))
                if module and module not in editor_modules:
                    unknown_editor.append({"path": entry.path, "modulePath": module})
            elif kind == "object":
                spawn = entry.node.get("spawnable", {})
                if isinstance(spawn, dict):
                    module = str(spawn.get("modulePath", ""))
                    if module and module not in spawn_modules:
                        unknown_spawn.append({"path": entry.path, "modulePath": module})
        schema = {
            "rootModule": project.data.get("modulePath"),
            "hasOrigin": isinstance(project.data.get("origin"), dict),
            "hasRotation": isinstance(project.data.get("rotation"), dict),
            "usesLegacyType": any("type" in e.node for e in project.iter_nodes()),
        }
        issues: list[dict[str, Any]] = []
        if unknown_editor:
            issues.append({"severity": "error", "code": "unknown-editor-module", "count": len(unknown_editor)})
        if unknown_spawn:
            issues.append({"severity": "error", "code": "unknown-spawn-module", "count": len(unknown_spawn)})
        if schema["usesLegacyType"]:
            issues.append({"severity": "warning", "code": "legacy-type-fields", "count": 1})
        result["project"] = {
            "file": str(Path(project_file).resolve()),
            "stats": project.stats(),
            "schema": schema,
            "unknownEditorModules": unknown_editor,
            "unknownSpawnModules": unknown_spawn,
        }
        result["issues"] = issues
        result["compatible"] = not any(i["severity"] == "error" for i in issues)
    return result
