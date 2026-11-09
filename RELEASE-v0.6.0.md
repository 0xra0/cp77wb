# cp77wb v0.6.0 — procedural intelligence and compatibility

v0.6 adds higher-level deterministic World Builder construction without replacing World Builder's own data model.

## Added

- tangent-aware marker/spline `path-array` placement;
- polygon and box/cylinder/sphere volume scatter;
- weighted real-asset pools;
- native World Builder Randomized Nested Group generation;
- typed parameterized JSON prefab/build rendering;
- room/corridor/market generators using verified asset IDs;
- reference-safe `device-connect`;
- conservative `elevator-wire` automation;
- World Builder source/version/module/schema compatibility scanning and critical-file fingerprints;
- 12 new MCP tools, for **57 total**.

## Safety

All saved-build mutations remain dry-run unless `--write`/`write=true` or `--output` is supplied. Device/elevator helpers never fabricate missing instance-data component IDs. Asset pools are resolved before mutation. Procedural random operations are seeded and reproducible.

The existing v0.5 live bridge remains protocol `cp77wb-live/3`; no new in-game write protocol was required for v0.6.

## Verification

The release suite contains **61 tests**. Release packaging additionally checks a clean offline install, both MCP handshakes, all 57 unique tools, Lua bridge syntax, compatibility scanning against the supplied World Builder source, the existing 358,971-entry asset catalog, and a generated room written to a copy then validated by cp77wb.
