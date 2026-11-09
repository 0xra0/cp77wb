from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any, Sequence

from .assets import resolve_asset
from .project import WorldBuilderProject, node_kind


def _point3(value: Any) -> tuple[float, float, float]:
    if isinstance(value, dict):
        return float(value["x"]), float(value["y"]), float(value.get("z", 0.0))
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return float(value[0]), float(value[1]), float(value[2]) if len(value) >= 3 else 0.0
    raise ValueError(f"Invalid point {value!r}")


def load_points(value: str | Path | list[Any]) -> list[tuple[float, float, float]]:
    if isinstance(value, list):
        data = value
    else:
        raw = str(value)
        p = Path(raw)
        if p.is_file():
            data = json.loads(p.read_text(encoding="utf-8-sig"))
        else:
            data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("Points must be a JSON array")
    points = [_point3(v) for v in data]
    if len(points) < 2:
        raise ValueError("At least two points are required")
    return points


def marker_group_points(project: WorldBuilderProject, group_path: str, *, curve_samples: int = 12) -> list[tuple[float, float, float]]:
    """Read direct marker children in hierarchy order, sampling WB spline tangents when present."""
    group = project.get(group_path)
    if node_kind(group.node) != "group":
        raise ValueError(f"{group.path} is not a group")
    defs: list[dict[str, Any]] = []
    for child in group.node.get("childs", []):
        if not isinstance(child, dict):
            continue
        spawn = child.get("spawnable")
        if isinstance(spawn, dict) and isinstance(spawn.get("position"), dict):
            defs.append(spawn)
    if len(defs) < 2:
        raise ValueError(f"{group.path} must contain at least two positioned child markers")
    positions = [_point3(d["position"]) for d in defs]
    if curve_samples <= 0:
        return positions

    def tangent(d: dict[str, Any], key: str) -> tuple[float, float, float]:
        value = d.get(key)
        if not isinstance(value, dict):
            return (0.0, 0.0, 0.0)
        return float(value.get("x", 0)), float(value.get("y", 0)), float(value.get("z", 0))

    has_curve = any(any(abs(v) > 1e-9 for v in tangent(d, "tangentIn") + tangent(d, "tangentOut")) for d in defs)
    if not has_curve:
        return positions
    samples = max(2, min(64, int(curve_samples)))
    out = [positions[0]]
    for i in range(len(defs) - 1):
        p0, p1 = positions[i], positions[i + 1]
        tout = tangent(defs[i], "tangentOut")
        tin = tangent(defs[i + 1], "tangentIn")
        c0 = (p0[0] + tout[0], p0[1] + tout[1], p0[2] + tout[2])
        c1 = (p1[0] + tin[0], p1[1] + tin[1], p1[2] + tin[2])
        for j in range(1, samples + 1):
            t = j / samples
            u = 1.0 - t
            out.append((
                u*u*u*p0[0] + 3*u*u*t*c0[0] + 3*u*t*t*c1[0] + t*t*t*p1[0],
                u*u*u*p0[1] + 3*u*u*t*c0[1] + 3*u*t*t*c1[1] + t*t*t*p1[1],
                u*u*u*p0[2] + 3*u*u*t*c0[2] + 3*u*t*t*c1[2] + t*t*t*p1[2],
            ))
    return out


