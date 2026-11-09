from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any, Callable

from . import __version__
from .assets import build_catalog, catalog_info, get_asset, resolve_asset, search_catalog
from .semantics import build_semantic_index, semantic_search
from .spatial import bounds_info, import_bounds, scan_project_collisions, set_asset_bounds
from .planner import apply_compiled_plan, compile_plan, preview_plan
from .structures import generate_cable_chain, generate_fence, generate_road
from .diff import json_diff
from .favorites import add_favorite, list_categories
from .compat import scan_worldbuilder
from .devices import connect_device, wire_elevator
from .procedural import (
    generate_corridor, generate_market, generate_room, load_asset_pool, load_points,
    marker_group_points, place_along_path, polygon_scatter, spawn_weighted_pool, volume_scatter,
)
from .templates import render_template_file
from .live import LiveBridgeClient
from .logs import read_logs
from .project import WorldBuilderProject, build_spawnable_node, node_kind
from .references import iter_known_references
from .validate import validate
from .build import inspect_export, prepare_build_workspace, build_status, backend_scan, build_pack, build_package, deploy_layout, verify_package, build_doctor, build_native_import, build_worker_import, archive_xl_config, _read_json
from .native import (required_template_types, make_template_capture_script, verify_template_bundle, prepare_native_json, native_preflight, native_convert, native_import, verify_native_outputs)
from .worker import build_worker, worker_preflight, worker_inspect, worker_doctor, worker_create_bundle, worker_import

LEGACY_PROTOCOL = "2025-11-25"
MODERN_PROTOCOL = "2026-07-28"
SERVER_INFO = {"name": "cp77wb", "version": __version__}


def _obj(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "object", "properties": properties, "additionalProperties": False}
    if required:
        schema["required"] = required
    return schema


STR = {"type": "string"}
NUM = {"type": "number"}
BOOL = {"type": "boolean"}
INT = {"type": "integer"}
PATHS = {"type": "array", "items": {"type": "string"}, "minItems": 2}
PATH_LIST = {"type": "array", "items": {"type": "string"}, "minItems": 1}

