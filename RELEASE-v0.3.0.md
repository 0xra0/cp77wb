# cp77wb v0.3.0

## Theme

v0.3 turns cp77wb from a saved-build transform tool into a practical World Builder/Claude Code authoring layer:

```text
real World Builder resource lists
        ↓
SQLite/FTS verified asset search
        ↓
exact #asset selection
        ↓
WB saved-build insertion
        ↓
native WB Favorite/prefab reuse
        ↓
optional live player/camera/selection context
```

## Real-source verification

Against the supplied World Builder source tree, `assets-build` produced:

```text
358,971 indexed spawnable choices
FTS5 enabled
```

Example searches successfully returned real resources for:

- `arasaka wall`
- `elevator`
- `neon sign`
- `industrial pipe`

A real-index `spawn-asset` dry run produced a standard WB `spawnableElement` using the selected resource path without touching the source build.

## Safety decisions

- saved-build mutations remain dry-run by default;
- ambiguous asset text queries fail instead of choosing arbitrarily;
- native Favorite files are backed up before changes;
- the CET bridge is observation-only in this release;
- no World Builder source files are patched or redistributed.

## Tests

```text
Ran 29 tests
OK
```


## Live bridge verification

The Python file-RPC client/protocol is covered by an automated round-trip test and the Lua companion is derived from the supplied World Builder/CET interfaces. This build environment cannot launch Cyberpunk 2077/CET, so the Lua companion itself still requires an in-game runtime smoke test. For that reason v0.3 exposes live state as read-only and does not attempt live editor writes.
