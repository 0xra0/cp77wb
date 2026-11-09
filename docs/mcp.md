# cp77wb MCP server

v0.9 includes a dependency-free stdio MCP server:

```bash
cp77wb-mcp
```

Register with Claude Code:

```bash
claude mcp add cp77wb -- cp77wb-mcp
```

The server uses only Python's standard library at runtime and supports both the initialize-era MCP handshake and the newer discovery flow supported by current clients.

## Tools

v1.0 exposes **92 unique tools**.

### Project inspection

```text
wb_tree
wb_get
wb_find
wb_validate
wb_refs
```

### Saved-build editing

```text
wb_move
wb_rotate
wb_scale
wb_generate_noderef
wb_duplicate
wb_array
wb_radial_array
wb_align
wb_distribute
wb_grid
wb_scatter
```

### Asset intelligence

```text
wb_assets_build
wb_assets_search
wb_assets_info
wb_spawn_asset
```

### Native Favorites/prefabs

```text
wb_favorites_list
wb_favorite_add
```

### Diagnostics

```text
wb_logs
```

### Live observation / scene context

```text
wb_live_ping
wb_live_state
wb_live_player
wb_live_camera
wb_live_selection
wb_live_history
wb_live_paths
wb_live_raycast
```

### Live authoring

```text
wb_live_select
wb_live_move
wb_live_rotate
wb_live_scale
wb_live_snap
wb_live_batch
wb_live_duplicate
wb_live_surface_scatter
wb_live_delete
wb_live_spawn_asset
wb_live_save
wb_live_reload
wb_live_undo
wb_live_redo
```

## Safety defaults

Saved-build mutations default to:

```json
{"write": false}
```

Live mutations default to:

```json
{"apply": false}
```

The CET bridge independently requires explicit RPC confirmation plus proof that it has World Builder's exact active history singleton. New v0.5 spatial operations require `cp77wb-live/3`; they are never downgraded to an older bridge.

Recommended live workflow:

```text
wb_live_ping
→ wb_live_history
→ wb_live_raycast / wb_live_paths / wb_live_selection
→ mutation apply=false
→ review preview
→ mutation apply=true
→ inspect state/history
→ wb_live_undo if needed
```

## Reference-aware duplicate/scatter

v0.5 live duplication and surface scatter regenerate NodeRef definitions and rewrite known internal references by default. `keep_noderefs=true` is an explicit unsafe override and should not be used for ordinary device/area/prefab duplication.

## Batch transactions

`wb_live_batch` accepts operations of types:

```text
move
rotate
scale
snap
```

The bridge snapshots the selected roots before running the batch, suppresses intermediate WB helper history records, and commits the successful sequence as one World Builder undo action.

## Recommended Claude rules

```markdown
# World Builder automation
- Prefer cp77wb MCP tools over hand-editing WB JSON.
- Dry-run saved-build mutations before write=true.
- Search wb_assets_search and choose a concrete #asset-id; never invent depot paths.
- Before any live write, call wb_live_ping and wb_live_history.
- Use wb_live_raycast when placement depends on the visible game surface.
- Keep live apply=false until selection and parameters are verified.
- Preserve default NodeRef remapping for live duplicate/scatter.
- Prefer wb_live_batch when several transforms should be one undo step.
- Use wb_logs when a live or exported operation fails.
- Run wb_validate after persisted saved-build changes.
```


## v0.6 procedural tools

`wb_path_array`, `wb_polygon_scatter`, `wb_volume_scatter`, `wb_asset_pool_spawn`, `wb_rng_create`, `wb_generate_room`, `wb_generate_corridor`, `wb_generate_market`, `wb_device_connect`, `wb_elevator_wire`, `wb_compat_scan`, and `wb_prefab_render` extend the same dry-run-by-default model to procedural construction.

## v0.7 planner tools

v0.7 adds 12 tools (69 total):

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
```

`wb_plan_apply` follows the normal saved-build rule: it returns a diff with `write=false` and only saves when `write=true`.


## v0.8 build tools

The server exposes 79 unique tools. New tools are `wb_export_inspect`, `wb_export_xl`, `wb_build_prepare`, `wb_build_status`, `wb_build_backends`, `wb_build_pack`, `wb_build_package`, `wb_build_verify`, `wb_build_deploy`, and `wb_build_doctor`. Workspace/package creation default to preview (`write=false`), packing defaults to `run=false`, and deployment defaults to `apply=false`.


## v0.9 native conversion tools

v0.9 adds eight tools (87 total):

```text
wb_native_template_plan
wb_native_template_verify
wb_native_json
wb_native_preflight
wb_native_convert
wb_native_import
wb_native_verify
wb_build_native_import
```

Template-plan/JSON generation tools remain preview-first where they can create files; conversion/import defaults to `run=false`. Agents should call `wb_native_preflight` against the exact CLI binary on the current machine before proposing a native import. A failed preflight means the v0.8 upstream-WScript path remains the supported fallback.

## v1.0 worker tools

- `wb_worker_build`
- `wb_worker_preflight`
- `wb_worker_bundle`
- `wb_worker_import`
- `wb_build_worker_import`

Worker build/import tools keep `run=false` by default. Claude should call `wb_worker_preflight` first and require both `ready=true` and `authoritativeNative=true` before selecting the worker backend.
