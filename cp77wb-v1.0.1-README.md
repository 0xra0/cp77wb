# cp77wb

`cp77wb` is an external, non-invasive automation layer for Cyberpunk 2077 **World Builder**. World Builder remains the visual/in-game editor; cp77wb adds Linux-native saved-build editing, real resource discovery, procedural construction, Claude Code MCP tools, validation and an optional history-safe CET bridge.

The project does not redistribute or fork World Builder. Saved-build mutations preserve unknown JSON fields and are dry-run by default.

## v1.0.1 — worker compatibility diagnostics

v1.0.1 hardens the v1.0 preferred native conversion backend a small .NET 10 worker instead of a one-time WScript template bootstrap. The worker references WolvenKit 9.0.1 packages, discovers the current RED JSON/CR2W services at runtime, and must pass its own real round-trip self-test before cp77wb marks it authoritative.

- bundled `extras/cp77wb_wkit_worker` .NET 10 project;
- `worker-inspect` reports discovered WolvenKit assemblies, serializer/writer signatures and a stable API-profile fingerprint;
- `worker-doctor` captures .NET SDK/runtime information, preflight/inspect results and can create a shareable diagnostic ZIP;
- `worker-build --log-file` preserves the complete `dotnet publish` output for later debugging;
- `worker-build` for guarded `dotnet publish`;
- `worker-preflight` requiring successful default RED instance serialization **and** real JSON→CR2W output;
- `worker-bundle` for exact RED default templates without WScript capture;
- `worker-import` and `build-worker-import` for direct World Builder export conversion;
- independent `CR2W` magic verification and normal `build-status` remain mandatory;
- v0.9 template+CLI and upstream World Builder WScript import remain supported fallbacks;
- **94 unique Claude Code MCP tools**;
- **107 automated tests**.

The worker is intentionally capability-gated. Having .NET 10 or WolvenKit packages installed is not enough: `worker-preflight` must report `authoritativeNative: true` on the actual machine before cp77wb uses that backend.

## Install

Python 3.11+ is required. The included installer has no pip/setuptools/runtime package dependency:

```bash
unzip cp77wb-v1.0.1.zip
cd cp77wb
./install.sh --prefix "$HOME/.local"
cp77wb --version
```

Or run directly:

```bash
./bin/cp77wb --version
./bin/cp77wb validate /path/to/Build.json
./bin/cp77wb-mcp
```

## Deferred real-worker test

You can install/use v1.0.1 now and run the real .NET/WolvenKit compatibility test later. When ready:

```bash
cp77wb worker-build --run --log-file ~/cp77wb-worker-build.log
cp77wb worker-inspect --worker ~/.local/lib/cp77wb-tools/extras/cp77wb_wkit_worker/publish/cp77wb-wkit-worker
cp77wb worker-preflight --worker ~/.local/lib/cp77wb-tools/extras/cp77wb_wkit_worker/publish/cp77wb-wkit-worker
cp77wb worker-doctor --worker ~/.local/lib/cp77wb-tools/extras/cp77wb_wkit_worker/publish/cp77wb-wkit-worker --output ~/cp77wb-worker-doctor.zip
```

If compilation or runtime reflection fails, the publish log plus doctor ZIP are intended to contain the actionable API/runtime evidence for a focused compatibility patch. The support bundle contains diagnostics and worker source, not your World Builder builds or game files.

## World Builder export → mod build

Inspect an export before handing it to WolvenKit:

```bash
cp77wb export-inspect /path/to/entSpawner/export/my_project_exported.json
```

Prepare a WolvenKit project using the exact importer shipped with your World Builder installation/source:

```bash
cp77wb build-prepare \
  /path/to/entSpawner/export/my_project_exported.json \
  ~/cp77-projects \
  --world-builder-root /path/to/entSpawner
```

Then run the generated `automation/import_object_spawner_<name>.wscript` in WolvenKit Script Manager. cp77wb checks the result:

```bash
cp77wb build-status ~/cp77-projects/my_project
```

After `importComplete` becomes true, preview packing:

```bash
cp77wb build-pack ~/cp77-projects/my_project --cli cp77tools
```

Execute only when the command looks correct:

```bash
cp77wb build-pack ~/cp77-projects/my_project --cli cp77tools --run
```

Assemble a distributable game-layout folder and ZIP:

