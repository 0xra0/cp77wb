# Changelog

## 1.0.1

- Fix the full static-analysis report from the real validation run: Ruff 476 findings, Pyright 54 type errors, and 5 C# compile errors are addressed in source rather than suppressed.
- Expand multi-statement Python lines into normal statements and remove all Ruff-reported unused imports/variables.
- Tighten Optional narrowing and public geometry parameter types for Pyright, including Sequence-based point/polygon APIs.
- Fix the .NET worker top-level constant scope so `dotnet build` no longer hits CS8801.
- Add strict `static-check.sh`; missing Ruff, Pyright, or dotnet is now a validation failure, and unit discovery explicitly uses `-s tests`.
- Add `worker-inspect` to expose discovered WolvenKit assemblies, serializer/writer method signatures and an API-profile SHA-256 fingerprint without requiring the conversion self-test to pass.
- Add `worker-doctor` to collect Python/platform information, `dotnet --info`, SDK/runtime inventories, worker inspect/preflight data and optionally produce a support ZIP.
- Add `worker-build --log-file` to preserve complete `dotnet publish` output on success or failure.
- Include the API-profile fingerprint in successful worker preflight results.
- Expand worker `inspect` output with assembly versions/locations, RED type count, serializer methods, CR2W writer constructors/methods and runtime architecture.
- Add MCP tools `wb_worker_inspect` and `wb_worker_doctor`; total MCP tool count is 94.
- Expand automated suite from 100 to 107 tests.
- Keep the real Void Linux/.NET/WolvenKit execution test explicitly deferred; v0.9 template+CLI and upstream WScript fallbacks remain unchanged.

## 1.0.0

- Add bundled .NET 10 `cp77wb-wkit-worker` source pinned to WolvenKit 9.0.1 packages.
- Add versioned `cp77wb-wkit-worker/1` JSON protocol and authoritative runtime self-test.
- Add `worker-build`, `worker-preflight`, `worker-bundle`, `worker-import`, and `build-worker-import`.
- Eliminate mandatory WScript template capture when the worker self-test verifies both RED default-instance JSON serialization and JSON→CR2W writing.
- Keep v0.9 template-bundle + WolvenKit CLI conversion and the exact upstream WScript importer as fallbacks.
- Require independent CR2W-magic verification for worker outputs and ordinary `build-status` before packing.
- Report worker readiness separately in build backend capability scans.
- Install the worker source alongside cp77wb so it can be built after a dependency-free Python install.
- Expand MCP from 87 to 92 unique tools.
- Expand automated suite from 92 to 100 tests.

## 0.9.0

- Add versioned WolvenKit RED default-template bundles (`cp77wb-wkit-templates/1`).
- Generate a capture WScript for the exact RED classes required by each World Builder export.
- Mirror World Builder Object Spawner import into WolvenKit JSON without requiring the WScript importer on every build.
- Add runtime probing for WolvenKit CLI `convert deserialize` support.
- Add guarded JSON→CR2W conversion plus strict produced-file and `CR2W` magic verification.
- Integrate conditional native conversion into build workspaces with `build-native-import`.
- Keep the exact World Builder importer as a supported fallback when the native backend is unavailable.
- Expand MCP from 79 to 87 unique tools.
- Expand automated suite from 83 to 92 tests.

## 0.8.0

- Add validation/summarization for World Builder `*_exported.json` files, including importer-version, sector, variant and duplicate-NodeRef checks.
- Add ArchiveXL streaming/resource-patch generation matching World Builder's importer behavior.
- Add WolvenKit `.cpmodproj` workspace generation and exact World Builder importer-script patching.
- Add build manifests and expected-output verification for streaming sectors/blocks, devices and persistent-state resources.
- Add WolvenKit CLI/cp77tools backend detection plus safe pack preview/execution.
- Add game-layout distribution/ZIP assembly, package verification and conflict-aware deployment with backups.
- Add explicit native-backend capability reporting; Linux-native Object Spawner CR2W conversion remains intentionally marked incomplete.
- Expand MCP from 69 to 79 unique tools.
- Expand automated suite from 74 to 83 tests.

## 0.7.0

- Add deterministic local semantic asset indexing with role/style/material/condition facets and user overrides.
- Add explicit asset-bounds storage/import plus low-confidence role-based fallback bounds.
- Add yaw-aware oriented-bounds collision scans with confidence/approximation reporting.
- Add versioned `cp77wb-plan/1` construction plans and compiled `cp77wb-compiled-plan/1` operations.
- Add plan compile/preview/apply workflow with exact indexed asset selections, clone validation and existing-build collision reporting.
- Add door-opening-aware room planning and deterministic collision-aware prop scatter.
- Add fence, road and cable/pipe path-structure generators over explicit points or existing WB marker/spline paths.
- Expand MCP from 57 to 69 unique tools.
- Expand automated suite from 61 to 74 tests.


