# cp77wb CLI

## Read-only project commands

```bash
cp77wb tree BUILD.json --modules
cp77wb info BUILD.json
cp77wb info BUILD.json /Build/Interior/Lamp01
cp77wb find BUILD.json "base\\environment"
cp77wb refs BUILD.json
cp77wb validate BUILD.json
```

`refs` reports both NodeRef definitions and known fields that point to paths/NodeRefs.

## Naming utility

```bash
cp77wb sanitize-name "Floor 01/West"
# Floor_01_West
```

This follows World Builder's `utils.createFileName()` replacement set.

## Saved-build mutation safety

Saved-build mutation commands are dry-run by default and print a unified JSON diff.

```bash
cp77wb move BUILD.json /Build/Floor01 --z 4.2
```

Persist:

```bash
cp77wb move BUILD.json /Build/Floor01 --z 4.2 --write
```

Or save a copy:

```bash
cp77wb move BUILD.json /Build/Floor01 --z 4.2 --output BUILD-test.json
```

Overwrites create `.cp77wb-backups/<file>.<UTC timestamp>.bak`.

## Geometry/editing commands

### `move`, `rotate`, `scale`

```bash
cp77wb move BUILD.json /Build/Room --x 2 --z 0.25
cp77wb rotate BUILD.json /Build/Room --yaw 90
cp77wb scale BUILD.json /Build/Room --uniform 1.2
```

Groups rotate/scale descendants around their saved origin unless an explicit pivot is supplied. For a single object with no `spawnable.scale`, `scale` refuses to invent one unless `--create-scale` is given.

### `rename`, `generate-noderef`, `set-noderef`

`rename` uses World Builder filename sanitization and repairs known path references. `generate-noderef` follows the World Builder NodeRef construction pattern, and `set-noderef` rewrites known references to the old value.

```bash
cp77wb generate-noderef BUILD.json /Build/Devices/Door --prefix my_mod
cp77wb set-noderef BUILD.json /Build/Devices/Door '$/my_mod/devices/#build_door' --write
```

### `duplicate`, `array`, `radial-array`

`duplicate --count` means new copies. `array --count` and `radial-array --count` mean total count including the source.

```bash
cp77wb duplicate BUILD.json /Build/Pillar --count 5 --x 3
cp77wb array BUILD.json /Build/Railing --count 12 --x 2.5
cp77wb radial-array BUILD.json /Build/Lamp --count 8 \
  --pivot-x 0 --pivot-y 0 --pivot-z 0
```

### `grid`

Create a rectangular 3D array. Each axis count includes the source cell `(0,0,0)`.

```bash
cp77wb grid BUILD.json /Build/Pillar \
  --count-x 8 --count-y 4 --count-z 1 \
  --step-x 3 --step-y 3
```

### `scatter`

Create deterministic offline box scatter. `--count` includes the source.

```bash
cp77wb scatter BUILD.json /Build/TrashBag \
  --count 30 --half-x 12 --half-y 4 --seed 2077
```

Optional yaw/scale randomization is deterministic for a given seed. This is geometry-only; it does not raycast against the running game.

### `align`, `distribute`

```bash
cp77wb align BUILD.json z /Build/A /Build/B /Build/C --mode max
cp77wb distribute BUILD.json x /Build/A /Build/B /Build/C /Build/D
```

## Asset catalog commands (v0.3)

### `assets-build`

Scan the installed World Builder `data/spawnables` tree into a local SQLite/FTS5 catalog:

```bash
cp77wb assets-build /path/to/entSpawner
```

Choose a custom DB location:

```bash
cp77wb assets-build /path/to/entSpawner --db ~/.cache/cp77wb/assets.sqlite3
```

### `assets-search`

```bash
cp77wb assets-search ~/.cache/cp77wb/assets.sqlite3 "industrial pipe" --variant Mesh --limit 10
cp77wb assets-search ~/.cache/cp77wb/assets.sqlite3 "neon sign"
```

Every result has a stable numeric selector such as `#75857` for that catalog build.

### `assets-info`

```bash
cp77wb assets-info ~/.cache/cp77wb/assets.sqlite3
cp77wb assets-info ~/.cache/cp77wb/assets.sqlite3 '#75857'
```

### `spawn-asset`

Insert the selected indexed asset under a saved-build group:

```bash
cp77wb spawn-asset BUILD.json /Build/Interior '#75857' \
  --catalog ~/.cache/cp77wb/assets.sqlite3 \
  --x 100 --y 200 --z 5
```

This is a dry run until `--write` is supplied. Ambiguous text selectors fail instead of silently selecting one resource.

## Native World Builder Favorites / prefabs

Create a reusable Favorite from a saved object/group:

```bash
cp77wb favorite-add BUILD.json /Build/Market/StallA /path/to/entSpawner \
  --category "Claude Prefabs" --tag market --tag stall
```

List Favorite categories:

```bash
cp77wb favorites-list /path/to/entSpawner
```

`favorite-add` modifies World Builder's Favorite data by design and backs up an existing category file before replacing it.

## Optional live bridge (v0.5)

With `extras/cp77wb_bridge` installed in CET:

```bash
RPC=/path/to/cp77wb_bridge/rpc
cp77wb live "$RPC" ping
cp77wb live "$RPC" history
cp77wb live "$RPC" state
cp77wb live "$RPC" player
cp77wb live "$RPC" camera
cp77wb live "$RPC" selection --include-data
cp77wb live "$RPC" raycast --ray-mode camera
```

The bridge refuses writes if it cannot prove access to World Builder's active history singleton. v0.5 scene queries also verify the active editor singleton.

