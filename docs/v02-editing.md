# v0.2 editing primitives

## World Builder naming compatibility

The supplied World Builder source uses `utils.createFileName()` when renaming elements. It replaces these characters with `_`:

```text
< > : " / \ | ? * ' [space]
```

World Builder's `utils.generateCopyName()` increments trailing decimal digits when present; otherwise it appends `_1`. cp77wb uses the same behavior for generated duplicate names and NodeRef collisions.

## NodeRef generation

The supplied `modules/utils/nodeRefRegistry.lua` generates:

```text
$/ + optional nodeRefPrefix + parent + /# + root + _ + object
```

where parent/root/object are lowercase and passed through World Builder filename sanitization.

Example:

```text
root:   MegaBuild
parent: Doors
object: Service Door
prefix: my_mod

$/my_mod/doors/#megabuild_service_door
```

If the reference already exists, World Builder repeatedly applies `generateCopyName()`. cp77wb does the same.

## Duplicate semantics

cp77wb deliberately goes one step safer than a raw JSON copy:

1. deep-copy the selected subtree;
2. generate a sibling-unique WB name;
3. repair internal path references under the copied root;
4. regenerate **existing non-empty** NodeRefs inside the copy;
5. rewrite known copied references from old internal NodeRefs to their generated equivalents;
6. optionally apply per-copy translation;
7. refresh linked area marker caches.

It does not generate NodeRefs for objects that originally had an empty NodeRef.

## Known reference registry

v0.2 recognizes reference-bearing forms observed in the supplied WB source:

- nested `nodeRef` fields such as device connections;
- `workspots[]`;
- `spotNodeRefs[]`;
- `communityRef`;
- `pursuitArea`;
- `outlinePath`;
- nested RED JSON values with `$type: NodeRef` and string `$value`.

This registry is used by validation, NodeRef changes and duplication.

## Rotation

For group geometry, cp77wb uses the same ZYX rotation matrix ordering used by World Builder's `utils.rotatePoint()` and composes descendant world rotations with a delta quaternion.

Offline transforms also update nested group origins/rotations so serialized hierarchy caches remain coherent. This is intentionally more conservative for file editing than relying on transient runtime group state.

## Scaling

Positionable groups have no serialized group-scale property. cp77wb therefore implements group scaling as geometry scaling around the group's origin/pivot:

```text
new_position = pivot + (old_position - pivot) * factors
```

Existing leaf `spawnable.scale` vectors are multiplied too. Missing scale vectors are not invented unless explicitly requested for a single object.

## Selection safety

`align` and `distribute` reject selections where one selected path is an ancestor of another selected path. Otherwise moving the parent would also move the child and make the requested operation ambiguous.
