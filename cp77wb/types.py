from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    path: str
    message: str
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "severity": self.severity,
            "code": self.code,
            "path": self.path,
            "message": self.message,
        }
        if self.details:
            out["details"] = self.details
        return out


@dataclass(frozen=True)
class NodeEntry:
    path: str
    node: dict[str, Any]
    parent: dict[str, Any] | None