### Live transform and history

Every mutation previews by default and needs `--apply` to execute.

```bash
cp77wb live "$RPC" paths --query light --limit 20
cp77wb live "$RPC" select --path /Build/Lights/Lamp01 --apply
cp77wb live "$RPC" move --x 1 --apply
cp77wb live "$RPC" rotate --yaw 15 --apply
cp77wb live "$RPC" scale --uniform 1.1 --apply
cp77wb live "$RPC" snap --apply
cp77wb live "$RPC" undo --apply
cp77wb live "$RPC" redo --apply
```

Non-uniform live scale uses `--scale-x`, `--scale-y`, `--scale-z`. An explicit pivot uses all of `--pivot-x`, `--pivot-y`, `--pivot-z`.

### One-undo batch

```bash
cp77wb live "$RPC" batch --ops-json '[{"type":"move","z":1},{"type":"rotate","yaw":15},{"type":"snap"}]
cp77wb live "$RPC" batch --ops-file operations.json --apply
```

Supported batch operation types are `move`, `rotate`, `scale`, and `snap`.

### Reference-aware live duplicate

```bash
cp77wb live "$RPC" duplicate --count 3 --x 2 --apply
```

NodeRefs and known internal references are remapped by default. `--keep-noderefs` is an explicit unsafe override.

### Surface-aware scatter

```bash
cp77wb live "$RPC" surface-scatter \
  --count 30 --half-x 12 --half-y 5 --seed 2077 --apply
```

Exactly one root element must be selected. Clones are projected with World Builder's native `dropToSurface()`.

### Live indexed asset spawn

```bash
cp77wb live "$RPC" spawn-asset \
  --catalog ~/.cache/cp77wb/assets.sqlite3 \
  --asset '#75857' --placement camera --distance 4 \
  --snap-to-surface --apply
```

### Save/reload active roots

```bash
cp77wb live "$RPC" save --apply
cp77wb live "$RPC" reload --path /Build --apply
```

Reload supports a top-level saveable root only.

## Log collection

```bash
cp77wb logs "/path/to/Cyberpunk 2077" --tail 200
cp77wb logs "/path/to/Cyberpunk 2077" --issues-only --json
```

The collector recognizes World Builder, CET, RED4ext, redscript, ArchiveXL and TweakXL logs when present.

## Area cache

```bash
cp77wb refresh-area-cache BUILD.json --write
```

Reconstructs saved area marker snapshots from resolvable `outlinePath` groups.

## v0.7 intelligence/planning commands

```text
semantic-build DATABASE [--overrides FILE]
semantic-search DATABASE QUERY [--role ... --style ... --material ... --condition ...]
bounds-set DATABASE ID --x X --y Y --z Z
bounds-import DATABASE JSON
bounds-info DATABASE [--id ID]
collisions BUILD --catalog DATABASE [--clearance N] [--explicit-only]
plan-compile PLAN --catalog DATABASE [--output FILE]
plan-preview BUILD PLAN --catalog DATABASE
plan-apply BUILD PLAN --catalog DATABASE [--write]
generate-fence BUILD PARENT --catalog DATABASE --segment-asset ID (--points JSON|--marker-group PATH) --spacing N
generate-road BUILD PARENT --catalog DATABASE --tile-asset ID (--points JSON|--marker-group PATH) --spacing N --width N
generate-cable BUILD PARENT --catalog DATABASE --segment-asset ID (--points JSON|--marker-group PATH) --spacing N
```

See `v07-ai-planner.md` for plan schema and safety semantics.


## v0.8 build commands

`export-inspect`, `export-xl`, `build-prepare`, `build-status`, `build-backends`, `build-pack`, `build-package`, `build-verify`, and `build-deploy` implement the preview-first World Builder export/build pipeline. `build-pack` needs `--run` for subprocess execution; `build-deploy` needs `--apply`, and conflicting files additionally need `--overwrite`.


## v0.9 native conversion commands

```text
native-template-plan EXPORT OUTPUT [--resource-name NAME]
native-template-verify EXPORT BUNDLE
native-json EXPORT BUNDLE OUTPUT
native-preflight [--cli PATH] [--timeout SECONDS]
native-convert NATIVE_JSON OUTPUT [--cli PATH] [--run] [--timeout SECONDS]
native-import EXPORT BUNDLE OUTPUT [--cli PATH] [--run] [--timeout SECONDS] [--clean-json]
native-verify OUTPUT [--target RELPATH ...] [--allow-non-cr2w]
build-native-import WORKSPACE BUNDLE [--cli PATH] [--run] [--timeout SECONDS] [--clean-json]
```

`native-template-plan` generates the one-time WolvenKit WScript needed to capture default RED JSON templates. `native-preflight` probes the actual CLI before the backend is treated as usable. `native-convert`, `native-import`, and `build-native-import` are preview-only until `--run`. Successful conversion is verified by expected output paths and `CR2W` magic, not only process exit status.

See `v09-native-conversion.md`.

## v1.0 WolvenKit worker

```bash
cp77wb worker-build [--source PROJECT] [--output DIR] [--dotnet PATH] [--run]
cp77wb worker-preflight [--worker PATH]
cp77wb worker-bundle EXPORT OUTPUT [--worker PATH] [--run]
cp77wb worker-import EXPORT OUTPUT [--worker PATH] [--run] [--clean-json]
cp77wb build-worker-import WORKSPACE [--worker PATH] [--run] [--clean-json]
```

All build/import commands are previews unless `--run` is supplied. `worker-preflight` is the authority for whether the worker is usable; package/version presence alone is insufficient.
