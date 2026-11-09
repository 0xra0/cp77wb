# cp77wb documentation

`cp77wb` is an external automation/agent layer around Cyberpunk 2077 World Builder.

## Start here

- `saved-build-format.md` — source-derived saved project structure
- `worldbuilder-source-map.md` — where relevant logic lives upstream
- `validation.md` — WB-specific checks
- `cli.md` — command reference
- `v02-editing.md` — transform/reference semantics
- `v03-assets.md` — verified World Builder asset index/search/insertion
- `v03-prefabs.md` — native Favorites as reusable prefabs
- `live-bridge.md` — optional CET file-RPC companion
- `v05-spatial-authoring.md` — v0.5 raycast/scale/snap/batch/scatter/save-reload semantics
- `v06-procedural-intelligence.md` — v0.6 spline paths, constrained scatter, asset pools, generators, device/elevator helpers and compatibility scanning
- `v07-ai-planner.md` — semantic assets, bounds/collision metadata, construction plans and path structures
- `v08-build-orchestration.md` — World Builder export → WolvenKit import → archive/package/deploy pipeline
- `v09-native-conversion.md` — captured RED templates + probed WolvenKit JSON→CR2W backend
- `v10-native-worker.md` — preferred .NET 10 WolvenKit worker, self-test and direct native import
- `mcp.md` — MCP server
- `claude-code.md` — recommended Claude Code workflows
- `roadmap.md` — next milestones
- `upstream-compatibility.md` — design rules for staying non-invasive

## v0.5

- [Live spatial authoring](v05-spatial-authoring.md)
- Live edits use World Builder's active history/undo stack and active editor APIs.
- v0.5 adds scene raycast, scale, surface snap, one-undo batches, surface scatter, reference-aware live duplicate, save/reload, and log diagnostics.
- All live mutations remain preview-only until `--apply` / `apply=true`.

## v0.6

- procedural path/spline placement and constrained scatter
- weighted real-asset pools and native RNG groups
- parameterized prefab/build JSON
- room/corridor/market generators
- device/elevator automation
- source/schema compatibility scanning
- 57 MCP tools

## v0.7

- local semantic asset facets and overrides
- explicit/heuristic asset bounds with confidence tracking
- yaw-aware approximate collision checks
- `cp77wb-plan/1` compile → preview → validate → apply workflow
- door-aware room composition and collision-aware deterministic scatter
- fence/road/cable path structures
- 69 MCP tools

## v0.8

- export/intermediate validation
- WolvenKit project + importer scaffolding
- ArchiveXL generation and expected-output verification
- safe CLI pack wrapper, distribution packaging and conflict-aware deploy
- 79 MCP tools


## v0.9

- versioned RED default-template bundle capture/verification
- Python mirror of the World Builder Object Spawner importer into inspectable WolvenKit JSON
- runtime probe for actual `convert deserialize` support
- guarded JSON→CR2W conversion with strict magic/output verification
- `build-native-import` workspace integration with upstream WScript fallback
- 87 MCP tools


## v1.0

- bundled .NET 10 WolvenKit worker source
- authoritative runtime self-test for RED defaults + CR2W writing
- WScript-free worker bundle/import path when verified
- v0.9 template+CLI and upstream importer fallbacks retained
- 92 MCP tools
- 100-test regression suite

- `v101-worker-diagnostics.md` — deferred .NET/WolvenKit worker testing, API profiles and support bundles.
