# v0.4: history-safe live authoring

v0.4 changes the optional CET bridge from observation-only to a guarded live authoring interface.

## Safety model

A live mutation is allowed only when all of the following are true:

1. The request uses `cp77wb-live/2`.
2. The request carries `confirm=true` (the Python CLI/MCP only sends this when `--apply` / `apply=true` is used).
3. World Builder is loaded.
4. The bridge can resolve `modules/utils/history`.
5. That history table's `spawnedUI` is the exact same object as `GetMod("entSpawner").baseUI.spawnedUI`.

If the last check fails, the bridge stays read-only. This is deliberate: loading a second copy of World Builder's history module would create an undo stack that the World Builder UI cannot see.

Check capability at runtime:

```bash
cp77wb live /path/to/cp77wb_bridge/rpc ping
cp77wb live /path/to/cp77wb_bridge/rpc history
```

Look for:

```json
{
  "liveMutation": true,
  "history": {
    "available": true
  }
}
```

## Preview then apply

All v0.4 CLI/MCP live mutations are previews by default.

```bash
cp77wb live "$RPC" move --x 2
```

This reads the current selection and prints the intended operation. It does not mutate World Builder.

Apply it explicitly:

```bash
cp77wb live "$RPC" move --x 2 --apply
```

The bridge snapshots the selected root elements through World Builder's own history API, then calls their World Builder transform methods.

## Search and select active elements

Search the loaded hierarchy:

```bash
cp77wb live "$RPC" paths --query light --limit 50
```

Select exact paths:

```bash
cp77wb live "$RPC" select \
  --path '/MyBuild/Lobby/Light01' \
  --path '/MyBuild/Lobby/Light02'
```

Apply selection change:

```bash
cp77wb live "$RPC" select \
  --path '/MyBuild/Lobby/Light01' \
  --path '/MyBuild/Lobby/Light02' \
  --apply
```

Selection itself is not an undoable content edit, but it still requires explicit `--apply` so Claude cannot silently change the user's active selection.

## Move and rotate

```bash
cp77wb live "$RPC" move --x 0 --y 2 --z 0 --apply
cp77wb live "$RPC" rotate --yaw 90 --apply
```

For multiple selected roots, v0.4 uses World Builder's `multiSelectGroup` as a temporary transform group. Rotation therefore occurs around the selection center instead of rotating every item around its individual origin.

## Duplicate

```bash
cp77wb live "$RPC" duplicate --count 5 --x 3 --apply
```

`--count` is the number of *new* copies. The per-copy offset is multiplied by 1, 2, 3 ... so the example creates five new copies at +3, +6, +9, +12 and +15 metres on X.

### NodeRef rule

Live duplicate refuses a selected subtree containing a non-empty NodeRef. World Builder's own in-memory duplicate path does not perform cp77wb's reference remapping, so blindly duplicating devices/areas can create duplicate NodeRefs or links pointing to the original hierarchy.

Use the offline reference-aware command for those cases:

```bash
cp77wb duplicate Build.json /Build/Devices/Elevator --count 2 --x 5
```

Review the diff, write it, and reload the build in World Builder.

## Delete, undo and redo

```bash
cp77wb live "$RPC" delete --apply
cp77wb live "$RPC" undo --apply
cp77wb live "$RPC" redo --apply
```

Delete is recorded with World Builder's `history.getRemove()`. Undo and redo invoke World Builder's active history object, not a cp77wb-local stack.

## Spawn a real indexed asset into the active editor

Build the asset database once:

```bash
cp77wb assets-build /path/to/entSpawner
```

Search:

```bash
cp77wb assets-search /path/to/entSpawner/.cp77wb/assets.sqlite3 'neon sign' --variant Mesh
```

Preview a live spawn in front of the camera:

```bash
cp77wb live "$RPC" spawn-asset \
  --catalog /path/to/entSpawner/.cp77wb/assets.sqlite3 \
  --asset '#12345' \
  --placement camera \
  --distance 4
```

Apply:

```bash
cp77wb live "$RPC" spawn-asset \
  --catalog /path/to/entSpawner/.cp77wb/assets.sqlite3 \
  --asset '#12345' \
  --placement camera \
  --distance 4 \
  --apply
```

Placement modes:

- `camera`: camera position + camera forward vector × distance; faces back toward the camera yaw convention used by WB spawning.
- `player`: current player position with camera-derived yaw.
- `serialized`: use the explicit `--x/--y/--z/--roll/--pitch/--yaw` values in the generated WB serialization.

Use `--parent '/Build/SomeGroup'` to insert into a specific active group. Without it, the bridge uses the sole selected expandable group when possible, otherwise the root.

## MCP tools

v0.4 adds:

- `wb_live_history`
- `wb_live_paths`
- `wb_live_select`
- `wb_live_move`
- `wb_live_rotate`
- `wb_live_duplicate`
- `wb_live_delete`
- `wb_live_spawn_asset`
- `wb_live_undo`
- `wb_live_redo`

Mutation tools require `apply=true`. Claude should first call `wb_live_ping` or `wb_live_history`, inspect the selection, make a preview call, and only apply after the intended operation is clear.

## Current limitations

- The Lua bridge cannot be integration-tested in this build container because Cyberpunk/CET is not available here. The Python/RPC/MCP paths are automated; the history singleton capability must be confirmed with the first in-game `ping`.
- Live duplicate intentionally refuses NodeRef-bearing subtrees rather than pretending it can safely rewrite every in-memory reference.
- Live scaling is not exposed in v0.4. World Builder's group scaling path is coupled to its interactive editor/gizmo behavior; it needs a dedicated compatibility pass before it is safe to automate.
- There is no collision-aware scatter yet. Ground/surface projection belongs in a later live geometry release.
