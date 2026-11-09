# v0.8 export/build orchestration

## Purpose

World Builder exports an intermediate `*_exported.json`. Its upstream `script/import_object_spawner.wscript` then uses WolvenKit's script runtime to instantiate RED types and serialize them as native CR2W `.streamingsector`, `.streamingblock`, `.devices` and `.psrep` files. v0.8 automates and verifies the workflow around that conversion without claiming that pure Python can replace the WolvenKit Script API.

## Pipeline

```text
World Builder saved build
        ↓ WB Export tab
*_exported.json
        ↓ cp77wb export-inspect
validated intermediate
        ↓ cp77wb build-prepare
WolvenKit .cpmodproj + raw export + .xl + patched importer
        ↓ WolvenKit Script Manager (official importer API)
native streamingsector/block/device files
        ↓ cp77wb build-status
verified expected outputs
        ↓ cp77wb build-pack --run
.archive
        ↓ cp77wb build-package
game-layout folder + optional ZIP
        ↓ cp77wb build-verify / build-deploy
installable mod
```

## Export validation

`export-inspect` checks the World Builder export version against the configured importer version, sector names, `variantIndices`, required node fields, duplicate non-empty NodeRefs, and device/PS container shape. It reports node-type counts for build diagnostics.

## Workspace layout

`build-prepare` creates:

```text
<name>/
├── <name>.cpmodproj
├── .cp77wb-build.json
├── BUILD-CP77WB.md
├── automation/
│   └── import_object_spawner_<export>.wscript
├── source/
│   ├── archive/
│   ├── raw/<export>_exported.json
│   ├── resources/<export>.xl
│   └── customSounds/
└── packed/
```

If `--world-builder-root` is supplied, cp77wb copies the exact importer from `<entSpawner>/script/import_object_spawner.wscript` and changes only `inputFilePathInRawFolder`.

## ArchiveXL generation

The generated `.xl` mirrors the upstream importer:

- `streaming.blocks` points at `<export>/all.streamingblock`;
- when device resources exist, `resource.patch` patches the Night City compiled `.devices`;
- when persistent-state entries exist, it patches the Night City compiled `.psrep`.

The export's `xlFormat` decides JSON vs YAML unless explicitly overridden.

## Build status

The manifest records every native file expected from the importer. `build-status` verifies them and also checks that the raw export's SHA-256 has not changed since workspace preparation. This makes partial/failed WolvenKit imports detectable before packing.

## Packing

`build-pack` requires `importComplete=true`. It detects `cp77tools`, `WolvenKit.CLI`, or accepts `--cli`. It is a preview unless `--run` is supplied. The wrapper invokes the documented `pack -p ... -o ...` command family and normalizes the resulting archive filename to the project name.

Important: WolvenKit CLI packing only creates the `.archive`; extra resources such as `.xl` are handled by `build-package`.

## Package and deploy

`build-package` creates the final Cyberpunk layout. Root `.xl` resources are mapped to `archive/pc/mod`; already game-relative `r6/`, `bin/`, `red4ext/`, `engine/` and `mods/` resources keep their paths. Unknown resource locations are moved into `cp77wb-unmapped-resources/` and make the package not-ready instead of guessing an install path.

`build-doctor` combines package/conflict verification with issue-only World Builder/CET/RED4ext/redscript/ArchiveXL/TweakXL log collection. Log findings produce a review state rather than being treated as proof that the current build caused an old error.

`build-deploy` is dry-run by default. Existing different files are conflicts. `--apply --overwrite` is required to replace them, and originals are copied to `<game>/.cp77wb-deploy-backups/<timestamp>/`.

## Linux-native conversion boundary

`build-backends` inspects the upstream importer and reports its WolvenKit script API dependencies. World Builder 1.0.81 uses calls including `CreateInstanceAsJSON`, `HashString`, `JsonToCR2W`, `SaveToProject` and `SaveToResources`. v0.8 does not reimplement these runtime RED schemas in Python. On Linux, cp77wb can perform every surrounding step natively; the actual Object Spawner→CR2W conversion still needs a compatible WolvenKit runtime until a cross-platform serializer path is validated.

## Claude/MCP safety

MCP workspace creation and packaging are previews unless `write=true`; pack execution is preview-only unless `run=true`; deployment requires `apply=true`. This keeps the build pipeline consistent with cp77wb's existing preview-first editing model.
