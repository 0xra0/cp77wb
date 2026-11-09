from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

_PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_.-]*)\}")


def parse_parameter_assignments(values: list[str]) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for item in values:
        if "=" not in item:
            raise ValueError(f"Expected KEY=VALUE, got {item!r}")
        key, raw = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("Parameter name cannot be empty")
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = raw
        params[key] = value
    return params


def _lookup(params: dict[str, Any], key: str) -> Any:
    if key in params:
        return params[key]
    current: Any = params
    for part in key.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(key)
        current = current[part]
    return current


def render_value(value: Any, params: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {k: render_value(v, params) for k, v in value.items()}
    if isinstance(value, list):
        return [render_value(v, params) for v in value]
    if not isinstance(value, str):
        return copy.deepcopy(value)
    full = _PLACEHOLDER.fullmatch(value)
    if full:
        return copy.deepcopy(_lookup(params, full.group(1)))

    def repl(match: re.Match[str]) -> str:
        return str(_lookup(params, match.group(1)))

    return _PLACEHOLDER.sub(repl, value)


def render_template_file(template_path: str | Path, params: dict[str, Any], output_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(template_path)
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    defaults = data.pop("__parameters__", {}) if isinstance(data, dict) else {}
    merged = dict(defaults) if isinstance(defaults, dict) else {}
    merged.update(params)
    rendered = render_value(data, merged)
    result = {"template": str(path.resolve()), "parameters": merged, "rendered": rendered}
    if output_path is not None:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rendered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result["output"] = str(out.resolve())
    return result
