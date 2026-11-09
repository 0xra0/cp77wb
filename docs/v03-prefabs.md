# v0.3 native prefabs through World Builder Favorites

World Builder's Favorites system stores serialized editor objects/groups under `data/favorite/*.json`. That makes it a useful native prefab boundary without modifying World Builder.

## Export an object or group

```bash
cp77wb favorite-add Build.json /Build/Interior/DeskSet /path/to/entSpawner \
  --category "Interior Prefabs" \
  --tag office --tag desk
```

The generated favorite contains:

```json
{
  "name": "DeskSet",
  "tags": {"office": true, "desk": true},
  "data": {"...": "the full serialized WB object/group"},
  "icon": ""
}
```

The category wrapper mirrors `modules/classes/favorites/category.lua`:

```text
name
icon
headerOpen
grouped
virtualGroupsPS
favorites[]
```

## Why groups work as prefabs

When World Builder spawns a Favorite it instantiates the serialized editor class, loads it silently, then applies the requested position/rotation to the loaded root before making it visible. Therefore a positionable group preserves its internal relative layout and behaves as a reusable prefab.

## Existing categories

`cp77wb` finds categories by the category `name` stored inside the JSON, not by guessing filenames. Existing files are backed up before modification.

```bash
cp77wb favorites-list /path/to/entSpawner
```

## Claude workflow

```text
wb_get / inspect source group
→ wb_favorite_add write=false
→ review category/name/tags
→ wb_favorite_add write=true
```

This is intentionally separate from modifying World Builder source code.
