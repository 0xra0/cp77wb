from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .assets import build_catalog, catalog_info, get_asset, resolve_asset, search_catalog
from .semantics import build_semantic_index, semantic_search
from .spatial import bounds_info, import_bounds, scan_project_collisions, set_asset_bounds
from .planner import apply_compiled_plan, compile_plan, load_plan, preview_plan
from .structures import generate_cable_chain, generate_fence, generate_road
from .diff import json_diff
from .errors import Cp77wbError
from .favorites import add_favorite, list_categories
from .compat import scan_worldbuilder
from .devices import connect_device, wire_elevator
from .procedural import (
    generate_corridor, generate_market, generate_room, load_asset_pool, load_points,
    marker_group_points, place_along_path, polygon_scatter, spawn_weighted_pool, volume_scatter,
)
from .templates import parse_parameter_assignments, render_template_file
from .live import LiveBridgeClient
from .logs import read_logs
from .naming import sanitize_filename
from .project import WorldBuilderProject, build_spawnable_node, node_kind
from .references import iter_known_references
from .validate import validate
from .build import (inspect_export, prepare_build_workspace, build_status, backend_scan, build_pack, build_package, deploy_layout, verify_package, build_doctor, build_native_import, build_worker_import, write_archive_xl)
from .native import (make_template_capture_script, verify_template_bundle, prepare_native_json, native_preflight, native_convert, native_import, verify_native_outputs)
from .worker import build_worker, worker_preflight, worker_inspect, worker_doctor, worker_create_bundle, worker_import


def _print_json(value) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _add_write_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--write", action="store_true", help="Write changes back to FILE. Without this flag, show a dry-run diff.")
    parser.add_argument("--output", type=Path, help="Write to a different file (implies persistence, original is untouched).")
    parser.add_argument("--no-backup", action="store_true", help="Do not create .cp77wb-backups copy when overwriting an existing file.")


def _add_xyz(parser: argparse.ArgumentParser, *, defaults: tuple[float, float, float], help_prefix: str = "") -> None:
    parser.add_argument("--x", type=float, default=defaults[0], help=f"{help_prefix}X")
    parser.add_argument("--y", type=float, default=defaults[1], help=f"{help_prefix}Y")
    parser.add_argument("--z", type=float, default=defaults[2], help=f"{help_prefix}Z")


def _add_pivot_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--pivot-x", type=float)
    parser.add_argument("--pivot-y", type=float)
    parser.add_argument("--pivot-z", type=float)


def _pivot(args: argparse.Namespace) -> tuple[float, float, float] | None:
    values = (args.pivot_x, args.pivot_y, args.pivot_z)
    if all(v is None for v in values):
        return None
    if any(v is None for v in values):
        raise ValueError("--pivot-x, --pivot-y and --pivot-z must be supplied together")
    return values  # type: ignore[return-value]


