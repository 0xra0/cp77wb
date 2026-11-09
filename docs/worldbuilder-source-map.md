# World Builder architecture / source map

This page is based on the supplied `CP77_entSpawner-main` source tree.

## Key directories

| Path | Purpose for cp77wb |
|---|---|
| `data/objects/` | Saved root groups/builds (`.json`) |
| `data/favorite/` | Favorites/prefab-related data |
| `data/spawnables/` | Lists/templates used by Spawn New |
| `data/exportTemplates/` | Saved export setups |
| `modules/classes/editor/` | Hierarchy, transforms, group/randomization/scatter behaviour |
| `modules/classes/spawn/` | Spawnable types and their save/export fields |
| `modules/ui/savedUI.lua` | Loading/saving/backward compatibility of saved builds |
| `modules/ui/exportUI.lua` | Export preparation and World Builder's export-time checks |
| `modules/utils/nodeRefRegistry.lua` | NodeRef indexing, duplicate detection and generation |
| `script/import_object_spawner.wscript` | WolvenKit-side importer script included by upstream |

## Saved hierarchy

`element:serialize()` stores common hierarchy metadata and recursively serializes `childs`.

`positionable:serialize()` adds transform/editor state plus cached `pos`.

`positionableGroup:serialize()` adds:

```json
{
  "origin": {"x": 0, "y": 0, "z": 0},
  "originInitialized": true,
  "rotation": {"roll": 0, "pitch": 0, "yaw": 0}
}
```

`spawnableElement:serialize()` stores the subclass-specific spawnable blob returned by `spawnable:save()`.

## Spawnable base fields

The base `spawnable:save()` contains at least:

- `modulePath`
- `position`
- `rotation`
- `spawnData`
- `dataType`
- `app`
- `rotationRelative`
- streaming distances (`primaryRange`, `secondaryRange`, `uk10`, `uk11`)
- `nodeRef`
- streaming-reference-point override fields

Every subclass may append more fields. This is why cp77wb preserves unknown keys rather than decoding into a closed schema.

## NodeRefs

World Builder's registry is scoped per root group. It detects duplicate non-empty NodeRefs and can generate refs in a shape similar to:

```text
$/[optional-prefix/]parent/#root_object
```

cp77wb v0.2+ implements compatible NodeRef generation for external automation and repairs known NodeRef references during supported edits.

## Areas

Area spawnables save an `outlinePath` pointing to a group containing direct `area/outlineMarker` children. They also save cached `markers` and `height` used later by export. World Builder only accepts candidate outline groups containing at least three direct markers. During native export, only the first 255 outline markers are used.

cp77wb therefore repairs known `outlinePath` references on rename and refreshes marker caches after geometry moves.

## Native export

World Builder uses an editable intermediary representation in-game, then `exportUI.lua` generates data for WolvenKit's `import_object_spawner.wscript`, which produces native world-edit resources. cp77wb v0.5 still leaves final native-sector conversion to the World Builder/WolvenKit export path; its focus is safe authoring, verified resources, reusable Favorites and Claude automation.


## Spawnable catalogs and Favorites

World Builder's `modules/ui/spawnUI.lua` maps Spawn New categories/variants to text lists and JSON templates below `data/spawnables/`. The configuration helpers load `.txt` choices as resource paths and `.json` files as richer spawnable templates. cp77wb v0.3+ mirrors those mappings into a local SQLite/FTS catalog without patching World Builder.

`data/favorite/*.json` stores Favorite categories. Each entry contains the Favorite name/tags/icon and the serialized World Builder object/group in `data`. cp77wb v0.3+ writes this native format so reusable generated groups appear through World Builder's existing Favorites UI.

## Live state boundary

The loaded CET mod is reachable as `GetMod("entSpawner")`. The active World Builder editor exposes its selection through the spawned UI state, including `baseUI.spawnedUI.selectedPaths`. The optional `cp77wb_bridge` companion reads that state and player/camera transforms over file-RPC. In v0.5 it performs guarded live edits only after proving that the resolved `modules/utils/history` table owns the exact active `spawnedUI`. Spatial operations also verify the active editor/NodeRef registry as needed, reuse `editor.getRaySceneIntersection()` and `dropToSurface()`, and coordinate root save/reload through World Builder's own model.
