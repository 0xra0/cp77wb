# Saved-build file format

World Builder saves root-level groups in:

```text
Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods/entSpawner/data/objects/<name>.json
```

The format is an editor-oriented hierarchy, not the final REDengine `streamingsector` format.

## Common element fields

Observed in `modules/classes/editor/element.lua`:

```json
{
  "name": "Example",
  "modulePath": "modules/classes/editor/positionableGroup",
  "headerOpen": true,
  "propertyHeaderStates": {},
  "visible": true,
  "hiddenByParent": false,
  "expandable": true,
  "selected": false,
  "isUsingSpawnables": true,
  "childs": []
}
```

Editor versions can add fields. Do not strip unknown values.

## Groups

Normal group module:

```text
modules/classes/editor/positionableGroup
```

Other editor group types currently include randomized and scattered groups. A normal group stores its world `origin`, cached `pos` and Euler `rotation`.

## Objects

Leaf editor objects use:

```text
modules/classes/editor/spawnableElement
```

Their game-facing data lives under `spawnable`:

```json
{
  "name": "My mesh",
  "modulePath": "modules/classes/editor/spawnableElement",
  "pos": {"x": 1, "y": 2, "z": 3},
  "spawnable": {
    "modulePath": "mesh/mesh",
    "position": {"x": 1, "y": 2, "z": 3, "w": 0},
    "rotation": {"roll": 0, "pitch": 0, "yaw": 90},
    "spawnData": "base\\...\\thing.mesh",
    "nodeRef": ""
  },
  "childs": []
}
```

`pos` is a convenience/editor cache; `spawnable.position` is the leaf object's authoritative spawn position in the current source.

## Path semantics

World Builder hierarchy paths look like:

```text
/RootGroup/ChildGroup/Object
```

Area `outlinePath` values use these paths. A rename can therefore break an area if dependent path strings are not repaired.

## Backward compatibility

`modules/ui/savedUI.lua` contains a `backwardComp()` pass for older Object Spawner structures (`type = object/group`, legacy `path`, and builds without `isUsingSpawnables`). cp77wb detects these legacy structures and refuses to silently reinterpret them as the current saved-build schema.
