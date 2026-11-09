from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator


@dataclass
class MutableReference:
    kind: str  # noderef | path
    field: str
    container: dict[str, Any] | list[Any]
    key: str | int
    value: str

    def set(self, value: str) -> None:
        self.container[self.key] = value  # type: ignore[index]
        self.value = value


NODE_REF_SCALAR_KEYS = {'pursuitArea', 'communityRef'}
NODE_REF_LIST_KEYS = {'workspots', 'spotNodeRefs'}
PATH_SCALAR_KEYS = {'outlinePath'}


def iter_known_references(spawnable: dict[str, Any]) -> Iterator[MutableReference]:
    """Yield mutable known WB references inside one serialized spawnable.

    The top-level spawnable.nodeRef is a definition and is intentionally not
    returned. Nested `nodeRef` keys are references (e.g. deviceConnections).
    Additional selectors are derived from current WB source: conversation-area
    workspots, community spot refs, guard-area community/pursuit refs, outline
    paths, and serialized `$type: NodeRef` values in instance data.
    """

    def walk(value: Any, field_path: str, *, top_level: bool = False) -> Iterator[MutableReference]:
        if isinstance(value, dict):
            if value.get('$type') == 'NodeRef' and isinstance(value.get('$value'), str):
                yield MutableReference('noderef', field_path + '.$value', value, '$value', value['$value'])
                # Do not return; other fields may also contain references.
            for key, child in list(value.items()):
                path = f'{field_path}.{key}' if field_path else key
                if top_level and key == 'nodeRef':
                    continue
                if key == 'nodeRef' and isinstance(child, str):
                    yield MutableReference('noderef', path, value, key, child)
                    continue
                if key in NODE_REF_SCALAR_KEYS and isinstance(child, str):
                    yield MutableReference('noderef', path, value, key, child)
                    continue
                if key in PATH_SCALAR_KEYS and isinstance(child, str):
                    yield MutableReference('path', path, value, key, child)
                    continue
                if key in NODE_REF_LIST_KEYS and isinstance(child, list):
                    for i, item in enumerate(child):
                        if isinstance(item, str):
                            yield MutableReference('noderef', f'{path}[{i}]', child, i, item)
                        else:
                            yield from walk(item, f'{path}[{i}]')
                    continue
                yield from walk(child, path)
        elif isinstance(value, list):
            for i, child in enumerate(value):
                yield from walk(child, f'{field_path}[{i}]')

    yield from walk(spawnable, 'spawnable', top_level=True)


def rewrite_known_references(spawnable: dict[str, Any], *, noderefs: dict[str, str] | None = None, paths: dict[str, str] | None = None) -> int:
    noderefs = noderefs or {}
    paths = paths or {}
    changed = 0
    for ref in iter_known_references(spawnable):
        mapping = noderefs if ref.kind == 'noderef' else paths
        new = mapping.get(ref.value)
        if new is not None and new != ref.value:
            ref.set(new)
            changed += 1
            continue
        # Prefix rewrite is needed for paths below a renamed/duplicated group.
        if ref.kind == 'path':
            for old_prefix, new_prefix in paths.items():
                if ref.value.startswith(old_prefix + '/'):
                    ref.set(new_prefix + ref.value[len(old_prefix):])
                    changed += 1
                    break
    return changed