```bash
cp77wb build-package ~/cp77-projects/my_project \
  --archive ~/cp77-projects/my_project/packed/archive/pc/mod/my_project.archive \
  --output ~/cp77-projects/my_project/dist \
  --zip ~/cp77-projects/my_project/my_project.zip
```

Deployment is a preview unless `--apply` is supplied, and conflicting installed files require `--overwrite` (with timestamped backups):

```bash
cp77wb build-deploy ~/cp77-projects/my_project/dist "/path/to/Cyberpunk 2077"
```

See `docs/v09-native-conversion.md` for the v0.9 native backend and `docs/v08-build-orchestration.md` for the surrounding packaging/deployment pipeline.


## v1.0 preferred native worker

Build the bundled worker with your .NET 10 SDK:

```bash
cp77wb worker-build --run
```

Or build it directly:

```bash
./extras/cp77wb_wkit_worker/build.sh
```

Then verify the **actual** worker/runtime combination:

```bash
cp77wb worker-preflight \
  --worker ./extras/cp77wb_wkit_worker/publish/cp77wb-wkit-worker
```

Only a response containing both:

```text
ready: true
authoritativeNative: true
```

enables the preferred backend. Preview a conversion:

```bash
cp77wb worker-import MyWorld_exported.json ./native-out \
  --worker /path/to/cp77wb-wkit-worker
```

Execute only after review:

```bash
cp77wb worker-import MyWorld_exported.json ./native-out \
  --worker /path/to/cp77wb-wkit-worker --run
```

For prepared build workspaces use `build-worker-import`. If worker preflight fails, use the v0.9 template+CLI path below or the exact World Builder importer generated by `build-prepare`.

## v0.9 native Object Spawner import

`build-prepare` now also writes a capture script for the RED default instances needed by that export. Run it once in a WScript-capable WolvenKit session, then verify the resulting template bundle:

```bash
cp77wb native-template-verify \
  /path/to/my_project_exported.json \
  /path/to/cp77wb_templates_my_project.json
```

Probe the exact CLI binary you intend to use on Linux:

```bash
cp77wb native-preflight --cli /path/to/cp77tools
```

Preview the workspace import:

```bash
cp77wb build-native-import \
  ~/cp77-projects/my_project \
  /path/to/cp77wb_templates_my_project.json \
  --cli /path/to/cp77tools
```

Only after the preview succeeds, run conversion:

```bash
cp77wb build-native-import \
  ~/cp77-projects/my_project \
  /path/to/cp77wb_templates_my_project.json \
  --cli /path/to/cp77tools \
  --run
```

cp77wb creates WolvenKit JSON by mirroring the World Builder importer, invokes `convert deserialize`, and rejects the result unless every expected output exists and has CR2W magic. `build-status` must still pass before archive packing. If preflight fails, use the generated upstream `import_object_spawner_*.wscript` fallback.

## Build the real World Builder asset catalog

```bash
cp77wb assets-build \
  "/path/to/Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods/entSpawner"

cp77wb assets-search \
  "/path/to/entSpawner/.cp77wb/assets.sqlite3" \
  "arasaka wall" --variant Mesh
```

Search results use deterministic IDs such as `#75857`. Prefer IDs in automated workflows so Claude cannot silently choose a different result.

## Procedural path placement

Use a World Builder marker/spline group directly:

```bash
cp77wb path-array Build.json /Build/Lamp \
  --marker-group /Build/PathMarkers \
  --spacing 2.5 \
  --curve-samples 12
```

If spline markers contain `tangentIn` / `tangentOut`, cp77wb samples the same cubic-Bezier representation World Builder uses for curved spline previews before spacing objects along the curve.

Or supply an arbitrary polyline:

```bash
cp77wb path-array Build.json /Build/Railing \
  --points '[[0,0,0],[10,0,0],[15,5,1]]' \
  --spacing 1.5 \
  --yaw-offset 90
```

Add `--write` only after reviewing the diff.

## Polygon and volume scatter

```bash
cp77wb polygon-scatter Build.json /Build/TrashBag \
  --points '[[0,0,0],[12,0,0],[10,8,0],[2,7,0]]' \
  --count 30 --seed 2077
```

```bash
cp77wb volume-scatter Build.json /Build/Particle \
  --shape cylinder --count 50 \
  --center-x 100 --center-y 200 --center-z 20 \
  --size-x 8 --size-z 4 --seed 42
```

