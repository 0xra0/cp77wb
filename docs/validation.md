# Validation

`cp77wb validate BUILD.json` is deliberately World Builder-aware.

## Errors

- legacy pre-spawnable format that should be migrated first
- element without a valid name
- non-array `childs`
- duplicate direct sibling names (path ambiguity)
- object without a spawnable blob
- duplicate non-empty NodeRefs
- broken `outlinePath`
- an area outline with fewer than three direct outline markers

## Warnings

- group `origin` and cached `pos` disagree
- object `spawnable.position` and cached `pos` disagree
- area contains more than 255 direct outline markers (upstream export truncates)
- device connection references a NodeRef absent from this saved build

The last case is only a warning because upstream World Builder explicitly allows the possibility that a referenced NodeRef is part of another export.

## Exit status

- `0`: no errors
- `2`: one or more errors
- `--strict`: warnings also produce exit `2`

This makes validation suitable for Claude Code hooks and CI.
