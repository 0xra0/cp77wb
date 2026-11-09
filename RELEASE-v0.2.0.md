# cp77wb v0.2.0

World Builder automation layer for Cyberpunk 2077, designed for safe CLI use and Claude Code/MCP integration.

## Highlights

- World Builder-compatible name sanitization and copy naming.
- World Builder-style NodeRef generation.
- Reference-aware NodeRef updates across known device, area, community, guard-area, conversation-area, and RED JSON fields.
- Safe subtree duplication with internal path and NodeRef remapping.
- Group/object rotation, geometric scaling, linear arrays, radial arrays, alignment, and distribution.
- Read-only `refs` inspection.
- Dependency-free stdio MCP server for Claude Code.
- MCP mutations are dry-run by default and return both a diff and validation output.
- Compatibility with handshake-era MCP plus the 2026 `server/discover` flow.
- Dependency-free local installer for Linux (`install.sh`) and source-tree launchers.
- Expanded World Builder integration wiki.
- 22 automated tests.

## Install on Linux without pip/setuptools

```bash
unzip cp77wb-v0.2.0.zip
cd cp77wb
./install.sh
~/.local/bin/cp77wb --version
```

Or run directly from the source tree:

```bash
./bin/cp77wb --version
./bin/cp77wb-mcp
```

## Claude Code MCP

After installing:

```bash
claude mcp add cp77wb -- ~/.local/bin/cp77wb-mcp
```

The MCP server exposes read/search/validation plus safe geometry and reference-aware editing operations. Mutation tools default to `write=false`.

## Important limitations

- v0.2 was derived from the supplied World Builder source snapshot and source-derived test fixtures. It still needs validation against multiple real user-created files from `entSpawner/data/objects`.
- The reference registry covers fields identified in the supplied source. Future World Builder releases may add new reference-bearing fields.
- Offline group rotation keeps serialized nested-group caches coherent, which is intentionally somewhat stricter than World Builder's runtime leaf-oriented transform path.
- Asset/resource indexing, a live CET bridge, and native WolvenKit/export automation are not yet included; these are planned for later releases.

## Safety model

- Mutating CLI commands are dry-run unless `--write` or `--output` is supplied.
- Writes are atomic and create timestamped backups.
- Unknown JSON fields are preserved.
- Validation can be run before and after mutations.
