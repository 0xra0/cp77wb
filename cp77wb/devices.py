from __future__ import annotations

import copy
from typing import Any

from .project import WorldBuilderProject


def _spawn(project: WorldBuilderProject, path: str) -> dict[str, Any]:
    entry = project.get(path)
    spawn = entry.node.get("spawnable")
    if not isinstance(spawn, dict):
        raise ValueError(f"{entry.path} is not a spawnable object")
    return spawn


def _ensure_node_ref(project: WorldBuilderProject, path: str, prefix: str) -> str:
    spawn = _spawn(project, path)
    ref = spawn.get("nodeRef")
    if isinstance(ref, str) and ref:
        return ref
    _, new_ref, _ = project.generate_node_ref(path, prefix=prefix, force=True)
    return new_ref


def connect_device(
    project: WorldBuilderProject,
    source_path: str,
    target_path: str,
    *,
    device_class_name: str | None = None,
    node_ref_prefix: str = "",
) -> dict[str, Any]:
    source = _spawn(project, source_path)
    target = _spawn(project, target_path)
    target_ref = _ensure_node_ref(project, target_path, node_ref_prefix)
    if not device_class_name:
        value = target.get("deviceClassName")
        device_class_name = str(value) if value else ""
    if not device_class_name:
        raise ValueError("Target has no deviceClassName; provide --device-class-name")
    connections = source.setdefault("deviceConnections", [])
    if not isinstance(connections, list):
        raise ValueError(f"{source_path} has invalid deviceConnections")
    entry = {"deviceClassName": device_class_name, "nodeRef": target_ref}
    if entry not in connections:
        connections.append(entry)
    return {"source": project.get(source_path).path, "target": project.get(target_path).path, "connection": entry}


def _find_key_path(value: Any, wanted: str, path: tuple[Any, ...] = ()) -> tuple[Any, ...] | None:
    if isinstance(value, dict):
        for key, child in value.items():
            current = path + (key,)
            if key == wanted:
                return current
            found = _find_key_path(child, wanted, current)
            if found is not None:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _find_key_path(child, wanted, path + (index,))
            if found is not None:
                return found
    return None


def _get_at(value: Any, path: tuple[Any, ...]) -> Any:
    current = value
    for part in path:
        current = current[part]
    return current


def _assign_existing(container: dict[str, Any], key: str, value: Any) -> None:
    current = container.get(key)
    if isinstance(current, dict) and "$value" in current:
        current["$value"] = value
    else:
        container[key] = value


def _patch_terminal_floor_setup(spawn: dict[str, Any], marker_ref: str, display_name: str) -> dict[str, Any]:
    defaults = spawn.get("defaultComponentData")
    if not isinstance(defaults, dict):
        return {"patched": False, "reason": "defaultComponentData missing"}
    path = _find_key_path(defaults, "elevatorFloorSetup")
    if path is None or len(path) < 2:
        return {"patched": False, "reason": "elevatorFloorSetup not found in defaultComponentData"}
    component_id = str(path[0])
    component_default = defaults.get(path[0])
    if not isinstance(component_default, dict):
        return {"patched": False, "reason": "component default is not an object"}
    top_key = path[1]
    if top_key not in component_default:
        return {"patched": False, "reason": "top-level instance property missing"}

    changes = spawn.setdefault("instanceDataChanges", {})
    if not isinstance(changes, dict):
        return {"patched": False, "reason": "instanceDataChanges is invalid"}
    component_changes = changes.setdefault(component_id, {})
    if not isinstance(component_changes, dict):
        changes[component_id] = {}
        component_changes = changes[component_id]
    if top_key not in component_changes:
        component_changes[top_key] = copy.deepcopy(component_default[top_key])

    relative = path[2:]
    target = component_changes[top_key]
    if relative:
        try:
            target = _get_at(target, relative)
        except (KeyError, IndexError, TypeError):
            return {"patched": False, "reason": "could not mirror elevatorFloorSetup path into instanceDataChanges"}
    if not isinstance(target, dict):
        return {"patched": False, "reason": "elevatorFloorSetup is not an object"}
    _assign_existing(target, "floorDisplayName", display_name)
    _assign_existing(target, "floorMarker", marker_ref)
    return {"patched": True, "componentId": component_id, "path": [str(p) for p in path]}


def wire_elevator(
    project: WorldBuilderProject,
    elevator_path: str,
    terminal_paths: list[str],
    marker_paths: list[str],
    *,
    floor_names: list[str] | None = None,
    terminal_class_name: str = "ElevatorFloorTerminalControllerPS",
    node_ref_prefix: str = "",
) -> dict[str, Any]:
    if len(terminal_paths) < 2:
        raise ValueError("An elevator needs at least two terminals")
    if len(terminal_paths) != len(marker_paths):
        raise ValueError("terminal_paths and marker_paths must have equal length")
    if floor_names is None:
        floor_names = [f"Floor {i + 1}" for i in range(len(terminal_paths))]
    if len(floor_names) != len(terminal_paths):
        raise ValueError("floor_names must match terminal_paths length")

    elevator = _spawn(project, elevator_path)
    elevator_ref = _ensure_node_ref(project, elevator_path, node_ref_prefix)
    floors = []
    connections = elevator.setdefault("deviceConnections", [])
    if not isinstance(connections, list):
        raise ValueError("Elevator deviceConnections is invalid")

    for index, (terminal_path, marker_path, floor_name) in enumerate(zip(terminal_paths, marker_paths, floor_names)):
        terminal = _spawn(project, terminal_path)
        _spawn(project, marker_path)
        terminal_ref = _ensure_node_ref(project, terminal_path, node_ref_prefix)
        marker_ref = _ensure_node_ref(project, marker_path, node_ref_prefix)
        terminal["persistent"] = True
        class_name = str(terminal.get("deviceClassName") or terminal_class_name)
        connection = {"deviceClassName": class_name, "nodeRef": terminal_ref}
        if connection not in connections:
            connections.append(connection)
        patch = _patch_terminal_floor_setup(terminal, marker_ref, floor_name)
        floors.append({
            "index": index,
            "terminal": project.get(terminal_path).path,
            "terminalNodeRef": terminal_ref,
            "marker": project.get(marker_path).path,
            "markerNodeRef": marker_ref,
            "displayName": floor_name,
            "instanceData": patch,
        })
    return {
        "elevator": project.get(elevator_path).path,
        "elevatorNodeRef": elevator_ref,
        "terminalClassName": terminal_class_name,
        "floors": floors,
        "instanceDataPatched": sum(1 for f in floors if f["instanceData"]["patched"]),
        "instanceDataUnresolved": [f["terminal"] for f in floors if not f["instanceData"]["patched"]],
    }
