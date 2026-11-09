from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable

from .assets import AssetSearchResult, _connect, get_asset
from .project import WorldBuilderProject, node_kind
from .semantics import infer_semantics


@dataclass(frozen=True)
class Bounds:
    x: float
    y: float
    z: float
    source: str = "user"
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


HEURISTIC_BOUNDS: dict[str, tuple[float, float, float]] = {
    "wall": (4.0, 0.25, 3.0),
    "floor": (2.0, 2.0, 0.20),
    "ceiling": (2.0, 2.0, 0.20),
    "door": (1.5, 0.35, 2.5),
    "window": (1.5, 0.25, 1.5),
    "column": (0.6, 0.6, 3.0),
    "fence": (2.0, 0.20, 1.5),
    "pipe": (2.0, 0.25, 0.25),
    "cable": (2.0, 0.10, 0.10),
    "light": (0.5, 0.5, 0.5),
    "sign": (1.5, 0.20, 1.0),
    "furniture": (1.2, 1.0, 1.2),
    "container": (1.0, 1.0, 1.0),
    "stall": (2.5, 2.0, 2.5),
    "clutter": (0.8, 0.8, 0.8),
    "plant": (1.0, 1.0, 1.5),
    "device": (0.8, 0.5, 1.5),
}


def ensure_bounds_schema(db_path: str | Path) -> None:
    con = _connect(db_path)
    try:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS asset_bounds (
                asset_id INTEGER PRIMARY KEY,
                size_x REAL NOT NULL,
                size_y REAL NOT NULL,
                size_z REAL NOT NULL,
                source TEXT NOT NULL,
                confidence REAL NOT NULL,
                FOREIGN KEY(asset_id) REFERENCES assets(id)
            );
            """
        )
        con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('bounds_schema','1')")
        con.commit()
    finally:
        con.close()


def set_asset_bounds(db_path: str | Path, asset_id: int, size: tuple[float, float, float], *, source: str = "user", confidence: float = 1.0) -> dict[str, Any]:
    if any(v <= 0 for v in size):
        raise ValueError("Bounds sizes must be > 0")
    if not (0 <= confidence <= 1):
        raise ValueError("confidence must be between 0 and 1")
    get_asset(db_path, asset_id)  # existence check
    ensure_bounds_schema(db_path)
    con = _connect(db_path)
    try:
        con.execute(
            "INSERT OR REPLACE INTO asset_bounds(asset_id,size_x,size_y,size_z,source,confidence) VALUES(?,?,?,?,?,?)",
            (int(asset_id), float(size[0]), float(size[1]), float(size[2]), source, float(confidence)),
        )
        con.commit()
    finally:
        con.close()
    return {"assetId": int(asset_id), "bounds": Bounds(*map(float, size), source=source, confidence=float(confidence)).to_dict()}


def import_bounds(db_path: str | Path, value: str | Path | list[dict[str, Any]]) -> dict[str, Any]:
    if isinstance(value, list):
        rows = value
    else:
        p = Path(value)
        data = json.loads(p.read_text(encoding="utf-8-sig")) if p.is_file() else json.loads(str(value))
        rows = data.get("bounds", []) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError("Bounds input must be an array or {bounds:[...]}")
    written = 0
    for entry in rows:
        if not isinstance(entry, dict):
            continue
        asset = entry.get("asset", entry.get("id"))
        if isinstance(asset, str) and asset.startswith("#"):
            asset = asset[1:]
        size = entry.get("size") or [entry.get("x"), entry.get("y"), entry.get("z")]
        if asset is None or not isinstance(size, (list, tuple)) or len(size) < 3:
            raise ValueError("Each bounds entry needs asset/#id and size [x,y,z]")
        size_x, size_y, size_z = size[0], size[1], size[2]
        if size_x is None or size_y is None or size_z is None:
            raise ValueError("Bounds size components cannot be null")
        set_asset_bounds(
            db_path,
            int(asset),
            (float(size_x), float(size_y), float(size_z)),
            source=str(entry.get("source", "import")),
            confidence=float(entry.get("confidence", 1.0)),
        )
        written += 1
    return {"database": str(Path(db_path).resolve()), "imported": written}


def get_asset_bounds(db_path: str | Path, asset_id: int) -> Bounds | None:
    con = _connect(db_path, readonly=True)
    try:
        try:
            row = con.execute("SELECT * FROM asset_bounds WHERE asset_id=?", (int(asset_id),)).fetchone()
        except Exception:
            return None
        if row is None:
            return None
        return Bounds(float(row["size_x"]), float(row["size_y"]), float(row["size_z"]), str(row["source"]), float(row["confidence"]))
    finally:
        con.close()


def effective_bounds(db_path: str | Path, asset: AssetSearchResult) -> Bounds:
    exact = get_asset_bounds(db_path, asset.id)
    if exact:
        return exact
    semantics = infer_semantics(asset)
    for role in semantics.get("roles", []):
        if role in HEURISTIC_BOUNDS:
            sx, sy, sz = HEURISTIC_BOUNDS[role]
            return Bounds(sx, sy, sz, source=f"heuristic:{role}", confidence=0.25)
    return Bounds(1.0, 1.0, 1.0, source="heuristic:generic", confidence=0.1)


def bounds_info(db_path: str | Path, asset_id: int | None = None) -> dict[str, Any]:
    ensure_bounds_schema(db_path)
    con = _connect(db_path, readonly=True)
    try:
        count = int(con.execute("SELECT COUNT(*) FROM asset_bounds").fetchone()[0])
        if asset_id is None:
            return {"database": str(Path(db_path).resolve()), "explicitBounds": count, "heuristics": HEURISTIC_BOUNDS}
        asset = get_asset(db_path, int(asset_id))
        explicit = get_asset_bounds(db_path, int(asset_id))
        effective = explicit or effective_bounds(db_path, asset)
        return {"asset": asset.to_dict(), "explicit": explicit.to_dict() if explicit else None, "effective": effective.to_dict()}
    finally:
        con.close()


@dataclass(frozen=True)
class PlacementBox:
    key: str
    x: float
    y: float
    z: float
    yaw: float
    sx: float
    sy: float
    sz: float
    source: str
    confidence: float
    path: str | None = None
    asset_id: int | None = None


def _axes(yaw: float) -> tuple[tuple[float, float], tuple[float, float]]:
    a = math.radians(yaw)
    return (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))


def _project_radius(box: PlacementBox, axis: tuple[float, float]) -> float:
    ux, uy = _axes(box.yaw)
    return abs((ux[0] * axis[0] + ux[1] * axis[1]) * box.sx / 2) + abs((uy[0] * axis[0] + uy[1] * axis[1]) * box.sy / 2)


def boxes_overlap(a: PlacementBox, b: PlacementBox, clearance: float = 0.0) -> bool:
    if abs(a.z - b.z) * 2 >= (a.sz + b.sz + 2 * clearance):
        return False
    delta = (b.x - a.x, b.y - a.y)
    for axis in (*_axes(a.yaw), *_axes(b.yaw)):
        distance = abs(delta[0] * axis[0] + delta[1] * axis[1])
        if distance >= _project_radius(a, axis) + _project_radius(b, axis) + clearance:
            return False
    return True


def placement_box(key: str, position: tuple[float, float, float], yaw: float, bounds: Bounds, *, path: str | None = None, asset_id: int | None = None, scale: tuple[float,float,float] = (1,1,1)) -> PlacementBox:
    return PlacementBox(key, position[0], position[1], position[2], yaw, bounds.x*abs(scale[0]), bounds.y*abs(scale[1]), bounds.z*abs(scale[2]), bounds.source, bounds.confidence, path, asset_id)


def detect_collisions(boxes: Iterable[PlacementBox], *, clearance: float = 0.0, max_pairs: int = 10000) -> list[dict[str, Any]]:
    items = list(boxes)
    out: list[dict[str, Any]] = []
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            if boxes_overlap(a, b, clearance):
                out.append({
                    "a": a.key, "b": b.key, "clearance": clearance,
                    "confidence": min(a.confidence, b.confidence),
                    "approximate": a.confidence < 1.0 or b.confidence < 1.0,
                })
                if len(out) >= max_pairs:
                    return out
    return out


def _asset_by_spawn_data(db_path: str | Path, spawn_data: str, module_path: str | None = None) -> AssetSearchResult | None:
    con = _connect(db_path, readonly=True)
    try:
        if module_path:
            row = con.execute("SELECT id FROM assets WHERE spawn_data=? AND module_path=? ORDER BY id LIMIT 1", (spawn_data, module_path)).fetchone()
        else:
            row = con.execute("SELECT id FROM assets WHERE spawn_data=? ORDER BY id LIMIT 1", (spawn_data,)).fetchone()
        return get_asset(db_path, int(row["id"])) if row else None
    finally:
        con.close()


def project_boxes(project: WorldBuilderProject, catalog: str | Path, *, include_heuristic: bool = True) -> list[PlacementBox]:
    out: list[PlacementBox] = []
    for entry in project.iter_nodes():
        if node_kind(entry.node) != "object":
            continue
        spawn = entry.node.get("spawnable")
        if not isinstance(spawn, dict):
            continue
        spawn_data = str(spawn.get("spawnData", ""))
        if not spawn_data:
            continue
        asset = _asset_by_spawn_data(catalog, spawn_data, str(spawn.get("modulePath", "")))
        if not asset:
            continue
        b = effective_bounds(catalog, asset)
        if not include_heuristic and b.confidence < 1.0:
            continue
        pos = project.position(entry.path)
        rotation_value = spawn.get("rotation")
        rot = rotation_value if isinstance(rotation_value, dict) else {}
        yaw = float(rot.get("yaw", 0.0))
        scale_value = spawn.get("scale")
        scl = scale_value if isinstance(scale_value, dict) else {}
        scale = (float(scl.get("x",1)),float(scl.get("y",1)),float(scl.get("z",1)))
        out.append(placement_box(entry.path, pos, yaw, b, path=entry.path, asset_id=asset.id, scale=scale))
    return out


def scan_project_collisions(project: WorldBuilderProject, catalog: str | Path, *, clearance: float = 0.0, include_heuristic: bool = True) -> dict[str, Any]:
    boxes = project_boxes(project, catalog, include_heuristic=include_heuristic)
    collisions = detect_collisions(boxes, clearance=clearance)
    return {
        "objectsWithBounds": len(boxes), "collisions": collisions, "count": len(collisions),
        "note": "Collision checks use oriented bounding boxes; heuristic bounds are explicitly marked approximate.",
    }
