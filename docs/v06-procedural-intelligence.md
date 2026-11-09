# v0.6 procedural intelligence and compatibility

v0.6 moves cp77wb from transform primitives into reusable procedural construction while keeping deterministic output and World Builder-native data structures.

## Path and spline placement

`path-array` accepts either a JSON polyline or a World Builder marker group. Direct marker order is hierarchy order. If marker spawnables contain non-zero `tangentIn`/`tangentOut`, cp77wb first samples cubic Bezier segments and then performs equal-distance polyline sampling.

The source object/group is treated as a template and is not moved. Each generated copy goes through cp77wb's normal duplicate path, so existing NodeRefs inside the template are regenerated and known internal references are rewritten unless `--keep-noderefs` is explicitly requested.

## Polygon and volume constraints

`polygon-scatter` uses deterministic seeded rejection sampling inside an arbitrary XY polygon. `volume-scatter` supports box, cylinder and sphere/ellipsoid volumes. These are offline constraints only: use the live bridge when collision or surface projection is required.

## Weighted asset pools

Pools are JSON arrays (or `{ "entries": [...] }`) where every entry has an exact/query-resolved `asset` and a positive `weight`. The pool is resolved against the local SQLite asset catalog before any mutation occurs. A fixed seed makes both asset choice and position reproducible.

## Native Randomized Groups

`rng-create` creates `modules/classes/editor/randomizedGroup`, including WB's `seed`, `randomizationRule`, `fixedAmountRule`, `fixedAmountPercentage` and `fixedAmountTotal` fields. This is deliberately different from baking a random selection into ordinary groups: World Builder keeps control over runtime/editor randomization.

## Layout generators

`generate-room`, `generate-corridor` and `generate-market` are conservative convenience layers built entirely from verified catalog assets and ordinary WB groups. They require explicit spacing/segment lengths because cp77wb does not infer architectural dimensions from mesh geometry offline.

## Parameterized JSON

`prefab-render` provides typed `${parameter}` replacement for JSON build/prefab templates. Defaults can be stored in a top-level `__parameters__` object. If a JSON string is exactly `${value}`, the supplied parameter keeps its JSON type; substitutions inside longer strings are converted to text.

## Device helpers

`device-connect` creates a target NodeRef when needed and adds the standard saved-build `deviceConnections` entry.

`elevator-wire` follows the native World Builder setup model: elevator plus ordered floor terminals plus static markers. It generates missing NodeRefs, makes terminals persistent, adds elevator-to-terminal connections and searches each terminal's saved `defaultComponentData` for `elevatorFloorSetup`. When found, the relevant default component subtree is copied into `instanceDataChanges` before changing `floorMarker` and `floorDisplayName`. If no such schema exists, the terminal is reported as unresolved rather than cp77wb inventing a component ID.

## Compatibility scanner

`compat-scan` treats the installed World Builder source tree as the authority. It extracts the current mod/dependency versions, inventories editor/spawn module paths, detects major features and fingerprints schema-critical Lua files. With `--project`, it reports any group/spawn module paths used by the build that are absent from that exact World Builder tree.

This is intended for Claude Code startup checks and CI: scan first, then decide whether it is safe to mutate a saved build with the currently installed World Builder.
