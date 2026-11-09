from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from .errors import Cp77wbError


LIVE_PROTOCOL = "cp77wb-live/3"
LEGACY_MUTATION_PROTOCOL = "cp77wb-live/2"
LEGACY_LIVE_PROTOCOL = "cp77wb-live/1"


class LiveBridgeError(Cp77wbError):
    pass


class LiveBridgeClient:
    """File-RPC client for the optional CET cp77wb_bridge companion mod.

    v0.5 uses protocol v3 for spatial authoring/transactions, keeps v2 support
    for v0.4-era live mutations on a v0.5 bridge, and keeps v1 support for the
    original observation-only bridge. All writes remain explicit ``apply=True``.
    """

    def __init__(self, rpc_dir: str | Path):
        self.rpc_dir = Path(rpc_dir).expanduser().resolve()
        self.requests = self.rpc_dir / "requests"
        self.responses = self.rpc_dir / "responses"

    def ensure_dirs(self) -> None:
        self.requests.mkdir(parents=True, exist_ok=True)
        self.responses.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp, path)
        except Exception:
            try:
                os.unlink(temp)
            except FileNotFoundError:
                pass
            raise

    def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float = 3.0,
        protocol: str = LIVE_PROTOCOL,
    ) -> Any:
        if timeout <= 0:
            raise ValueError("timeout must be > 0")
        self.ensure_dirs()
        request_id = uuid.uuid4().hex
        req = self.requests / f"{request_id}.json"
        resp = self.responses / f"{request_id}.json"
        payload = {
            "id": request_id,
            "protocol": protocol,
            "method": method,
            "params": params or {},
            "createdUnix": time.time(),
        }
        self._atomic_json(req, payload)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if resp.exists():
                try:
                    data = json.loads(resp.read_text(encoding="utf-8-sig"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise LiveBridgeError(f"Invalid bridge response {resp}: {exc}") from exc
                finally:
                    try:
                        resp.unlink()
                    except OSError:
                        pass
                if not isinstance(data, dict):
                    raise LiveBridgeError("Bridge response must be a JSON object")
                if data.get("ok") is not True:
                    raise LiveBridgeError(str(data.get("error", "Unknown live bridge error")))
                return data.get("result")
            time.sleep(0.05)
        try:
            req.unlink()
        except OSError:
            pass
        raise LiveBridgeError(
            f"Timed out waiting for cp77wb CET bridge in {self.rpc_dir}. Is Cyberpunk/CET running with cp77wb_bridge installed?"
        )

    def _read_request(self, method: str, params: dict[str, Any] | None = None, *, timeout: float = 3.0) -> Any:
        """Try v3, v2, then v1 for observation-call compatibility."""
        last: LiveBridgeError | None = None
        for protocol in (LIVE_PROTOCOL, LEGACY_MUTATION_PROTOCOL, LEGACY_LIVE_PROTOCOL):
            try:
                return self.request(method, params, timeout=timeout, protocol=protocol)
            except LiveBridgeError as exc:
                last = exc
                if "unsupported protocol" not in str(exc):
                    raise
        assert last is not None
        raise last

    @staticmethod
    def _dict(value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {"value": value}

    def ping(self, *, timeout: float = 3.0) -> dict[str, Any]:
        return self._dict(self._read_request("ping", timeout=timeout))

    def player(self, *, timeout: float = 3.0) -> dict[str, Any]:
        return self._dict(self._read_request("get_player_transform", timeout=timeout))

    def camera(self, *, timeout: float = 3.0) -> dict[str, Any]:
        return self._dict(self._read_request("get_camera_transform", timeout=timeout))

    def selection(self, *, timeout: float = 3.0, include_data: bool = False) -> list[dict[str, Any]]:
        value = self._read_request("get_worldbuilder_selection", {"includeData": bool(include_data)}, timeout=timeout)
        if not isinstance(value, list):
            raise LiveBridgeError("Selection response was not a list")
        return [item for item in value if isinstance(item, dict)]

    def state(self, *, timeout: float = 3.0) -> dict[str, Any]:
        return self._dict(self._read_request("get_worldbuilder_state", timeout=timeout))

    def history(self, *, timeout: float = 3.0) -> dict[str, Any]:
        return self._dict(self._read_request("get_history_state", timeout=timeout))

    def paths(self, query: str = "", *, timeout: float = 3.0, limit: int = 100) -> list[dict[str, Any]]:
        value = self._read_request("find_worldbuilder_paths", {"query": query, "limit": int(limit)}, timeout=timeout)
        if not isinstance(value, list):
            raise LiveBridgeError("Path search response was not a list")
        return [item for item in value if isinstance(item, dict)]

    def raycast(
        self,
        *,
        mode: str = "camera",
        origin: tuple[float, float, float] | None = None,
        direction: tuple[float, float, float] | None = None,
        use_physical: bool = True,
        timeout: float = 3.0,
    ) -> dict[str, Any]:
        if mode not in {"camera", "custom"}:
            raise ValueError("raycast mode must be camera or custom")
        params: dict[str, Any] = {"mode": mode, "usePhysical": bool(use_physical)}
        if mode == "custom":
            if origin is None or direction is None:
                raise ValueError("custom raycast requires origin and direction")
            params["origin"] = {"x": float(origin[0]), "y": float(origin[1]), "z": float(origin[2])}
            params["direction"] = {"x": float(direction[0]), "y": float(direction[1]), "z": float(direction[2])}
        return self._dict(self.request("raycast_scene", params, timeout=timeout))

    def select_paths(self, paths: list[str], *, apply: bool = False, timeout: float = 3.0) -> dict[str, Any]:
        if not apply:
            return {"applied": False, "operation": "select_paths", "paths": list(paths)}
        return self._dict(self.request("select_paths", {"paths": list(paths), "confirm": True}, timeout=timeout))

    def move_selection(self, x: float, y: float, z: float, *, apply: bool = False, timeout: float = 3.0) -> dict[str, Any]:
        if not apply:
            return {
                "applied": False,
                "operation": "move_selection",
                "delta": {"x": float(x), "y": float(y), "z": float(z)},
                "selection": self.selection(timeout=timeout),
            }
        return self._dict(self.request("move_selection", {"x": float(x), "y": float(y), "z": float(z), "confirm": True}, timeout=timeout))

    def rotate_selection(
        self,
        roll: float,
        pitch: float,
        yaw: float,
        *,
        apply: bool = False,
        timeout: float = 3.0,
    ) -> dict[str, Any]:
        if not apply:
            return {
                "applied": False,
                "operation": "rotate_selection",
                "delta": {"roll": float(roll), "pitch": float(pitch), "yaw": float(yaw)},
                "selection": self.selection(timeout=timeout),
            }
        return self._dict(self.request(
            "rotate_selection",
            {"roll": float(roll), "pitch": float(pitch), "yaw": float(yaw), "confirm": True},
            timeout=timeout,
        ))

    def scale_selection(
        self,
        x: float = 1.0,
        y: float = 1.0,
        z: float = 1.0,
        *,
        pivot: tuple[float, float, float] | None = None,
        allow_partial: bool = False,
        apply: bool = False,
        timeout: float = 3.0,
    ) -> dict[str, Any]:
        if x == 0 or y == 0 or z == 0:
            raise ValueError("scale factors cannot be zero")
        params: dict[str, Any] = {
            "x": float(x), "y": float(y), "z": float(z),
            "allowPartial": bool(allow_partial),
        }
        if pivot is not None:
            params["pivot"] = {"x": float(pivot[0]), "y": float(pivot[1]), "z": float(pivot[2])}
        if not apply:
            return {
                "applied": False,
                "operation": "scale_selection",
                "factors": {"x": float(x), "y": float(y), "z": float(z)},
                "pivot": params.get("pivot"),
                "allowPartial": bool(allow_partial),
                "selection": self.selection(timeout=timeout),
            }
        params["confirm"] = True
        return self._dict(self.request("scale_selection", params, timeout=timeout))

    def snap_selection(
        self,
        *,
        direction: tuple[float, float, float] = (0.0, 0.0, -1.0),
        apply: bool = False,
        timeout: float = 8.0,
    ) -> dict[str, Any]:
        dx, dy, dz = (float(v) for v in direction)
        if dx == 0 and dy == 0 and dz == 0:
            raise ValueError("snap direction cannot be zero")
        if not apply:
            return {
                "applied": False,
                "operation": "snap_selection",
                "direction": {"x": dx, "y": dy, "z": dz},
                "selection": self.selection(timeout=timeout),
            }
        return self._dict(self.request(
            "snap_selection",
            {"direction": {"x": dx, "y": dy, "z": dz}, "confirm": True},
            timeout=timeout,
        ))

    def duplicate_selection(
        self,
        *,
        count: int = 1,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        keep_noderefs: bool = False,
        apply: bool = False,
        timeout: float = 5.0,
    ) -> dict[str, Any]:
        if count < 1:
            raise ValueError("count must be >= 1")
        if not apply:
            return {
                "applied": False,
                "operation": "duplicate_selection",
                "count": int(count),
                "perCopyOffset": {"x": float(x), "y": float(y), "z": float(z)},
                "keepNodeRefs": bool(keep_noderefs),
                "selection": self.selection(timeout=timeout, include_data=True),
            }
        return self._dict(self.request(
            "duplicate_selection",
            {
                "count": int(count), "x": float(x), "y": float(y), "z": float(z),
                "keepNodeRefs": bool(keep_noderefs), "confirm": True,
            },
            timeout=timeout,
        ))

    def surface_scatter(
        self,
        *,
        count: int,
        half_x: float = 5.0,
        half_y: float = 5.0,
        half_z: float = 0.0,
        seed: int = 1,
        random_yaw: bool = True,
        direction: tuple[float, float, float] = (0.0, 0.0, -1.0),
        keep_noderefs: bool = False,
        apply: bool = False,
        timeout: float = 20.0,
    ) -> dict[str, Any]:
        if count < 1 or count > 500:
            raise ValueError("count must be between 1 and 500")
        dx, dy, dz = (float(v) for v in direction)
        if dx == 0 and dy == 0 and dz == 0:
            raise ValueError("scatter direction cannot be zero")
        params = {
            "count": int(count),
            "halfX": float(half_x), "halfY": float(half_y), "halfZ": float(half_z),
            "seed": int(seed), "randomYaw": bool(random_yaw),
            "direction": {"x": dx, "y": dy, "z": dz},
            "keepNodeRefs": bool(keep_noderefs),
        }
        if not apply:
            return {
                "applied": False,
                "operation": "surface_scatter",
                **params,
                "selection": self.selection(timeout=min(timeout, 5.0), include_data=True),
            }
        params["confirm"] = True
        return self._dict(self.request("surface_scatter", params, timeout=timeout))

    def batch_transform(
        self,
        operations: list[dict[str, Any]],
        *,
        apply: bool = False,
        timeout: float = 15.0,
    ) -> dict[str, Any]:
        if not operations:
            raise ValueError("batch requires at least one operation")
        allowed = {"move", "rotate", "scale", "snap"}
        normalized: list[dict[str, Any]] = []
        for op in operations:
            if not isinstance(op, dict) or str(op.get("type", "")) not in allowed:
                raise ValueError("batch operations must be objects with type move, rotate, scale, or snap")
            normalized.append(dict(op))
        if not apply:
            return {
                "applied": False,
                "operation": "batch_transform",
                "operations": normalized,
                "selection": self.selection(timeout=min(timeout, 5.0)),
            }
        return self._dict(self.request("batch_transform", {"operations": normalized, "confirm": True}, timeout=timeout))

    def delete_selection(self, *, apply: bool = False, timeout: float = 3.0) -> dict[str, Any]:
        if not apply:
            return {"applied": False, "operation": "delete_selection", "selection": self.selection(timeout=timeout)}
        return self._dict(self.request("delete_selection", {"confirm": True}, timeout=timeout))

    def spawn_serialized(
        self,
        data: dict[str, Any],
        *,
        parent_path: str | None = None,
        placement: str = "serialized",
        distance: float = 4.0,
        snap_to_surface: bool = False,
        apply: bool = False,
        timeout: float = 8.0,
    ) -> dict[str, Any]:
        if not isinstance(data, dict) or not data.get("modulePath"):
            raise ValueError("serialized World Builder data must contain modulePath")
        if placement not in {"serialized", "camera", "player"}:
            raise ValueError("placement must be serialized, camera or player")
        if not apply:
            return {
                "applied": False,
                "operation": "spawn_serialized",
                "parentPath": parent_path,
                "placement": placement,
                "distance": float(distance),
                "snapToSurface": bool(snap_to_surface),
                "data": data,
            }
        params: dict[str, Any] = {
            "data": data, "placement": placement, "distance": float(distance),
            "snapToSurface": bool(snap_to_surface), "confirm": True,
        }
        if parent_path:
            params["parentPath"] = parent_path
        return self._dict(self.request("spawn_serialized", params, timeout=timeout))

    def save_roots(self, *, apply: bool = False, timeout: float = 5.0) -> dict[str, Any]:
        if not apply:
            return {"applied": False, "operation": "save_roots", "state": self.state(timeout=timeout)}
        return self._dict(self.request("save_roots", {"confirm": True}, timeout=timeout))

    def reload_root(self, path: str, *, apply: bool = False, timeout: float = 8.0) -> dict[str, Any]:
        if not path.startswith("/"):
            raise ValueError("reload path must be a World Builder path such as /MyBuild")
        if not apply:
            return {"applied": False, "operation": "reload_root", "path": path}
        return self._dict(self.request("reload_root", {"path": path, "confirm": True}, timeout=timeout))

    def undo(self, *, apply: bool = False, timeout: float = 3.0) -> dict[str, Any]:
        if not apply:
            return {"applied": False, "operation": "undo", "history": self.history(timeout=timeout)}
        return self._dict(self.request("history_undo", {"confirm": True}, timeout=timeout))

    def redo(self, *, apply: bool = False, timeout: float = 3.0) -> dict[str, Any]:
        if not apply:
            return {"applied": False, "operation": "redo", "history": self.history(timeout=timeout)}
        return self._dict(self.request("history_redo", {"confirm": True}, timeout=timeout))
