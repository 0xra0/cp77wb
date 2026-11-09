from __future__ import annotations

from collections import defaultdict

from .project import WorldBuilderProject, _xyz, node_kind
from .references import iter_known_references
from .types import Issue


def _close(a: tuple[float, float, float] | None, b: tuple[float, float, float] | None, eps: float = 1e-5) -> bool:
    if a is None or b is None:
        return True
    return all(abs(x - y) <= eps for x, y in zip(a, b))


def validate(project: WorldBuilderProject) -> list[Issue]:
    issues: list[Issue] = []
    path_map = project.path_map()

    root = project.data
    if root.get("type") in {"object", "group"} and not root.get("isUsingSpawnables") and not root.get("modulePath"):
        issues.append(Issue(
            "error", "legacy_format", project.root_path,
            "Legacy World Builder/Object Spawner format detected; open it in World Builder once or migrate it before editing with cp77wb.",
        ))

    node_refs: dict[str, list[str]] = defaultdict(list)
    references: list[tuple[str, str, str, str]] = []  # path, field, kind, value

    for entry in project.iter_nodes():
        node = entry.node
        kind = node_kind(node)

        name = node.get("name")
        if not isinstance(name, str) or not name:
            issues.append(Issue("error", "missing_name", entry.path, "Element has no valid name."))

        children = node.get("childs")
        if children is not None and not isinstance(children, list):
            issues.append(Issue("error", "invalid_children", entry.path, "`childs` must be an array."))
        elif isinstance(children, list):
            names: dict[str, int] = defaultdict(int)
            for child in children:
                if isinstance(child, dict):
                    names[str(child.get("name", ""))] += 1
            for child_name, count in names.items():
                if child_name and count > 1:
                    issues.append(Issue(
                        "error", "duplicate_sibling_name", entry.path,
                        f"{count} direct children are named {child_name!r}; hierarchy paths are ambiguous.",
                    ))

        if kind == "group":
            if not _close(_xyz(node.get("origin")), _xyz(node.get("pos"))):
                issues.append(Issue(
                    "warning", "group_position_cache_mismatch", entry.path,
                    "Group `origin` and cached `pos` differ.",
                    {"origin": node.get("origin"), "pos": node.get("pos")},
                ))

        if kind != "object":
            continue
        spawn = node.get("spawnable")
        if not isinstance(spawn, dict):
            issues.append(Issue("error", "missing_spawnable", entry.path, "Object has no `spawnable` object."))
            continue

        if not _close(_xyz(spawn.get("position")), _xyz(node.get("pos"))):
            issues.append(Issue(
                "warning", "object_position_cache_mismatch", entry.path,
                "Spawnable `position` and cached element `pos` differ.",
                {"position": spawn.get("position"), "pos": node.get("pos")},
            ))

        node_ref = spawn.get("nodeRef")
        if isinstance(node_ref, str) and node_ref:
            node_refs[node_ref].append(entry.path)

        for ref in iter_known_references(spawn):
            if ref.value and ref.value != "0":
                references.append((entry.path, ref.field, ref.kind, ref.value))

        outline_path = spawn.get("outlinePath")
        if isinstance(outline_path, str) and outline_path:
            outline = path_map.get(outline_path)
            if outline is None:
                issues.append(Issue(
                    "error", "broken_outline_path", entry.path,
                    f"Area outlinePath {outline_path!r} does not resolve inside this saved build.",
                ))
            else:
                markers = []
                for child in outline.node.get("childs", []) if isinstance(outline.node.get("childs"), list) else []:
                    if isinstance(child, dict) and isinstance(child.get("spawnable"), dict):
                        if child["spawnable"].get("modulePath") == "area/outlineMarker":
                            markers.append(child)
                if len(markers) < 3:
                    issues.append(Issue(
                        "error", "outline_too_small", entry.path,
                        f"Area outline {outline_path!r} contains {len(markers)} direct outline marker(s); World Builder requires at least 3.",
                    ))
                elif len(markers) > 255:
                    issues.append(Issue(
                        "warning", "outline_marker_limit", entry.path,
                        f"Area outline contains {len(markers)} markers; World Builder export only uses the first 255.",
                    ))

    for ref, paths in sorted(node_refs.items()):
        if len(paths) > 1:
            issues.append(Issue(
                "error", "duplicate_noderef", paths[0],
                f"NodeRef {ref!r} is used by {len(paths)} objects.",
                {"paths": paths},
            ))

    known_refs = set(node_refs)
    for source_path, field, kind, value in references:
        if kind == "noderef" and value not in known_refs:
            issues.append(Issue(
                "warning", "external_or_missing_noderef", source_path,
                f"{field} points to NodeRef {value!r}, which is not present in this saved build/export candidate.",
                {"field": field, "nodeRef": value},
            ))
        elif kind == "path" and value not in path_map:
            # outlinePath gets the stronger error above; avoid duplicate reporting.
            if not field.endswith("outlinePath"):
                issues.append(Issue(
                    "warning", "external_or_missing_path", source_path,
                    f"{field} points to path {value!r}, which is not present in this saved build.",
                    {"field": field, "path": value},
                ))

    return issues
