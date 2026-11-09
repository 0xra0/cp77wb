# cp77wb v0.5.0 — live spatial authoring and transactions

v0.5 extends the guarded World Builder live bridge from basic transforms into scene-aware procedural authoring while keeping World Builder's own state/history as the authority.

## Highlights

- `cp77wb-live/3` spatial/transaction protocol
- World Builder-native scene raycast through `editor.getRaySceneIntersection()`
- history-safe live scale with optional world-space pivot
- native `dropToSurface()` snap/ground projection
- move/rotate/scale/snap batches committed as **one undo action**
- deterministic surface-aware scatter
- reference-aware live duplicate/scatter with regenerated NodeRefs and known internal-reference remapping
- live indexed-asset spawn with optional surface snap
- guarded root save and top-level reload
- automatic World Builder/CET/RED4ext/redscript/ArchiveXL/TweakXL log collection
- **45 MCP tools**
- **48 automated tests**
- v1/v2 compatibility retained for older observation/v0.4 calls where safe

## Safety changes

Live writes still require both `apply=true` and an RPC `confirm=true` envelope. The CET bridge refuses mutation unless it resolves World Builder's exact active history singleton. Spatial/editor and reference-aware operations additionally verify the active editor/NodeRef registry as required.

Live duplicate no longer blanket-refuses NodeRef-bearing subtrees. Instead, default cloning regenerates NodeRef definitions with World Builder's registry and rewrites known references inside the cloned subtree. `keep_noderefs=true` / `--keep-noderefs` is an explicit unsafe override.

Batch transforms snapshot the selected roots before execution. Temporary history entries from WB helpers such as `dropToSurface()` are discarded; a successful batch gets one history action, while a failing batch attempts to restore the pre-operation snapshot.

## Important first-run checks

The build environment cannot launch Cyberpunk/CET. After installing/upgrading the bridge, run in a live game session:

```bash
cp77wb live "$RPC" ping
cp77wb live "$RPC" history
cp77wb live "$RPC" raycast --ray-mode camera
```

Only use `--apply` when `liveMutation` and `history.available` are true. The raycast check should also report a valid scene-query response in the installed World Builder version.

If any capability is unavailable, collect diagnostics without mutating the editor:

```bash
cp77wb logs "/path/to/Cyberpunk 2077" --issues-only
```

## Upgrade

Upgrade both the Linux-side package and CET bridge; protocol-v3 operations require the v0.5 companion:

```bash
./install.sh --prefix "$HOME/.local"
./extras/install-cet-bridge.sh "/path/to/Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods"
```
