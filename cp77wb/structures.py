from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Sequence

from .assets import resolve_asset
from .procedural import sample_polyline
from .project import WorldBuilderProject


def _spawn(project: WorldBuilderProject, parent: str, catalog: str | Path, asset_query: str, pos: tuple[float,float,float], yaw: float, name: str) -> str:
    asset=resolve_asset(catalog,asset_query)
    return project.add_spawnable(parent,module_path=asset.module_path,data_type=asset.data_type,spawn_data=asset.spawn_data,template=asset.template,name=name,position=pos,rotation=(0,0,yaw))


def generate_fence(project: WorldBuilderProject, parent: str, *, catalog: str | Path, segment_asset: str, points: Sequence[tuple[float,float,float]], spacing: float, post_asset: str | None = None, name: str = "Generated Fence", yaw_offset: float = 0.0) -> dict[str,Any]:
    group=project.add_group(parent,name=name,position=points[0])
    samples=sample_polyline(points,spacing=spacing)
    segments=[]
    posts=[]
    for i,(pos,yaw) in enumerate(samples[:-1] if len(samples)>1 else samples):
        segments.append(_spawn(project,group,catalog,segment_asset,pos,yaw+yaw_offset,"Fence Segment"))
    if post_asset:
        for pos,_ in samples:
            posts.append(_spawn(project,group,catalog,post_asset,pos,0,"Fence Post"))
    return {"group":group,"segments":segments,"posts":posts,"samples":len(samples)}


def generate_road(project: WorldBuilderProject, parent: str, *, catalog: str | Path, tile_asset: str, points: Sequence[tuple[float,float,float]], spacing: float, width: float, edge_asset: str | None = None, name: str = "Generated Road", yaw_offset: float = 0.0) -> dict[str,Any]:
    if width <= 0:
        raise ValueError("width must be > 0")
    group=project.add_group(parent,name=name,position=points[0])
    samples=sample_polyline(points,spacing=spacing)
    tiles=[]
    edges=[]
    for pos,yaw in samples:
        tiles.append(_spawn(project,group,catalog,tile_asset,pos,yaw+yaw_offset,"Road Tile"))
        if edge_asset:
            a=math.radians(yaw)
            nx=-math.sin(a)
            ny=math.cos(a)
            left=(pos[0]+nx*width/2,pos[1]+ny*width/2,pos[2])
            right=(pos[0]-nx*width/2,pos[1]-ny*width/2,pos[2])
            edges.append(_spawn(project,group,catalog,edge_asset,left,yaw+yaw_offset,"Road Edge L"))
            edges.append(_spawn(project,group,catalog,edge_asset,right,yaw+yaw_offset,"Road Edge R"))
    return {"group":group,"tiles":tiles,"edges":edges,"samples":len(samples),"width":width}


def generate_cable_chain(project: WorldBuilderProject, parent: str, *, catalog: str | Path, segment_asset: str, points: Sequence[tuple[float,float,float]], spacing: float, name: str = "Generated Cable", yaw_offset: float = 0.0) -> dict[str,Any]:
    group=project.add_group(parent,name=name,position=points[0])
    samples=sample_polyline(points,spacing=spacing)
    segments=[]
    for pos,yaw in samples:
        segments.append(_spawn(project,group,catalog,segment_asset,pos,yaw+yaw_offset,"Cable Segment"))
    return {"group":group,"segments":segments,"samples":len(samples),"note":"Repeated-segment cable; no mesh stretching is inferred."}
