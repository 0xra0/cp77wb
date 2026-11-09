# Optional CET live bridge

`extras/cp77wb_bridge` is a separate CET companion. It does not modify or redistribute World Builder. Linux-native `cp77wb` communicates with it through JSON request/response files.

```text
Claude Code / cp77wb
        ↓
cp77wb_bridge/rpc/requests
        ↓
CET companion
        ↓
active World Builder state
        ↓
cp77wb_bridge/rpc/responses
```

This avoids GUI automation and avoids requiring Claude Code itself to run inside Proton.

## Install

```bash
./extras/install-cet-bridge.sh "/path/to/Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods"
```

Set:

```bash
RPC="/path/to/Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods/cp77wb_bridge/rpc"
```

## Capability checks

```bash
cp77wb live "$RPC" ping
cp77wb live "$RPC" history
cp77wb live "$RPC" state
cp77wb live "$RPC" raycast --ray-mode camera
```

The bridge enables writes only when the history module it sees owns the exact same `spawnedUI` as the loaded `entSpawner` mod. Scene raycast requires the same identity check for the active editor module. Reference-aware duplication requires the active NodeRef registry.

## Protocols

- `cp77wb-live/1`: original observation protocol
- `cp77wb-live/2`: v0.4 explicit-confirm mutations
- `cp77wb-live/3`: v0.5 spatial and transaction operations

Python read calls may fall back across compatible protocols. v0.5-only mutations use v3 and fail clearly against an older bridge.

## Read operations

```bash
cp77wb live "$RPC" player
cp77wb live "$RPC" camera
cp77wb live "$RPC" state
cp77wb live "$RPC" selection --include-data
cp77wb live "$RPC" paths --query neon --limit 30
cp77wb live "$RPC" raycast --ray-mode camera
```

## Mutation model

All writes require `--apply`. Without it the CLI returns a preview.

```bash
cp77wb live "$RPC" move --x 1
cp77wb live "$RPC" move --x 1 --apply
```

World Builder history is used for undo/redo:

```bash
cp77wb live "$RPC" undo --apply
cp77wb live "$RPC" redo --apply
```

## Spatial operations

```bash
cp77wb live "$RPC" scale --uniform 1.1 --apply
cp77wb live "$RPC" snap --apply
cp77wb live "$RPC" surface-scatter --count 20 --half-x 8 --half-y 5 --seed 42 --apply
```

`scale` is strict about objects that do not expose scale. `snap` and surface scatter use World Builder's native `dropToSurface()` implementation.

## One-step batch undo

```bash
cp77wb live "$RPC" batch --ops-file ops.json --apply
```

Supported operation types are `move`, `rotate`, `scale`, and `snap`. The bridge records one pre-change WB snapshot and one committed history action for the whole successful batch.

## Reference-aware duplicate

```bash
cp77wb live "$RPC" duplicate --count 5 --x 3 --apply
```

By default, NodeRef definitions in every clone are regenerated using World Builder's NodeRef registry and known internal references are rewritten. This replaces v0.4's blanket refusal for NodeRef-bearing selections.

`--keep-noderefs` disables this protection and is intentionally explicit.

## Save/reload

```bash
cp77wb live "$RPC" save --apply
cp77wb live "$RPC" reload --path /MyBuild --apply
```

`save` calls native root `save()` methods. `reload` is limited to top-level saveable roots and uses WB's config loader plus an undoable remove/insert action.

## Failure diagnosis

```bash
cp77wb logs "/path/to/Cyberpunk 2077" --issues-only
```

Claude can invoke the same collector through `wb_logs`.

## Runtime validation caveat

The release environment can test Python RPC behavior, protocol envelopes, MCP routing and bridge source invariants, but it cannot launch Cyberpunk/CET. Always run `ping`, `history`, and `raycast` after installing a new bridge/World Builder version. If identity checks fail, live writes remain disabled instead of guessing.
