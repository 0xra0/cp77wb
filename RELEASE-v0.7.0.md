# cp77wb v0.7.0

AI construction-planner release.

## Highlights

- Deterministic local semantic asset index with role/style/material/condition facets.
- User semantic overrides while preserving verified base catalog records.
- Explicit/imported asset bounds plus low-confidence heuristic planning bounds.
- Yaw-aware oriented bounding-box collision scans with approximation/confidence reporting.
- Versioned `cp77wb-plan/1` and `cp77wb-compiled-plan/1` formats.
- Plan compile → preview → validate → apply workflow.
- Door-opening-aware room composition.
- Deterministic collision-aware prop scatter.
- Fence, road and cable path generators using real indexed assets and WB spline/marker paths.
- 69 unique MCP tools.
- 74 automated tests.

## Real World Builder source/catalog smoke test

Using the supplied World Builder 1.0.81 source, the existing scanner indexes 358,971 asset choices. The v0.7 semantic index builds over all 358,971 entries locally with FTS5 and no external dependencies/API calls.

## Safety

- Saved-build writes remain dry-run by default.
- Plan application requires `--write` / `write=true` to persist.
- Semantic plan selection requires exact assets unless the plan explicitly sets `autoSelect:true`.
- Heuristic asset bounds are never represented as measured geometry; collision reports involving them are marked approximate.
- Live REDengine spatial truth remains the v0.5+ bridge raycast/surface-snap path.

## Known limits

- v0.7 does not parse `.mesh` files to extract true render/collision bounds. Exact bounds must currently be supplied/imported; the fallback role table is a planning heuristic.
- Offline OBB collision checks cannot replace in-game REDengine collision/navmesh/surface tests.
- Road/fence/cable generators repeat assets; they do not infer mesh-specific pivots, stretch axes, or physical dimensions.
- Semantic inference comes from resource/catalog names and optional user overrides, so unusual naming can require custom tags.