def _persist_or_diff(project: WorldBuilderProject, before: WorldBuilderProject, args: argparse.Namespace) -> int:
    if args.output:
        backup = project.save(args.output, backup=not args.no_backup)
        print(f"Wrote {args.output}")
        if backup:
            print(f"Backup: {backup}")
        return 0
    if args.write:
        backup = project.save(backup=not args.no_backup)
        print(f"Wrote {project.source}")
        if backup:
            print(f"Backup: {backup}")
        return 0
    diff = json_diff(before.data, project.data, str(project.source), f"{project.source} (dry-run)")
    print(diff if diff else "No changes.")
    print("Dry run only. Add --write to modify the source file, or --output PATH to create a copy.", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cp77wb", description="External tooling for Cyberpunk 2077 World Builder saved builds")
    p.add_argument("--version", action="version", version=f"cp77wb {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    sanitize = sub.add_parser("sanitize-name", help="Apply World Builder's exact createFileName() sanitization")
    sanitize.add_argument("name")

    tree = sub.add_parser("tree", help="Print the saved-build hierarchy")
    tree.add_argument("file", type=Path)
    tree.add_argument("--modules", action="store_true", help="Show editor/spawnable module paths")

    info = sub.add_parser("info", help="Show project or element information")
    info.add_argument("file", type=Path)
    info.add_argument("path", nargs="?")
    info.add_argument("--json", action="store_true")

    find = sub.add_parser("find", help="Search names, paths, modules, assets and NodeRefs")
    find.add_argument("file", type=Path)
    find.add_argument("query")
    find.add_argument("--case-sensitive", action="store_true")
    find.add_argument("--json", action="store_true")

    refs = sub.add_parser("refs", help="List NodeRef definitions and known references")
    refs.add_argument("file", type=Path)
    refs.add_argument("--json", action="store_true")

    val = sub.add_parser("validate", help="Validate World Builder-specific invariants")
    val.add_argument("file", type=Path)
    val.add_argument("--json", action="store_true")
    val.add_argument("--strict", action="store_true", help="Return non-zero for warnings as well as errors")

    move = sub.add_parser("move", help="Translate an object or group subtree")
    move.add_argument("file", type=Path)
    move.add_argument("path")
    _add_xyz(move, defaults=(0.0, 0.0, 0.0), help_prefix="Translation on ")
    _add_write_args(move)

    rotate = sub.add_parser("rotate", help="Rotate an object/group; groups rotate descendants around a pivot")
    rotate.add_argument("file", type=Path)
    rotate.add_argument("path")
    rotate.add_argument("--roll", type=float, default=0.0)
    rotate.add_argument("--pitch", type=float, default=0.0)
    rotate.add_argument("--yaw", type=float, default=0.0)
    _add_pivot_args(rotate)
    relative = rotate.add_mutually_exclusive_group()
    relative.add_argument("--relative", action="store_const", const=True, default=None, help="For a single object, compose the delta in local orientation")
    relative.add_argument("--world-components", action="store_const", dest="relative", const=False, help="For a single object, add roll/pitch/yaw components like normal WB editing")
    _add_write_args(rotate)

    scale = sub.add_parser("scale", help="Scale an object, or scale a group hierarchy around its origin/pivot")
    scale.add_argument("file", type=Path)
    scale.add_argument("path")
    _add_xyz(scale, defaults=(1.0, 1.0, 1.0), help_prefix="Scale factor on ")
    scale.add_argument("--uniform", type=float, help="Use one scale factor for X/Y/Z")
    _add_pivot_args(scale)
    scale.add_argument("--create-scale", action="store_true", help="Create missing spawnable.scale={1,1,1} before scaling (unsafe for types that do not support scale)")
    _add_write_args(scale)

    rename = sub.add_parser("rename", help="Rename with WB sanitization and repair known path references")
    rename.add_argument("file", type=Path)
    rename.add_argument("path")
    rename.add_argument("new_name")
    rename.add_argument("--no-update-path-refs", action="store_true")
    _add_write_args(rename)

    noderef = sub.add_parser("set-noderef", help="Set an object's NodeRef and update known NodeRef references")
    noderef.add_argument("file", type=Path)
    noderef.add_argument("path")
    noderef.add_argument("node_ref")
    noderef.add_argument("--no-update-references", action="store_true")
    _add_write_args(noderef)

    gennr = sub.add_parser("generate-noderef", help="Generate a NodeRef exactly like World Builder's nodeRefRegistry.generate()")
    gennr.add_argument("file", type=Path)
    gennr.add_argument("path")
    gennr.add_argument("--prefix", default="", help="Equivalent to World Builder nodeRefPrefix setting")
    gennr.add_argument("--force", action="store_true", help="Replace an existing NodeRef")
    gennr.add_argument("--no-update-references", action="store_true")
    _add_write_args(gennr)

    dup = sub.add_parser("duplicate", help="Duplicate an element/group with unique names and internal reference repair")
    dup.add_argument("file", type=Path)
    dup.add_argument("path")
    dup.add_argument("--count", type=int, default=1, help="Number of new copies")
    _add_xyz(dup, defaults=(0.0, 0.0, 0.0), help_prefix="Per-copy position offset on ")
    dup.add_argument("--noderef-prefix", default="")
    dup.add_argument("--keep-noderefs", action="store_true", help="Do not regenerate non-empty NodeRefs (usually creates validation errors)")
    _add_write_args(dup)

    array = sub.add_parser("array", help="Create a linear array; --count includes the original")
    array.add_argument("file", type=Path)
    array.add_argument("path")
    array.add_argument("--count", type=int, required=True, help="Total element count including the existing source")
    _add_xyz(array, defaults=(0.0, 0.0, 0.0), help_prefix="Array step on ")
    array.add_argument("--noderef-prefix", default="")
    array.add_argument("--keep-noderefs", action="store_true")
    _add_write_args(array)

    radial = sub.add_parser("radial-array", help="Create an XY radial array; --count includes the original")
    radial.add_argument("file", type=Path)
    radial.add_argument("path")
    radial.add_argument("--count", type=int, required=True)
    radial.add_argument("--angle", type=float, default=360.0, help="Total arc in degrees (default 360)")
    _add_pivot_args(radial)
    radial.add_argument("--no-rotate-items", action="store_true", help="Orbit copies without changing their orientation")
    radial.add_argument("--noderef-prefix", default="")
    radial.add_argument("--keep-noderefs", action="store_true")
    _add_write_args(radial)

    align = sub.add_parser("align", help="Align independent objects/groups on one axis")
    align.add_argument("file", type=Path)
    align.add_argument("axis", choices=("x", "y", "z"))
    align.add_argument("paths", nargs="+")
    align.add_argument("--mode", choices=("first", "min", "max", "average", "center", "value"), default="first")
    align.add_argument("--value", type=float)
    _add_write_args(align)

    distribute = sub.add_parser("distribute", help="Evenly distribute 3+ independent objects/groups between current endpoints")
    distribute.add_argument("file", type=Path)
    distribute.add_argument("axis", choices=("x", "y", "z"))
    distribute.add_argument("paths", nargs="+")
    _add_write_args(distribute)

    grid = sub.add_parser("grid", help="Create a rectangular 3D grid; counts include the original")
    grid.add_argument("file", type=Path)
    grid.add_argument("path")
    grid.add_argument("--count-x", type=int, default=1)
    grid.add_argument("--count-y", type=int, default=1)
    grid.add_argument("--count-z", type=int, default=1)
    grid.add_argument("--step-x", type=float, default=0.0)
    grid.add_argument("--step-y", type=float, default=0.0)
    grid.add_argument("--step-z", type=float, default=0.0)
    grid.add_argument("--noderef-prefix", default="")
    grid.add_argument("--keep-noderefs", action="store_true")
    _add_write_args(grid)

    scatter = sub.add_parser("scatter", help="Deterministically scatter copies in an offline box; count includes original")
    scatter.add_argument("file", type=Path)
    scatter.add_argument("path")
    scatter.add_argument("--count", type=int, required=True)
    scatter.add_argument("--half-x", type=float, default=5.0)
    scatter.add_argument("--half-y", type=float, default=5.0)
    scatter.add_argument("--half-z", type=float, default=0.0)
    scatter.add_argument("--seed", type=int, default=1)
    scatter.add_argument("--no-random-yaw", action="store_true")
    scatter.add_argument("--scale-min", type=float)
    scatter.add_argument("--scale-max", type=float)
    scatter.add_argument("--create-scale", action="store_true")
    scatter.add_argument("--noderef-prefix", default="")
    scatter.add_argument("--keep-noderefs", action="store_true")
    _add_write_args(scatter)

    patharr = sub.add_parser("path-array", help="Place copies along a polyline or World Builder marker group")
    patharr.add_argument("file", type=Path)
    patharr.add_argument("path", help="Source object/group to duplicate")
    source = patharr.add_mutually_exclusive_group(required=True)
    source.add_argument("--points", help="JSON array or JSON file with [[x,y,z], ...]")
    source.add_argument("--marker-group", help="WB group whose direct positioned children define the path")
    amount = patharr.add_mutually_exclusive_group(required=True)
    amount.add_argument("--spacing", type=float)
    amount.add_argument("--count", type=int)
    patharr.add_argument("--closed", action="store_true")
    patharr.add_argument("--no-orient", action="store_true")
    patharr.add_argument("--yaw-offset", type=float, default=0.0)
    patharr.add_argument("--noderef-prefix", default="")
    patharr.add_argument("--keep-noderefs", action="store_true")
    _add_write_args(patharr)

    pscatter = sub.add_parser("polygon-scatter", help="Deterministically scatter copies inside an XY polygon")
    pscatter.add_argument("file", type=Path)
    pscatter.add_argument("path")
    pscatter.add_argument("--points", required=True, help="JSON array or JSON file with polygon vertices")
    pscatter.add_argument("--count", type=int, required=True)
    pscatter.add_argument("--seed", type=int, default=1)
    pscatter.add_argument("--z", type=float)
    pscatter.add_argument("--z-jitter", type=float, default=0.0)
    pscatter.add_argument("--no-random-yaw", action="store_true")
    pscatter.add_argument("--scale-min", type=float)
    pscatter.add_argument("--scale-max", type=float)
    pscatter.add_argument("--create-scale", action="store_true")
    pscatter.add_argument("--noderef-prefix", default="")
    pscatter.add_argument("--keep-noderefs", action="store_true")
    _add_write_args(pscatter)

    vscatter = sub.add_parser("volume-scatter", help="Scatter copies in a box, cylinder, or sphere/ellipsoid volume")
    vscatter.add_argument("file", type=Path)
    vscatter.add_argument("path")
    vscatter.add_argument("--shape", choices=("box", "cylinder", "sphere"), required=True)
    vscatter.add_argument("--count", type=int, required=True)
    vscatter.add_argument("--center-x", type=float, default=0.0)
    vscatter.add_argument("--center-y", type=float, default=0.0)
    vscatter.add_argument("--center-z", type=float, default=0.0)
    vscatter.add_argument("--size-x", type=float, default=5.0, help="Half-size X; cylinder radius; sphere X radius")
    vscatter.add_argument("--size-y", type=float, default=5.0, help="Half-size Y; sphere Y radius")
    vscatter.add_argument("--size-z", type=float, default=5.0, help="Half-size Z; cylinder half-height; sphere Z radius")
    vscatter.add_argument("--seed", type=int, default=1)
    vscatter.add_argument("--no-random-yaw", action="store_true")
    vscatter.add_argument("--noderef-prefix", default="")
    vscatter.add_argument("--keep-noderefs", action="store_true")
    _add_write_args(vscatter)

    pool = sub.add_parser("asset-pool-spawn", help="Spawn a deterministic weighted pool of real indexed WB assets")
    pool.add_argument("file", type=Path)
    pool.add_argument("parent")
    pool.add_argument("--catalog", required=True, type=Path)
    pool.add_argument("--pool", required=True, help="Pool JSON file/string: {entries:[{asset:'#1',weight:2}, ...]}")
    pool.add_argument("--count", type=int, required=True)
    pool.add_argument("--seed", type=int, default=1)
    pool.add_argument("--center-x", type=float, default=0.0)
    pool.add_argument("--center-y", type=float, default=0.0)
    pool.add_argument("--center-z", type=float, default=0.0)
    pool.add_argument("--half-x", type=float, default=5.0)
    pool.add_argument("--half-y", type=float, default=5.0)
    pool.add_argument("--half-z", type=float, default=0.0)
    pool.add_argument("--no-random-yaw", action="store_true")
    pool.add_argument("--generate-noderef", action="store_true")
    pool.add_argument("--noderef-prefix", default="")
    _add_write_args(pool)

    rng = sub.add_parser("rng-create", help="Create a native World Builder Randomized Nested Group")
    rng.add_argument("file", type=Path)
    rng.add_argument("parent")
    rng.add_argument("name")
    rng.add_argument("--seed", type=int, default=1)
    rng.add_argument("--rule", choices=("per-object", "fixed"), default="per-object")
    rng.add_argument("--fixed-mode", choices=("percentage", "total"), default="percentage")
    rng.add_argument("--percentage", type=float, default=50.0)
    rng.add_argument("--total", type=int, default=1)
    _add_xyz(rng, defaults=(0.0, 0.0, 0.0), help_prefix="Group origin on ")
    _add_write_args(rng)

    room = sub.add_parser("generate-room", help="Generate a rectangular room shell from verified indexed assets")
    room.add_argument("file", type=Path)
    room.add_argument("parent")
    room.add_argument("--catalog", required=True, type=Path)
    room.add_argument("--wall-asset", required=True)
    room.add_argument("--floor-asset")
    room.add_argument("--width", type=float, required=True)
    room.add_argument("--depth", type=float, required=True)
    room.add_argument("--segment", type=float, required=True)
    room.add_argument("--name", default="Generated Room")
    _add_xyz(room, defaults=(0.0, 0.0, 0.0), help_prefix="Origin on ")
    _add_write_args(room)

    corridor = sub.add_parser("generate-corridor", help="Generate a corridor shell from verified indexed assets")
    corridor.add_argument("file", type=Path)
    corridor.add_argument("parent")
    corridor.add_argument("--catalog", required=True, type=Path)
    corridor.add_argument("--wall-asset", required=True)
    corridor.add_argument("--floor-asset")
    corridor.add_argument("--length", type=float, required=True)
    corridor.add_argument("--width", type=float, required=True)
    corridor.add_argument("--segment", type=float, required=True)
    corridor.add_argument("--name", default="Generated Corridor")
    _add_xyz(corridor, defaults=(0.0, 0.0, 0.0), help_prefix="Origin on ")
    _add_write_args(corridor)

    market = sub.add_parser("generate-market", help="Generate a deterministic market grid from a weighted asset pool")
    market.add_argument("file", type=Path)
    market.add_argument("parent")
    market.add_argument("--catalog", required=True, type=Path)
    market.add_argument("--pool", required=True)
    market.add_argument("--rows", type=int, required=True)
    market.add_argument("--columns", type=int, required=True)
    market.add_argument("--spacing-x", type=float, required=True)
    market.add_argument("--spacing-y", type=float, required=True)
    market.add_argument("--seed", type=int, default=1)
    market.add_argument("--name", default="Generated Market")
    _add_xyz(market, defaults=(0.0, 0.0, 0.0), help_prefix="Origin on ")
    _add_write_args(market)

    dconnect = sub.add_parser("device-connect", help="Connect two saved World Builder device nodes by NodeRef")
    dconnect.add_argument("file", type=Path)
    dconnect.add_argument("source")
    dconnect.add_argument("target")
    dconnect.add_argument("--device-class-name")
    dconnect.add_argument("--noderef-prefix", default="")
    _add_write_args(dconnect)

    elevator = sub.add_parser("elevator-wire", help="Wire an existing elevator, terminals and markers; patches instance data when present")
    elevator.add_argument("file", type=Path)
    elevator.add_argument("elevator")
    elevator.add_argument("--terminal", action="append", required=True)
    elevator.add_argument("--marker", action="append", required=True)
    elevator.add_argument("--floor-name", action="append", default=[])
    elevator.add_argument("--terminal-class-name", default="ElevatorFloorTerminalControllerPS")
    elevator.add_argument("--noderef-prefix", default="")
    _add_write_args(elevator)

    exinspect = sub.add_parser("export-inspect", help="Validate and summarize a World Builder *_exported.json before WolvenKit import")
    exinspect.add_argument("export_file", type=Path)
    exinspect.add_argument("--importer-version", default="1.0.4")
    exinspect.add_argument("--json", action="store_true")

    xlgen = sub.add_parser("export-xl", help="Generate the ArchiveXL .xl configuration implied by a World Builder export")
    xlgen.add_argument("export_file", type=Path)
    xlgen.add_argument("output", type=Path)
    xlgen.add_argument("--format", choices=("json","yaml"))
    xlgen.add_argument("--json", action="store_true")

    bprep = sub.add_parser("build-prepare", help="Create a WolvenKit project/workspace around a World Builder export")
    bprep.add_argument("export_file", type=Path)
    bprep.add_argument("workspace", type=Path)
    bprep.add_argument("--world-builder-root", type=Path)
    bprep.add_argument("--project-name")
    bprep.add_argument("--author", default="")
    bprep.add_argument("--project-version", default="1.0.0")
    bprep.add_argument("--description", default="World Builder project prepared by cp77wb")
    bprep.add_argument("--force", action="store_true")
    bprep.add_argument("--scaffold-tweak", action="store_true")
    bprep.add_argument("--json", action="store_true")

    bstatus = sub.add_parser("build-status", help="Check whether WolvenKit Object Spawner import produced every expected REDengine file")
    bstatus.add_argument("workspace", type=Path)
    bstatus.add_argument("--json", action="store_true")

    bnimp = sub.add_parser("build-native-import", help="Use a captured template bundle + WolvenKit JSON deserializer to populate source/archive; preview unless --run")
    bnimp.add_argument("workspace", type=Path)
    bnimp.add_argument("bundle", type=Path)
    bnimp.add_argument("--cli")
    bnimp.add_argument("--run", action="store_true")
    bnimp.add_argument("--timeout", type=int, default=300)
    bnimp.add_argument("--clean-json", action="store_true")
    bnimp.add_argument("--json", action="store_true")

    bwimp = sub.add_parser("build-worker-import", help="Use the verified .NET 10 WolvenKit worker to populate source/archive; preview unless --run")
    bwimp.add_argument("workspace", type=Path)
    bwimp.add_argument("--worker")
    bwimp.add_argument("--run", action="store_true")
    bwimp.add_argument("--timeout", type=int, default=300)
    bwimp.add_argument("--clean-json", action="store_true")
    bwimp.add_argument("--json", action="store_true")

    bbackend = sub.add_parser("build-backends", help="Detect WolvenKit CLI and explain native/Object-Spawner conversion capability")
    bbackend.add_argument("--cli", type=Path)
    bbackend.add_argument("--world-builder-root", type=Path)
    bbackend.add_argument("--json", action="store_true")

    bpack = sub.add_parser("build-pack", help="Pack completed source/archive with WolvenKit CLI/cp77tools; preview unless --run")
    bpack.add_argument("workspace", type=Path)
    bpack.add_argument("--cli")
    bpack.add_argument("--output", type=Path)
    bpack.add_argument("--run", action="store_true")
    bpack.add_argument("--timeout", type=int, default=300)
    bpack.add_argument("--json", action="store_true")

    bpackage = sub.add_parser("build-package", help="Assemble a distributable Cyberpunk game-layout folder/ZIP from a built archive and resources")
    bpackage.add_argument("workspace", type=Path)
    bpackage.add_argument("--archive", required=True, type=Path)
    bpackage.add_argument("--output", required=True, type=Path)
    bpackage.add_argument("--zip", dest="zip_output", type=Path)
    bpackage.add_argument("--no-clean", action="store_true")
    bpackage.add_argument("--json", action="store_true")

    bverify = sub.add_parser("build-verify", help="Verify game-layout package structure and optional conflicts against an installed game")
    bverify.add_argument("layout", type=Path)
    bverify.add_argument("--game-root", type=Path)
    bverify.add_argument("--json", action="store_true")

    bdeploy = sub.add_parser("build-deploy", help="Preview or deploy a prepared game-layout folder into Cyberpunk; requires --apply to write")
    bdeploy.add_argument("layout", type=Path)
    bdeploy.add_argument("game_root", type=Path)
    bdeploy.add_argument("--apply", action="store_true")
    bdeploy.add_argument("--overwrite", action="store_true")
    bdeploy.add_argument("--json", action="store_true")

    bdoctor = sub.add_parser("build-doctor", help="Combine package verification with issue-only World Builder/CET/framework log review")
    bdoctor.add_argument("layout", type=Path)
    bdoctor.add_argument("--game-root", type=Path)
    bdoctor.add_argument("--tail", type=int, default=200)
    bdoctor.add_argument("--json", action="store_true")

    ntpl = sub.add_parser("native-template-plan", help="Generate a WolvenKit wscript that captures the exact RED default types needed for an export")
    ntpl.add_argument("export_file", type=Path)
    ntpl.add_argument("output", type=Path)
    ntpl.add_argument("--resource-name")
    ntpl.add_argument("--json", action="store_true")

    ntplv = sub.add_parser("native-template-verify", help="Verify a captured RED type template bundle covers a World Builder export")
    ntplv.add_argument("export_file", type=Path)
    ntplv.add_argument("bundle", type=Path)
    ntplv.add_argument("--json", action="store_true")

    njson = sub.add_parser("native-json", help="Reproduce World Builder importer output as WolvenKit JSON using a captured template bundle")
    njson.add_argument("export_file", type=Path)
    njson.add_argument("bundle", type=Path)
    njson.add_argument("output", type=Path)
    njson.add_argument("--json", action="store_true")

    npre = sub.add_parser("native-preflight", help="Probe a WolvenKit CLI/cp77tools binary for cross-platform JSON-to-CR2W support")
    npre.add_argument("--cli")
    npre.add_argument("--timeout", type=int, default=30)
    npre.add_argument("--json", action="store_true")

    nconv = sub.add_parser("native-convert", help="Convert prepared WolvenKit JSON intermediates to CR2W; preview unless --run")
    nconv.add_argument("native_json", type=Path)
    nconv.add_argument("output", type=Path)
    nconv.add_argument("--cli")
    nconv.add_argument("--run", action="store_true")
    nconv.add_argument("--timeout", type=int, default=300)
    nconv.add_argument("--json", action="store_true")

    nimp = sub.add_parser("native-import", help="Prepare WolvenKit JSON and convert a WB export to CR2W in one step; preview unless --run")
    nimp.add_argument("export_file", type=Path)
    nimp.add_argument("bundle", type=Path)
    nimp.add_argument("output", type=Path)
    nimp.add_argument("--cli")
    nimp.add_argument("--run", action="store_true")
    nimp.add_argument("--timeout", type=int, default=300)
    nimp.add_argument("--clean-json", action="store_true")
    nimp.add_argument("--json", action="store_true")

    nverify = sub.add_parser("native-verify", help="Verify native-conversion CR2W outputs exist and carry CR2W magic")
    nverify.add_argument("output", type=Path)
    nverify.add_argument("--target", action="append", default=[])
    nverify.add_argument("--allow-non-cr2w", action="store_true")
    nverify.add_argument("--json", action="store_true")

    wbuild = sub.add_parser("worker-build", help="Build the bundled .NET 10 WolvenKit worker with dotnet publish; preview unless --run")
    wbuild.add_argument("--source", type=Path)
    wbuild.add_argument("--output", type=Path)
    wbuild.add_argument("--dotnet")
    wbuild.add_argument("--run", action="store_true")
    wbuild.add_argument("--timeout", type=int, default=600)
    wbuild.add_argument("--log-file", type=Path)
    wbuild.add_argument("--json", action="store_true")

    wpre = sub.add_parser("worker-preflight", help="Run authoritative self-test of the .NET WolvenKit worker")
    wpre.add_argument("--worker")
    wpre.add_argument("--timeout", type=int, default=30)
    wpre.add_argument("--json", action="store_true")

    winspect = sub.add_parser("worker-inspect", help="Inspect WolvenKit assemblies/reflection API surface without requiring the CR2W self-test to pass")
    winspect.add_argument("--worker")
    winspect.add_argument("--timeout", type=int, default=30)
    winspect.add_argument("--json", action="store_true")

    wdoctor = sub.add_parser("worker-doctor", help="Collect worker/.NET diagnostics and optionally write a support ZIP for later compatibility testing")
    wdoctor.add_argument("--worker")
    wdoctor.add_argument("--dotnet")
    wdoctor.add_argument("--output", type=Path)
    wdoctor.add_argument("--timeout", type=int, default=30)
    wdoctor.add_argument("--json", action="store_true")

    wbundle = sub.add_parser("worker-bundle", help="Create exact RED default templates directly through the .NET WolvenKit worker; preview unless --run")
    wbundle.add_argument("export_file", type=Path)
    wbundle.add_argument("output", type=Path)
    wbundle.add_argument("--worker")
    wbundle.add_argument("--run", action="store_true")
    wbundle.add_argument("--timeout", type=int, default=120)
    wbundle.add_argument("--json", action="store_true")

    wimp = sub.add_parser("worker-import", help="Convert a WB export through the .NET WolvenKit worker without WScript template capture; preview unless --run")
    wimp.add_argument("export_file", type=Path)
    wimp.add_argument("output", type=Path)
    wimp.add_argument("--worker")
    wimp.add_argument("--run", action="store_true")
    wimp.add_argument("--timeout", type=int, default=300)
    wimp.add_argument("--clean-json", action="store_true")
    wimp.add_argument("--json", action="store_true")

    compat = sub.add_parser("compat-scan", help="Scan a World Builder install/source and optionally compare a saved build against its modules/schema")
    compat.add_argument("world_builder_root", type=Path)
    compat.add_argument("--project", type=Path)
    compat.add_argument("--json", action="store_true")

    render = sub.add_parser("prefab-render", help="Render ${parameter} placeholders in a JSON World Builder prefab/build template")
    render.add_argument("template", type=Path)
    render.add_argument("--set", action="append", default=[])
    render.add_argument("--output", type=Path)
    render.add_argument("--json", action="store_true")

    abuild = sub.add_parser("assets-build", help="Build a searchable SQLite asset index from World Builder data/spawnables")
    abuild.add_argument("world_builder_root", type=Path)
    abuild.add_argument("--db", type=Path)
    abuild.add_argument("--json", action="store_true")

    asearch = sub.add_parser("assets-search", help="Search a cp77wb World Builder asset index")
    asearch.add_argument("database", type=Path)
    asearch.add_argument("query")
    asearch.add_argument("--category")
    asearch.add_argument("--variant")
    asearch.add_argument("--module")
    asearch.add_argument("--ext")
    asearch.add_argument("--limit", type=int, default=25)
    asearch.add_argument("--json", action="store_true")

    ainfo = sub.add_parser("assets-info", help="Show asset-index metadata or a single asset by numeric ID")
    ainfo.add_argument("database", type=Path)
    ainfo.add_argument("--id", type=int)
    ainfo.add_argument("--json", action="store_true")

    sem_build = sub.add_parser("semantic-build", help="Build deterministic semantic tags/facets over an existing asset catalog")
    sem_build.add_argument("database", type=Path)
    sem_build.add_argument("--overrides", type=Path)
    sem_build.add_argument("--json", action="store_true")

    sem_search = sub.add_parser("semantic-search", help="Search assets by derived/user semantic tags plus depot-path text")
    sem_search.add_argument("database", type=Path)
    sem_search.add_argument("query")
    sem_search.add_argument("--role")
    sem_search.add_argument("--style")
    sem_search.add_argument("--material")
    sem_search.add_argument("--condition")
    sem_search.add_argument("--category")
    sem_search.add_argument("--variant")
    sem_search.add_argument("--limit", type=int, default=25)
    sem_search.add_argument("--json", action="store_true")

    bset = sub.add_parser("bounds-set", help="Attach explicit local XYZ bounds to one indexed asset")
    bset.add_argument("database", type=Path)
    bset.add_argument("asset_id", type=int)
    bset.add_argument("--x", type=float, required=True)
    bset.add_argument("--y", type=float, required=True)
    bset.add_argument("--z", type=float, required=True)
    bset.add_argument("--source", default="user")
    bset.add_argument("--confidence", type=float, default=1.0)
    bset.add_argument("--json", action="store_true")

    bimport = sub.add_parser("bounds-import", help="Import explicit asset bounds from JSON")
    bimport.add_argument("database", type=Path)
    bimport.add_argument("input")
    bimport.add_argument("--json", action="store_true")

    binfo = sub.add_parser("bounds-info", help="Show explicit/effective asset bounds and fallback heuristics")
    binfo.add_argument("database", type=Path)
    binfo.add_argument("--id", type=int)
    binfo.add_argument("--json", action="store_true")

    collisions = sub.add_parser("collisions", help="Approximate saved-build collision scan using explicit/heuristic oriented bounds")
    collisions.add_argument("file", type=Path)
    collisions.add_argument("--catalog", required=True, type=Path)
    collisions.add_argument("--clearance", type=float, default=0.0)
    collisions.add_argument("--explicit-only", action="store_true")
    collisions.add_argument("--json", action="store_true")

    pcompile = sub.add_parser("plan-compile", help="Compile a declarative cp77wb construction plan into exact indexed spawn operations")
    pcompile.add_argument("plan")
    pcompile.add_argument("--catalog", required=True, type=Path)
    pcompile.add_argument("--output", type=Path)
    pcompile.add_argument("--json", action="store_true")

    ppreview = sub.add_parser("plan-preview", help="Compile a construction plan, apply to a clone, validate and report approximate existing collisions")
    ppreview.add_argument("file", type=Path)
    ppreview.add_argument("plan")
    ppreview.add_argument("--catalog", required=True, type=Path)
    ppreview.add_argument("--json", action="store_true")

    papply = sub.add_parser("plan-apply", help="Apply a declarative construction plan to a saved build; dry-run unless --write")
    papply.add_argument("file", type=Path)
    papply.add_argument("plan")
    papply.add_argument("--catalog", required=True, type=Path)
    _add_write_args(papply)

    fence = sub.add_parser("generate-fence", help="Generate repeated fence segments/posts along explicit points or a WB marker/spline group")
    fence.add_argument("file", type=Path)
    fence.add_argument("parent")
    fence.add_argument("--catalog", required=True, type=Path)
    fence.add_argument("--segment-asset", required=True)
    fence.add_argument("--post-asset")
    fsrc=fence.add_mutually_exclusive_group(required=True)
    fsrc.add_argument("--points")
    fsrc.add_argument("--marker-group")
    fence.add_argument("--spacing", type=float, required=True)
    fence.add_argument("--curve-samples", type=int, default=12)
    fence.add_argument("--yaw-offset", type=float, default=0)
    fence.add_argument("--name", default="Generated Fence")
    _add_write_args(fence)

    road = sub.add_parser("generate-road", help="Generate repeated road tiles and optional edge assets along a path")
    road.add_argument("file", type=Path)
    road.add_argument("parent")
    road.add_argument("--catalog", required=True, type=Path)
    road.add_argument("--tile-asset", required=True)
    road.add_argument("--edge-asset")
    rsrc=road.add_mutually_exclusive_group(required=True)
    rsrc.add_argument("--points")
    rsrc.add_argument("--marker-group")
    road.add_argument("--spacing", type=float, required=True)
    road.add_argument("--width", type=float, required=True)
    road.add_argument("--curve-samples", type=int, default=12)
    road.add_argument("--yaw-offset", type=float, default=0)
    road.add_argument("--name", default="Generated Road")
    _add_write_args(road)

    cable = sub.add_parser("generate-cable", help="Generate a repeated cable/pipe segment chain along a path without guessing mesh stretch")
    cable.add_argument("file", type=Path)
    cable.add_argument("parent")
    cable.add_argument("--catalog", required=True, type=Path)
    cable.add_argument("--segment-asset", required=True)
    csrc=cable.add_mutually_exclusive_group(required=True)
    csrc.add_argument("--points")
    csrc.add_argument("--marker-group")
    cable.add_argument("--spacing", type=float, required=True)
    cable.add_argument("--curve-samples", type=int, default=12)
    cable.add_argument("--yaw-offset", type=float, default=0)
    cable.add_argument("--name", default="Generated Cable")
    _add_write_args(cable)

    spawn = sub.add_parser("spawn-asset", help="Insert an indexed World Builder asset under a saved-build group")
    spawn.add_argument("file", type=Path)
    spawn.add_argument("parent")
    spawn.add_argument("asset", help="Asset search text or #ID from assets-search")
    spawn.add_argument("--catalog", required=True, type=Path)
    spawn.add_argument("--module", help="Require this spawnable module (for example mesh/mesh)")
    spawn.add_argument("--variant")
    spawn.add_argument("--name")
    _add_xyz(spawn, defaults=(0.0, 0.0, 0.0), help_prefix="World position on ")
    spawn.add_argument("--roll", type=float, default=0.0)
    spawn.add_argument("--pitch", type=float, default=0.0)
    spawn.add_argument("--yaw", type=float, default=0.0)
    spawn.add_argument("--generate-noderef", action="store_true")
    spawn.add_argument("--noderef-prefix", default="")
    _add_write_args(spawn)

    favadd = sub.add_parser("favorite-add", help="Add a saved-build object/group to World Builder's native Favorites as a reusable prefab")
    favadd.add_argument("file", type=Path)
    favadd.add_argument("path")
    favadd.add_argument("world_builder_root", type=Path)
    favadd.add_argument("--category", required=True)
    favadd.add_argument("--name")
    favadd.add_argument("--tag", action="append", default=[])
    favadd.add_argument("--icon", default="")
    favadd.add_argument("--category-icon", default="")
    favadd.add_argument("--no-backup", action="store_true")
    favadd.add_argument("--json", action="store_true")

    favlist = sub.add_parser("favorites-list", help="List World Builder favorite/prefab categories")
    favlist.add_argument("world_builder_root", type=Path)
    favlist.add_argument("--json", action="store_true")

    live = sub.add_parser("live", help="Read or history-safely mutate the optional cp77wb CET live bridge")
    live.add_argument("rpc_dir", type=Path, help="Path to cp77wb_bridge/rpc")
    live.add_argument("action", choices=(
        "ping", "state", "player", "camera", "selection", "history", "paths", "raycast",
        "select", "move", "rotate", "scale", "snap", "batch", "duplicate", "surface-scatter",
        "delete", "save", "reload", "undo", "redo", "spawn-asset"
    ))
    live.add_argument("--include-data", action="store_true", help="Include serialized World Builder data for selection")
    live.add_argument("--timeout", type=float, default=3.0)
    live.add_argument("--apply", action="store_true", help="Actually perform a live mutation. Mutations are previews without this flag.")
    live.add_argument("--query", default="", help="Path/name query for the paths action")
    live.add_argument("--limit", type=int, default=100)
    live.add_argument("--path", action="append", default=[], help="World Builder path; repeat for live select, or one top-level path for reload")
    live.add_argument("--x", type=float, default=0.0)
    live.add_argument("--y", type=float, default=0.0)
    live.add_argument("--z", type=float, default=0.0)
    live.add_argument("--roll", type=float, default=0.0)
    live.add_argument("--pitch", type=float, default=0.0)
    live.add_argument("--yaw", type=float, default=0.0)
    live.add_argument("--scale-x", type=float, default=1.0)
    live.add_argument("--scale-y", type=float, default=1.0)
    live.add_argument("--scale-z", type=float, default=1.0)
    live.add_argument("--uniform", type=float, help="Uniform factor for live scale")
    live.add_argument("--pivot-x", type=float)
    live.add_argument("--pivot-y", type=float)
    live.add_argument("--pivot-z", type=float)
    live.add_argument("--allow-partial", action="store_true", help="Allow scale to reposition objects that do not support scale")
    live.add_argument("--dir-x", type=float, default=0.0)
    live.add_argument("--dir-y", type=float, default=0.0)
    live.add_argument("--dir-z", type=float, default=-1.0)
    live.add_argument("--origin-x", type=float)
    live.add_argument("--origin-y", type=float)
    live.add_argument("--origin-z", type=float)
    live.add_argument("--ray-mode", choices=("camera", "custom"), default="camera")
    live.add_argument("--no-physical", action="store_true", help="For raycast, prefer WB node intersections over physical collision")
    live.add_argument("--count", type=int, default=1)
    live.add_argument("--half-x", type=float, default=5.0)
    live.add_argument("--half-y", type=float, default=5.0)
    live.add_argument("--half-z", type=float, default=0.0)
    live.add_argument("--seed", type=int, default=1)
    live.add_argument("--no-random-yaw", action="store_true")
    live.add_argument("--keep-noderefs", action="store_true", help="Keep duplicate NodeRefs instead of v0.5 live remapping (unsafe)")
    live.add_argument("--ops-json", help="JSON array for live batch, e.g. '[{\"type\":\"move\",\"z\":1}]'")
    live.add_argument("--ops-file", type=Path, help="Read live batch operation array from JSON file")
    live.add_argument("--catalog", type=Path, help="Asset SQLite database for live spawn-asset")
    live.add_argument("--asset", help="Exact #asset-id or unambiguous asset query for live spawn-asset")
    live.add_argument("--module", help="Optional module filter for live spawn-asset")
    live.add_argument("--variant", help="Optional variant filter for live spawn-asset")
    live.add_argument("--name", help="Optional World Builder element name for live spawn-asset")
    live.add_argument("--parent", help="Optional active World Builder parent path for live spawn-asset")
    live.add_argument("--placement", choices=("serialized", "camera", "player"), default="camera", help="Placement for live spawn-asset")
    live.add_argument("--distance", type=float, default=4.0, help="Camera-forward distance for --placement camera")
    live.add_argument("--snap-to-surface", action="store_true", help="Drop a live-spawned asset to the surface before recording its insert")
    live.add_argument("--json", action="store_true")

    logs = sub.add_parser("logs", help="Read/tail World Builder, CET and related Cyberpunk mod logs")
    logs.add_argument("game_root", type=Path, help="Cyberpunk 2077 root, or the installed entSpawner directory")
    logs.add_argument("--tail", type=int, default=200)
    logs.add_argument("--issues-only", action="store_true", help="Keep only error/warning/failure-like lines")
    logs.add_argument("--json", action="store_true")

    refresh = sub.add_parser("refresh-area-cache", help="Refresh saved area marker snapshots from outlinePath groups")
    refresh.add_argument("file", type=Path)
    _add_write_args(refresh)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "sanitize-name":
            print(sanitize_filename(args.name))
            return 0

        if args.command == "export-inspect":
            result = inspect_export(args.export_file, importer_version=args.importer_version)
            _print_json(result)
            return 0 if result["valid"] else 2

        if args.command == "export-xl":
            result = write_archive_xl(args.export_file, args.output, format=args.format)
            _print_json(result)
            return 0

        if args.command == "build-prepare":
            result = prepare_build_workspace(args.export_file, args.workspace, world_builder_root=args.world_builder_root, project_name=args.project_name, author=args.author, version=args.project_version, description=args.description, force=args.force, scaffold_tweak=args.scaffold_tweak)
            _print_json(result)
            return 0

        if args.command == "build-status":
            result = build_status(args.workspace)
            _print_json(result)
            return 0 if result["importComplete"] else 2

        if args.command == "build-native-import":
            result = build_native_import(args.workspace, args.bundle, cli=args.cli, run=args.run, keep_json=not args.clean_json, timeout=args.timeout)
            _print_json(result)
            return 0 if (not args.run or result.get("ready")) else 2

        if args.command == "build-worker-import":
            result = build_worker_import(args.workspace, worker=args.worker, run=args.run, keep_json=not args.clean_json, timeout=args.timeout)
            _print_json(result)
            return 0 if (not args.run or result.get("ready")) else 2

        if args.command == "build-backends":
            result = backend_scan(cli=args.cli, world_builder_root=args.world_builder_root)
            _print_json(result)
            return 0

        if args.command == "build-pack":
            result = build_pack(args.workspace, cli=args.cli, output=args.output, run=args.run, timeout=args.timeout)
            _print_json(result)
            return 0

        if args.command == "build-package":
            result = build_package(args.workspace, archive=args.archive, output=args.output, zip_output=args.zip_output, clean=not args.no_clean)
            _print_json(result)
            return 0 if result["ready"] else 2

        if args.command == "build-verify":
            result = verify_package(args.layout, game_root=args.game_root)
            _print_json(result)
            return 0 if result["valid"] else 2

        if args.command == "build-deploy":
            result = deploy_layout(args.layout, args.game_root, apply=args.apply, overwrite=args.overwrite)
            _print_json(result)
            return 0

        if args.command == "build-doctor":
            result = build_doctor(args.layout, game_root=args.game_root, tail=args.tail)
            _print_json(result)
            return 0 if result["package"]["valid"] else 2

        if args.command == "native-template-plan":
            result = make_template_capture_script(args.export_file, args.output, resource_name=args.resource_name)
            _print_json(result)
            return 0

        if args.command == "native-template-verify":
            result = verify_template_bundle(args.export_file, args.bundle)
            _print_json(result)
            return 0 if result["valid"] else 2

        if args.command == "native-json":
            result = prepare_native_json(args.export_file, args.bundle, args.output)
            _print_json(result)
            return 0

        if args.command == "native-preflight":
            result = native_preflight(cli=args.cli, timeout=args.timeout)
            _print_json(result)
            return 0 if result["ready"] else 2

        if args.command == "native-convert":
            result = native_convert(args.native_json, args.output, cli=args.cli, run=args.run, timeout=args.timeout)
            _print_json(result)
            return 0 if (not args.run or result.get("verification", {}).get("valid")) else 2

        if args.command == "native-import":
            result = native_import(args.export_file, args.bundle, args.output, cli=args.cli, run=args.run, keep_json=not args.clean_json, timeout=args.timeout)
            _print_json(result)
            return 0 if (not args.run or result.get("native")) else 2

        if args.command == "native-verify":
            result = verify_native_outputs(args.output, args.target or None, strict_magic=not args.allow_non_cr2w)
            _print_json(result)
            return 0 if result["valid"] else 2

        if args.command == "worker-build":
            result = build_worker(source=args.source, output=args.output, dotnet=args.dotnet, run=args.run, timeout=args.timeout, log_file=args.log_file)
            _print_json(result)
            return 0 if (not args.run or result.get("ready")) else 2

        if args.command == "worker-preflight":
            result = worker_preflight(worker=args.worker, timeout=args.timeout)
            _print_json(result)
            return 0 if result.get("ready") else 2

        if args.command == "worker-inspect":
            result = worker_inspect(worker=args.worker, timeout=args.timeout)
            _print_json(result)
            return 0 if result.get("inspectAvailable") else 2

        if args.command == "worker-doctor":
            result = worker_doctor(worker=args.worker, dotnet=args.dotnet, output=args.output, timeout=args.timeout)
            _print_json(result)
            return 0

        if args.command == "worker-bundle":
            result = worker_create_bundle(args.export_file, args.output, worker=args.worker, run=args.run, timeout=args.timeout)
            _print_json(result)
            return 0 if (not args.run or result.get("created")) else 2

        if args.command == "worker-import":
            result = worker_import(args.export_file, args.output, worker=args.worker, run=args.run, keep_json=not args.clean_json, timeout=args.timeout)
            _print_json(result)
            return 0 if (not args.run or result.get("native")) else 2

        if args.command == "compat-scan":
            result = scan_worldbuilder(args.world_builder_root, args.project)
            _print_json(result)
            return 0 if result.get("compatible", True) else 2

        if args.command == "prefab-render":
            result = render_template_file(args.template, parse_parameter_assignments(args.set), args.output)
            if args.json or args.output is None:
                _print_json(result)
            else:
                print(f"Rendered {args.template} -> {result['output']}")
            return 0

        if args.command == "semantic-build":
            result = build_semantic_index(args.database, args.overrides)
            if args.json:
                _print_json(result)
            else:
                print(f"Built semantic index for {result['assets']} assets ({result['seconds']}s, FTS5={result['fts5']})")
            return 0

        if args.command == "semantic-search":
            result = semantic_search(args.database, args.query, role=args.role, style=args.style, material=args.material, condition=args.condition, category=args.category, variant=args.variant, limit=args.limit)
            if args.json:
                _print_json(result)
            else:
                for row in result:
                    facets=[]
                    for key in ("roles","styles","materials","conditions"):
                        if row[key]:
                            facets.append(f"{key}={','.join(row[key])}")
                    print(f"#{row['id']}  {row['category']}/{row['variant']}  {row['spawn_data']}" + ("  ["+"; ".join(facets)+"]" if facets else ""))
            return 0

        if args.command == "bounds-set":
            result=set_asset_bounds(args.database,args.asset_id,(args.x,args.y,args.z),source=args.source,confidence=args.confidence)
            _print_json(result)
            return 0
        if args.command == "bounds-import":
            result=import_bounds(args.database,args.input)
            _print_json(result)
            return 0
        if args.command == "bounds-info":
            result=bounds_info(args.database,args.id)
            _print_json(result)
            return 0
        if args.command == "plan-compile":
            result=compile_plan(load_plan(args.plan),args.catalog)
            if args.output:
                args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
                print(f"Wrote {args.output}")
            else:
                _print_json(result)
            return 0
        if args.command == "plan-preview":
            result=preview_plan(WorldBuilderProject.load(args.file),load_plan(args.plan),args.catalog)
            _print_json(result)
            return 0 if result["valid"] else 2

        if args.command == "assets-build":
            result = build_catalog(args.world_builder_root, args.db)
            if args.json:
                _print_json(result)
            else:
                print(f"Built {result['assets']} assets in {result['database']} ({result['seconds']}s, FTS5={result['fts5']})")
                for key, count in result["counts"].items():
                    print(f"{count:>7}  {key}")
            return 0

        if args.command == "assets-search":
            results = search_catalog(args.database, args.query, category=args.category, variant=args.variant, module_path=args.module, extension=args.ext, limit=args.limit)
            if args.json:
                _print_json([r.to_dict() for r in results])
            else:
                for r in results:
                    print(f"#{r.id:<7} {r.category}/{r.variant:<22} {r.module_path:<24} {r.spawn_data or r.name}")
            return 0 if results else 1

        if args.command == "assets-info":
            result = get_asset(args.database, args.id).to_dict() if args.id is not None else catalog_info(args.database)
            if args.json:
                _print_json(result)
            else:
                _print_json(result)
            return 0

        if args.command == "favorite-add":
            result = add_favorite(args.file, args.path, args.world_builder_root, category=args.category, name=args.name, tags=args.tag, icon=args.icon, category_icon=args.category_icon, backup=not args.no_backup)
            if args.json:
                _print_json(result)
            else:
                print(f"Added {result['favorite']!r} to {result['category']!r}: {result['categoryFile']}")
                if result.get("backup"):
                    print(f"Backup: {result['backup']}")
            return 0

        if args.command == "favorites-list":
            result = list_categories(args.world_builder_root)
            if args.json:
                _print_json(result)
            else:
                for item in result:
                    print(f"{item['count']:>4}  {item['name']}  {item['file']}")
            return 0

        if args.command == "logs":
            result = read_logs(args.game_root, tail=args.tail, issues_only=args.issues_only)
            if args.json:
                _print_json(result)
            else:
                if result["found"] == 0:
                    print(f"No known logs found under {result['gameRoot']}")
                for log in result["logs"]:
                    print(f"== {log['name']} :: {log['path']} ==")
                    for line in log["lines"]:
                        print(line)
            return 0

        if args.command == "live":
            client = LiveBridgeClient(args.rpc_dir)
            if args.action == "ping":
                result = client.ping(timeout=args.timeout)
            elif args.action == "state":
                result = client.state(timeout=args.timeout)
            elif args.action == "player":
                result = client.player(timeout=args.timeout)
            elif args.action == "camera":
                result = client.camera(timeout=args.timeout)
            elif args.action == "selection":
                result = client.selection(timeout=args.timeout, include_data=args.include_data)
            elif args.action == "history":
                result = client.history(timeout=args.timeout)
            elif args.action == "paths":
                result = client.paths(args.query, timeout=args.timeout, limit=args.limit)
            elif args.action == "raycast":
                origin = None
                if args.ray_mode == "custom":
                    if None in (args.origin_x, args.origin_y, args.origin_z):
                        raise ValueError("live raycast --ray-mode custom requires --origin-x/--origin-y/--origin-z")
                    origin = (args.origin_x, args.origin_y, args.origin_z)
                result = client.raycast(
                    mode=args.ray_mode, origin=origin,
                    direction=(args.dir_x, args.dir_y, args.dir_z) if args.ray_mode == "custom" else None,
                    use_physical=not args.no_physical, timeout=args.timeout,
                )
            elif args.action == "select":
                if not args.path:
                    raise ValueError("live select requires at least one --path")
                result = client.select_paths(args.path, apply=args.apply, timeout=args.timeout)
            elif args.action == "move":
                result = client.move_selection(args.x, args.y, args.z, apply=args.apply, timeout=args.timeout)
            elif args.action == "rotate":
                result = client.rotate_selection(args.roll, args.pitch, args.yaw, apply=args.apply, timeout=args.timeout)
            elif args.action == "scale":
                sx, sy, sz = ((args.uniform,) * 3) if args.uniform is not None else (args.scale_x, args.scale_y, args.scale_z)
                pivot_values = (args.pivot_x, args.pivot_y, args.pivot_z)
                if all(v is None for v in pivot_values):
                    pivot = None
                elif any(v is None for v in pivot_values):
                    raise ValueError("live scale requires all of --pivot-x/--pivot-y/--pivot-z or none")
                else:
                    pivot = pivot_values
                result = client.scale_selection(sx, sy, sz, pivot=pivot, allow_partial=args.allow_partial, apply=args.apply, timeout=args.timeout)
            elif args.action == "snap":
                result = client.snap_selection(direction=(args.dir_x, args.dir_y, args.dir_z), apply=args.apply, timeout=max(args.timeout, 8.0))
            elif args.action == "batch":
                if args.ops_file:
                    operations = json.loads(args.ops_file.read_text(encoding="utf-8"))
                elif args.ops_json:
                    operations = json.loads(args.ops_json)
                else:
                    raise ValueError("live batch requires --ops-json or --ops-file")
                if not isinstance(operations, list):
                    raise ValueError("live batch JSON must be an array")
                result = client.batch_transform(operations, apply=args.apply, timeout=max(args.timeout, 15.0))
            elif args.action == "duplicate":
                result = client.duplicate_selection(count=args.count, x=args.x, y=args.y, z=args.z, keep_noderefs=args.keep_noderefs, apply=args.apply, timeout=max(args.timeout, 5.0))
            elif args.action == "surface-scatter":
                result = client.surface_scatter(
                    count=args.count, half_x=args.half_x, half_y=args.half_y, half_z=args.half_z,
                    seed=args.seed, random_yaw=not args.no_random_yaw,
                    direction=(args.dir_x, args.dir_y, args.dir_z), keep_noderefs=args.keep_noderefs,
                    apply=args.apply, timeout=max(args.timeout, 20.0),
                )
            elif args.action == "delete":
                result = client.delete_selection(apply=args.apply, timeout=args.timeout)
            elif args.action == "save":
                result = client.save_roots(apply=args.apply, timeout=max(args.timeout, 5.0))
            elif args.action == "reload":
                if len(args.path) != 1:
                    raise ValueError("live reload requires exactly one --path to a top-level root")
                result = client.reload_root(args.path[0], apply=args.apply, timeout=max(args.timeout, 8.0))
            elif args.action == "undo":
                result = client.undo(apply=args.apply, timeout=args.timeout)
            elif args.action == "redo":
                result = client.redo(apply=args.apply, timeout=args.timeout)
            elif args.action == "spawn-asset":
                if args.catalog is None or not args.asset:
                    raise ValueError("live spawn-asset requires --catalog and --asset")
                asset = resolve_asset(args.catalog, args.asset, module_path=args.module, variant=args.variant)
                node = build_spawnable_node(
                    module_path=asset.module_path,
                    data_type=asset.data_type,
                    spawn_data=asset.spawn_data,
                    template=asset.template,
                    name=args.name,
                    position=(args.x, args.y, args.z),
                    rotation=(args.roll, args.pitch, args.yaw),
                )
                result = client.spawn_serialized(
                    node, parent_path=args.parent, placement=args.placement, distance=args.distance,
                    snap_to_surface=args.snap_to_surface, apply=args.apply, timeout=max(args.timeout, 8.0)
                )
                result.setdefault("asset", asset.to_dict())
            else:
                raise ValueError(f"unknown live action: {args.action}")
            _print_json(result)
            return 0

        project = WorldBuilderProject.load(args.file)

        if args.command == "tree":
            print("\n".join(project.tree_lines(args.modules)))
            return 0

        if args.command == "info":
            if args.path:
                entry = project.get(args.path)
                value = {"path": entry.path, "kind": node_kind(entry.node), "data": entry.node}
            else:
                value = project.stats()
            _print_json(value)
            return 0

        if args.command == "find":
            results = project.find(args.query, case_sensitive=args.case_sensitive)
            if args.json:
                _print_json([{"path": e.path, "kind": node_kind(e.node), "name": e.node.get("name")} for e in results])
            else:
                for e in results:
                    spawn = e.node.get("spawnable", {}) if isinstance(e.node.get("spawnable"), dict) else {}
                    detail = spawn.get("spawnData") or spawn.get("modulePath") or e.node.get("modulePath", "")
                    print(f"{e.path}\t{detail}")
            return 0 if results else 1

        if args.command == "refs":
            defs = project.node_refs()
            known = []
            for entry in project.iter_nodes():
                spawn = entry.node.get("spawnable")
                if not isinstance(spawn, dict):
                    continue
                for ref in iter_known_references(spawn):
                    known.append({"source": entry.path, "field": ref.field, "kind": ref.kind, "value": ref.value})
            value = {"definitions": defs, "references": known}
            if args.json:
                _print_json(value)
            else:
                for ref, owners in sorted(defs.items()):
                    print(f"DEF\t{ref}\t{', '.join(owners)}")
                for ref in known:
                    print(f"REF:{ref['kind']}\t{ref['value']}\t{ref['source']}:{ref['field']}")
            return 0

        if args.command == "validate":
            issues = validate(project)
            if args.json:
                _print_json([issue.to_dict() for issue in issues])
            else:
                if not issues:
                    print("OK: no cp77wb validation issues found.")
                for issue in issues:
                    print(f"{issue.severity.upper():7} {issue.code:32} {issue.path}: {issue.message}")
            errors = any(i.severity == "error" for i in issues)
            warnings = any(i.severity == "warning" for i in issues)
            return 2 if errors or (args.strict and warnings) else 0

        before = project.clone()
        if args.command == "move":
            result = project.translate(args.path, args.x, args.y, args.z)
            print(f"Translated {args.path}: {result}", file=sys.stderr)
            return _persist_or_diff(project, before, args)
        if args.command == "rotate":
            result = project.rotate(args.path, args.roll, args.pitch, args.yaw, pivot=_pivot(args), relative=args.relative)
            print(f"Rotated {args.path}: {result}", file=sys.stderr)
            return _persist_or_diff(project, before, args)
        if args.command == "scale":
            sx, sy, sz = (args.uniform, args.uniform, args.uniform) if args.uniform is not None else (args.x, args.y, args.z)
            result = project.scale(args.path, sx, sy, sz, pivot=_pivot(args), create_scale=args.create_scale)
            print(f"Scaled {args.path}: {result}", file=sys.stderr)
            return _persist_or_diff(project, before, args)
        if args.command == "rename":
            old, new = project.rename(args.path, args.new_name, update_path_refs=not args.no_update_path_refs)
            print(f"Renamed {old} -> {new}", file=sys.stderr)
            return _persist_or_diff(project, before, args)
        if args.command == "set-noderef":
            old, count = project.set_node_ref(args.path, args.node_ref, update_references=not args.no_update_references)
            print(f"NodeRef {old!r} -> {args.node_ref!r}; updated {count} known reference(s)", file=sys.stderr)
            return _persist_or_diff(project, before, args)
        if args.command == "generate-noderef":
            old, new, count = project.generate_node_ref(args.path, prefix=args.prefix, force=args.force, update_references=not args.no_update_references)
            print(f"Generated NodeRef {old!r} -> {new!r}; updated {count} known reference(s)", file=sys.stderr)
            return _persist_or_diff(project, before, args)
        if args.command == "duplicate":
            paths = project.duplicate(args.path, count=args.count, offset=(args.x, args.y, args.z), node_ref_prefix=args.noderef_prefix, keep_node_refs=args.keep_noderefs)
            print(f"Created {len(paths)} copy/copies: {', '.join(paths)}", file=sys.stderr)
            return _persist_or_diff(project, before, args)
        if args.command == "array":
            paths = project.linear_array(args.path, count=args.count, step=(args.x, args.y, args.z), node_ref_prefix=args.noderef_prefix, keep_node_refs=args.keep_noderefs)
            print(f"Linear array total={args.count}; created {len(paths)}: {', '.join(paths)}", file=sys.stderr)
            return _persist_or_diff(project, before, args)
        if args.command == "radial-array":
            paths = project.radial_array(args.path, count=args.count, pivot=_pivot(args), angle=args.angle, rotate_items=not args.no_rotate_items, node_ref_prefix=args.noderef_prefix, keep_node_refs=args.keep_noderefs)
            print(f"Radial array total={args.count}; created {len(paths)}: {', '.join(paths)}", file=sys.stderr)
            return _persist_or_diff(project, before, args)
        if args.command == "align":
            result = project.align(args.paths, axis=args.axis, mode=args.mode, value=args.value)
            print(f"Aligned: {result}", file=sys.stderr)
            return _persist_or_diff(project, before, args)
        if args.command == "distribute":
            result = project.distribute(args.paths, axis=args.axis)
            print(f"Distributed: {result}", file=sys.stderr)
            return _persist_or_diff(project, before, args)
        if args.command == "grid":
            paths = project.grid_array(args.path, counts=(args.count_x, args.count_y, args.count_z), step=(args.step_x, args.step_y, args.step_z), node_ref_prefix=args.noderef_prefix, keep_node_refs=args.keep_noderefs)
            print(f"Grid total={args.count_x * args.count_y * args.count_z}; created {len(paths)}", file=sys.stderr)
            return _persist_or_diff(project, before, args)
        if args.command == "scatter":
            result = project.scatter(args.path, count=args.count, half_extents=(args.half_x, args.half_y, args.half_z), seed=args.seed, random_yaw=not args.no_random_yaw, scale_min=args.scale_min, scale_max=args.scale_max, create_scale=args.create_scale, node_ref_prefix=args.noderef_prefix, keep_node_refs=args.keep_noderefs)
            print(f"Scatter seed={result['seed']}; created {len(result['created'])}", file=sys.stderr)
            return _persist_or_diff(project, before, args)
        if args.command == "path-array":
            points = marker_group_points(project, args.marker_group, curve_samples=args.curve_samples) if args.marker_group else load_points(args.points)
            result = place_along_path(project, args.path, points, spacing=args.spacing, count=args.count, closed=args.closed, orient_to_path=not args.no_orient, yaw_offset=args.yaw_offset, node_ref_prefix=args.noderef_prefix, keep_node_refs=args.keep_noderefs)
            print(f"Path array created {len(result['created'])} copies", file=sys.stderr)
            return _persist_or_diff(project, before, args)
        if args.command == "polygon-scatter":
            result = polygon_scatter(project, args.path, load_points(args.points), count=args.count, seed=args.seed, z=args.z, z_jitter=args.z_jitter, random_yaw=not args.no_random_yaw, scale_min=args.scale_min, scale_max=args.scale_max, create_scale=args.create_scale, node_ref_prefix=args.noderef_prefix, keep_node_refs=args.keep_noderefs)
            print(f"Polygon scatter seed={args.seed}; created {len(result['created'])}", file=sys.stderr)
            return _persist_or_diff(project, before, args)
        if args.command == "volume-scatter":
            result = volume_scatter(project, args.path, shape=args.shape, count=args.count, center=(args.center_x,args.center_y,args.center_z), size=(args.size_x,args.size_y,args.size_z), seed=args.seed, random_yaw=not args.no_random_yaw, node_ref_prefix=args.noderef_prefix, keep_node_refs=args.keep_noderefs)
            print(f"Volume scatter {args.shape}; created {len(result['created'])}", file=sys.stderr)
            return _persist_or_diff(project, before, args)
        if args.command == "asset-pool-spawn":
            result = spawn_weighted_pool(project, args.parent, catalog=args.catalog, pool=load_asset_pool(args.pool), count=args.count, seed=args.seed, center=(args.center_x,args.center_y,args.center_z), half_extents=(args.half_x,args.half_y,args.half_z), random_yaw=not args.no_random_yaw, generate_node_ref=args.generate_noderef, node_ref_prefix=args.noderef_prefix)
            print(f"Weighted pool seed={args.seed}; created {len(result['created'])}", file=sys.stderr)
            return _persist_or_diff(project, before, args)
        if args.command == "rng-create":
            path = project.add_group(args.parent, name=args.name, position=(args.x,args.y,args.z), module_path="modules/classes/editor/randomizedGroup", seed=args.seed, randomization_rule=1 if args.rule == "fixed" else 0, fixed_amount_rule=1 if args.fixed_mode == "total" else 0, fixed_amount_percentage=args.percentage / 100.0, fixed_amount_total=args.total)
            print(f"Created randomized group {path}", file=sys.stderr)
            return _persist_or_diff(project, before, args)
        if args.command == "generate-room":
            result = generate_room(project, args.parent, catalog=args.catalog, wall_asset=args.wall_asset, floor_asset=args.floor_asset, width=args.width, depth=args.depth, segment=args.segment, origin=(args.x,args.y,args.z), name=args.name)
            print(f"Generated room {result['group']} with {len(result['walls'])} walls", file=sys.stderr)
            return _persist_or_diff(project, before, args)
        if args.command == "generate-corridor":
            result = generate_corridor(project, args.parent, catalog=args.catalog, wall_asset=args.wall_asset, floor_asset=args.floor_asset, length=args.length, width=args.width, segment=args.segment, origin=(args.x,args.y,args.z), name=args.name)
            print(f"Generated corridor {result['group']} with {len(result['walls'])} walls", file=sys.stderr)
            return _persist_or_diff(project, before, args)
        if args.command == "generate-market":
            result = generate_market(project, args.parent, catalog=args.catalog, pool=load_asset_pool(args.pool), rows=args.rows, columns=args.columns, spacing_x=args.spacing_x, spacing_y=args.spacing_y, origin=(args.x,args.y,args.z), seed=args.seed, name=args.name)
            print(f"Generated market {result['group']} with {len(result['created'])} stalls", file=sys.stderr)
            return _persist_or_diff(project, before, args)
        if args.command == "device-connect":
            result = connect_device(project, args.source, args.target, device_class_name=args.device_class_name, node_ref_prefix=args.noderef_prefix)
            print(f"Connected {result['source']} -> {result['target']}", file=sys.stderr)
            return _persist_or_diff(project, before, args)
        if args.command == "elevator-wire":
            result = wire_elevator(project, args.elevator, args.terminal, args.marker, floor_names=args.floor_name or None, terminal_class_name=args.terminal_class_name, node_ref_prefix=args.noderef_prefix)
            print(f"Wired elevator {result['elevator']} floors={len(result['floors'])} instanceDataPatched={result['instanceDataPatched']}", file=sys.stderr)
            return _persist_or_diff(project, before, args)
        if args.command == "collisions":
            result=scan_project_collisions(project,args.catalog,clearance=args.clearance,include_heuristic=not args.explicit_only)
            _print_json(result)
            return 0
        if args.command == "plan-apply":
            compiled=compile_plan(load_plan(args.plan),args.catalog)
            result=apply_compiled_plan(project,compiled,args.catalog)
            print(f"Applied plan {compiled['name']}: {result['count']} objects under {result['group']}",file=sys.stderr)
            return _persist_or_diff(project,before,args)
        if args.command == "generate-fence":
            points=marker_group_points(project,args.marker_group,curve_samples=args.curve_samples) if args.marker_group else load_points(args.points)
            result=generate_fence(project,args.parent,catalog=args.catalog,segment_asset=args.segment_asset,post_asset=args.post_asset,points=points,spacing=args.spacing,name=args.name,yaw_offset=args.yaw_offset)
            print(f"Generated fence {result['group']} segments={len(result['segments'])} posts={len(result['posts'])}",file=sys.stderr)
            return _persist_or_diff(project,before,args)
        if args.command == "generate-road":
            points=marker_group_points(project,args.marker_group,curve_samples=args.curve_samples) if args.marker_group else load_points(args.points)
            result=generate_road(project,args.parent,catalog=args.catalog,tile_asset=args.tile_asset,edge_asset=args.edge_asset,points=points,spacing=args.spacing,width=args.width,name=args.name,yaw_offset=args.yaw_offset)
            print(f"Generated road {result['group']} tiles={len(result['tiles'])} edges={len(result['edges'])}",file=sys.stderr)
            return _persist_or_diff(project,before,args)
        if args.command == "generate-cable":
            points=marker_group_points(project,args.marker_group,curve_samples=args.curve_samples) if args.marker_group else load_points(args.points)
            result=generate_cable_chain(project,args.parent,catalog=args.catalog,segment_asset=args.segment_asset,points=points,spacing=args.spacing,name=args.name,yaw_offset=args.yaw_offset)
            print(f"Generated cable {result['group']} segments={len(result['segments'])}",file=sys.stderr)
            return _persist_or_diff(project,before,args)
        if args.command == "spawn-asset":
            asset = resolve_asset(args.catalog, args.asset, module_path=args.module, variant=args.variant)
            path = project.add_spawnable(args.parent, module_path=asset.module_path, data_type=asset.data_type, spawn_data=asset.spawn_data, template=asset.template, name=args.name, position=(args.x, args.y, args.z), rotation=(args.roll, args.pitch, args.yaw), generate_node_ref=args.generate_noderef, node_ref_prefix=args.noderef_prefix)
            print(f"Inserted asset #{asset.id} {asset.spawn_data or asset.name} -> {path}", file=sys.stderr)
            return _persist_or_diff(project, before, args)
        if args.command == "refresh-area-cache":
            count = project.refresh_area_marker_caches()
            print(f"Refreshed {count} area cache(s)", file=sys.stderr)
            return _persist_or_diff(project, before, args)

        return 2
    except (Cp77wbError, ValueError) as exc:
        print(f"cp77wb: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
