from __future__ import annotations

import copy
import json
import random
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .errors import PathNotFoundError, ProjectFormatError
from .io import atomic_save_json, load_json
from .naming import generate_copy_name, sanitize_filename, unique_name
from .references import iter_known_references, rewrite_known_references
from .transforms import (
    add_vec,
    clean_float,
    compose_local_euler,
    compose_world_euler,
    euler3,
    mul_vec,
    rotate_point,
    sub_vec,
    vec3,
)
from .types import NodeEntry

GROUP_MODULES = {
    "modules/classes/editor/positionableGroup",
    "modules/classes/editor/randomizedGroup",
    "modules/classes/editor/scatteredGroup",
}
OBJECT_MODULE = "modules/classes/editor/spawnableElement"


def node_kind(node: dict[str, Any]) -> str:
    module = node.get("modulePath")
    if module in GROUP_MODULES:
        return "group"
    if module == OBJECT_MODULE:
        return "object"
    legacy_type = node.get("type")
    if legacy_type in {"group", "object", "element"}:
        return "group" if legacy_type == "group" else "object"
    if isinstance(node.get("spawnable"), dict):
        return "object"
    if isinstance(node.get("childs"), list):
        return "group"
    return "unknown"




def build_spawnable_node(
    *,
    module_path: str,
    data_type: str,
    spawn_data: str = "",
    template: dict[str, Any] | None = None,
    name: str | None = None,
    position: tuple[float, float, float] = (0.0, 0.0, 0.0),
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> dict[str, Any]:
    """Build one World Builder spawnableElement without inserting it.

    This is shared by offline saved-build insertion and the v0.5 live bridge,
    so Claude sends the same WB serialization shape that ``add_spawnable``
    writes to disk. Name uniqueness and NodeRef generation belong to the
    destination hierarchy and are therefore handled after insertion.
    """
    if name is None:
        raw = spawn_data.replace("/", "\\").rsplit("\\", 1)[-1] if spawn_data else data_type
        if "." in raw:
            raw = raw.rsplit(".", 1)[0]
        name = raw or "New_Element"
    final_name = sanitize_filename(name)

    spawn = copy.deepcopy(template) if isinstance(template, dict) else {}
    spawn["modulePath"] = module_path
    spawn["dataType"] = data_type
    if spawn_data:
        spawn["spawnData"] = spawn_data
    spawn["position"] = {"x": clean_float(position[0]), "y": clean_float(position[1]), "z": clean_float(position[2]), "w": 0}
    spawn["rotation"] = {"roll": clean_float(rotation[0]), "pitch": clean_float(rotation[1]), "yaw": clean_float(rotation[2])}
    spawn.setdefault("app", "default")
    spawn.setdefault("rotationRelative", False)
    spawn.setdefault("nodeRef", "")
    spawn.setdefault("streamingRefPointOverride", False)
    spawn.setdefault("streamingRefPoint", {"x": 0, "y": 0, "z": 0, "w": 0})

    return {
        "name": final_name,
        "modulePath": OBJECT_MODULE,
        "headerOpen": False,
        "propertyHeaderStates": [],
        "visible": True,
        "hiddenByParent": False,
        "expandable": False,
        "selected": False,
        "isUsingSpawnables": True,
        "childs": [],
        "transformExpanded": True,
        "rotationRelative": False,
        "scaleLocked": True,
        "rotationLocked": False,
        "randomizationSettings": {"probability": 0.5, "randomizeRotation": False, "randomizeRotationAxis": 2, "randomizeAppearance": False},
        "pos": {"x": clean_float(position[0]), "y": clean_float(position[1]), "z": clean_float(position[2]), "w": 0},
        "applyRotationWhenDropped": True,
        "spawnable": spawn,
    }




def build_group_node(
    *,
    name: str,
    position: tuple[float, float, float] = (0.0, 0.0, 0.0),
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
    module_path: str = "modules/classes/editor/positionableGroup",
    seed: int = 1,
    randomization_rule: int = 0,
    fixed_amount_rule: int = 0,
    fixed_amount_percentage: float = 0.5,
    fixed_amount_total: int = 1,
) -> dict[str, Any]:
    """Build a World Builder positionable/randomized group serialization."""
    if module_path not in GROUP_MODULES:
        raise ValueError(f"Unsupported group module {module_path!r}")
    final_name = sanitize_filename(name) or "New_Group"
    pos = {"x": clean_float(position[0]), "y": clean_float(position[1]), "z": clean_float(position[2])}
    data: dict[str, Any] = {
        "name": final_name,
        "modulePath": module_path,
        "headerOpen": False,
        "propertyHeaderStates": [],
        "visible": True,
        "hiddenByParent": False,
        "expandable": True,
        "selected": False,
        "isUsingSpawnables": True,
        "childs": [],
        "transformExpanded": True,
        "rotationRelative": False,
        "scaleLocked": True,
        "rotationLocked": False,
        "randomizationSettings": {"probability": 0.5},
        "pos": dict(pos),
        "applyRotationWhenDropped": False,
        "origin": dict(pos),
        "originInitialized": False,
        "rotation": {"roll": clean_float(rotation[0]), "pitch": clean_float(rotation[1]), "yaw": clean_float(rotation[2])},
    }
    if module_path == "modules/classes/editor/randomizedGroup":
        data.update({
            "seed": int(seed),
            "randomizationRule": int(randomization_rule),
            "fixedAmountRule": int(fixed_amount_rule),
            "fixedAmountPercentage": float(fixed_amount_percentage),
            "fixedAmountTotal": int(fixed_amount_total),
        })
    return data

def _xyz(value: Any) -> tuple[float, float, float] | None:
    return vec3(value)


def _assign_xyz(value: Any, xyz: tuple[float, float, float]) -> bool:
    if not isinstance(value, dict):
        return False
    for key, component in zip(("x", "y", "z"), xyz):
        value[key] = clean_float(component)
    return True


def _translate_xyz(value: Any, dx: float, dy: float, dz: float) -> bool:
    current = vec3(value)
    if current is None or not isinstance(value, dict):
        return False
    return _assign_xyz(value, (current[0] + dx, current[1] + dy, current[2] + dz))


def _children(node: dict[str, Any]) -> list[dict[str, Any]]:
    value = node.get("childs")
    if not isinstance(value, list):
        return []
    return [child for child in value if isinstance(child, dict)]


def _iter_subtree(node: dict[str, Any]) -> Iterator[dict[str, Any]]:
    yield node
    for child in _children(node):
        yield from _iter_subtree(child)


def _get_position(node: dict[str, Any]) -> tuple[float, float, float] | None:
    if node_kind(node) == "group":
        return vec3(node.get("origin")) or vec3(node.get("pos"))
    spawn = node.get("spawnable")
    if isinstance(spawn, dict):
        return vec3(spawn.get("position")) or vec3(node.get("pos"))
    return vec3(node.get("pos"))


def _set_position(node: dict[str, Any], position: tuple[float, float, float]) -> int:
    changed = 0
    if node_kind(node) == "group":
        if not isinstance(node.get("origin"), dict):
            node["origin"] = {"x": position[0], "y": position[1], "z": position[2]}
            changed += 1
        elif _assign_xyz(node["origin"], position):
            changed += 1
        if isinstance(node.get("pos"), dict) and _assign_xyz(node["pos"], position):
            changed += 1
        return changed

    spawn = node.get("spawnable")
    if isinstance(spawn, dict):
        if not isinstance(spawn.get("position"), dict):
            spawn["position"] = {"x": position[0], "y": position[1], "z": position[2], "w": 0}
            changed += 1
        elif _assign_xyz(spawn["position"], position):
            changed += 1
    if isinstance(node.get("pos"), dict) and _assign_xyz(node["pos"], position):
        changed += 1
    return changed


def _get_rotation(node: dict[str, Any]) -> tuple[float, float, float] | None:
    if node_kind(node) == "group":
        return euler3(node.get("rotation"))
    spawn = node.get("spawnable")
    if isinstance(spawn, dict):
        return euler3(spawn.get("rotation"))
    return None


def _set_rotation(node: dict[str, Any], rotation: tuple[float, float, float]) -> bool:
    target: Any
    if node_kind(node) == "group":
        target = node.get("rotation")
        if not isinstance(target, dict):
            node["rotation"] = {"roll": rotation[0], "pitch": rotation[1], "yaw": rotation[2]}
            return True
    else:
        spawn = node.get("spawnable")
        if not isinstance(spawn, dict):
            return False
        target = spawn.get("rotation")
        if not isinstance(target, dict):
            spawn["rotation"] = {"roll": rotation[0], "pitch": rotation[1], "yaw": rotation[2]}
            return True
    target["roll"] = clean_float(rotation[0])
    target["pitch"] = clean_float(rotation[1])
    target["yaw"] = clean_float(rotation[2])
    return True


class WorldBuilderProject:
    """Loss-minimizing wrapper around a World Builder saved-build JSON file.

    Unknown fields are retained verbatim. cp77wb only mutates fields required by an
    explicitly requested operation.
    """

    def __init__(self, data: dict[str, Any], source: Path | None = None):
        self.data = data
        self.source = source

    @classmethod
    def load(cls, path: str | Path) -> "WorldBuilderProject":
        p = Path(path)
        return cls(load_json(p), p)

    @property
    def name(self) -> str:
        return str(self.data.get("name", self.source.stem if self.source else "<unnamed>"))

    @property
    def root_path(self) -> str:
        return "/" + self.name

    def clone(self) -> "WorldBuilderProject":
        return WorldBuilderProject(copy.deepcopy(self.data), self.source)

    def save(
        self,
        path: str | Path | None = None,
        *,
        backup: bool = True,
        indent: int = 2,
    ) -> Path | None:
        target = Path(path) if path is not None else self.source
        if target is None:
            raise ProjectFormatError("No output path was supplied")
        self.source = target
        return atomic_save_json(target, self.data, make_backup=backup, indent=indent)

    def dumps(self) -> str:
        return json.dumps(self.data, ensure_ascii=False, indent=2)

    def iter_nodes(self) -> Iterator[NodeEntry]:
        def walk(node: dict[str, Any], path: str, parent: dict[str, Any] | None) -> Iterator[NodeEntry]:
            yield NodeEntry(path=path, node=node, parent=parent)
            children = node.get("childs", [])
            if not isinstance(children, list):
                return
            for i, child in enumerate(children):
                if not isinstance(child, dict):
                    continue
                name = str(child.get("name", f"<child-{i}>"))
                yield from walk(child, f"{path}/{name}", node)

        yield from walk(self.data, self.root_path, None)

    def path_map(self) -> dict[str, NodeEntry]:
        return {entry.path: entry for entry in self.iter_nodes()}

    def get(self, path: str) -> NodeEntry:
        normalized = self.normalize_path(path)
        try:
            return self.path_map()[normalized]
        except KeyError as exc:
            raise PathNotFoundError(f"No World Builder element at {normalized}") from exc

    def normalize_path(self, path: str) -> str:
        if not path:
            return self.root_path
        if not path.startswith("/"):
            path = "/" + path
        path = path.rstrip("/") or "/"
        if path == "/":
            return self.root_path
        if path == self.root_path or path.startswith(self.root_path + "/"):
            return path
        return self.root_path + path

    def tree_lines(self, show_module: bool = False) -> list[str]:
        lines: list[str] = []
        root_depth = self.root_path.count("/")
        for entry in self.iter_nodes():
            depth = entry.path.count("/") - root_depth
            kind = node_kind(entry.node)
            icon = {"group": "+", "object": "-"}.get(kind, "?")
            suffix = ""
            if show_module:
                if kind == "object":
                    suffix = f" [{entry.node.get('spawnable', {}).get('modulePath', '?')}]"
                else:
                    suffix = f" [{entry.node.get('modulePath', '?')}]"
            lines.append(f"{'  ' * depth}{icon} {entry.node.get('name', '<unnamed>')}{suffix}")
        return lines

    def find(self, query: str, *, case_sensitive: bool = False) -> list[NodeEntry]:
        needle = query if case_sensitive else query.lower()
        results: list[NodeEntry] = []
        for entry in self.iter_nodes():
            node = entry.node
            spawn_value = node.get("spawnable")
            spawn = spawn_value if isinstance(spawn_value, dict) else {}
            haystacks = [
                entry.path,
                str(node.get("name", "")),
                str(node.get("modulePath", "")),
                str(spawn.get("modulePath", "")),
                str(spawn.get("spawnData", "")),
                str(spawn.get("dataType", "")),
                str(spawn.get("nodeRef", "")),
            ]
            if any(needle in (h if case_sensitive else h.lower()) for h in haystacks):
                results.append(entry)
        return results

    def stats(self) -> dict[str, Any]:
        groups = 0
        objects = 0
        modules: dict[str, int] = {}
        node_refs = 0
        references = 0
        for entry in self.iter_nodes():
            kind = node_kind(entry.node)
            if kind == "group":
                groups += 1
            elif kind == "object":
                objects += 1
                spawn = entry.node.get("spawnable", {})
                module = str(spawn.get("modulePath", "<unknown>"))
                modules[module] = modules.get(module, 0) + 1
                if spawn.get("nodeRef"):
                    node_refs += 1
                references += sum(1 for _ in iter_known_references(spawn))
        return {
            "name": self.name,
            "groups": groups,
            "objects": objects,
            "nodeRefs": node_refs,
            "knownReferences": references,
            "spawnableModules": dict(sorted(modules.items())),
        }

    def node_refs(self) -> dict[str, list[str]]:
        refs: dict[str, list[str]] = {}
        for entry in self.iter_nodes():
            spawn = entry.node.get("spawnable")
            if not isinstance(spawn, dict):
                continue
            ref = spawn.get("nodeRef")
            if isinstance(ref, str) and ref:
                refs.setdefault(ref, []).append(entry.path)
        return refs

    def position(self, path: str) -> tuple[float, float, float]:
        entry = self.get(path)
        pos = _get_position(entry.node)
        if pos is None:
            raise ValueError(f"{entry.path} has no position")
        return pos

    def translate(self, path: str, dx: float, dy: float, dz: float) -> dict[str, int]:
        target = self.get(path)
        counters = {"groups": 0, "objects": 0, "positions": 0}

        def apply(node: dict[str, Any]) -> None:
            kind = node_kind(node)
            if kind == "group":
                counters["groups"] += 1
                if _translate_xyz(node.get("origin"), dx, dy, dz):
                    counters["positions"] += 1
                if _translate_xyz(node.get("pos"), dx, dy, dz):
                    counters["positions"] += 1
                for child in _children(node):
                    apply(child)
            elif kind == "object":
                counters["objects"] += 1
                spawn = node.get("spawnable")
                if isinstance(spawn, dict) and _translate_xyz(spawn.get("position"), dx, dy, dz):
                    counters["positions"] += 1
                if _translate_xyz(node.get("pos"), dx, dy, dz):
                    counters["positions"] += 1
            else:
                for child in _children(node):
                    apply(child)

        apply(target.node)
        self.refresh_area_marker_caches()
        return counters

    def rename(self, path: str, new_name: str, *, update_path_refs: bool = True) -> tuple[str, str]:
        sanitized = sanitize_filename(new_name)
        if not sanitized:
            raise ValueError("Name cannot be empty")
        entry = self.get(path)
        old_path = entry.path
        if entry.parent:
            sibling_names = {
                str(c.get("name"))
                for c in entry.parent.get("childs", [])
                if isinstance(c, dict) and c is not entry.node
            }
            sanitized = unique_name(sanitized, sibling_names)
        entry.node["name"] = sanitized
        if entry.parent is None:
            new_path = "/" + sanitized
        else:
            parent_path = old_path.rsplit("/", 1)[0]
            new_path = parent_path + "/" + sanitized

        if update_path_refs:
            paths = {old_path: new_path}
            for e in self.iter_nodes():
                spawn = e.node.get("spawnable")
                if isinstance(spawn, dict):
                    rewrite_known_references(spawn, paths=paths)
        self.refresh_area_marker_caches()
        return old_path, new_path

    def _node_ref_base(self, *, parent_name: str, object_name: str, prefix: str = "") -> str:
        generated = "$/"
        prefix = prefix.strip("/")
        if prefix:
            generated += prefix + "/"
        parent = sanitize_filename(parent_name.lower())
        root = sanitize_filename(self.name.lower())
        name = sanitize_filename(object_name.lower())
        return generated + parent + "/#" + root + "_" + name

    def generate_node_ref(self, path: str, *, prefix: str = "", force: bool = False, update_references: bool = True) -> tuple[str, str, int]:
        entry = self.get(path)
        if entry.parent is None:
            raise ValueError("The project root cannot have a NodeRef")
        spawn = entry.node.get("spawnable")
        if not isinstance(spawn, dict):
            raise ValueError(f"{entry.path} is not a spawnable object")
        old = str(spawn.get("nodeRef", ""))
        if old and not force:
            raise ValueError(f"{entry.path} already has NodeRef {old!r}; use --force to replace it")
        parent_name = str(entry.parent.get("name", ""))
        generated = self._node_ref_base(parent_name=parent_name, object_name=str(entry.node.get("name", "")), prefix=prefix)
        used = set(self.node_refs())
        if old:
            used.discard(old)
        while generated in used:
            generated = generate_copy_name(generated)
        previous, updated = self.set_node_ref(entry.path, generated, update_references=update_references)
        return previous, generated, updated

    def set_node_ref(self, path: str, new_ref: str, *, update_references: bool = True) -> tuple[str, int]:
        entry = self.get(path)
        spawn = entry.node.get("spawnable")
        if not isinstance(spawn, dict):
            raise ValueError(f"{entry.path} is not a spawnable object")
        old_ref = str(spawn.get("nodeRef", ""))
        if new_ref and new_ref != old_ref:
            owners = self.node_refs().get(new_ref, [])
            if owners:
                raise ValueError(f"NodeRef {new_ref!r} is already used by {owners[0]}")
        spawn["nodeRef"] = new_ref
        updated = 0
        if update_references and old_ref and old_ref != new_ref:
            mapping = {old_ref: new_ref}
            for e in self.iter_nodes():
                s = e.node.get("spawnable")
                if isinstance(s, dict):
                    updated += rewrite_known_references(s, noderefs=mapping)
        return old_ref, updated

    def _regenerate_clone_node_refs(self, clone: dict[str, Any], *, prefix: str = "", used: set[str], root_parent_name: str | None = None) -> dict[str, str]:
        mapping: dict[str, str] = {}

        def walk(node: dict[str, Any], parent_name: str | None) -> None:
            kind = node_kind(node)
            if kind == "object":
                spawn = node.get("spawnable")
                if isinstance(spawn, dict):
                    old = spawn.get("nodeRef")
                    if isinstance(old, str) and old:
                        base = self._node_ref_base(parent_name=parent_name or self.name, object_name=str(node.get("name", "")), prefix=prefix)
                        new = base
                        while new in used:
                            new = generate_copy_name(new)
                        used.add(new)
                        mapping[old] = new
                        spawn["nodeRef"] = new
            this_parent = str(node.get("name", parent_name or self.name))
            for child in _children(node):
                walk(child, this_parent)

        walk(clone, root_parent_name)
        if mapping:
            for node in _iter_subtree(clone):
                spawn = node.get("spawnable")
                if isinstance(spawn, dict):
                    rewrite_known_references(spawn, noderefs=mapping)
        return mapping

    def _translate_node(self, node: dict[str, Any], delta: tuple[float, float, float]) -> None:
        dx, dy, dz = delta
        for current in _iter_subtree(node):
            kind = node_kind(current)
            if kind == "group":
                _translate_xyz(current.get("origin"), dx, dy, dz)
                _translate_xyz(current.get("pos"), dx, dy, dz)
            elif kind == "object":
                spawn = current.get("spawnable")
                if isinstance(spawn, dict):
                    _translate_xyz(spawn.get("position"), dx, dy, dz)
                _translate_xyz(current.get("pos"), dx, dy, dz)

    def duplicate(
        self,
        path: str,
        *,
        count: int = 1,
        offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
        node_ref_prefix: str = "",
        keep_node_refs: bool = False,
    ) -> list[str]:
        if count < 1:
            raise ValueError("count must be >= 1")
        target = self.get(path)
        if target.parent is None:
            raise ValueError("Duplicating the project root is not supported")
        children = target.parent.get("childs")
        if not isinstance(children, list):
            raise ValueError("Target parent has no child list")
        try:
            base_index = next(i for i, child in enumerate(children) if child is target.node)
        except StopIteration as exc:
            raise ValueError("Target is not present in its parent") from exc

        old_path = target.path
        existing_names = {str(c.get("name", "")) for c in children if isinstance(c, dict)}
        used_refs = set(self.node_refs())
        new_paths: list[str] = []

        for i in range(1, count + 1):
            clone = copy.deepcopy(target.node)
            original_name = str(clone.get("name", "Copy"))
            clone_name = unique_name(generate_copy_name(original_name), existing_names)
            clone["name"] = clone_name
            existing_names.add(clone_name)
            if clone.get("modulePath") == "modules/classes/editor/randomizedGroup":
                clone["seed"] = -1

            new_path = old_path.rsplit("/", 1)[0] + "/" + clone_name
            for current in _iter_subtree(clone):
                spawn = current.get("spawnable")
                if isinstance(spawn, dict):
                    rewrite_known_references(spawn, paths={old_path: new_path})

            if not keep_node_refs:
                self._regenerate_clone_node_refs(
                    clone, prefix=node_ref_prefix, used=used_refs, root_parent_name=str(target.parent.get("name", self.name))
                )

            if offset != (0.0, 0.0, 0.0):
                self._translate_node(clone, (offset[0] * i, offset[1] * i, offset[2] * i))

            children.insert(base_index + i, clone)
            new_paths.append(new_path)

        self.refresh_area_marker_caches()
        return new_paths

    def rotate(
        self,
        path: str,
        roll: float = 0.0,
        pitch: float = 0.0,
        yaw: float = 0.0,
        *,
        pivot: tuple[float, float, float] | None = None,
        relative: bool | None = None,
    ) -> dict[str, int]:
        target = self.get(path)
        delta = (roll, pitch, yaw)
        target_pos = _get_position(target.node)
        if target_pos is None:
            raise ValueError(f"{target.path} has no position")
        pivot = pivot or target_pos
        counters = {"positions": 0, "rotations": 0, "groups": 0, "objects": 0}
        target_kind = node_kind(target.node)

        if target_kind == "object":
            counters["objects"] = 1
            if pivot != target_pos:
                counters["positions"] += _set_position(target.node, rotate_point(target_pos, pivot, delta))
            current = _get_rotation(target.node) or (0.0, 0.0, 0.0)
            if not target.node.get("rotationLocked"):
                use_relative = bool(target.node.get("rotationRelative")) if relative is None else relative
                new_rotation = compose_local_euler(current, delta) if use_relative else add_vec(current, delta)
                if _set_rotation(target.node, new_rotation):
                    counters["rotations"] += 1
            self.refresh_area_marker_caches()
            return counters

        if target_kind != "group":
            raise ValueError(f"{target.path} is not positionable")
        if target.node.get("rotationLocked"):
            return counters

        # Target group itself rotates, and may orbit an explicitly supplied pivot.
        counters["groups"] += 1
        if pivot != target_pos:
            counters["positions"] += _set_position(target.node, rotate_point(target_pos, pivot, delta))
        current_group_rot = _get_rotation(target.node) or (0.0, 0.0, 0.0)
        if _set_rotation(target.node, add_vec(current_group_rot, delta)):
            counters["rotations"] += 1

        # Descendants rotate in world space around the same pivot. Updating nested
        # group origins/rotations keeps serialized caches coherent for offline edits.
        for child in _children(target.node):
            for node in _iter_subtree(child):
                kind = node_kind(node)
                if kind == "group":
                    counters["groups"] += 1
                elif kind == "object":
                    counters["objects"] += 1
                pos = _get_position(node)
                if pos is not None:
                    counters["positions"] += _set_position(node, rotate_point(pos, pivot, delta))
                current = _get_rotation(node)
                if current is not None and not node.get("rotationLocked"):
                    if _set_rotation(node, compose_world_euler(current, delta)):
                        counters["rotations"] += 1
        self.refresh_area_marker_caches()
        return counters

    def scale(
        self,
        path: str,
        sx: float = 1.0,
        sy: float = 1.0,
        sz: float = 1.0,
        *,
        pivot: tuple[float, float, float] | None = None,
        create_scale: bool = False,
    ) -> dict[str, int]:
        if sx == 0 or sy == 0 or sz == 0:
            raise ValueError("scale factors cannot be zero")
        target = self.get(path)
        factors = (sx, sy, sz)
        target_pos = _get_position(target.node)
        if target_pos is None:
            raise ValueError(f"{target.path} has no position")
        pivot = pivot or target_pos
        counters = {"positions": 0, "scales": 0, "objects_without_scale": 0}

        def scale_spawn(node: dict[str, Any]) -> None:
            spawn = node.get("spawnable")
            if not isinstance(spawn, dict):
                return
            scale_value = spawn.get("scale")
            if not isinstance(scale_value, dict):
                if not create_scale:
                    counters["objects_without_scale"] += 1
                    return
                scale_value = {"x": 1.0, "y": 1.0, "z": 1.0}
                spawn["scale"] = scale_value
            current = vec3(scale_value)
            if current is None:
                raise ValueError(f"Invalid scale on object {node.get('name', '<unnamed>')}")
            _assign_xyz(scale_value, mul_vec(current, factors))
            counters["scales"] += 1

        if node_kind(target.node) == "object":
            spawn = target.node.get("spawnable")
            if isinstance(spawn, dict) and not isinstance(spawn.get("scale"), dict) and not create_scale:
                raise ValueError(f"{target.path} has no spawnable.scale; use --create-scale only if this WB type supports scaling")
            scale_spawn(target.node)
            if pivot != target_pos:
                relative_pos = sub_vec(target_pos, pivot)
                counters["positions"] += _set_position(target.node, add_vec(pivot, mul_vec(relative_pos, factors)))
        elif node_kind(target.node) == "group":
            for child in _children(target.node):
                for node in _iter_subtree(child):
                    pos = _get_position(node)
                    if pos is not None:
                        relative_pos = sub_vec(pos, pivot)
                        counters["positions"] += _set_position(node, add_vec(pivot, mul_vec(relative_pos, factors)))
                    if node_kind(node) == "object":
                        scale_spawn(node)
        else:
            raise ValueError(f"{target.path} is not positionable")
        self.refresh_area_marker_caches()
        return counters

    def linear_array(
        self,
        path: str,
        *,
        count: int,
        step: tuple[float, float, float],
        node_ref_prefix: str = "",
        keep_node_refs: bool = False,
    ) -> list[str]:
        """Create a total of `count` elements including the existing source."""
        if count < 1:
            raise ValueError("count must be >= 1")
        if count == 1:
            return []
        return self.duplicate(
            path,
            count=count - 1,
            offset=step,
            node_ref_prefix=node_ref_prefix,
            keep_node_refs=keep_node_refs,
        )

    def radial_array(
        self,
        path: str,
        *,
        count: int,
        pivot: tuple[float, float, float] | None = None,
        angle: float = 360.0,
        rotate_items: bool = True,
        node_ref_prefix: str = "",
        keep_node_refs: bool = False,
    ) -> list[str]:
        """Create a radial array in the XY plane; count includes the source."""
        if count < 1:
            raise ValueError("count must be >= 1")
        if count == 1:
            return []
        source = self.get(path)
        if pivot is None:
            if source.parent is None:
                raise ValueError("radial array needs an explicit pivot for the root")
            pivot = _get_position(source.parent)
            if pivot is None:
                raise ValueError("Could not derive pivot from parent; provide --pivot-x/y/z")
        new_paths: list[str] = []
        step = angle / count
        for i in range(1, count):
            clone_path = self.duplicate(
                path,
                count=1,
                node_ref_prefix=node_ref_prefix,
                keep_node_refs=keep_node_refs,
            )[0]
            # The duplicate is initially colocated with source. Orbit around pivot.
            if rotate_items:
                self.rotate(clone_path, yaw=step * i, pivot=pivot)
            else:
                clone_pos = self.position(clone_path)
                new_pos = rotate_point(clone_pos, pivot, (0.0, 0.0, step * i))
                delta = sub_vec(new_pos, clone_pos)
                self.translate(clone_path, *delta)
            new_paths.append(clone_path)
        self.refresh_area_marker_caches()
        return new_paths

    def _independent_entries(self, paths: list[str]) -> list[NodeEntry]:
        entries = [self.get(path) for path in paths]
        normalized = [entry.path for entry in entries]
        if len(set(normalized)) != len(normalized):
            raise ValueError("Paths must be unique")
        for i, path in enumerate(normalized):
            for other in normalized[i + 1:]:
                if other.startswith(path + "/") or path.startswith(other + "/"):
                    raise ValueError("Cannot transform an ancestor and its descendant in the same align/distribute operation")
        return entries

    def align(self, paths: list[str], *, axis: str, mode: str = "first", value: float | None = None) -> dict[str, str | float]:
        if axis not in {"x", "y", "z"}:
            raise ValueError("axis must be x, y, or z")
        if len(paths) < 2:
            raise ValueError("align requires at least two paths")
        entries = self._independent_entries(paths)
        idx = {"x": 0, "y": 1, "z": 2}[axis]
        positions = [self.position(e.path) for e in entries]
        values = [p[idx] for p in positions]
        if mode == "first":
            target = values[0]
        elif mode == "min":
            target = min(values)
        elif mode == "max":
            target = max(values)
        elif mode in {"average", "center"}:
            target = sum(values) / len(values)
        elif mode == "value":
            if value is None:
                raise ValueError("mode=value requires --value")
            target = value
        else:
            raise ValueError("mode must be first, min, max, average, center, or value")
        for entry, pos in zip(entries, positions):
            delta = [0.0, 0.0, 0.0]
            delta[idx] = target - pos[idx]
            self.translate(entry.path, *delta)
        return {"axis": axis, "target": target, "count": float(len(entries))}

    def distribute(self, paths: list[str], *, axis: str) -> dict[str, str | float]:
        if axis not in {"x", "y", "z"}:
            raise ValueError("axis must be x, y, or z")
        if len(paths) < 3:
            raise ValueError("distribute requires at least three paths")
        entries = self._independent_entries(paths)
        idx = {"x": 0, "y": 1, "z": 2}[axis]
        pairs = sorted(((self.position(e.path)[idx], e) for e in entries), key=lambda item: item[0])
        start, end = pairs[0][0], pairs[-1][0]
        spacing = (end - start) / (len(pairs) - 1)
        for i, (current, entry) in enumerate(pairs[1:-1], start=1):
            target = start + spacing * i
            delta = [0.0, 0.0, 0.0]
            delta[idx] = target - current
            self.translate(entry.path, *delta)
        return {"axis": axis, "start": start, "end": end, "spacing": spacing, "count": float(len(entries))}

    def add_group(
        self,
        parent_path: str,
        *,
        name: str,
        position: tuple[float, float, float] = (0.0, 0.0, 0.0),
        rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
        module_path: str = "modules/classes/editor/positionableGroup",
        seed: int = 1,
        randomization_rule: int = 0,
        fixed_amount_rule: int = 0,
        fixed_amount_percentage: float = 0.5,
        fixed_amount_total: int = 1,
    ) -> str:
        parent = self.get(parent_path)
        if node_kind(parent.node) != "group":
            raise ValueError(f"Parent {parent.path} is not a group")
        children = parent.node.get("childs")
        if not isinstance(children, list):
            parent.node["childs"] = []
            children = parent.node["childs"]
        node = build_group_node(
            name=name, position=position, rotation=rotation, module_path=module_path, seed=seed,
            randomization_rule=randomization_rule, fixed_amount_rule=fixed_amount_rule,
            fixed_amount_percentage=fixed_amount_percentage, fixed_amount_total=fixed_amount_total,
        )
        existing = {str(c.get("name", "")) for c in children if isinstance(c, dict)}
        node["name"] = unique_name(str(node["name"]), existing)
        children.append(node)
        return parent.path + "/" + str(node["name"])

    def add_spawnable(
        self,
        parent_path: str,
        *,
        module_path: str,
        data_type: str,
        spawn_data: str = "",
        template: dict[str, Any] | None = None,
        name: str | None = None,
        position: tuple[float, float, float] = (0.0, 0.0, 0.0),
        rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
        generate_node_ref: bool = False,
        node_ref_prefix: str = "",
    ) -> str:
        """Insert a World Builder spawnableElement under a group."""
        parent = self.get(parent_path)
        if node_kind(parent.node) != "group":
            raise ValueError(f"Parent {parent.path} is not a group")
        children = parent.node.get("childs")
        if not isinstance(children, list):
            parent.node["childs"] = []
            children = parent.node["childs"]

        node = build_spawnable_node(
            module_path=module_path,
            data_type=data_type,
            spawn_data=spawn_data,
            template=template,
            name=name,
            position=position,
            rotation=rotation,
        )
        existing = {str(c.get("name", "")) for c in children if isinstance(c, dict)}
        node["name"] = unique_name(str(node["name"]), existing)
        children.append(node)
        new_path = parent.path + "/" + str(node["name"])
        if generate_node_ref:
            self.generate_node_ref(new_path, prefix=node_ref_prefix, force=True)
        return new_path

    def grid_array(
        self,
        path: str,
        *,
        counts: tuple[int, int, int],
        step: tuple[float, float, float],
        node_ref_prefix: str = "",
        keep_node_refs: bool = False,
    ) -> list[str]:
        """Create a rectangular 3D grid; counts include the existing source."""
        nx, ny, nz = counts
        if nx < 1 or ny < 1 or nz < 1:
            raise ValueError("grid counts must all be >= 1")
        new_paths: list[str] = []
        for iz in range(nz):
            for iy in range(ny):
                for ix in range(nx):
                    if ix == 0 and iy == 0 and iz == 0:
                        continue
                    new_paths.extend(self.duplicate(
                        path,
                        count=1,
                        offset=(step[0] * ix, step[1] * iy, step[2] * iz),
                        node_ref_prefix=node_ref_prefix,
                        keep_node_refs=keep_node_refs,
                    ))
        self.refresh_area_marker_caches()
        return new_paths

    def scatter(
        self,
        path: str,
        *,
        count: int,
        half_extents: tuple[float, float, float] = (5.0, 5.0, 0.0),
        seed: int = 1,
        random_yaw: bool = True,
        scale_min: float | None = None,
        scale_max: float | None = None,
        create_scale: bool = False,
        node_ref_prefix: str = "",
        keep_node_refs: bool = False,
    ) -> dict[str, Any]:
        """Create a deterministic box scatter; count includes the source.

        This is deliberately geometry-only. Collision/surface projection belongs
        in the live bridge because offline JSON has no access to game world
        collision data.
        """
        if count < 1:
            raise ValueError("count must be >= 1")
        if any(v < 0 for v in half_extents):
            raise ValueError("half extents must be >= 0")
        if (scale_min is None) != (scale_max is None):
            raise ValueError("scale_min and scale_max must be supplied together")
        if scale_min is not None and scale_max is not None:
            if scale_min <= 0 or scale_max <= 0 or scale_max < scale_min:
                raise ValueError("scale range must be positive and max >= min")

        rng = random.Random(seed)
        created: list[str] = []
        placements: list[dict[str, Any]] = []
        for _ in range(count - 1):
            delta = (
                rng.uniform(-half_extents[0], half_extents[0]),
                rng.uniform(-half_extents[1], half_extents[1]),
                rng.uniform(-half_extents[2], half_extents[2]),
            )
            clone_path = self.duplicate(
                path,
                count=1,
                offset=delta,
                node_ref_prefix=node_ref_prefix,
                keep_node_refs=keep_node_refs,
            )[0]
            yaw = rng.uniform(0.0, 360.0) if random_yaw else 0.0
            if random_yaw:
                self.rotate(clone_path, yaw=yaw)
            scale_value: float | None = None
            if scale_min is not None and scale_max is not None:
                scale_value = rng.uniform(scale_min, scale_max)
                self.scale(clone_path, scale_value, scale_value, scale_value, create_scale=create_scale)
            created.append(clone_path)
            placements.append({
                "path": clone_path,
                "offset": {"x": delta[0], "y": delta[1], "z": delta[2]},
                "yaw": yaw,
                "scale": scale_value,
            })
        self.refresh_area_marker_caches()
        return {"seed": seed, "created": created, "placements": placements}

    def refresh_area_marker_caches(self) -> int:
        path_map = self.path_map()
        refreshed = 0
        for entry in self.iter_nodes():
            spawn = entry.node.get("spawnable")
            if not isinstance(spawn, dict):
                continue
            outline_path = spawn.get("outlinePath")
            if not isinstance(outline_path, str) or not outline_path:
                continue
            outline = path_map.get(outline_path)
            if outline is None:
                continue
            markers: list[dict[str, Any]] = []
            height: float | int = 0
            for child in _children(outline.node):
                child_spawn = child.get("spawnable")
                if not isinstance(child_spawn, dict) or child_spawn.get("modulePath") != "area/outlineMarker":
                    continue
                pos = child_spawn.get("position")
                if isinstance(pos, dict):
                    markers.append({k: pos[k] for k in ("x", "y", "z", "w") if k in pos})
                if isinstance(child_spawn.get("height"), (int, float)):
                    height = child_spawn["height"]
            spawn["markers"] = markers
            spawn["height"] = height
            refreshed += 1
        return refreshed
