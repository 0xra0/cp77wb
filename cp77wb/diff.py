from __future__ import annotations

import difflib
import json
from typing import Any


def json_diff(before: dict[str, Any], after: dict[str, Any], fromfile: str = "before", tofile: str = "after") -> str:
    a = json.dumps(before, ensure_ascii=False, indent=2, sort_keys=True).splitlines(keepends=True)
    b = json.dumps(after, ensure_ascii=False, indent=2, sort_keys=True).splitlines(keepends=True)
    return "".join(difflib.unified_diff(a, b, fromfile=fromfile, tofile=tofile))