TOOLS: list[dict[str, Any]] = [
    {"name": "wb_tree", "description": "Read a World Builder build hierarchy.", "inputSchema": _obj({"file": STR, "show_modules": BOOL}, ["file"])},
    {"name": "wb_get", "description": "Read project stats or one World Builder element by path.", "inputSchema": _obj({"file": STR, "path": STR}, ["file"])},
    {"name": "wb_find", "description": "Search World Builder names, paths, modules, assets and NodeRefs.", "inputSchema": _obj({"file": STR, "query": STR, "case_sensitive": BOOL}, ["file", "query"])},
    {"name": "wb_validate", "description": "Validate World Builder-specific references, NodeRefs and caches.", "inputSchema": _obj({"file": STR}, ["file"])},
    {"name": "wb_refs", "description": "List NodeRef definitions and known World Builder references.", "inputSchema": _obj({"file": STR}, ["file"])},
    {"name": "wb_move", "description": "Translate an object/group. Dry-run unless write=true.", "inputSchema": _obj({"file": STR, "path": STR, "x": NUM, "y": NUM, "z": NUM, "write": BOOL}, ["file", "path"])},
    {"name": "wb_rotate", "description": "Rotate an object/group around its origin or explicit pivot. Dry-run unless write=true.", "inputSchema": _obj({"file": STR, "path": STR, "roll": NUM, "pitch": NUM, "yaw": NUM, "pivot_x": NUM, "pivot_y": NUM, "pivot_z": NUM, "write": BOOL}, ["file", "path"])},
    {"name": "wb_scale", "description": "Scale an object/group hierarchy. Existing scale fields only by default. Dry-run unless write=true.", "inputSchema": _obj({"file": STR, "path": STR, "x": NUM, "y": NUM, "z": NUM, "uniform": NUM, "create_scale": BOOL, "write": BOOL}, ["file", "path"])},
    {"name": "wb_generate_noderef", "description": "Generate a World Builder-compatible NodeRef. Dry-run unless write=true.", "inputSchema": _obj({"file": STR, "path": STR, "prefix": STR, "force": BOOL, "write": BOOL}, ["file", "path"])},
    {"name": "wb_duplicate", "description": "Duplicate an object/group with unique names and repaired internal references. Dry-run unless write=true.", "inputSchema": _obj({"file": STR, "path": STR, "count": INT, "x": NUM, "y": NUM, "z": NUM, "noderef_prefix": STR, "keep_noderefs": BOOL, "write": BOOL}, ["file", "path"])},
    {"name": "wb_array", "description": "Create a linear array; count includes source. Dry-run unless write=true.", "inputSchema": _obj({"file": STR, "path": STR, "count": INT, "x": NUM, "y": NUM, "z": NUM, "noderef_prefix": STR, "keep_noderefs": BOOL, "write": BOOL}, ["file", "path", "count"])},
    {"name": "wb_radial_array", "description": "Create an XY radial array; count includes source. Dry-run unless write=true.", "inputSchema": _obj({"file": STR, "path": STR, "count": INT, "angle": NUM, "pivot_x": NUM, "pivot_y": NUM, "pivot_z": NUM, "rotate_items": BOOL, "noderef_prefix": STR, "keep_noderefs": BOOL, "write": BOOL}, ["file", "path", "count"])},
    {"name": "wb_align", "description": "Align independent objects/groups on x/y/z. Dry-run unless write=true.", "inputSchema": _obj({"file": STR, "axis": {"type": "string", "enum": ["x", "y", "z"]}, "paths": PATHS, "mode": {"type": "string", "enum": ["first", "min", "max", "average", "center", "value"]}, "value": NUM, "write": BOOL}, ["file", "axis", "paths"])},
    {"name": "wb_distribute", "description": "Evenly distribute 3+ independent objects/groups on x/y/z. Dry-run unless write=true.", "inputSchema": _obj({"file": STR, "axis": {"type": "string", "enum": ["x", "y", "z"]}, "paths": {"type": "array", "items": {"type": "string"}, "minItems": 3}, "write": BOOL}, ["file", "axis", "paths"])},
    {"name": "wb_grid", "description": "Create a 3D rectangular array; counts include source. Dry-run unless write=true.", "inputSchema": _obj({"file": STR, "path": STR, "count_x": INT, "count_y": INT, "count_z": INT, "step_x": NUM, "step_y": NUM, "step_z": NUM, "noderef_prefix": STR, "keep_noderefs": BOOL, "write": BOOL}, ["file", "path", "count_x", "count_y", "count_z"])},
    {"name": "wb_scatter", "description": "Deterministically scatter copies inside an offline box. Dry-run unless write=true.", "inputSchema": _obj({"file": STR, "path": STR, "count": INT, "half_x": NUM, "half_y": NUM, "half_z": NUM, "seed": INT, "random_yaw": BOOL, "scale_min": NUM, "scale_max": NUM, "create_scale": BOOL, "noderef_prefix": STR, "keep_noderefs": BOOL, "write": BOOL}, ["file", "path", "count"])},
    {"name": "wb_path_array", "description": "Place reference-safe copies along a polyline or WB marker group. Dry-run unless write=true.", "inputSchema": _obj({"file": STR, "path": STR, "points": {"type":"array","items":{"type":"array","items":NUM,"minItems":2}}, "marker_group": STR, "curve_samples": INT, "spacing": NUM, "count": INT, "closed": BOOL, "orient": BOOL, "yaw_offset": NUM, "noderef_prefix": STR, "keep_noderefs": BOOL, "write": BOOL}, ["file", "path"])},
    {"name": "wb_polygon_scatter", "description": "Deterministically scatter copies inside an XY polygon. Dry-run unless write=true.", "inputSchema": _obj({"file":STR,"path":STR,"points":{"type":"array","items":{"type":"array","items":NUM,"minItems":2},"minItems":3},"count":INT,"seed":INT,"z":NUM,"z_jitter":NUM,"random_yaw":BOOL,"scale_min":NUM,"scale_max":NUM,"create_scale":BOOL,"noderef_prefix":STR,"keep_noderefs":BOOL,"write":BOOL}, ["file","path","points","count"])},
    {"name": "wb_volume_scatter", "description": "Scatter copies inside box/cylinder/sphere volumes. Dry-run unless write=true.", "inputSchema": _obj({"file":STR,"path":STR,"shape":{"type":"string","enum":["box","cylinder","sphere"]},"count":INT,"center_x":NUM,"center_y":NUM,"center_z":NUM,"size_x":NUM,"size_y":NUM,"size_z":NUM,"seed":INT,"random_yaw":BOOL,"noderef_prefix":STR,"keep_noderefs":BOOL,"write":BOOL}, ["file","path","shape","count"])},
    {"name": "wb_asset_pool_spawn", "description": "Spawn a deterministic weighted pool of exact indexed World Builder assets. Dry-run unless write=true.", "inputSchema": _obj({"file":STR,"parent":STR,"catalog":STR,"pool":{"type":"array","items":{"type":"object"},"minItems":1},"count":INT,"seed":INT,"center_x":NUM,"center_y":NUM,"center_z":NUM,"half_x":NUM,"half_y":NUM,"half_z":NUM,"random_yaw":BOOL,"generate_noderef":BOOL,"noderef_prefix":STR,"write":BOOL}, ["file","parent","catalog","pool","count"])},
    {"name": "wb_rng_create", "description": "Create a native World Builder Randomized Nested Group. Dry-run unless write=true.", "inputSchema": _obj({"file":STR,"parent":STR,"name":STR,"seed":INT,"rule":{"type":"string","enum":["per-object","fixed"]},"fixed_mode":{"type":"string","enum":["percentage","total"]},"percentage":NUM,"total":INT,"x":NUM,"y":NUM,"z":NUM,"write":BOOL}, ["file","parent","name"])},
    {"name": "wb_generate_room", "description": "Generate a rectangular room shell from verified indexed assets. Dry-run unless write=true.", "inputSchema": _obj({"file":STR,"parent":STR,"catalog":STR,"wall_asset":STR,"floor_asset":STR,"width":NUM,"depth":NUM,"segment":NUM,"name":STR,"x":NUM,"y":NUM,"z":NUM,"write":BOOL}, ["file","parent","catalog","wall_asset","width","depth","segment"])},
    {"name": "wb_generate_corridor", "description": "Generate a corridor shell from verified indexed assets. Dry-run unless write=true.", "inputSchema": _obj({"file":STR,"parent":STR,"catalog":STR,"wall_asset":STR,"floor_asset":STR,"length":NUM,"width":NUM,"segment":NUM,"name":STR,"x":NUM,"y":NUM,"z":NUM,"write":BOOL}, ["file","parent","catalog","wall_asset","length","width","segment"])},
    {"name": "wb_generate_market", "description": "Generate a market grid from a deterministic weighted asset pool. Dry-run unless write=true.", "inputSchema": _obj({"file":STR,"parent":STR,"catalog":STR,"pool":{"type":"array","items":{"type":"object"},"minItems":1},"rows":INT,"columns":INT,"spacing_x":NUM,"spacing_y":NUM,"seed":INT,"name":STR,"x":NUM,"y":NUM,"z":NUM,"write":BOOL}, ["file","parent","catalog","pool","rows","columns","spacing_x","spacing_y"])},
    {"name": "wb_device_connect", "description": "Connect two saved World Builder device nodes with a unique target NodeRef. Dry-run unless write=true.", "inputSchema": _obj({"file":STR,"source":STR,"target":STR,"device_class_name":STR,"noderef_prefix":STR,"write":BOOL}, ["file","source","target"])},
    {"name": "wb_elevator_wire", "description": "Wire an existing elevator, terminals and floor markers; patch saved instance data when available. Dry-run unless write=true.", "inputSchema": _obj({"file":STR,"elevator":STR,"terminals":{"type":"array","items":STR,"minItems":2},"markers":{"type":"array","items":STR,"minItems":2},"floor_names":{"type":"array","items":STR},"terminal_class_name":STR,"noderef_prefix":STR,"write":BOOL}, ["file","elevator","terminals","markers"])},
    {"name": "wb_compat_scan", "description": "Scan World Builder version/features/module schema and optionally compare a saved build against that exact source/install.", "inputSchema": _obj({"world_builder_root":STR,"project":STR}, ["world_builder_root"])},
    {"name": "wb_prefab_render", "description": "Render ${parameter} placeholders in a JSON WB prefab/build template. Returns rendered JSON unless output is supplied.", "inputSchema": _obj({"template":STR,"parameters":{"type":"object"},"output":STR}, ["template"])},
    {"name": "wb_assets_build", "description": "Build/rebuild a local SQLite/FTS asset catalog from a World Builder installation/source tree.", "inputSchema": _obj({"world_builder_root": STR, "database": STR}, ["world_builder_root"])},
    {"name": "wb_assets_search", "description": "Search a cp77wb asset catalog built from World Builder's real spawnable lists. Use returned #IDs for deterministic spawning.", "inputSchema": _obj({"database": STR, "query": STR, "category": STR, "variant": STR, "module": STR, "extension": STR, "limit": INT}, ["database", "query"])},
    {"name": "wb_assets_info", "description": "Read asset-catalog metadata or one exact asset ID.", "inputSchema": _obj({"database": STR, "id": INT}, ["database"])},
    {"name": "wb_spawn_asset", "description": "Insert one exact/search-resolved indexed asset into a saved-build group. Ambiguous text queries fail. Dry-run unless write=true.", "inputSchema": _obj({"file": STR, "parent": STR, "catalog": STR, "asset": STR, "module": STR, "variant": STR, "name": STR, "x": NUM, "y": NUM, "z": NUM, "roll": NUM, "pitch": NUM, "yaw": NUM, "generate_noderef": BOOL, "noderef_prefix": STR, "write": BOOL}, ["file", "parent", "catalog", "asset"])},
    {"name": "wb_favorites_list", "description": "List World Builder native Favorite categories (reusable object/group prefabs).", "inputSchema": _obj({"world_builder_root": STR}, ["world_builder_root"])},
    {"name": "wb_favorite_add", "description": "Add an object/group to World Builder Favorites as a reusable prefab. Preview-only unless write=true.", "inputSchema": _obj({"file": STR, "path": STR, "world_builder_root": STR, "category": STR, "name": STR, "tags": {"type": "array", "items": STR}, "icon": STR, "category_icon": STR, "write": BOOL}, ["file", "path", "world_builder_root", "category"])},
    {"name": "wb_logs", "description": "Read/tail World Builder, CET and related Cyberpunk mod logs from a game root (or entSpawner directory).", "inputSchema": _obj({"game_root": STR, "tail": INT, "issues_only": BOOL}, ["game_root"])},
    {"name": "wb_live_ping", "description": "Ping the optional cp77wb CET file-RPC companion and report v0.5 spatial/history capabilities.", "inputSchema": _obj({"rpc_dir": STR, "timeout": NUM}, ["rpc_dir"])},
    {"name": "wb_live_state", "description": "Read current World Builder/CET state through the optional live bridge.", "inputSchema": _obj({"rpc_dir": STR, "timeout": NUM}, ["rpc_dir"])},
    {"name": "wb_live_player", "description": "Read the live player transform through the optional CET bridge.", "inputSchema": _obj({"rpc_dir": STR, "timeout": NUM}, ["rpc_dir"])},
    {"name": "wb_live_camera", "description": "Read the live FPP camera transform through the optional CET bridge.", "inputSchema": _obj({"rpc_dir": STR, "timeout": NUM}, ["rpc_dir"])},
    {"name": "wb_live_selection", "description": "Read current World Builder selection through the optional CET bridge.", "inputSchema": _obj({"rpc_dir": STR, "timeout": NUM, "include_data": BOOL}, ["rpc_dir"])},
    {"name": "wb_live_history", "description": "Read World Builder's active undo/redo state and whether history-safe live mutation is available.", "inputSchema": _obj({"rpc_dir": STR, "timeout": NUM}, ["rpc_dir"])},
    {"name": "wb_live_paths", "description": "Search paths/names in the currently loaded World Builder hierarchy.", "inputSchema": _obj({"rpc_dir": STR, "query": STR, "limit": INT, "timeout": NUM}, ["rpc_dir"])},
    {"name": "wb_live_raycast", "description": "Raycast through World Builder's live scene intersection system; camera mode uses the current FPP camera.", "inputSchema": _obj({"rpc_dir": STR, "mode": {"type": "string", "enum": ["camera", "custom"]}, "origin_x": NUM, "origin_y": NUM, "origin_z": NUM, "dir_x": NUM, "dir_y": NUM, "dir_z": NUM, "use_physical": BOOL, "timeout": NUM}, ["rpc_dir"])},
    {"name": "wb_live_select", "description": "Select exact paths in the active World Builder UI. Preview unless apply=true.", "inputSchema": _obj({"rpc_dir": STR, "paths": PATH_LIST, "apply": BOOL, "timeout": NUM}, ["rpc_dir", "paths"])},
    {"name": "wb_live_move", "description": "Move the current World Builder selection as one WB history action. Preview unless apply=true.", "inputSchema": _obj({"rpc_dir": STR, "x": NUM, "y": NUM, "z": NUM, "apply": BOOL, "timeout": NUM}, ["rpc_dir"])},
    {"name": "wb_live_rotate", "description": "Rotate the current World Builder selection as one WB history action; multi-selection rotates around its center. Preview unless apply=true.", "inputSchema": _obj({"rpc_dir": STR, "roll": NUM, "pitch": NUM, "yaw": NUM, "apply": BOOL, "timeout": NUM}, ["rpc_dir"])},
    {"name": "wb_live_scale", "description": "Scale current selection around its selection pivot or explicit pivot as one WB history action. Refuses non-scaleable leaves unless allow_partial=true. Preview unless apply=true.", "inputSchema": _obj({"rpc_dir": STR, "x": NUM, "y": NUM, "z": NUM, "pivot_x": NUM, "pivot_y": NUM, "pivot_z": NUM, "allow_partial": BOOL, "apply": BOOL, "timeout": NUM}, ["rpc_dir"])},
    {"name": "wb_live_snap", "description": "Drop/snap the current selection to the live scene surface along a direction, collapsed into one WB undo action. Preview unless apply=true.", "inputSchema": _obj({"rpc_dir": STR, "dir_x": NUM, "dir_y": NUM, "dir_z": NUM, "apply": BOOL, "timeout": NUM}, ["rpc_dir"])},
    {"name": "wb_live_batch", "description": "Apply move/rotate/scale/snap operations to the current selection as one World Builder undo transaction. Preview unless apply=true.", "inputSchema": _obj({"rpc_dir": STR, "operations": {"type": "array", "minItems": 1, "maxItems": 50, "items": {"type": "object", "additionalProperties": True}}, "apply": BOOL, "timeout": NUM}, ["rpc_dir", "operations"])},
    {"name": "wb_live_duplicate", "description": "Duplicate the current WB selection with optional per-copy offset. v0.5 remaps cloned NodeRefs and known internal references by default. Preview unless apply=true.", "inputSchema": _obj({"rpc_dir": STR, "count": INT, "x": NUM, "y": NUM, "z": NUM, "keep_noderefs": BOOL, "apply": BOOL, "timeout": NUM}, ["rpc_dir"])},
    {"name": "wb_live_surface_scatter", "description": "Create deterministic copies around one selected source and drop each copy onto the live scene surface; one undo removes the whole scatter. Preview unless apply=true.", "inputSchema": _obj({"rpc_dir": STR, "count": INT, "half_x": NUM, "half_y": NUM, "half_z": NUM, "seed": INT, "random_yaw": BOOL, "dir_x": NUM, "dir_y": NUM, "dir_z": NUM, "keep_noderefs": BOOL, "apply": BOOL, "timeout": NUM}, ["rpc_dir", "count"])},
    {"name": "wb_live_delete", "description": "Delete the current World Builder selection through WB history. Preview unless apply=true.", "inputSchema": _obj({"rpc_dir": STR, "apply": BOOL, "timeout": NUM}, ["rpc_dir"])},
    {"name": "wb_live_spawn_asset", "description": "Spawn one exact indexed WB asset directly into the active editor, optionally in front of the camera and dropped to the surface. Preview unless apply=true.", "inputSchema": _obj({"rpc_dir": STR, "catalog": STR, "asset": STR, "module": STR, "variant": STR, "name": STR, "parent": STR, "placement": {"type": "string", "enum": ["serialized", "camera", "player"]}, "distance": NUM, "x": NUM, "y": NUM, "z": NUM, "roll": NUM, "pitch": NUM, "yaw": NUM, "snap_to_surface": BOOL, "apply": BOOL, "timeout": NUM}, ["rpc_dir", "catalog", "asset"])},
    {"name": "wb_live_save", "description": "Save all saveable top-level active World Builder roots through WB's native save() path. Preview unless apply=true.", "inputSchema": _obj({"rpc_dir": STR, "apply": BOOL, "timeout": NUM}, ["rpc_dir"])},
    {"name": "wb_live_reload", "description": "Reload one top-level active WB root from data/objects while preserving an undoable pre-reload state. Preview unless apply=true.", "inputSchema": _obj({"rpc_dir": STR, "path": STR, "apply": BOOL, "timeout": NUM}, ["rpc_dir", "path"])},
    {"name": "wb_live_undo", "description": "Undo one World Builder history action. Preview/history check unless apply=true.", "inputSchema": _obj({"rpc_dir": STR, "apply": BOOL, "timeout": NUM}, ["rpc_dir"])},
    {"name": "wb_live_redo", "description": "Redo one World Builder history action. Preview/history check unless apply=true.", "inputSchema": _obj({"rpc_dir": STR, "apply": BOOL, "timeout": NUM}, ["rpc_dir"])},
    {"name": "wb_semantic_build", "description": "Build deterministic local semantic tags/facets over an existing World Builder asset catalog.", "inputSchema": _obj({"database":STR,"overrides":STR}, ["database"])},
    {"name": "wb_semantic_search", "description": "Search the local asset catalog by semantic role/style/material/condition and depot-path text.", "inputSchema": _obj({"database":STR,"query":STR,"role":STR,"style":STR,"material":STR,"condition":STR,"category":STR,"variant":STR,"limit":INT}, ["database","query"])},
    {"name": "wb_bounds_set", "description": "Attach explicit local XYZ bounds to one indexed asset for collision-aware planning.", "inputSchema": _obj({"database":STR,"id":INT,"x":NUM,"y":NUM,"z":NUM,"source":STR,"confidence":NUM}, ["database","id","x","y","z"])},
    {"name": "wb_bounds_import", "description": "Import explicit asset bounds records into the catalog.", "inputSchema": _obj({"database":STR,"bounds":{"type":"array","items":{"type":"object"}}}, ["database","bounds"])},
    {"name": "wb_bounds_info", "description": "Read explicit/effective asset bounds and heuristic fallback metadata.", "inputSchema": _obj({"database":STR,"id":INT}, ["database"])},
    {"name": "wb_collisions", "description": "Approximate saved-build collision scan using yaw-aware oriented bounds; heuristic results are marked approximate.", "inputSchema": _obj({"file":STR,"catalog":STR,"clearance":NUM,"explicit_only":BOOL}, ["file","catalog"])},
    {"name": "wb_plan_compile", "description": "Compile a declarative cp77wb-plan/1 specification into exact indexed spawn operations without editing a build.", "inputSchema": _obj({"catalog":STR,"plan":{"type":"object","additionalProperties":True}}, ["catalog","plan"])},
    {"name": "wb_plan_preview", "description": "Compile a construction plan, apply it to a clone, validate it and report approximate collisions with the existing build.", "inputSchema": _obj({"file":STR,"catalog":STR,"plan":{"type":"object","additionalProperties":True}}, ["file","catalog","plan"])},
    {"name": "wb_plan_apply", "description": "Apply a declarative construction plan to a saved build. Dry-run unless write=true.", "inputSchema": _obj({"file":STR,"catalog":STR,"plan":{"type":"object","additionalProperties":True},"write":BOOL}, ["file","catalog","plan"])},
    {"name": "wb_generate_fence", "description": "Generate repeated verified fence segments and optional posts along a path. Dry-run unless write=true.", "inputSchema": _obj({"file":STR,"parent":STR,"catalog":STR,"segment_asset":STR,"post_asset":STR,"points":{"type":"array","items":{"type":"array","items":NUM,"minItems":2},"minItems":2},"spacing":NUM,"name":STR,"yaw_offset":NUM,"write":BOOL}, ["file","parent","catalog","segment_asset","points","spacing"])},
    {"name": "wb_generate_road", "description": "Generate repeated road tiles and optional edge assets along a path. Dry-run unless write=true.", "inputSchema": _obj({"file":STR,"parent":STR,"catalog":STR,"tile_asset":STR,"edge_asset":STR,"points":{"type":"array","items":{"type":"array","items":NUM,"minItems":2},"minItems":2},"spacing":NUM,"width":NUM,"name":STR,"yaw_offset":NUM,"write":BOOL}, ["file","parent","catalog","tile_asset","points","spacing","width"])},
    {"name": "wb_generate_cable", "description": "Generate a repeated cable/pipe segment chain along a path without guessing mesh stretching. Dry-run unless write=true.", "inputSchema": _obj({"file":STR,"parent":STR,"catalog":STR,"segment_asset":STR,"points":{"type":"array","items":{"type":"array","items":NUM,"minItems":2},"minItems":2},"spacing":NUM,"name":STR,"yaw_offset":NUM,"write":BOOL}, ["file","parent","catalog","segment_asset","points","spacing"])},
    {"name":"wb_export_inspect","description":"Validate/summarize a World Builder *_exported.json before conversion.","inputSchema":_obj({"export_file":STR,"importer_version":STR},["export_file"])},
    {"name":"wb_export_xl","description":"Generate the ArchiveXL structure implied by a World Builder export without writing files.","inputSchema":_obj({"export_file":STR},["export_file"])},
    {"name":"wb_build_prepare","description":"Preview or create a WolvenKit workspace around a WB export. write=false by default.","inputSchema":_obj({"export_file":STR,"workspace":STR,"world_builder_root":STR,"project_name":STR,"author":STR,"project_version":STR,"description":STR,"scaffold_tweak":BOOL,"write":BOOL},["export_file","workspace"])},
    {"name":"wb_build_status","description":"Check expected streamingblock/sector/device outputs after WolvenKit Object Spawner import.","inputSchema":_obj({"workspace":STR},["workspace"])},
    {"name":"wb_build_native_import","description":"Preview or run the template-bundle + WolvenKit JSON-deserialize import directly into a prepared workspace. run=false by default.","inputSchema":_obj({"workspace":STR,"bundle":STR,"cli":STR,"run":BOOL,"keep_json":BOOL,"timeout":INT},["workspace","bundle"])},
    {"name":"wb_build_backends","description":"Detect WolvenKit CLI/importer availability and report the Linux-native conversion boundary.","inputSchema":_obj({"cli":STR,"world_builder_root":STR})},
    {"name":"wb_build_pack","description":"Preview or run WolvenKit CLI/cp77tools pack after verified Object Spawner import. run=false by default.","inputSchema":_obj({"workspace":STR,"cli":STR,"output":STR,"run":BOOL,"timeout":INT},["workspace"])},
    {"name":"wb_build_package","description":"Preview or assemble a game-layout distribution folder/ZIP from a built archive. write=false by default.","inputSchema":_obj({"workspace":STR,"archive":STR,"output":STR,"zip":STR,"write":BOOL},["workspace","archive","output"])},
    {"name":"wb_build_verify","description":"Verify a prepared game-layout package and optional conflicts with an installed game.","inputSchema":_obj({"layout":STR,"game_root":STR},["layout"])},
    {"name":"wb_build_deploy","description":"Preview or deploy a game-layout folder into Cyberpunk. apply=false by default; overwrite required for conflicting existing files.","inputSchema":_obj({"layout":STR,"game_root":STR,"apply":BOOL,"overwrite":BOOL},["layout","game_root"])},
    {"name":"wb_build_doctor","description":"Verify package structure/conflicts and summarize issue-like World Builder/CET/framework log lines.","inputSchema":_obj({"layout":STR,"game_root":STR,"tail":INT},["layout"])},
    {"name":"wb_native_template_plan","description":"Plan or write a WolvenKit template-capture wscript for exactly the RED types used by an export. write=false by default.","inputSchema":_obj({"export_file":STR,"output":STR,"resource_name":STR,"write":BOOL},["export_file","output"])},
    {"name":"wb_native_template_verify","description":"Verify a captured cp77wb RED type template bundle covers every type required by a World Builder export.","inputSchema":_obj({"export_file":STR,"bundle":STR},["export_file","bundle"])},
    {"name":"wb_native_json","description":"Generate WolvenKit JSON intermediates mirroring the WB importer from a captured template bundle. write=false by default.","inputSchema":_obj({"export_file":STR,"bundle":STR,"output":STR,"write":BOOL},["export_file","bundle","output"])},
    {"name":"wb_native_preflight","description":"Probe WolvenKit CLI/cp77tools for the convert deserialize JSON-to-CR2W capability.","inputSchema":_obj({"cli":STR,"timeout":INT})},
    {"name":"wb_native_convert","description":"Preview or execute conversion of prepared WolvenKit JSON intermediates to CR2W using a verified CLI. run=false by default.","inputSchema":_obj({"native_json":STR,"output":STR,"cli":STR,"run":BOOL,"timeout":INT},["native_json","output"])},
    {"name":"wb_native_import","description":"Prepare/import a WB export through template-bundle + WKit JSON deserialize backend. run=false by default.","inputSchema":_obj({"export_file":STR,"bundle":STR,"output":STR,"cli":STR,"run":BOOL,"keep_json":BOOL,"timeout":INT},["export_file","bundle","output"])},
    {"name":"wb_native_verify","description":"Verify converted sector/block/device files exist and carry CR2W magic.","inputSchema":_obj({"output":STR,"targets":{"type":"array","items":STR},"strict_magic":BOOL},["output"])},
    {"name":"wb_worker_build","description":"Preview or build the bundled .NET 10 WolvenKit worker. run=false by default; optional log_file captures full dotnet publish output.","inputSchema":_obj({"source":STR,"output":STR,"dotnet":STR,"run":BOOL,"timeout":INT,"log_file":STR})},
    {"name":"wb_worker_preflight","description":"Run the worker self-test; authoritative native is true only when RED default serialization and JSON-to-CR2W both pass.","inputSchema":_obj({"worker":STR,"timeout":INT})},
    {"name":"wb_worker_inspect","description":"Inspect discovered WolvenKit assemblies, serializer/writer API signatures and API profile without requiring the round-trip self-test to pass.","inputSchema":_obj({"worker":STR,"timeout":INT})},
    {"name":"wb_worker_doctor","description":"Collect .NET/worker diagnostics and optionally write a support ZIP for deferred compatibility testing.","inputSchema":_obj({"worker":STR,"dotnet":STR,"output":STR,"timeout":INT})},
    {"name":"wb_worker_bundle","description":"Preview or create exact RED default templates directly through the verified .NET worker. run=false by default.","inputSchema":_obj({"export_file":STR,"output":STR,"worker":STR,"run":BOOL,"timeout":INT},["export_file","output"])},
    {"name":"wb_worker_import","description":"Preview or import a WB export directly through the verified .NET WolvenKit worker, without WScript template capture. run=false by default.","inputSchema":_obj({"export_file":STR,"output":STR,"worker":STR,"run":BOOL,"keep_json":BOOL,"timeout":INT},["export_file","output"])},
    {"name":"wb_build_worker_import","description":"Preview or populate a prepared workspace/source/archive through the verified .NET WolvenKit worker. run=false by default.","inputSchema":_obj({"workspace":STR,"worker":STR,"run":BOOL,"keep_json":BOOL,"timeout":INT},["workspace"])},

]


