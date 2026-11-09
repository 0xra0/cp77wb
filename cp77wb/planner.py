from __future__ import annotations

import copy
import json
import math
import random
from pathlib import Path
from typing import Any

from .assets import AssetSearchResult, get_asset, resolve_asset
from .project import WorldBuilderProject
from .semantics import semantic_search
from .spatial import Bounds, PlacementBox, boxes_overlap, detect_collisions, effective_bounds, placement_box, project_boxes
from .validate import validate

PLAN_SCHEMA = "cp77wb-plan/1"
COMPILED_SCHEMA = "cp77wb-compiled-plan/1"


def load_plan(value: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        data = copy.deepcopy(value)
    else:
        p = Path(value)
        data = json.loads(p.read_text(encoding="utf-8-sig")) if p.is_file() else json.loads(str(value))
    if not isinstance(data, dict):
        raise ValueError("Plan must be a JSON object")
    return data


def _point(value: Any, default: tuple[float,float,float]=(0,0,0)) -> tuple[float,float,float]:
    if value is None:
        return default
    if isinstance(value, dict):
        return float(value.get("x",0)), float(value.get("y",0)), float(value.get("z",0))
    if isinstance(value, (list,tuple)) and len(value) >= 2:
        return float(value[0]), float(value[1]), float(value[2]) if len(value) >= 3 else 0.0
    raise ValueError(f"Invalid point {value!r}")


def _resolve_spec_asset(catalog: str | Path, spec: dict[str, Any], selections: list[dict[str, Any]]) -> AssetSearchResult:
    if spec.get("asset"):
        asset = resolve_asset(catalog, str(spec["asset"]), module_path=spec.get("module"), variant=spec.get("variant"))
        selections.append({"request": spec.get("asset"), "assetId": asset.id, "reason": "exact/indexed"})
        return asset
    query = str(spec.get("semanticQuery", "")).strip()
    if not query:
        raise ValueError("Plan asset requires asset or semanticQuery")
    if not bool(spec.get("autoSelect", False)):
        raise ValueError(f"semanticQuery {query!r} requires autoSelect=true or an exact asset ID")
    results = semantic_search(
        catalog, query, role=spec.get("role"), style=spec.get("style"), material=spec.get("material"),
        condition=spec.get("condition"), category=spec.get("category"), variant=spec.get("variant"), limit=5,
    )
    if not results:
        raise ValueError(f"No semantic asset matched {query!r}")
    choice = results[0]
    asset = get_asset(catalog, int(choice["id"]))
    selections.append({
        "request": query, "assetId": asset.id, "reason": "semantic-best-explicit-autoselect",
        "candidates": [{"id": r["id"], "spawn_data": r["spawn_data"], "rank": r["rank"]} for r in results],
    })
    return asset


def _op(asset: AssetSearchResult, pos: tuple[float,float,float], yaw: float, *, name: str | None = None, role: str | None = None, allow_overlap: bool = False) -> dict[str, Any]:
    return {
        "op": "spawn", "assetId": asset.id, "position": [pos[0],pos[1],pos[2]], "rotation": [0.0,0.0,yaw],
        "name": name, "role": role, "allowOverlap": allow_overlap,
    }


def _door_opening_matches(side: str, coord: float, door: dict[str, Any]) -> bool:
    if str(door.get("side", "")).lower() != side:
        return False
    offset = float(door.get("offset", 0.0))
    width = float(door.get("width", 1.5))
    return abs(coord - offset) < width / 2


def compile_plan(spec: dict[str, Any], catalog: str | Path) -> dict[str, Any]:
    schema = str(spec.get("schema", PLAN_SCHEMA))
    if schema != PLAN_SCHEMA:
        raise ValueError(f"Unsupported plan schema {schema!r}; expected {PLAN_SCHEMA}")
    parent = str(spec.get("parent", ""))
    if not parent:
        raise ValueError("Plan requires parent")
    origin = _point(spec.get("origin"))
    selections: list[dict[str, Any]] = []
    warnings: list[str] = []
    operations: list[dict[str, Any]] = []
    boxes: list[PlacementBox] = []

    def add(asset: AssetSearchResult, pos: tuple[float,float,float], yaw: float, *, name: str | None = None, role: str | None = None, allow_overlap: bool = False, bounds_override: Any = None) -> None:
        idx = len(operations)
        operations.append(_op(asset, pos, yaw, name=name, role=role, allow_overlap=allow_overlap))
        if bounds_override:
            size = _point(bounds_override)
            b = Bounds(size[0], size[1], size[2], "plan", 1.0)
        else:
            b = effective_bounds(catalog, asset)
        boxes.append(placement_box(f"plan:{idx}:{name or asset.file_name}", pos, yaw, b, asset_id=asset.id))

    room = spec.get("room")
    if isinstance(room, dict):
        width = float(room.get("width", 0))
        depth = float(room.get("depth", 0))
        wall_step = float(room.get("wallStep", room.get("segment", 2.0)))
        if width <= 0 or depth <= 0 or wall_step <= 0:
            raise ValueError("room width/depth/wallStep must be > 0")
        wall_value = room.get("wall")
        wall_spec: dict[str, Any] = wall_value if isinstance(wall_value, dict) else {"asset": room.get("wallAsset")}
        wall_asset = _resolve_spec_asset(catalog, wall_spec, selections)
        doors = [d for d in room.get("doors", []) if isinstance(d, dict)]
        nx = max(2, int(round(width / wall_step)) + 1)
        ny = max(2, int(round(depth / wall_step)) + 1)
        # South/north: coordinate along X; west/east: coordinate along Y.
        for i in range(nx):
            local_x = -width/2 + width*i/(nx-1)
            if not any(_door_opening_matches("south", local_x, d) for d in doors):
                add(wall_asset, (origin[0]+local_x, origin[1]-depth/2, origin[2]), 0, name="Wall South", role="wall", allow_overlap=True)
            if not any(_door_opening_matches("north", local_x, d) for d in doors):
                add(wall_asset, (origin[0]+local_x, origin[1]+depth/2, origin[2]), 180, name="Wall North", role="wall", allow_overlap=True)
        for i in range(1, ny-1):
            local_y = -depth/2 + depth*i/(ny-1)
            if not any(_door_opening_matches("west", local_y, d) for d in doors):
                add(wall_asset, (origin[0]-width/2, origin[1]+local_y, origin[2]), 90, name="Wall West", role="wall", allow_overlap=True)
            if not any(_door_opening_matches("east", local_y, d) for d in doors):
                add(wall_asset, (origin[0]+width/2, origin[1]+local_y, origin[2]), -90, name="Wall East", role="wall", allow_overlap=True)
        for door in doors:
            side = str(door.get("side", "")).lower()
            if side not in {"north","south","east","west"}:
                raise ValueError(f"Door side must be north/south/east/west, got {side!r}")
            asset = _resolve_spec_asset(catalog, door, selections)
            off = float(door.get("offset",0))
            z = origin[2] + float(door.get("z",0))
            if side == "south":
                pos=(origin[0]+off, origin[1]-depth/2, z)
                yaw=0
            elif side == "north":
                pos=(origin[0]+off, origin[1]+depth/2, z)
                yaw=180
            elif side == "west":
                pos=(origin[0]-width/2, origin[1]+off, z)
                yaw=90
            else:
                pos=(origin[0]+width/2, origin[1]+off, z)
                yaw=-90
            add(asset, pos, yaw, name=str(door.get("name","Door")), role="door", allow_overlap=True, bounds_override=door.get("bounds"))
        floor_value = room.get("floor")
        floor_asset_value = room.get("floorAsset")
        floor_spec: dict[str, Any] | None = (
            floor_value
            if isinstance(floor_value, dict)
            else ({"asset": floor_asset_value} if floor_asset_value else None)
        )
        if isinstance(floor_spec, dict) and (floor_spec.get("asset") or floor_spec.get("semanticQuery")):
            floor_asset = _resolve_spec_asset(catalog, floor_spec, selections)
            step = float(room.get("floorStep", wall_step))
            fx=max(1,int(math.ceil(width/step)))
            fy=max(1,int(math.ceil(depth/step)))
            for ix in range(fx):
                for iy in range(fy):
                    x=origin[0]-width/2+(ix+0.5)*width/fx
                    y=origin[1]-depth/2+(iy+0.5)*depth/fy
                    add(floor_asset,(x,y,origin[2]),0,name="Floor",role="floor",allow_overlap=True)

    for item in spec.get("placements", []):
        if not isinstance(item, dict):
            continue
        asset = _resolve_spec_asset(catalog, item, selections)
        p = _point(item.get("position"))
        pos=(origin[0]+p[0],origin[1]+p[1],origin[2]+p[2])
        add(asset, pos, float(item.get("yaw",0)), name=item.get("name"), role=item.get("role"), allow_overlap=bool(item.get("allowOverlap",False)), bounds_override=item.get("bounds"))

    # Deterministic, collision-aware prop scatter. It avoids compiled boxes unless
    # those boxes explicitly allow overlap. A failed requested count is an error by default.
    for scat in spec.get("scatter", []):
        if not isinstance(scat, dict):
            continue
        asset = _resolve_spec_asset(catalog, scat, selections)
        count=int(scat.get("count",1))
        seed=int(scat.get("seed",1))
        clearance=float(scat.get("clearance",0.2))
        if count < 1:
            raise ValueError("scatter count must be >= 1")
        region_value = scat.get("region")
        region: dict[str, Any] = region_value if isinstance(region_value, dict) else {}
        center=_point(region.get("center"), (0,0,0))
        half=_point(region.get("halfExtents"), (2,2,0))
        center=(origin[0]+center[0],origin[1]+center[1],origin[2]+center[2])
        b=effective_bounds(catalog,asset)
        rng=random.Random(seed)
        made=0
        attempts=0
        # Structural walls/doors block props even though their mutual seam overlaps are ignored in the final collision report.
        # Floors/ceilings are excluded because WB object origins are not guaranteed to be geometric centers.
        blockers=[box for box,op in zip(boxes,operations) if op.get("role") not in {"floor","ceiling"}]
        while made<count and attempts<max(1000,count*250):
            attempts += 1
            pos=(center[0]+rng.uniform(-half[0],half[0]),center[1]+rng.uniform(-half[1],half[1]),center[2]+rng.uniform(-half[2],half[2]))
            yaw=rng.uniform(0,360) if bool(scat.get("randomYaw",True)) else float(scat.get("yaw",0))
            candidate=placement_box(f"scatter:{len(operations)}",pos,yaw,b,asset_id=asset.id)
            if any(boxes_overlap(candidate,x,clearance) for x in blockers):
                continue
            add(asset,pos,yaw,name=scat.get("name"),role=scat.get("role"),allow_overlap=False,bounds_override=scat.get("bounds"))
            blockers.append(boxes[-1])
            made += 1
        if made != count:
            msg=f"scatter {scat.get('name') or asset.file_name}: placed {made}/{count} after {attempts} attempts"
            if scat.get("allowPartial"):
                warnings.append(msg)
            else:
                raise ValueError(msg)

    # Only report collisions where neither side opted out. This mostly targets
    # explicit props; structural seams and floors intentionally overlap/touch.
    active_boxes=[box for box,op in zip(boxes,operations) if not op.get("allowOverlap")]
    collisions=detect_collisions(active_boxes,clearance=float(spec.get("clearance",0)))
    return {
        "schema": COMPILED_SCHEMA, "name": str(spec.get("name","Claude Plan")), "parent": parent, "origin": list(origin),
        "operations": operations, "assetSelections": selections, "warnings": warnings, "collisions": collisions,
        "summary": {"operations":len(operations),"collisions":len(collisions),"warnings":len(warnings)},
    }


def apply_compiled_plan(project: WorldBuilderProject, compiled: dict[str, Any], catalog: str | Path) -> dict[str, Any]:
    if compiled.get("schema") != COMPILED_SCHEMA:
        raise ValueError("Expected a compiled cp77wb plan")
    group = project.add_group(str(compiled["parent"]), name=str(compiled.get("name","Claude Plan")), position=_point(compiled.get("origin")))
    created=[]
    for op in compiled.get("operations",[]):
        if not isinstance(op,dict) or op.get("op") != "spawn":
            continue
        asset=get_asset(catalog,int(op["assetId"]))
        pos=_point(op.get("position"))
        rot=_point(op.get("rotation"))
        created.append(project.add_spawnable(group,module_path=asset.module_path,data_type=asset.data_type,spawn_data=asset.spawn_data,template=asset.template,name=op.get("name"),position=pos,rotation=rot))
    return {"group":group,"created":created,"count":len(created)}


def preview_plan(project: WorldBuilderProject, spec: dict[str, Any], catalog: str | Path) -> dict[str, Any]:
    compiled=compile_plan(spec,catalog)
    before_boxes=project_boxes(project,catalog)
    clone=project.clone()
    result=apply_compiled_plan(clone,compiled,catalog)
    new_boxes=project_boxes(clone,catalog)
    existing_keys={b.key for b in before_boxes}
    planned=[b for b in new_boxes if b.key not in existing_keys]
    cross=[]
    for a in planned:
        for b in before_boxes:
            if boxes_overlap(a,b,0):
                cross.append({"planned":a.key,"existing":b.key,"confidence":min(a.confidence,b.confidence),"approximate":a.confidence<1 or b.confidence<1})
    issues=[i.to_dict() for i in validate(clone)]
    return {"compiled":compiled,"applyPreview":result,"existingCollisions":cross,"validation":issues,"valid":not any(i["severity"]=="error" for i in issues)}