Offline geometry has no game collision knowledge; use the v0.5 live `surface-scatter`/`snap` commands when projection onto actual REDengine surfaces is required.

## Weighted asset pools

Example `pool.json`:

```json
{
  "entries": [
    {"asset":"#1201", "weight":4, "name":"Common Stall"},
    {"asset":"#1770", "weight":1, "name":"Rare Stall"}
  ]
}
```

Then:

```bash
cp77wb asset-pool-spawn Build.json /Build/Market \
  --catalog /path/to/assets.sqlite3 \
  --pool pool.json --count 20 --seed 77 \
  --half-x 12 --half-y 6
```

Every entry is resolved against the actual local asset catalog before the build is changed.

## Native Randomized Nested Groups

```bash
cp77wb rng-create Build.json /Build "Trash RNG" \
  --seed 42 \
  --rule fixed \
  --fixed-mode total \
  --total 2
```

This creates `modules/classes/editor/randomizedGroup` with World Builder's native randomization fields, so it remains editable/randomizable in WB rather than being baked into a one-time cp77wb result.

## High-level generators

Room shell:

```bash
cp77wb generate-room Build.json /Build \
  --catalog /path/to/assets.sqlite3 \
  --wall-asset '#1234' \
  --floor-asset '#4321' \
  --width 12 --depth 8 --segment 2
```

Corridor:

```bash
cp77wb generate-corridor Build.json /Build \
  --catalog /path/to/assets.sqlite3 \
  --wall-asset '#1234' \
  --length 30 --width 4 --segment 2
```

Market from a weighted pool:

```bash
cp77wb generate-market Build.json /Build \
  --catalog /path/to/assets.sqlite3 \
  --pool market-pool.json \
  --rows 3 --columns 6 \
  --spacing-x 3 --spacing-y 5 --seed 2077
```

These generators intentionally require explicit segment/spacing information rather than pretending cp77wb knows every mesh's architectural dimensions.

## Parameterized prefab/build JSON

Template:

```json
{
  "__parameters__": {"name":"Default Room", "height":3.0},
  "name":"${name}",
  "height":"${height}",
  "label":"Generated ${name}"
}
```

Render:

```bash
cp77wb prefab-render template.json \
  --set name="Lobby" \
  --set height=4.2 \
  --output lobby.json
```

A placeholder that occupies the whole JSON string preserves the supplied JSON type; embedded placeholders are string substitutions.

## Device and elevator helpers

Connect one device to another:

```bash
cp77wb device-connect Build.json \
  /Build/SecuritySystem \
  /Build/SecurityArea \
  --device-class-name SecurityAreaControllerPS
```

Wire an existing elevator setup:

```bash
cp77wb elevator-wire Build.json /Build/Lift \
  --terminal /Build/Floor0Terminal --marker /Build/Floor0Marker --floor-name 'LocKey#100' \
  --terminal /Build/Floor1Terminal --marker /Build/Floor1Marker --floor-name 'LocKey#101' \
  --noderef-prefix my_mod/elevator
```

The helper generates missing unique NodeRefs, links the elevator to terminals in list order, sets terminals persistent, and patches `elevatorFloorSetup.floorMarker` / `floorDisplayName` if those structures exist in the saved `defaultComponentData`. Missing instance-data schemas are reported rather than fabricated.

## World Builder compatibility scan

```bash
cp77wb compat-scan "/path/to/entSpawner"
```

Compare a build against that exact installation/source tree:

```bash
cp77wb compat-scan "/path/to/entSpawner" --project Build.json
```

The scan reports:

- World Builder `ModVersion`;
- required Codeware / ArchiveXL versions;
- exporter script minimum version;
- RNG/scattered-group/spline/history/exporter feature presence;
- editor/spawn module counts;
- unknown module paths used by the selected build;
- SHA-256 fingerprints for schema-critical World Builder Lua files.

That output can be stored with a project or CI job to detect upstream drift before Claude edits a build created against a different World Builder version.

## Semantic asset intelligence

Build the normal asset catalog, then derive local semantic facets:

```bash
cp77wb semantic-build /path/to/entSpawner/.cp77wb/assets.sqlite3
cp77wb semantic-search /path/to/entSpawner/.cp77wb/assets.sqlite3 \
  "arasaka industrial wall" --role wall --style arasaka --variant Mesh
```

The semantic layer is local and deterministic; it does not call an embedding/API service. Exact `#asset-id` remains the preferred stable identifier.

