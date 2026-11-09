# Claude Code workflow

## Implemented architecture in v0.7

```text
Claude Code
    │
    ▼
cp77wb MCP (69 tools)
    │
    ├── saved-build model / validator
    ├── World Builder asset catalog
    ├── native Favorites/prefabs
    ├── log collector
    └── file-RPC client
              │
              ▼
       cp77wb_bridge (CET)
              │
              ▼
       active World Builder
```

## Project rule file

A useful `CLAUDE.md`:

```markdown
# World Builder automation rules
- Use cp77wb tools rather than manually editing WB JSON when a supported operation exists.
- Saved-build mutations remain write=false until their diff is reviewed.
- Never invent a Cyberpunk depot path; search the cp77wb asset catalog and choose a concrete #ID.
- Validate persisted saved builds after edits.
- Before live mutation call wb_live_ping and wb_live_history.
- If placement is surface-dependent, call wb_live_raycast or use wb_live_snap/surface scatter.
- Live mutations remain apply=false until selection and parameters are confirmed.
- Keep default NodeRef remapping for live duplicate and scatter.
- Prefer wb_live_batch when a generated transform sequence should undo in one step.
- Use wb_logs when World Builder/CET/export behavior is unexpected.
```

## Example: spatial placement

User intent:

> Move the selected prop two metres forward, rotate it 15 degrees, then drop it to the floor. I want one undo action.

Claude should:

```text
wb_live_ping
wb_live_history
wb_live_selection
wb_live_batch apply=false
review
wb_live_batch apply=true
wb_live_selection
```

with operations similar to:

```json
[
  {"type":"move","y":2},
  {"type":"rotate","yaw":15},
  {"type":"snap","direction":{"x":0,"y":0,"z":-1}}
]
```

## Example: verified asset placement

User intent:

> Find an industrial pipe and place it four metres in front of the camera, then snap it down.

Workflow:

```text
wb_assets_search("industrial pipe")
→ user/agent chooses concrete #asset-id
→ wb_live_spawn_asset apply=false, placement=camera, snap_to_surface=true
→ review
→ wb_live_spawn_asset apply=true
```

No resource path should be synthesized by the model.

## Example: scatter

> Scatter 30 copies of this selected trash prop over a 20×8 m region and make it undoable in one step.

Use `wb_live_surface_scatter` with `half_x=10`, `half_y=4`, a recorded seed, and default NodeRef remapping. Preview first, then apply.

## Example: failure diagnosis

If the editor operation does not behave as expected:

```text
wb_live_state
wb_live_history
wb_logs issues_only=true
```

Use the returned World Builder/CET/RED4ext/redscript/ArchiveXL/TweakXL excerpts as evidence before changing the build.

## What Claude should not do

- bypass the `apply`/`write` safety defaults;
- directly mutate active WB state when `liveMutation=false`;
- use `keep_noderefs=true` merely to get past a duplicate conflict;
- invent depot paths;
- assume a bridge built for one WB version remains compatible without `ping/history/raycast` checks;
- treat log warnings as proof of a root cause without correlating them with the project/state.


## v0.6 recommended Claude workflow

1. Run `wb_compat_scan` against the installed World Builder and current build.
2. Use `wb_assets_search` and exact asset IDs for resources.
3. Preview a procedural operation (`write=false`).
4. Validate the dry-run result and inspect its diff.
5. Apply with `write=true` only after the plan is accepted.
6. For collision-dependent placement, switch to the v0.5 live bridge and preview before `apply=true`.

## v0.7 construction-planner workflow

For high-level authoring, prefer this sequence:

1. `wb_compat_scan` the installed World Builder.
2. `wb_semantic_search` candidate resources; retain exact `#ID`s.
3. Read/import bounds where spatial clearance matters.
4. Build a `cp77wb-plan/1` JSON object.
5. `wb_plan_compile` and inspect `assetSelections`/warnings/collisions.
6. `wb_plan_preview` against the real build.
7. `wb_plan_apply` with `write=false` and inspect the diff.
8. Set `write=true` only after the plan is accepted.
9. Run `wb_validate`.

Semantic auto-selection is never implicit: a plan entry using `semanticQuery` must state `autoSelect:true`. Exact catalog IDs remain preferred for repeatable project recipes.


## v0.8 recommended build workflow

After World Builder export, have Claude call `wb_export_inspect` → `wb_build_backends` → `wb_build_prepare` (preview then `write=true`). Run the generated importer in WolvenKit, then use `wb_build_status`. Only after `importComplete=true` should Claude preview `wb_build_pack`, execute it if approved, preview/create `wb_build_package`, run `wb_build_verify`, and finally preview deployment. Do not tell Claude that Object Spawner conversion is Linux-native in v0.8; `wb_build_backends` explicitly reports that boundary.


## v0.9 recommended native-conversion workflow

After `wb_build_prepare`, prefer this sequence when a template bundle is available:

1. `wb_native_template_verify` against the exact export and bundle.
2. `wb_native_preflight` against the exact WolvenKit CLI/cp77tools binary on this machine.
3. `wb_build_native_import` with `run=false` and review required types/targets/CLI probe.
4. Set `run=true` only after the preview passes.
5. Require `wb_native_verify`/`wb_build_status` success before packing.
6. Continue the v0.8 pack → package → verify → doctor → deploy flow.

If template verification or CLI preflight fails, use the generated upstream World Builder WScript importer instead. Do not claim Linux-native conversion merely because WolvenKit has a recent version number; capability is established by the runtime probe and verified CR2W outputs.