def _pivot(a: dict[str, Any]) -> tuple[float, float, float] | None:
    pivot_x = a.get("pivot_x")
    pivot_y = a.get("pivot_y")
    pivot_z = a.get("pivot_z")
    if pivot_x is None and pivot_y is None and pivot_z is None:
        return None
    if pivot_x is None or pivot_y is None or pivot_z is None:
        raise ValueError("pivot_x, pivot_y and pivot_z must be supplied together")
    return float(pivot_x), float(pivot_y), float(pivot_z)


def _mutation(file: str, write: bool, operation: Callable[[WorldBuilderProject], Any]) -> dict[str, Any]:
    project = WorldBuilderProject.load(file)
    before = project.clone()
    result = operation(project)
    issues = [issue.to_dict() for issue in validate(project)]
    diff = json_diff(before.data, project.data, str(project.source), f"{project.source} (proposed)")
    backup = None
    if write:
        backup_path = project.save(backup=True)
        backup = str(backup_path) if backup_path else None
    return {
        "written": bool(write),
        "backup": backup,
        "result": result,
        "validation": issues,
        "diff": diff,
    }


def call_tool(name: str, a: dict[str, Any]) -> Any:
    if name == "wb_tree":
        p = WorldBuilderProject.load(a["file"])
        return {"root": p.root_path, "tree": p.tree_lines(bool(a.get("show_modules", False)))}
    if name == "wb_get":
        p = WorldBuilderProject.load(a["file"])
        if a.get("path"):
            e = p.get(a["path"])
            return {"path": e.path, "kind": node_kind(e.node), "data": e.node}
        return p.stats()
    if name == "wb_find":
        p = WorldBuilderProject.load(a["file"])
        return [{"path": e.path, "kind": node_kind(e.node), "name": e.node.get("name")} for e in p.find(a["query"], case_sensitive=bool(a.get("case_sensitive", False)))]
    if name == "wb_validate":
        return [i.to_dict() for i in validate(WorldBuilderProject.load(a["file"]))]
    if name == "wb_refs":
        p = WorldBuilderProject.load(a["file"])
        refs = []
        for e in p.iter_nodes():
            spawn = e.node.get("spawnable")
            if isinstance(spawn, dict):
                refs.extend({"source": e.path, "field": r.field, "kind": r.kind, "value": r.value} for r in iter_known_references(spawn))
        return {"definitions": p.node_refs(), "references": refs}
    if name == "wb_export_inspect":
        return inspect_export(a["export_file"], importer_version=str(a.get("importer_version","1.0.4")))
    if name == "wb_export_xl":
        return archive_xl_config(_read_json(a["export_file"]))
    if name == "wb_build_prepare":
        if not bool(a.get("write",False)):
            rep=inspect_export(a["export_file"])
            name0=a.get("project_name") or rep.get("name")
            return {"written":False,"export":rep,"workspace":str(Path(a["workspace"])/str(name0)),"requiresWrite":True}
        return {"written":True,"result":prepare_build_workspace(a["export_file"],a["workspace"],world_builder_root=a.get("world_builder_root"),project_name=a.get("project_name"),author=str(a.get("author","")),version=str(a.get("project_version","1.0.0")),description=str(a.get("description","World Builder project prepared by cp77wb")),scaffold_tweak=bool(a.get("scaffold_tweak",False)))}
    if name == "wb_build_status":
        return build_status(a["workspace"])
    if name == "wb_build_native_import":
        return build_native_import(a["workspace"],a["bundle"],cli=a.get("cli"),run=bool(a.get("run",False)),keep_json=bool(a.get("keep_json",True)),timeout=int(a.get("timeout",300)))
    if name == "wb_build_backends":
        return backend_scan(cli=a.get("cli"),world_builder_root=a.get("world_builder_root"))
    if name == "wb_build_pack":
        return build_pack(a["workspace"],cli=a.get("cli"),output=a.get("output"),run=bool(a.get("run",False)),timeout=int(a.get("timeout",300)))
    if name == "wb_build_package":
        if not bool(a.get("write",False)):
            return {"written":False,"workspace":a["workspace"],"archive":a["archive"],"output":a["output"],"zip":a.get("zip"),"requiresWrite":True}
        return {"written":True,"result":build_package(a["workspace"],archive=a["archive"],output=a["output"],zip_output=a.get("zip"))}
    if name == "wb_build_verify":
        return verify_package(a["layout"],game_root=a.get("game_root"))
    if name == "wb_build_deploy":
        return deploy_layout(a["layout"],a["game_root"],apply=bool(a.get("apply",False)),overwrite=bool(a.get("overwrite",False)))
    if name == "wb_build_doctor":
        return build_doctor(a["layout"],game_root=a.get("game_root"),tail=int(a.get("tail",200)))
    if name == "wb_native_template_plan":
        required = required_template_types(a["export_file"])
        if not bool(a.get("write",False)):
            return {"written":False,"output":a["output"],"resource":a.get("resource_name"),"requiredTypes":required,"count":len(required)}
        return {"written":True,"result":make_template_capture_script(a["export_file"],a["output"],resource_name=a.get("resource_name"))}
    if name == "wb_native_template_verify":
        return verify_template_bundle(a["export_file"],a["bundle"])
    if name == "wb_native_json":
        coverage=verify_template_bundle(a["export_file"],a["bundle"])
        if not bool(a.get("write",False)):
            return {"written":False,"output":a["output"],"coverage":coverage,"requiresWrite":True}
        return {"written":True,"result":prepare_native_json(a["export_file"],a["bundle"],a["output"])}
    if name == "wb_native_preflight":
        return native_preflight(cli=a.get("cli"),timeout=int(a.get("timeout",30)))
    if name == "wb_native_convert":
        return native_convert(a["native_json"],a["output"],cli=a.get("cli"),run=bool(a.get("run",False)),timeout=int(a.get("timeout",300)))
    if name == "wb_native_import":
        return native_import(a["export_file"],a["bundle"],a["output"],cli=a.get("cli"),run=bool(a.get("run",False)),keep_json=bool(a.get("keep_json",True)),timeout=int(a.get("timeout",300)))
    if name == "wb_native_verify":
        return verify_native_outputs(a["output"],list(a.get("targets",[])) or None,strict_magic=bool(a.get("strict_magic",True)))
    if name == "wb_worker_build":
        return build_worker(source=a.get("source"),output=a.get("output"),dotnet=a.get("dotnet"),run=bool(a.get("run",False)),timeout=int(a.get("timeout",600)),log_file=a.get("log_file"))
    if name == "wb_worker_preflight":
        return worker_preflight(worker=a.get("worker"),timeout=int(a.get("timeout",30)))
    if name == "wb_worker_inspect":
        return worker_inspect(worker=a.get("worker"),timeout=int(a.get("timeout",30)))
    if name == "wb_worker_doctor":
        return worker_doctor(worker=a.get("worker"),dotnet=a.get("dotnet"),output=a.get("output"),timeout=int(a.get("timeout",30)))
    if name == "wb_worker_bundle":
        return worker_create_bundle(a["export_file"],a["output"],worker=a.get("worker"),run=bool(a.get("run",False)),timeout=int(a.get("timeout",120)))
    if name == "wb_worker_import":
        return worker_import(a["export_file"],a["output"],worker=a.get("worker"),run=bool(a.get("run",False)),keep_json=bool(a.get("keep_json",True)),timeout=int(a.get("timeout",300)))
    if name == "wb_build_worker_import":
        return build_worker_import(a["workspace"],worker=a.get("worker"),run=bool(a.get("run",False)),keep_json=bool(a.get("keep_json",True)),timeout=int(a.get("timeout",300)))
    if name == "wb_compat_scan":
        return scan_worldbuilder(a["world_builder_root"], a.get("project"))
    if name == "wb_prefab_render":
        return render_template_file(a["template"], dict(a.get("parameters", {})), a.get("output"))
    if name == "wb_assets_build":
        return build_catalog(a["world_builder_root"], a.get("database"))
    if name == "wb_assets_search":
        return [r.to_dict() for r in search_catalog(a["database"], a["query"], category=a.get("category"), variant=a.get("variant"), module_path=a.get("module"), extension=a.get("extension"), limit=int(a.get("limit", 25)))]
    if name == "wb_assets_info":
        return get_asset(a["database"], int(a["id"])).to_dict() if a.get("id") is not None else catalog_info(a["database"])
    if name == "wb_semantic_build":
        return build_semantic_index(a["database"], a.get("overrides"))
    if name == "wb_semantic_search":
        return semantic_search(a["database"], a["query"], role=a.get("role"), style=a.get("style"), material=a.get("material"), condition=a.get("condition"), category=a.get("category"), variant=a.get("variant"), limit=int(a.get("limit",25)))
    if name == "wb_bounds_set":
        return set_asset_bounds(a["database"], int(a["id"]), (float(a["x"]),float(a["y"]),float(a["z"])), source=str(a.get("source","user")), confidence=float(a.get("confidence",1.0)))
    if name == "wb_bounds_import":
        return import_bounds(a["database"], list(a.get("bounds",[])))
    if name == "wb_bounds_info":
        return bounds_info(a["database"], int(a["id"]) if a.get("id") is not None else None)
    if name == "wb_plan_compile":
        return compile_plan(dict(a["plan"]), a["catalog"])
    if name == "wb_plan_preview":
        return preview_plan(WorldBuilderProject.load(a["file"]), dict(a["plan"]), a["catalog"])
    if name == "wb_collisions":
        return scan_project_collisions(WorldBuilderProject.load(a["file"]), a["catalog"], clearance=float(a.get("clearance",0)), include_heuristic=not bool(a.get("explicit_only",False)))
    if name == "wb_favorites_list":
        return list_categories(a["world_builder_root"])
    if name == "wb_logs":
        return read_logs(a["game_root"], tail=int(a.get("tail", 200)), issues_only=bool(a.get("issues_only", False)))
    if name.startswith("wb_live_"):
        client = LiveBridgeClient(a["rpc_dir"])
        timeout = float(a.get("timeout", 3.0))
        if name == "wb_live_ping":
            return client.ping(timeout=timeout)
        if name == "wb_live_state":
            return client.state(timeout=timeout)
        if name == "wb_live_player":
            return client.player(timeout=timeout)
        if name == "wb_live_camera":
            return client.camera(timeout=timeout)
        if name == "wb_live_selection":
            return client.selection(timeout=timeout, include_data=bool(a.get("include_data", False)))
        if name == "wb_live_history":
            return client.history(timeout=timeout)
        if name == "wb_live_paths":
            return client.paths(str(a.get("query", "")), timeout=timeout, limit=int(a.get("limit", 100)))
        if name == "wb_live_raycast":
            mode = str(a.get("mode", "camera"))
            origin = None
            direction = None
            if mode == "custom":
                origin_x = a.get("origin_x")
                origin_y = a.get("origin_y")
                origin_z = a.get("origin_z")
                if origin_x is None or origin_y is None or origin_z is None:
                    raise ValueError("custom live raycast requires origin_x/origin_y/origin_z")
                origin = (float(origin_x), float(origin_y), float(origin_z))
                direction = (float(a.get("dir_x", 0)), float(a.get("dir_y", 0)), float(a.get("dir_z", -1)))
            return client.raycast(mode=mode, origin=origin, direction=direction, use_physical=bool(a.get("use_physical", True)), timeout=timeout)
        apply = bool(a.get("apply", False))
        if name == "wb_live_select":
            return client.select_paths(list(a["paths"]), apply=apply, timeout=timeout)
        if name == "wb_live_move":
            return client.move_selection(float(a.get("x", 0)), float(a.get("y", 0)), float(a.get("z", 0)), apply=apply, timeout=timeout)
        if name == "wb_live_rotate":
            return client.rotate_selection(float(a.get("roll", 0)), float(a.get("pitch", 0)), float(a.get("yaw", 0)), apply=apply, timeout=timeout)
        if name == "wb_live_scale":
            pivot_x = a.get("pivot_x")
            pivot_y = a.get("pivot_y")
            pivot_z = a.get("pivot_z")
            pivot = None
            if pivot_x is not None or pivot_y is not None or pivot_z is not None:
                if pivot_x is None or pivot_y is None or pivot_z is None:
                    raise ValueError("pivot_x, pivot_y and pivot_z must be supplied together")
                pivot = (float(pivot_x), float(pivot_y), float(pivot_z))
            return client.scale_selection(float(a.get("x", 1)), float(a.get("y", 1)), float(a.get("z", 1)), pivot=pivot, allow_partial=bool(a.get("allow_partial", False)), apply=apply, timeout=max(timeout, 8.0))
        if name == "wb_live_snap":
            return client.snap_selection(direction=(float(a.get("dir_x", 0)), float(a.get("dir_y", 0)), float(a.get("dir_z", -1))), apply=apply, timeout=max(timeout, 8.0))
        if name == "wb_live_batch":
            return client.batch_transform(list(a["operations"]), apply=apply, timeout=max(timeout, 15.0))
        if name == "wb_live_duplicate":
            return client.duplicate_selection(count=int(a.get("count", 1)), x=float(a.get("x", 0)), y=float(a.get("y", 0)), z=float(a.get("z", 0)), keep_noderefs=bool(a.get("keep_noderefs", False)), apply=apply, timeout=max(timeout, 5.0))
        if name == "wb_live_surface_scatter":
            return client.surface_scatter(
                count=int(a["count"]), half_x=float(a.get("half_x", 5)), half_y=float(a.get("half_y", 5)), half_z=float(a.get("half_z", 0)),
                seed=int(a.get("seed", 1)), random_yaw=bool(a.get("random_yaw", True)),
                direction=(float(a.get("dir_x", 0)), float(a.get("dir_y", 0)), float(a.get("dir_z", -1))),
                keep_noderefs=bool(a.get("keep_noderefs", False)), apply=apply, timeout=max(timeout, 20.0),
            )
        if name == "wb_live_delete":
            return client.delete_selection(apply=apply, timeout=timeout)
        if name == "wb_live_save":
            return client.save_roots(apply=apply, timeout=max(timeout, 5.0))
        if name == "wb_live_reload":
            return client.reload_root(a["path"], apply=apply, timeout=max(timeout, 8.0))
        if name == "wb_live_undo":
            return client.undo(apply=apply, timeout=timeout)
        if name == "wb_live_redo":
            return client.redo(apply=apply, timeout=timeout)
        if name == "wb_live_spawn_asset":
            asset = resolve_asset(a["catalog"], a["asset"], module_path=a.get("module"), variant=a.get("variant"))
            node = build_spawnable_node(
                module_path=asset.module_path, data_type=asset.data_type, spawn_data=asset.spawn_data,
                template=asset.template, name=a.get("name"),
                position=(float(a.get("x", 0)), float(a.get("y", 0)), float(a.get("z", 0))),
                rotation=(float(a.get("roll", 0)), float(a.get("pitch", 0)), float(a.get("yaw", 0))),
            )
            result = client.spawn_serialized(
                node, parent_path=a.get("parent"), placement=str(a.get("placement", "camera")),
                distance=float(a.get("distance", 4.0)), snap_to_surface=bool(a.get("snap_to_surface", False)),
                apply=apply, timeout=max(timeout, 8.0)
            )
            result.setdefault("asset", asset.to_dict())
            return result
        raise ValueError(f"Unknown live tool {name!r}")

    write = bool(a.get("write", False))
    file = a["file"]
    if name == "wb_move":
        return _mutation(file, write, lambda p: p.translate(a["path"], float(a.get("x", 0)), float(a.get("y", 0)), float(a.get("z", 0))))
    if name == "wb_rotate":
        return _mutation(file, write, lambda p: p.rotate(a["path"], float(a.get("roll", 0)), float(a.get("pitch", 0)), float(a.get("yaw", 0)), pivot=_pivot(a)))
    if name == "wb_scale":
        if a.get("uniform") is not None:
            sx = sy = sz = float(a["uniform"])
        else:
            sx, sy, sz = float(a.get("x", 1)), float(a.get("y", 1)), float(a.get("z", 1))
        return _mutation(file, write, lambda p: p.scale(a["path"], sx, sy, sz, create_scale=bool(a.get("create_scale", False))))
    if name == "wb_generate_noderef":
        return _mutation(file, write, lambda p: p.generate_node_ref(a["path"], prefix=str(a.get("prefix", "")), force=bool(a.get("force", False))))
    if name == "wb_duplicate":
        return _mutation(file, write, lambda p: p.duplicate(a["path"], count=int(a.get("count", 1)), offset=(float(a.get("x", 0)), float(a.get("y", 0)), float(a.get("z", 0))), node_ref_prefix=str(a.get("noderef_prefix", "")), keep_node_refs=bool(a.get("keep_noderefs", False))))
    if name == "wb_array":
        return _mutation(file, write, lambda p: p.linear_array(a["path"], count=int(a["count"]), step=(float(a.get("x", 0)), float(a.get("y", 0)), float(a.get("z", 0))), node_ref_prefix=str(a.get("noderef_prefix", "")), keep_node_refs=bool(a.get("keep_noderefs", False))))
    if name == "wb_radial_array":
        return _mutation(file, write, lambda p: p.radial_array(a["path"], count=int(a["count"]), angle=float(a.get("angle", 360)), pivot=_pivot(a), rotate_items=bool(a.get("rotate_items", True)), node_ref_prefix=str(a.get("noderef_prefix", "")), keep_node_refs=bool(a.get("keep_noderefs", False))))
    if name == "wb_align":
        return _mutation(file, write, lambda p: p.align(list(a["paths"]), axis=a["axis"], mode=str(a.get("mode", "first")), value=float(a["value"]) if a.get("value") is not None else None))
    if name == "wb_distribute":
        return _mutation(file, write, lambda p: p.distribute(list(a["paths"]), axis=a["axis"]))
    if name == "wb_grid":
        return _mutation(file, write, lambda p: p.grid_array(a["path"], counts=(int(a["count_x"]), int(a["count_y"]), int(a["count_z"])), step=(float(a.get("step_x", 0)), float(a.get("step_y", 0)), float(a.get("step_z", 0))), node_ref_prefix=str(a.get("noderef_prefix", "")), keep_node_refs=bool(a.get("keep_noderefs", False))))
    if name == "wb_scatter":
        return _mutation(file, write, lambda p: p.scatter(a["path"], count=int(a["count"]), half_extents=(float(a.get("half_x", 5)), float(a.get("half_y", 5)), float(a.get("half_z", 0))), seed=int(a.get("seed", 1)), random_yaw=bool(a.get("random_yaw", True)), scale_min=float(a["scale_min"]) if a.get("scale_min") is not None else None, scale_max=float(a["scale_max"]) if a.get("scale_max") is not None else None, create_scale=bool(a.get("create_scale", False)), node_ref_prefix=str(a.get("noderef_prefix", "")), keep_node_refs=bool(a.get("keep_noderefs", False))))
    if name == "wb_path_array":
        def op(p):
            points = marker_group_points(p, a["marker_group"], curve_samples=int(a.get("curve_samples",12))) if a.get("marker_group") else load_points(list(a.get("points", [])))
            return place_along_path(p, a["path"], points, spacing=float(a["spacing"]) if a.get("spacing") is not None else None, count=int(a["count"]) if a.get("count") is not None else None, closed=bool(a.get("closed", False)), orient_to_path=bool(a.get("orient", True)), yaw_offset=float(a.get("yaw_offset",0)), node_ref_prefix=str(a.get("noderef_prefix","")), keep_node_refs=bool(a.get("keep_noderefs",False)))
        return _mutation(file, write, op)
    if name == "wb_polygon_scatter":
        return _mutation(file, write, lambda p: polygon_scatter(p, a["path"], load_points(list(a["points"])), count=int(a["count"]), seed=int(a.get("seed",1)), z=float(a["z"]) if a.get("z") is not None else None, z_jitter=float(a.get("z_jitter",0)), random_yaw=bool(a.get("random_yaw",True)), scale_min=float(a["scale_min"]) if a.get("scale_min") is not None else None, scale_max=float(a["scale_max"]) if a.get("scale_max") is not None else None, create_scale=bool(a.get("create_scale",False)), node_ref_prefix=str(a.get("noderef_prefix","")), keep_node_refs=bool(a.get("keep_noderefs",False))))
    if name == "wb_volume_scatter":
        return _mutation(file, write, lambda p: volume_scatter(p, a["path"], shape=a["shape"], count=int(a["count"]), center=(float(a.get("center_x",0)),float(a.get("center_y",0)),float(a.get("center_z",0))), size=(float(a.get("size_x",5)),float(a.get("size_y",5)),float(a.get("size_z",5))), seed=int(a.get("seed",1)), random_yaw=bool(a.get("random_yaw",True)), node_ref_prefix=str(a.get("noderef_prefix","")), keep_node_refs=bool(a.get("keep_noderefs",False))))
    if name == "wb_asset_pool_spawn":
        return _mutation(file, write, lambda p: spawn_weighted_pool(p, a["parent"], catalog=a["catalog"], pool=load_asset_pool(list(a["pool"])), count=int(a["count"]), seed=int(a.get("seed",1)), center=(float(a.get("center_x",0)),float(a.get("center_y",0)),float(a.get("center_z",0))), half_extents=(float(a.get("half_x",5)),float(a.get("half_y",5)),float(a.get("half_z",0))), random_yaw=bool(a.get("random_yaw",True)), generate_node_ref=bool(a.get("generate_noderef",False)), node_ref_prefix=str(a.get("noderef_prefix",""))))
    if name == "wb_rng_create":
        return _mutation(file, write, lambda p: p.add_group(a["parent"], name=a["name"], position=(float(a.get("x",0)),float(a.get("y",0)),float(a.get("z",0))), module_path="modules/classes/editor/randomizedGroup", seed=int(a.get("seed",1)), randomization_rule=1 if a.get("rule") == "fixed" else 0, fixed_amount_rule=1 if a.get("fixed_mode") == "total" else 0, fixed_amount_percentage=float(a.get("percentage",50))/100.0, fixed_amount_total=int(a.get("total",1))))
    if name == "wb_generate_room":
        return _mutation(file, write, lambda p: generate_room(p, a["parent"], catalog=a["catalog"], wall_asset=a["wall_asset"], floor_asset=a.get("floor_asset"), width=float(a["width"]), depth=float(a["depth"]), segment=float(a["segment"]), origin=(float(a.get("x",0)),float(a.get("y",0)),float(a.get("z",0))), name=str(a.get("name","Generated Room"))))
    if name == "wb_generate_corridor":
        return _mutation(file, write, lambda p: generate_corridor(p, a["parent"], catalog=a["catalog"], wall_asset=a["wall_asset"], floor_asset=a.get("floor_asset"), length=float(a["length"]), width=float(a["width"]), segment=float(a["segment"]), origin=(float(a.get("x",0)),float(a.get("y",0)),float(a.get("z",0))), name=str(a.get("name","Generated Corridor"))))
    if name == "wb_generate_market":
        return _mutation(file, write, lambda p: generate_market(p, a["parent"], catalog=a["catalog"], pool=load_asset_pool(list(a["pool"])), rows=int(a["rows"]), columns=int(a["columns"]), spacing_x=float(a["spacing_x"]), spacing_y=float(a["spacing_y"]), origin=(float(a.get("x",0)),float(a.get("y",0)),float(a.get("z",0))), seed=int(a.get("seed",1)), name=str(a.get("name","Generated Market"))))
    if name == "wb_device_connect":
        return _mutation(file, write, lambda p: connect_device(p, a["source"], a["target"], device_class_name=a.get("device_class_name"), node_ref_prefix=str(a.get("noderef_prefix",""))))
    if name == "wb_elevator_wire":
        return _mutation(file, write, lambda p: wire_elevator(p, a["elevator"], list(a["terminals"]), list(a["markers"]), floor_names=list(a.get("floor_names",[])) or None, terminal_class_name=str(a.get("terminal_class_name","ElevatorFloorTerminalControllerPS")), node_ref_prefix=str(a.get("noderef_prefix",""))))
    if name == "wb_plan_apply":
        compiled=compile_plan(dict(a["plan"]),a["catalog"])
        return _mutation(file,write,lambda p: apply_compiled_plan(p,compiled,a["catalog"]))
    if name == "wb_generate_fence":
        return _mutation(file,write,lambda p: generate_fence(p,a["parent"],catalog=a["catalog"],segment_asset=a["segment_asset"],post_asset=a.get("post_asset"),points=load_points(list(a["points"])),spacing=float(a["spacing"]),name=str(a.get("name","Generated Fence")),yaw_offset=float(a.get("yaw_offset",0))))
    if name == "wb_generate_road":
        return _mutation(file,write,lambda p: generate_road(p,a["parent"],catalog=a["catalog"],tile_asset=a["tile_asset"],edge_asset=a.get("edge_asset"),points=load_points(list(a["points"])),spacing=float(a["spacing"]),width=float(a["width"]),name=str(a.get("name","Generated Road")),yaw_offset=float(a.get("yaw_offset",0))))
    if name == "wb_generate_cable":
        return _mutation(file,write,lambda p: generate_cable_chain(p,a["parent"],catalog=a["catalog"],segment_asset=a["segment_asset"],points=load_points(list(a["points"])),spacing=float(a["spacing"]),name=str(a.get("name","Generated Cable")),yaw_offset=float(a.get("yaw_offset",0))))
    if name == "wb_spawn_asset":
        asset = resolve_asset(a["catalog"], a["asset"], module_path=a.get("module"), variant=a.get("variant"))
        return _mutation(file, write, lambda p: p.add_spawnable(a["parent"], module_path=asset.module_path, data_type=asset.data_type, spawn_data=asset.spawn_data, template=asset.template, name=a.get("name"), position=(float(a.get("x", 0)), float(a.get("y", 0)), float(a.get("z", 0))), rotation=(float(a.get("roll", 0)), float(a.get("pitch", 0)), float(a.get("yaw", 0))), generate_node_ref=bool(a.get("generate_noderef", False)), node_ref_prefix=str(a.get("noderef_prefix", ""))))
    if name == "wb_favorite_add":
        if not write:
            p = WorldBuilderProject.load(file)
            entry = p.get(a["path"])
            return {"written": False, "preview": {"sourcePath": entry.path, "favorite": a.get("name") or entry.node.get("name"), "category": a["category"], "tags": list(a.get("tags", [])), "worldBuilderRoot": a["world_builder_root"]}}
        return {"written": True, "result": add_favorite(file, a["path"], a["world_builder_root"], category=a["category"], name=a.get("name"), tags=list(a.get("tags", [])), icon=str(a.get("icon", "")), category_icon=str(a.get("category_icon", "")), backup=True)}
    raise ValueError(f"Unknown tool {name!r}")