## Bounds and collision planning

```bash
cp77wb bounds-set assets.sqlite3 40238 --x 3 --y .25 --z 3.2 --source measured
cp77wb collisions Build.json --catalog assets.sqlite3 --clearance .2
```

When exact bounds are unavailable, cp77wb can use low-confidence role heuristics. Collision results involving those bounds are marked approximate. This is not a replacement for REDengine live scene raycasts.

## Construction plans

A `cp77wb-plan/1` file can describe a room, door openings, exact or explicitly auto-selected semantic assets, fixed placements, and collision-aware deterministic scatter.

```bash
cp77wb plan-compile examples/construction-plan.json --catalog assets.sqlite3
cp77wb plan-preview Build.json examples/construction-plan.json --catalog assets.sqlite3
cp77wb plan-apply Build.json examples/construction-plan.json --catalog assets.sqlite3
# after reviewing the diff:
cp77wb plan-apply Build.json examples/construction-plan.json --catalog assets.sqlite3 --write
```

`plan-preview` applies the compiled operations to an in-memory clone, runs normal World Builder validation, and reports approximate collisions with the existing build. Semantic selection inside plans requires explicit `autoSelect:true`; otherwise an exact indexed asset is required.

Path structures are also available:

```bash
cp77wb generate-fence Build.json /Build --catalog assets.sqlite3 \
  --segment-asset '#1001' --post-asset '#1002' \
  --marker-group /Build/FencePath --spacing 2

cp77wb generate-road Build.json /Build --catalog assets.sqlite3 \
  --tile-asset '#2001' --edge-asset '#2002' \
  --points '[[0,0,0],[20,0,0],[30,10,0]]' --spacing 2 --width 6
```

See `docs/v07-ai-planner.md` for the complete schema and agent workflow.

## Claude Code MCP

```bash
claude mcp add cp77wb -- cp77wb-mcp
```

v1.0 exposes **92 unique tools**. In addition to the v0.8 build tools, v0.9 adds:

```text
wb_semantic_build
wb_semantic_search
wb_bounds_set
wb_bounds_import
wb_bounds_info
wb_collisions
wb_plan_compile
wb_plan_preview
wb_plan_apply
wb_generate_fence
wb_generate_road
wb_generate_cable

wb_export_inspect
wb_export_xl
wb_build_prepare
wb_build_status
wb_build_backends
wb_build_pack
wb_build_package
wb_build_verify
wb_build_deploy
wb_build_doctor

wb_native_template_plan
wb_native_template_verify
wb_native_json
wb_native_preflight
wb_native_convert
wb_native_import
wb_native_verify
wb_build_native_import
```

Saved-build mutations still require `write=true`. Live mutations still require `apply=true` and World Builder's verified active history singleton.

## Optional CET live bridge

The v0.5 `cp77wb-live/3` bridge is included unchanged. Install/upgrade it with:

```bash
./extras/install-cet-bridge.sh \
  "/path/to/Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods"
```

Then verify in-game before applying live edits:

```bash
RPC="/path/to/Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods/cp77wb_bridge/rpc"
cp77wb live "$RPC" ping
cp77wb live "$RPC" history
cp77wb live "$RPC" raycast --ray-mode camera
```

## Safety model

- offline mutation is dry-run unless `--write` or `--output` is supplied;
- asset queries used for spawning must resolve uniquely;
- generated duplicate NodeRefs are remapped by default;
- procedural randomization is deterministic when a seed is supplied;
- elevator instance-data is patched only when the saved schema exists;
- compatibility scans expose unknown WB modules instead of guessing them;
- live writes remain explicit `--apply` operations guarded by WB history identity;
- unknown saved-build fields are preserved;
- writes remain atomic with backups when overwriting existing saved builds.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

v0.9 contains **92 tests** covering the offline project model, references, asset/semantic indexes, explicit/heuristic bounds, oriented collision checks, construction planning, Favorites, live-RPC client, MCP, logs, procedural placement/scatter, path structures, weighted pools/generators, native RNG groups, device/elevator helpers, compatibility scanning and parameter rendering.

## Documentation

Start with [`docs/index.md`](docs/index.md). v0.9 native conversion is documented in [`docs/v09-native-conversion.md`](docs/v09-native-conversion.md); v0.8 packaging/deployment remains in [`docs/v08-build-orchestration.md`](docs/v08-build-orchestration.md).
