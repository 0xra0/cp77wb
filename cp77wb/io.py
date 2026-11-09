from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .errors import ProjectFormatError


def load_json(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    try:
        with p.open("r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ProjectFormatError(f"Invalid JSON in {p}: {exc}") from exc
    except OSError as exc:
        raise ProjectFormatError(f"Could not read {p}: {exc}") from exc

    if not isinstance(data, dict):
        raise ProjectFormatError(f"World Builder project root must be a JSON object: {p}")
    return data


def backup_path(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    backup_dir = path.parent / ".cp77wb-backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir / f"{path.name}.{stamp}.bak"


def atomic_save_json(
    path: str | Path,
    data: dict[str, Any],
    *,
    make_backup: bool = True,
    indent: int = 2,
) -> Path | None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    backup: Path | None = None
    if make_backup and p.exists():
        backup = backup_path(p)
        shutil.copy2(p, backup)

    fd, temp_name = tempfile.mkstemp(prefix=f".{p.name}.", suffix=".tmp", dir=p.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_name, p)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise
    return backup