def _dist(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.dist(a, b)


def sample_polyline(
    points: Sequence[tuple[float, float, float]],
    *,
    spacing: float | None = None,
    count: int | None = None,
    closed: bool = False,
) -> list[tuple[tuple[float, float, float], float]]:
    if spacing is None and count is None:
        raise ValueError("Specify spacing or count")
    if spacing is not None and count is not None:
        raise ValueError("Specify only one of spacing or count")
    if spacing is not None and spacing <= 0:
        raise ValueError("spacing must be > 0")
    if count is not None and count < 1:
        raise ValueError("count must be >= 1")

    path = list(points)
    if closed and path[0] != path[-1]:
        path.append(path[0])
    seg_lengths = [_dist(path[i], path[i + 1]) for i in range(len(path) - 1)]
    total = sum(seg_lengths)
    if total <= 1e-9:
        raise ValueError("Path has zero length")
    if count is not None:
        if count == 1:
            distances = [0.0]
        else:
            distances = [total * i / (count - 1) for i in range(count)]
    else:
        assert spacing is not None
        n = int(math.floor(total / spacing))
        distances = [i * spacing for i in range(n + 1)]
        if not math.isclose(distances[-1], total, abs_tol=1e-8):
            distances.append(total)

    out: list[tuple[tuple[float, float, float], float]] = []
    for target in distances:
        remain = target
        seg_idx = 0
        while seg_idx < len(seg_lengths) - 1 and remain > seg_lengths[seg_idx]:
            remain -= seg_lengths[seg_idx]
            seg_idx += 1
        a, b = path[seg_idx], path[seg_idx + 1]
        seg_len = seg_lengths[seg_idx]
        t = 0.0 if seg_len <= 1e-12 else min(1.0, max(0.0, remain / seg_len))
        pos = (
            a[0] + (b[0] - a[0]) * t,
            a[1] + (b[1] - a[1]) * t,
            a[2] + (b[2] - a[2]) * t,
        )
        yaw = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
        out.append((pos, yaw))
    return out


def place_along_path(
    project: WorldBuilderProject,
    source_path: str,
    points: Sequence[tuple[float, float, float]],
    *,
    spacing: float | None = None,
    count: int | None = None,
    closed: bool = False,
    orient_to_path: bool = True,
    yaw_offset: float = 0.0,
    node_ref_prefix: str = "",
    keep_node_refs: bool = False,
) -> dict[str, Any]:
    source_pos = project.position(source_path)
    samples = sample_polyline(points, spacing=spacing, count=count, closed=closed)
    created: list[dict[str, Any]] = []
    for pos, yaw in samples:
        path = project.duplicate(source_path, count=1, node_ref_prefix=node_ref_prefix, keep_node_refs=keep_node_refs)[0]
        current = project.position(path)
        project.translate(path, pos[0] - current[0], pos[1] - current[1], pos[2] - current[2])
        if orient_to_path:
            project.rotate(path, yaw=yaw + yaw_offset)
        created.append({"path": path, "position": {"x": pos[0], "y": pos[1], "z": pos[2]}, "yaw": yaw + yaw_offset if orient_to_path else None})
    return {"source": source_path, "sourcePosition": source_pos, "samples": len(samples), "created": created}


def _inside_polygon(x: float, y: float, polygon: Sequence[tuple[float, float, float]]) -> bool:
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi, _ = polygon[i]
        xj, yj, _ = polygon[j]
        if ((yi > y) != (yj > y)) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-30) + xi:
            inside = not inside
        j = i
    return inside


def polygon_scatter(
    project: WorldBuilderProject,
    source_path: str,
    polygon: Sequence[tuple[float, float, float]],
    *,
    count: int,
    seed: int = 1,
    z: float | None = None,
    z_jitter: float = 0.0,
    random_yaw: bool = True,
    scale_min: float | None = None,
    scale_max: float | None = None,
    create_scale: bool = False,
    node_ref_prefix: str = "",
    keep_node_refs: bool = False,
) -> dict[str, Any]:
    if len(polygon) < 3:
        raise ValueError("polygon requires at least three points")
    if count < 1:
        raise ValueError("count must be >= 1")
    if z_jitter < 0:
        raise ValueError("z_jitter must be >= 0")
    if (scale_min is None) != (scale_max is None):
        raise ValueError("scale_min and scale_max must be supplied together")
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    base_z = sum(p[2] for p in polygon) / len(polygon) if z is None else z
    rng = random.Random(seed)
    created: list[dict[str, Any]] = []
    attempts = 0
    max_attempts = max(1000, count * 200)
    while len(created) < count and attempts < max_attempts:
        attempts += 1
        x = rng.uniform(min(xs), max(xs))
        y = rng.uniform(min(ys), max(ys))
        if not _inside_polygon(x, y, polygon):
            continue
        zz = base_z + rng.uniform(-z_jitter, z_jitter)
        path = project.duplicate(source_path, count=1, node_ref_prefix=node_ref_prefix, keep_node_refs=keep_node_refs)[0]
        cur = project.position(path)
        project.translate(path, x - cur[0], y - cur[1], zz - cur[2])
        yaw = rng.uniform(0.0, 360.0) if random_yaw else 0.0
        if random_yaw:
            project.rotate(path, yaw=yaw)
        scale = None
        if scale_min is not None and scale_max is not None:
            scale = rng.uniform(scale_min, scale_max)
            project.scale(path, scale, scale, scale, create_scale=create_scale)
        created.append({"path": path, "position": {"x": x, "y": y, "z": zz}, "yaw": yaw, "scale": scale})
    if len(created) != count:
        raise RuntimeError(f"Could place only {len(created)}/{count} points in polygon after {attempts} attempts")
    return {"seed": seed, "attempts": attempts, "created": created}


