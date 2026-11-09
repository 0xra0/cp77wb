# v0.3 asset intelligence

## Why the index exists

Claude must not invent REDengine depot paths. `cp77wb` therefore builds a local catalog from the same files World Builder uses to populate its Spawn UI.

World Builder loads two source styles:

1. path lists (`*.txt`) through `config.loadLists()`;
2. JSON templates through `config.loadFiles()`.

`cp77wb assets-build` mirrors that boundary into SQLite.

## Indexed World Builder sources

The v0.3 classifier mirrors `modules/ui/spawnUI.lua` and the `spawnDataPath/modulePath` values from the supplied source. Examples:

| Category | Variant | World Builder module | Source |
|---|---|---|---|
| Entity | Template | `entity/entityTemplate` | `data/spawnables/entity/templates` |
| Entity | Device | `entity/device` | `data/spawnables/entity/device` |
| Mesh | Mesh | `mesh/mesh` | `data/spawnables/mesh/all` |
| Mesh | Rotating Mesh | `mesh/rotatingMesh` | same mesh list |
| Mesh | Proxy Mesh | `mesh/proxyMesh` | same mesh list |
| Mesh | Cloth Mesh | `mesh/clothMesh` | `data/spawnables/mesh/cloth` |
| Mesh | Dynamic Mesh | `physics/dynamicMesh` | `data/spawnables/mesh/physics` |
| Deco | Particles | `visual/particle` | particle path list |
| Deco | Decals | `visual/decal` | material-instance path list |
| Deco | Effects | `visual/effect` | effect path list |
| Lighting | Static Light | `light/light` | JSON templates |
| AI | AI Spot | `ai/aiSpot` | workspot path list |

JSON templates retain their complete `spawnable` payload, so fields such as light intensity/radius are preserved when an indexed template is inserted into a build.

## Build

```bash
cp77wb assets-build /path/to/entSpawner
```

The index includes a source fingerprint and records the World Builder root it came from.

## Search

```bash
cp77wb assets-search DB "industrial pipe" --variant Mesh
cp77wb assets-search DB "arasaka wall" --module mesh/mesh
cp77wb assets-search DB "elevator" --category Entity
cp77wb assets-search DB "smoke" --ext particle
```

The FTS query uses strict AND first and falls back to ranked OR only when strict search has no results. Filters are still enforced.

## Stable IDs

Search results are displayed as:

```text
#75857 Mesh/Mesh mesh/mesh base\...\industrial_pipe_structure_a_cap.mesh
```

The recommended agent flow is:

```text
wb_assets_search
→ user/Claude selects one result
→ wb_spawn_asset asset="#75857"
```

This is safer than allowing an LLM to resolve an ambiguous phrase implicitly.

## Asset insertion

`spawn-asset` creates a standard `modules/classes/editor/spawnableElement`. For path-list resources it supplies the minimal fields World Builder requires and lets the corresponding Lua class fill subclass defaults on load. For JSON templates it copies the template payload and overrides only placement/module identity fields needed for the requested insertion.

Unknown template fields are retained.
