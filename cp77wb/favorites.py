from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

from .assets import find_worldbuilder_root
from .io import atomic_save_json
from .naming import sanitize_filename
from .project import WorldBuilderProject


def _load_dict(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def list_categories(world_builder_root: str | Path) -> list[dict[str, Any]]:
    root = find_worldbuilder_root(world_builder_root)
    favorite_dir = root / "data" / "favorite"
    results: list[dict[str, Any]] = []
    if not favorite_dir.is_dir():
        return results
    for path in sorted(favorite_dir.glob("*.json")):
        data = _load_dict(path)
        if not data or not isinstance(data.get("favorites"), list):
            continue
        results.append({
            "name": str(data.get("name", path.stem)),
            "file": str(path),
            "icon": str(data.get("icon", "")),
            "grouped": bool(data.get("grouped", False)),
            "count": len(data["favorites"]),
        })
    return results


def _find_category(root: Path, name: str) -> tuple[Path, dict[str, Any]] | None:
    favorite_dir = root / "data" / "favorite"
    if not favorite_dir.is_dir():
        return None
    for path in sorted(favorite_dir.glob("*.json")):
        data = _load_dict(path)
        if data and str(data.get("name", "")).casefold() == name.casefold() and isinstance(data.get("favorites"), list):
            return path, data
    return None


def _new_category_path(root: Path, name: str) -> Path:
    favorite_dir = root / "data" / "favorite"
    favorite_dir.mkdir(parents=True, exist_ok=True)
    stamp = int(time.time())
    base = sanitize_filename(name) or "cp77wb"
    candidate = favorite_dir / f"{base}_{stamp}.json"
    i = 1
    while candidate.exists():
        candidate = favorite_dir / f"{base}_{stamp}_{i}.json"
        i += 1
    return candidate


def add_favorite(
    project_file: str | Path,
    element_path: str,
    world_builder_root: str | Path,
    *,
    category: str,
    name: str | None = None,
    tags: list[str] | tuple[str, ...] = (),
    icon: str = "",
    category_icon: str = "",
    backup: bool = True,
) -> dict[str, Any]:
    """Add a serialized WB object/group to a World Builder favorites category.

    Favorites are World Builder's native reusable object/group format. A saved
    positionableGroup works as a prefab because spawnUI loads it silently then
    moves/rotates the root to the requested spawn transform.
    """
    root = find_worldbuilder_root(world_builder_root)
    project = WorldBuilderProject.load(project_file)
    entry = project.get(element_path)
    favorite_name = name or str(entry.node.get("name", "Favorite"))
    tag_map = {str(tag): True for tag in tags if str(tag)}

    found = _find_category(root, category)
    created_category = found is None
    if found is None:
        path = _new_category_path(root, category)
        data: dict[str, Any] = {
            "name": category,
            "icon": category_icon,
            "headerOpen": False,
            "grouped": False,
            "virtualGroupsPS": {},
            "favorites": [],
        }
    else:
        path, data = found

    favorites = data.setdefault("favorites", [])
    if not isinstance(favorites, list):
        raise ValueError(f"Favorite category has invalid favorites field: {path}")

    favorite = {
        "name": favorite_name,
        "tags": tag_map,
        "data": copy.deepcopy(entry.node),
        "icon": icon,
    }
    favorites.append(favorite)
    backup_path = atomic_save_json(path, data, make_backup=backup, indent=2)
    return {
        "worldBuilderRoot": str(root),
        "category": category,
        "categoryFile": str(path),
        "createdCategory": created_category,
        "favorite": favorite_name,
        "source": str(Path(project_file).resolve()),
        "sourcePath": entry.path,
        "tags": sorted(tag_map),
        "count": len(favorites),
        "backup": str(backup_path) if backup_path else None,
    }


def remove_favorite(
    world_builder_root: str | Path,
    *,
    category: str,
    name: str,
    backup: bool = True,
) -> dict[str, Any]:
    root = find_worldbuilder_root(world_builder_root)
    found = _find_category(root, category)
    if found is None:
        raise ValueError(f"No World Builder favorite category named {category!r}")
    path, data = found
    favorites = data.get("favorites")
    if not isinstance(favorites, list):
        raise ValueError(f"Favorite category has invalid favorites field: {path}")
    matches = [i for i, fav in enumerate(favorites) if isinstance(fav, dict) and str(fav.get("name", "")) == name]
    if not matches:
        raise ValueError(f"No favorite named {name!r} in category {category!r}")
    # Match WB's UI expectation that duplicate names are possible; remove only
    # the first exact match and report whether more remain.
    del favorites[matches[0]]
    backup_path = atomic_save_json(path, data, make_backup=backup, indent=2)
    return {
        "category": category,
        "categoryFile": str(path),
        "removed": name,
        "remaining": len(favorites),
        "moreWithSameName": len(matches) > 1,
        "backup": str(backup_path) if backup_path else None,
    }