def volume_scatter(
    project: WorldBuilderProject,
    source_path: str,
    *,
    shape: str,
    count: int,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    seed: int = 1,
    random_yaw: bool = True,
    node_ref_prefix: str = "",
    keep_node_refs: bool = False,
) -> dict[str, Any]:
    if count < 1:
        raise ValueError("count must be >= 1")
    if any(v < 0 for v in size):
        raise ValueError("size values must be >= 0")
    shape = shape.lower()
    if shape not in {"box", "cylinder", "sphere"}:
        raise ValueError("shape must be box, cylinder, or sphere")
    rng = random.Random(seed)
    created = []
    for _ in range(count):
        if shape == "box":
            dx = rng.uniform(-size[0], size[0])
            dy = rng.uniform(-size[1], size[1])
            dz = rng.uniform(-size[2], size[2])
        elif shape == "cylinder":
            radius = size[0] * math.sqrt(rng.random())
            angle = rng.random() * math.tau
            dx = radius * math.cos(angle)
            dy = radius * math.sin(angle)
            dz = rng.uniform(-size[2], size[2])
        else:
            while True:
                dx = rng.uniform(-1, 1)
                dy = rng.uniform(-1, 1)
                dz = rng.uniform(-1, 1)
                if dx * dx + dy * dy + dz * dz <= 1:
                    break
            dx *= size[0]
            dy *= size[1]
            dz *= size[2]
        pos = (center[0] + dx, center[1] + dy, center[2] + dz)
        path = project.duplicate(source_path, count=1, node_ref_prefix=node_ref_prefix, keep_node_refs=keep_node_refs)[0]
        cur = project.position(path)
        project.translate(path, pos[0] - cur[0], pos[1] - cur[1], pos[2] - cur[2])
        yaw = rng.uniform(0, 360) if random_yaw else 0.0
        if random_yaw:
            project.rotate(path, yaw=yaw)
        created.append({"path": path, "position": {"x": pos[0], "y": pos[1], "z": pos[2]}, "yaw": yaw})
    return {"shape": shape, "seed": seed, "created": created}


def load_asset_pool(path_or_json: str | Path | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(path_or_json, list):
        data = path_or_json
    else:
        raw = str(path_or_json)
        p = Path(raw)
        data = json.loads(p.read_text(encoding="utf-8-sig")) if p.is_file() else json.loads(raw)
    if isinstance(data, dict):
        data = data.get("entries", [])
    if not isinstance(data, list) or not data:
        raise ValueError("Asset pool must contain a non-empty entries array")
    out: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict) or not item.get("asset"):
            raise ValueError("Every pool entry requires asset")
        weight = float(item.get("weight", 1.0))
        if weight <= 0:
            raise ValueError("Asset weights must be > 0")
        out.append(dict(item, weight=weight))
    return out


def spawn_weighted_pool(
    project: WorldBuilderProject,
    parent_path: str,
    *,
    catalog: str | Path,
    pool: list[dict[str, Any]],
    count: int,
    seed: int = 1,
    center: tuple[float, float, float] = (0, 0, 0),
    half_extents: tuple[float, float, float] = (5, 5, 0),
    random_yaw: bool = True,
    generate_node_ref: bool = False,
    node_ref_prefix: str = "",
) -> dict[str, Any]:
    if count < 1:
        raise ValueError("count must be >= 1")
    resolved = []
    for item in pool:
        asset = resolve_asset(catalog, str(item["asset"]), module_path=item.get("module"), variant=item.get("variant"))
        resolved.append((item, asset))
    rng = random.Random(seed)
    weights = [float(item[0]["weight"]) for item in resolved]
    created = []
    for i in range(count):
        item, asset = rng.choices(resolved, weights=weights, k=1)[0]
        pos = (
            center[0] + rng.uniform(-half_extents[0], half_extents[0]),
            center[1] + rng.uniform(-half_extents[1], half_extents[1]),
            center[2] + rng.uniform(-half_extents[2], half_extents[2]),
        )
        yaw = rng.uniform(0, 360) if random_yaw else float(item.get("yaw", 0))
        path = project.add_spawnable(
            parent_path, module_path=asset.module_path, data_type=asset.data_type, spawn_data=asset.spawn_data,
            template=asset.template, name=item.get("name"), position=pos, rotation=(0, 0, yaw),
            generate_node_ref=generate_node_ref, node_ref_prefix=node_ref_prefix,
        )
        created.append({"path": path, "assetId": asset.id, "spawnData": asset.spawn_data, "position": {"x": pos[0], "y": pos[1], "z": pos[2]}, "yaw": yaw})
    return {"seed": seed, "count": count, "created": created}


def _spawn_asset(project: WorldBuilderProject, parent: str, catalog: str | Path, asset_query: str, *, name: str | None, position: tuple[float, float, float], yaw: float = 0.0) -> str:
    asset = resolve_asset(catalog, asset_query)
    return project.add_spawnable(parent, module_path=asset.module_path, data_type=asset.data_type, spawn_data=asset.spawn_data, template=asset.template, name=name, position=position, rotation=(0, 0, yaw))


