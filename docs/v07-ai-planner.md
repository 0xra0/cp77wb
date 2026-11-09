# v0.7 AI construction planner

v0.7 adds a deterministic planning layer between an LLM and World Builder. Claude can describe intent, but cp77wb resolves real local assets, computes placements, checks approximate spatial constraints, validates the resulting saved-build structure, and only then writes when explicitly allowed.

## Semantic asset index

Build the normal World Builder asset catalog first, then add semantic facets:

```bash
cp77wb assets-build /path/to/entSpawner
cp77wb semantic-build /path/to/entSpawner/.cp77wb/assets.sqlite3
```

Semantic tags are derived locally from asset/depot names using an explicit taxonomy. Current facets are `roles`, `styles`, `materials`, and `conditions`. No cloud embeddings or online model calls are used.

Search:

```bash
cp77wb semantic-search assets.sqlite3 "arasaka industrial wall" \
  --role wall --style arasaka --variant Mesh
```

Results always retain the real catalog `#ID` and depot path.

### Overrides

Derived tags can be supplemented without editing the base catalog:

```json
{
  "overrides": [
    {"asset":"#40238", "tags":["hero_asset"], "styles":["custom_style"]},
    {"contains":"my_mod\\environment", "tags":["my_pack"]}
  ]
}
```

```bash
cp77wb semantic-build assets.sqlite3 --overrides semantic-overrides.json
```

Overrides only add tags/facets; they do not rewrite the underlying asset record.

## Asset bounds

World Builder's spawnable catalogs do not provide reliable mesh dimensions. v0.7 therefore keeps explicit measured/imported bounds separate from low-confidence role heuristics.

```bash
cp77wb bounds-set assets.sqlite3 40238 --x 3.0 --y 0.25 --z 3.2 --source measured
cp77wb bounds-info assets.sqlite3 --id 40238
```

Bulk import:

```json
{
  "bounds": [
    {"asset":"#40238", "size":[3.0,0.25,3.2], "source":"measured", "confidence":1.0}
  ]
}
```

```bash
cp77wb bounds-import assets.sqlite3 bounds.json
```

If no explicit bounds exist, cp77wb can use role-based planning bounds such as wall/door/furniture/container. Those results have low confidence and are explicitly marked `approximate` in collision reports.

## Collision scan

```bash
cp77wb collisions Build.json --catalog assets.sqlite3
```

The offline scanner uses yaw-aware 2D oriented rectangles plus vertical extent, including saved `spawnable.scale` when present.

```bash
cp77wb collisions Build.json --catalog assets.sqlite3 --clearance 0.25
```

Use `--explicit-only` when heuristic geometry should be excluded entirely.

This is a planning aid, not REDengine collision. For actual scene/surface intersection use the live bridge raycast/snap functions.

## Construction plan format

Plan schema: `cp77wb-plan/1`.

Example:

```json
{
  "schema":"cp77wb-plan/1",
  "name":"Warehouse Office",
  "parent":"/Build",
  "origin":[100,200,5],
  "room":{
    "width":12,
    "depth":8,
    "wallStep":2,
    "wall":{"asset":"#40238"},
    "floor":{"asset":"#60952"},
    "floorStep":2,
    "doors":[
      {"side":"north", "offset":0, "width":2.2, "asset":"#62873", "name":"Office Door"}
    ]
  },
  "placements":[
    {"asset":"#67472", "position":[2,1,0], "yaw":90, "name":"Crate"}
  ],
  "scatter":[
    {
      "asset":"#67472",
      "count":5,
      "seed":2077,
      "clearance":0.3,
      "region":{"center":[0,0,0], "halfExtents":[4,2.5,0]}
    }
  ]
}
```

Room door openings remove wall placements whose centers fall inside the requested opening. Scatter uses a deterministic rejection solver against known/planned OBB footprints.

### Semantic selection inside a plan

Exact IDs are preferred. A plan may explicitly authorize semantic auto-selection:

```json
{
  "semanticQuery":"dirty warehouse crate",
  "role":"container",
  "autoSelect":true,
  "position":[1,2,0]
}
```

Without `autoSelect:true`, a semantic plan entry is rejected. A compiled plan records the chosen ID plus candidate list in `assetSelections`, so the selection is reviewable.

## Plan → preview → apply

Compile without touching a World Builder file:

```bash
cp77wb plan-compile plan.json --catalog assets.sqlite3 --output compiled-plan.json
```

Preview against an actual build:

```bash
cp77wb plan-preview Build.json plan.json --catalog assets.sqlite3
```

Preview performs:

1. asset resolution;
2. deterministic placement generation;
3. approximate collision checks;
4. application to an in-memory clone;
5. normal cp77wb World Builder validation.

Apply still defaults to a diff:

```bash
cp77wb plan-apply Build.json plan.json --catalog assets.sqlite3
```

Write only after review:

```bash
cp77wb plan-apply Build.json plan.json --catalog assets.sqlite3 --write
```

Generated content is grouped under the plan name and remains ordinary editable World Builder hierarchy data.

## Path structures

Fence:

```bash
cp77wb generate-fence Build.json /Build \
  --catalog assets.sqlite3 \
  --segment-asset '#1001' --post-asset '#1002' \
  --marker-group /Build/FencePath --spacing 2
```

Road strip:

```bash
cp77wb generate-road Build.json /Build \
  --catalog assets.sqlite3 \
  --tile-asset '#2001' --edge-asset '#2002' \
  --points '[[0,0,0],[20,0,0],[30,10,0]]' \
  --spacing 2 --width 6
```

Cable/pipe chain:

```bash
cp77wb generate-cable Build.json /Build \
  --catalog assets.sqlite3 \
  --segment-asset '#3001' \
  --marker-group /Build/CablePath --spacing 1
```

The cable helper deliberately repeats real segments rather than guessing mesh stretching or a forward axis.

## Claude workflow

A recommended agent flow is:

1. `wb_compat_scan`
2. `wb_semantic_search` for candidate assets
3. optionally `wb_bounds_info` / `wb_bounds_set`
4. `wb_plan_compile`
5. inspect `assetSelections`, warnings and collisions
6. `wb_plan_preview`
7. `wb_plan_apply` with `write=false`
8. only after review, `wb_plan_apply` with `write=true`
9. `wb_validate`

This keeps natural-language interpretation in Claude while transforms, reference preservation, asset identity and validation remain deterministic code paths.
