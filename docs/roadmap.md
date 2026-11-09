# Roadmap

## 0.1 — safe saved-build core ✅

- loss-minimizing JSON model
- hierarchy/path traversal and validation
- safe translate/rename/NodeRef/reference edits
- area cache rebuild and backups/dry-run diffs

## 0.2 — editing primitives + MCP ✅

- WB naming/NodeRef compatibility
- reference-aware duplicate
- rotate/scale/linear/radial arrays, align/distribute
- dependency-free MCP

## 0.3 — asset intelligence + native prefabs + read-only bridge ✅

- scan World Builder `data/spawnables`
- SQLite/FTS5 verified resource index
- deterministic `#asset-id`
- indexed saved-build spawn
- grid/offline scatter
- native WB Favorites/prefabs
- CET file-RPC companion for player/camera/WB state/selection

## 0.4 — history-safe live authoring ✅

- `cp77wb-live/2`
- runtime proof of active WB history singleton
- live path selection, move, rotate, delete
- guarded duplicate
- indexed camera/player spawn
- WB undo/redo

## 0.5 — live spatial authoring + transactions ✅

- `cp77wb-live/3`
- active WB scene raycast
- live scale
- native surface snap / ground projection
- deterministic surface-aware scatter
- one-undo batch transforms
- reference-aware live duplicate with NodeRef remapping
- root save/reload coordination
- World Builder/CET/RED4ext/redscript/ArchiveXL/TweakXL log collection
- 45 MCP tools

## 0.6 — procedural authoring + compatibility intelligence ✅

- line/spline placement helpers
- polygon/volume placement constraints
- weighted asset pools and prefab parameters
- room/corridor/market generators
- device/elevator helpers
- source/schema compatibility scanner

## 0.7 — AI construction planner ✅

- deterministic semantic asset facets and custom overrides
- asset-bounds cache/import with confidence tracking
- yaw-aware approximate collision checks
- versioned declarative construction plans
- plan compile → preview → validate → apply workflow
- room door openings and collision-aware deterministic prop placement
- fence/road/cable path-structure generators
- 69 MCP tools

## 0.8 — export/build orchestration ✅

- validate World Builder exported intermediates
- generate WolvenKit project/raw/resources structure and patched upstream importer
- generate ArchiveXL streaming/device patch config
- verify expected native importer outputs before packing
- preview/execute WolvenKit CLI/cp77tools archive packing
- game-layout package/ZIP assembly and conflict-aware deployment with backups
- explicit capability report for the still-unfinished Linux-native Object Spawner CR2W conversion
- 79 MCP tools


## 0.9 — template-driven cross-platform conversion ✅

- generated WolvenKit RED default-template capture script
- versioned template-bundle coverage verification
- Python mirror of World Builder Object Spawner import into WolvenKit JSON
- runtime-probed `convert deserialize` backend
- CR2W magic/output verification
- build-workspace `build-native-import` integration with upstream WScript fallback
- 87 MCP tools

## 1.0 — verified native worker ✅

- bundled .NET 10 WolvenKit worker and versioned worker protocol
- runtime self-test for RED default-instance JSON + JSON→CR2W
- worker-backed template generation and Object Spawner import without mandatory WScript capture
- template+CLI and upstream WScript fallback paths retained
- 92 MCP tools and 100-test regression suite

## Candidate 1.1+

- real WolvenKit Linux CI matrix and pinned API compatibility profiles
- asset-bounds extraction from WolvenKit/resource metadata instead of heuristic fallbacks
- native Scattered Group generation rather than only baked scatter
- door/security/fast-travel recipes
- spline-following live placement projected onto surfaces
- higher-order multi-room/corridor graph planner