def generate_room(project: WorldBuilderProject, parent_path: str, *, catalog: str | Path, wall_asset: str, width: float, depth: float, segment: float, origin: tuple[float, float, float] = (0, 0, 0), name: str = "Generated Room", floor_asset: str | None = None) -> dict[str, Any]:
    if width <= 0 or depth <= 0 or segment <= 0:
        raise ValueError("width, depth and segment must be > 0")
    group = project.add_group(parent_path, name=name, position=origin)
    created: list[str] = []
    nx = max(2, int(round(width / segment)) + 1)
    ny = max(2, int(round(depth / segment)) + 1)
    for i in range(nx):
        x = origin[0] - width / 2 + width * i / (nx - 1)
        created.append(_spawn_asset(project, group, catalog, wall_asset, name="Wall", position=(x, origin[1] - depth / 2, origin[2]), yaw=0))
        created.append(_spawn_asset(project, group, catalog, wall_asset, name="Wall", position=(x, origin[1] + depth / 2, origin[2]), yaw=180))
    for i in range(1, ny - 1):
        y = origin[1] - depth / 2 + depth * i / (ny - 1)
        created.append(_spawn_asset(project, group, catalog, wall_asset, name="Wall", position=(origin[0] - width / 2, y, origin[2]), yaw=90))
        created.append(_spawn_asset(project, group, catalog, wall_asset, name="Wall", position=(origin[0] + width / 2, y, origin[2]), yaw=-90))
    floors: list[str] = []
    if floor_asset:
        fx = max(1, int(math.ceil(width / segment)))
        fy = max(1, int(math.ceil(depth / segment)))
        for ix in range(fx):
            for iy in range(fy):
                x = origin[0] - width / 2 + (ix + 0.5) * width / fx
                y = origin[1] - depth / 2 + (iy + 0.5) * depth / fy
                floors.append(_spawn_asset(project, group, catalog, floor_asset, name="Floor", position=(x, y, origin[2]), yaw=0))
    return {"group": group, "walls": created, "floors": floors, "width": width, "depth": depth, "segment": segment}


def generate_corridor(project: WorldBuilderProject, parent_path: str, *, catalog: str | Path, wall_asset: str, length: float, width: float, segment: float, origin: tuple[float, float, float] = (0, 0, 0), name: str = "Generated Corridor", floor_asset: str | None = None) -> dict[str, Any]:
    if length <= 0 or width <= 0 or segment <= 0:
        raise ValueError("length, width and segment must be > 0")
    group = project.add_group(parent_path, name=name, position=origin)
    n = max(2, int(round(length / segment)) + 1)
    walls: list[str] = []
    floors: list[str] = []
    for i in range(n):
        x = origin[0] - length / 2 + length * i / (n - 1)
        walls.append(_spawn_asset(project, group, catalog, wall_asset, name="Wall L", position=(x, origin[1] - width / 2, origin[2]), yaw=0))
        walls.append(_spawn_asset(project, group, catalog, wall_asset, name="Wall R", position=(x, origin[1] + width / 2, origin[2]), yaw=180))
        if floor_asset:
            floors.append(_spawn_asset(project, group, catalog, floor_asset, name="Floor", position=(x, origin[1], origin[2]), yaw=0))
    return {"group": group, "walls": walls, "floors": floors, "length": length, "width": width}


def generate_market(project: WorldBuilderProject, parent_path: str, *, catalog: str | Path, pool: list[dict[str, Any]], rows: int, columns: int, spacing_x: float, spacing_y: float, origin: tuple[float, float, float] = (0, 0, 0), seed: int = 1, name: str = "Generated Market") -> dict[str, Any]:
    if rows < 1 or columns < 1:
        raise ValueError("rows and columns must be >= 1")
    group = project.add_group(parent_path, name=name, position=origin)
    resolved = []
    for item in pool:
        resolved.append((item, resolve_asset(catalog, str(item["asset"]), module_path=item.get("module"), variant=item.get("variant"))))
    weights = [float(item[0].get("weight", 1.0)) for item in resolved]
    rng = random.Random(seed)
    created = []
    for r in range(rows):
        for c in range(columns):
            item, asset = rng.choices(resolved, weights=weights, k=1)[0]
            x = origin[0] + (c - (columns - 1) / 2) * spacing_x
            y = origin[1] + (r - (rows - 1) / 2) * spacing_y
            yaw = 0.0 if r % 2 == 0 else 180.0
            path = project.add_spawnable(group, module_path=asset.module_path, data_type=asset.data_type, spawn_data=asset.spawn_data, template=asset.template, name=item.get("name", "Stall"), position=(x, y, origin[2]), rotation=(0, 0, yaw))
            created.append({"path": path, "assetId": asset.id, "row": r, "column": c})
    return {"group": group, "seed": seed, "rows": rows, "columns": columns, "created": created}