## 0.6.0

- Add spline/marker path placement with tangent-aware Bezier sampling.
- Add polygon and volume constrained deterministic scatter.
- Add weighted indexed-asset pools and room/corridor/market generators.
- Add native World Builder Randomized Nested Group creation.
- Add typed parameterized JSON prefab/build rendering.
- Add device connection and conservative custom-elevator wiring helpers.
- Add World Builder version/feature/module/schema compatibility scanner and source fingerprints.
- Expand MCP from 45 to 57 tools.
- Expand automated suite from 48 to 61 tests.

## 0.5.0

- Add `cp77wb-live/3` for spatial authoring and transaction operations while retaining v1/v2 read/mutation compatibility where safe.
- Add World Builder scene raycasts through the active editor singleton.
- Add history-safe live scale with optional explicit pivot and strict unsupported-scale handling.
- Add native World Builder `dropToSurface()` snapping.
- Add multi-operation live transform batches committed as one World Builder history action.
- Add deterministic surface-aware scatter with native surface projection and one-step undo.
- Upgrade live duplication from NodeRef refusal to reference-aware clone remapping by default.
- Refresh the NodeRef registry path cache during clone generation to prevent same-transaction collisions.
- Add guarded live root save and top-level reload from World Builder `data/objects`.
- Add log discovery/tailing/issue filtering for World Builder, CET, RED4ext, redscript, ArchiveXL and TweakXL.
- Add `wb_logs` plus v0.5 live MCP tools; total MCP tool count is 45.
- Harden clone/scatter cleanup and transaction rollback behavior.
- Expand the automated test suite to 48 tests.

## 0.4.0

- Add `cp77wb-live/2` with explicit-confirm live mutations.
- Require the exact World Builder `modules/utils/history` singleton before any live write is enabled.
- Add live path search and active-editor path selection.
- Add history-safe live move and rotate for the current WB selection.
- Add history-safe live duplicate with NodeRef safety refusal.
- Add history-safe live delete.
- Add direct indexed-asset spawning into the active editor, including camera/player placement.
- Add live World Builder undo/redo.
- Add `wb_live_*` MCP tools for all v0.4 operations; live tools remain preview-only unless `apply=true`.
- Split spawnable serialization into reusable `build_spawnable_node()` for identical offline/live payloads.
- Keep v0.3 read-only bridge compatibility for observation calls.
- Expand tests to 36.

## 0.3.0

- Add `assets-build` SQLite/FTS5 catalog generation from World Builder `data/spawnables`.
- Classify list-backed resources according to World Builder category/variant/module paths.
- Index JSON spawn templates while retaining their full spawnable payload.
- Add `assets-search` with category/variant/module/extension filters and stable numeric IDs.
- Add ambiguity-safe asset resolution: non-exact multi-match queries must be replaced by a `#ID`.
- Add `assets-info`.
- Add `spawn-asset` for inserting a verified indexed asset into a saved WB group.
- Add `WorldBuilderProject.add_spawnable()` with loss-minimizing template preservation.
- Add 3D `grid` arrays.
- Add deterministic seeded offline `scatter` with optional random yaw/scale.
- Add native World Builder Favorites category parser/writer.
- Add `favorite-add` to export any object/group as a reusable World Builder Favorite/prefab.
- Add `favorites-list`.
- Add optional separate `extras/cp77wb_bridge` CET companion using JSON file RPC.
- Add read-only live queries for bridge status, player transform, camera transform, World Builder state and current selection.
- Add CLI `live` commands.
- Add MCP tools for asset build/search/info/spawn, grid/scatter, Favorites and live bridge queries.
- Keep live bridge mutation disabled until World Builder history/undo integration is implemented.
- Expand test suite from 22 to 29 tests.
- Add v0.3 asset, prefab and live-bridge wiki pages.

## 0.2.0

- Match World Builder `utils.createFileName()` and `utils.generateCopyName()` naming rules.
- Add World Builder-compatible NodeRef generation based on `nodeRefRegistry.generate()`.
- Add known-reference registry and reference-aware duplication/transforms.
- Add rotate/scale/linear/radial array/align/distribute operations.
- Add dependency-free MCP server and offline installer.
- Expand tests from 6 to 22.

## 0.1.0

- Initial safe saved-build tooling prototype.