def _modern_meta() -> dict[str, Any]:
    return {"io.modelcontextprotocol/serverInfo": SERVER_INFO}


def _ok(msg_id: Any, result: Any, *, modern: bool = False) -> dict[str, Any]:
    if modern and isinstance(result, dict):
        result = dict(result)
        # MCP 2026-07-28 requires every successful result to declare
        # whether the response is complete or part of a stream. cp77wb
        # currently returns complete, non-streaming results only.
        result.setdefault("resultType", "complete")
        meta = dict(result.get("_meta", {}))
        meta.update(_modern_meta())
        result["_meta"] = meta
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _err(msg_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": msg_id, "error": error}


def handle_message(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    msg_id = message.get("id")
    params = message.get("params") or {}
    meta = params.get("_meta", {}) if isinstance(params, dict) else {}
    modern = meta.get("io.modelcontextprotocol/protocolVersion") == MODERN_PROTOCOL

    # Notifications intentionally have no response.
    if msg_id is None and isinstance(method, str) and method.startswith("notifications/"):
        return None

    try:
        if method == "server/discover":
            return _ok(msg_id, {
                "supportedVersions": [MODERN_PROTOCOL, LEGACY_PROTOCOL],
                "capabilities": {"tools": {"listChanged": False}},
                "instructions": "cp77wb saved-build tools are dry-run by default (write=true to persist); live mutation tools are previews by default (apply=true to execute after reviewing selection/plan).",
                "ttlMs": 60000,
                "cacheScope": "private",
            }, modern=True)
        if method == "initialize":
            requested = str(params.get("protocolVersion", LEGACY_PROTOCOL))
            negotiated = requested if requested in {"2024-11-05", "2025-03-26", "2025-06-18", LEGACY_PROTOCOL} else LEGACY_PROTOCOL
            return _ok(msg_id, {
                "protocolVersion": negotiated,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
                "instructions": "cp77wb saved-build tools are dry-run by default (write=true to persist); live mutation tools are previews by default (apply=true to execute after reviewing selection/plan).",
            })
        if method == "ping":
            return _ok(msg_id, {}, modern=modern)
        if method == "tools/list":
            result: dict[str, Any] = {"tools": TOOLS}
            if modern:
                result.update({"ttlMs": 60000, "cacheScope": "private"})
            return _ok(msg_id, result, modern=modern)
        if method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if not isinstance(name, str) or not isinstance(arguments, dict):
                return _err(msg_id, -32602, "Invalid tools/call params")
            try:
                value = call_tool(name, arguments)
                text = json.dumps(value, ensure_ascii=False, indent=2)
                return _ok(msg_id, {"content": [{"type": "text", "text": text}], "isError": False}, modern=modern)
            except Exception as exc:  # Tool errors are returned as tool results, not protocol errors.
                text = json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2)
                return _ok(msg_id, {"content": [{"type": "text", "text": text}], "isError": True}, modern=modern)
        return _err(msg_id, -32601, f"Method not found: {method}")
    except Exception as exc:
        return _err(msg_id, -32603, "Internal error", {"message": str(exc)})


def main() -> int:
    # MCP stdio messages are one JSON object per line. stderr is reserved for diagnostics.
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            message = json.loads(raw)
            if not isinstance(message, dict):
                raise ValueError("JSON-RPC message must be an object")
            response = handle_message(message)
            if response is not None:
                sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
                sys.stdout.flush()
        except Exception as exc:
            sys.stderr.write(f"cp77wb-mcp: {exc}\n")
            if "CP77WB_MCP_TRACEBACK" in __import__("os").environ:
                traceback.print_exc(file=sys.stderr)
            response = _err(None, -32700, "Parse error", {"message": str(exc)})
            sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
