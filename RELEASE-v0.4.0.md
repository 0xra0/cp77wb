# cp77wb v0.4.0 — history-safe live authoring

v0.4 promotes the optional CET bridge from read-only observation to guarded World Builder-native editing.

## Highlights

- `cp77wb-live/2` protocol
- explicit-confirm mutation model (`--apply` / `apply=true`)
- runtime proof that the bridge is using World Builder's real history singleton
- live hierarchy path search and exact selection
- live move and multi-selection rotation through WB transform methods
- live duplication for NodeRef-free selections
- live delete through WB history
- live indexed-asset spawn with camera/player placement
- live World Builder undo/redo
- 37 MCP tools total
- 36 automated Python tests
- v0.3 read-only live protocol compatibility

## Important first-run check

The release container cannot launch Cyberpunk/CET. After installing the bridge, run:

```bash
cp77wb live "$RPC" ping
cp77wb live "$RPC" history
```

Only use live mutation when `liveMutation` and `history.available` are both `true`.

If they are false, attach the returned reason plus `cyber_engine_tweaks.log`/World Builder log and the bridge can be adjusted for the installed CET/World Builder build without risking the active editor state.
