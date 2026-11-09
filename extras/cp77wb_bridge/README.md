# cp77wb_bridge v0.5 (optional CET companion)

This is a separate companion mod. It does not patch or redistribute World Builder.

Install this directory as:

```text
Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods/cp77wb_bridge/
```

RPC directory:

```text
.../mods/cp77wb_bridge/rpc/
```

The Linux-side `cp77wb live ...` commands and MCP tools write JSON requests to `rpc/requests`; this CET companion writes responses to `rpc/responses`.

## Safety/capability gate

Live writes are enabled only when the bridge sees World Builder's **existing** `modules/utils/history` singleton and verifies:

```text
history.spawnedUI == GetMod("entSpawner").baseUI.spawnedUI
```

Spatial scene queries additionally require the matching World Builder editor singleton. Reference-aware cloning requires the matching NodeRef registry singleton.

Check after launching the game:

```bash
cp77wb live /path/to/cp77wb_bridge/rpc ping
cp77wb live /path/to/cp77wb_bridge/rpc history
cp77wb live /path/to/cp77wb_bridge/rpc raycast --ray-mode camera
```

If the shared history object cannot be proven, `ping` reports `liveMutation: false` and mutations are refused.

## Protocols

- `cp77wb-live/1`: legacy observation calls
- `cp77wb-live/2`: v0.4 mutations
- `cp77wb-live/3`: v0.5 spatial/transaction operations

v0.5 additions include scale, native surface snap, one-undo batch transforms, surface scatter, reference-aware duplicate, root save/reload and scene raycast.

All mutating CLI/MCP calls are previews unless `--apply` / `apply=true` is supplied.

See `docs/v05-spatial-authoring.md` in the main cp77wb package.
