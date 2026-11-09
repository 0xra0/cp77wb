# cp77wb v0.8.0

## Export/build orchestration

v0.8 adds a preview-first pipeline around World Builder's native export and WolvenKit Object Spawner importer. It validates exported intermediates, creates standard WolvenKit project workspaces, patches the exact importer shipped with the selected entSpawner tree, generates ArchiveXL configuration, verifies expected native outputs, packs via WolvenKit CLI/cp77tools, assembles distributable game-layout ZIPs, and deploys with conflict checks/backups.

## Native conversion status

The upstream importer still depends on WolvenKit Script API runtime facilities (`CreateInstanceAsJSON`, `HashString`, `JsonToCR2W`, `SaveToProject`, `SaveToResources`). cp77wb v0.8 deliberately reports Linux-native Object Spawner conversion as incomplete instead of generating unverified CR2W files. The surrounding validation, workspace, package and deploy steps are cross-platform Python.

## Safety

- MCP workspace/package creation is preview-first.
- CLI pack execution requires `--run`.
- Deployment requires `--apply`; conflicting existing files additionally require `--overwrite` and are backed up.
- Unknown resource install locations are quarantined under `cp77wb-unmapped-resources` and make a package not-ready.

## Verification

- 83/83 automated tests
- 79 unique MCP tools
- World Builder 1.0.81 importer API detection
- exact upstream importer patch smoke
- ArchiveXL device/PS generation tests
- pack wrapper exercised with a CLI-compatible test backend
- package ZIP + deploy conflict/backup tests
- integrated package + issue-log build doctor
