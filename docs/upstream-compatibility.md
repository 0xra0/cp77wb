# Upstream compatibility and scope

`cp77wb` is an external companion tool. It is not an upstream World Builder component and does not redistribute the supplied World Builder source.

The implementation is derived from the user's local World Builder source snapshot, especially:

- `modules/classes/editor/element.lua`
- `modules/classes/editor/positionable.lua`
- `modules/classes/editor/positionableGroup.lua`
- `modules/classes/editor/spawnableElement.lua`
- `modules/classes/spawn/spawnable.lua`
- `modules/classes/spawn/ai/communityArea.lua`
- `modules/classes/spawn/area/area.lua`
- `modules/classes/spawn/area/conversationArea.lua`
- `modules/classes/spawn/area/guardArea.lua`
- `modules/classes/spawn/entity/device.lua`
- `modules/utils/nodeRefRegistry.lua`
- `modules/utils/history.lua`
- `modules/utils/editor/editor.lua`
- `modules/utils/config.lua`
- `modules/utils/utils.lua`
- `modules/ui/savedUI.lua`
- `modules/ui/exportUI.lua`

## Compatibility strategy

World Builder has many spawnable subclasses and new releases can add fields. cp77wb therefore uses a loss-minimizing dictionary model: unknown fields are retained as loaded.

v0.2 also centralizes the known reference patterns derived from the current source rather than scattering hard-coded rewrite logic across commands.

## Important transform note

World Builder's runtime group rotation ultimately transforms leaf objects. cp77wb additionally updates nested group transform caches during offline rotation/scaling so serialized hierarchy state remains self-consistent. This is an intentional external-editor behavior, not a claim that upstream mutates every nested group field in exactly the same way at runtime.

Before using cp77wb against a newer World Builder release, run tests and validate a copy of a real project first. Automated source/schema drift detection remains planned; v0.3 already scans upstream resource lists for the asset catalog, while v0.4+ performs runtime identity checks before enabling live history-backed mutation; v0.5 additionally verifies the active editor/NodeRef registry for scene and reference-aware operations and reuses native `dropToSurface()` / root save-load paths.


## v0.6 compatibility scanner

Run `cp77wb compat-scan /path/to/entSpawner --project Build.json` before automated mutation against a newly updated World Builder install. The scanner reads the current `ModVersion`, dependency requirements and module paths from that source tree, compares project modules, and reports SHA-256 fingerprints for schema-critical Lua files. This replaces the previous roadmap-only drift detection with an executable compatibility check.
