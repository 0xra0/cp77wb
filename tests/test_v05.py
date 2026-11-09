from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from cp77wb import __version__
from cp77wb.live import LIVE_PROTOCOL, LiveBridgeClient
from cp77wb.logs import discover_logs, normalize_game_root, read_logs
from cp77wb.mcp_server import TOOLS, call_tool


class RpcCapture:
    def __init__(self, rpc: Path, result: object):
        self.rpc = rpc
        self.result = result
        self.request: dict | None = None
        self.thread = threading.Thread(target=self._run)

    def _run(self):
        requests = self.rpc / "requests"
        deadline = time.monotonic() + 2.5
        while time.monotonic() < deadline:
            files = list(requests.glob("*.json")) if requests.exists() else []
            if files:
                req_path = files[0]
                req = json.loads(req_path.read_text(encoding="utf-8"))
                self.request = req
                response = self.rpc / "responses" / f"{req['id']}.json"
                response.parent.mkdir(parents=True, exist_ok=True)
                response.write_text(json.dumps({
                    "id": req["id"], "protocol": LIVE_PROTOCOL, "ok": True,
                    "result": self.result,
                }), encoding="utf-8")
                req_path.unlink(missing_ok=True)
                return
            time.sleep(0.01)

    def start(self):
        self.thread.start()
        return self

    def finish(self):
        self.thread.join(timeout=1)
        if self.thread.is_alive():
            raise AssertionError("fake bridge did not receive a request")
        if self.request is None:
            raise AssertionError("fake bridge captured no request")
        return self.request


class LiveV05Tests(unittest.TestCase):
    def test_version_and_protocol(self):
        self.assertEqual(__version__, "1.0.1")
        self.assertEqual(LIVE_PROTOCOL, "cp77wb-live/3")

    def test_applied_scale_uses_v3_and_confirmation(self):
        with tempfile.TemporaryDirectory() as td:
            rpc = Path(td) / "rpc"
            capture = RpcCapture(rpc, {"applied": True, "changed": 2}).start()
            result = LiveBridgeClient(rpc).scale_selection(
                1.25, 0.75, 2.0,
                pivot=(10, 20, 30), allow_partial=True,
                apply=True, timeout=1.5,
            )
            request = capture.finish()
            self.assertTrue(result["applied"])
            self.assertEqual(request["protocol"], "cp77wb-live/3")
            self.assertEqual(request["method"], "scale_selection")
            self.assertTrue(request["params"]["confirm"])
            self.assertEqual(request["params"]["pivot"]["z"], 30.0)
            self.assertTrue(request["params"]["allowPartial"])

    def test_snap_rejects_zero_direction_without_rpc(self):
        with tempfile.TemporaryDirectory() as td:
            rpc = Path(td) / "rpc"
            with self.assertRaises(ValueError):
                LiveBridgeClient(rpc).snap_selection(direction=(0, 0, 0), apply=True)
            self.assertFalse((rpc / "requests").exists())

    def test_batch_rejects_unknown_operation(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                LiveBridgeClient(Path(td) / "rpc").batch_transform([{"type": "explode"}])

    def test_applied_batch_is_single_v3_request(self):
        with tempfile.TemporaryDirectory() as td:
            rpc = Path(td) / "rpc"
            capture = RpcCapture(rpc, {"applied": True, "operations": [{"type": "move"}, {"type": "snap"}]}).start()
            result = LiveBridgeClient(rpc).batch_transform([
                {"type": "move", "x": 1, "z": 2},
                {"type": "snap", "direction": {"x": 0, "y": 0, "z": -1}},
            ], apply=True, timeout=1.5)
            request = capture.finish()
            self.assertTrue(result["applied"])
            self.assertEqual(request["method"], "batch_transform")
            self.assertEqual(len(request["params"]["operations"]), 2)
            self.assertTrue(request["params"]["confirm"])

    def test_surface_scatter_applied_parameters(self):
        with tempfile.TemporaryDirectory() as td:
            rpc = Path(td) / "rpc"
            capture = RpcCapture(rpc, {"applied": True, "created": 12, "nodeRefsRemapped": True}).start()
            result = LiveBridgeClient(rpc).surface_scatter(
                count=12, half_x=8, half_y=2, seed=2077,
                random_yaw=False, keep_noderefs=False,
                apply=True, timeout=1.5,
            )
            request = capture.finish()
            self.assertEqual(result["created"], 12)
            self.assertEqual(request["method"], "surface_scatter")
            self.assertEqual(request["params"]["seed"], 2077)
            self.assertFalse(request["params"]["randomYaw"])
            self.assertFalse(request["params"]["keepNodeRefs"])
            self.assertTrue(request["params"]["confirm"])

    def test_spawn_preview_can_request_surface_snap_without_game(self):
        with tempfile.TemporaryDirectory() as td:
            data = {"modulePath": "modules/classes/editor/spawnableElement", "spawnable": {"modulePath": "mesh/mesh"}}
            result = LiveBridgeClient(Path(td) / "rpc").spawn_serialized(
                data, placement="camera", snap_to_surface=True, apply=False
            )
            self.assertFalse(result["applied"])
            self.assertTrue(result["snapToSurface"])
            self.assertFalse((Path(td) / "rpc" / "requests").exists())

    def test_save_and_reload_require_explicit_apply_for_rpc(self):
        with tempfile.TemporaryDirectory() as td:
            client = LiveBridgeClient(Path(td) / "rpc")
            result = client.reload_root("/Demo", apply=False)
            self.assertFalse(result["applied"])
            self.assertEqual(result["path"], "/Demo")
            self.assertFalse((Path(td) / "rpc" / "requests").exists())

    def test_v05_tools_registered(self):
        names = {tool["name"] for tool in TOOLS}
        for name in {
            "wb_logs", "wb_live_raycast", "wb_live_scale", "wb_live_snap",
            "wb_live_batch", "wb_live_surface_scatter", "wb_live_save", "wb_live_reload",
        }:
            self.assertIn(name, names)
        self.assertGreaterEqual(len(names), 45)

    def test_bridge_source_has_v3_guards_and_native_wb_apis(self):
        text = (Path(__file__).parents[1] / "extras" / "cp77wb_bridge" / "init.lua").read_text(encoding="utf-8")
        self.assertIn('protocol = "cp77wb-live/3"', text)
        self.assertIn('package.loaded["modules/utils/history"]', text)
        self.assertIn('loadedModule("modules/utils/editor/editor")', text)
        self.assertIn("editor.spawnedUI ~= sUI", text)
        self.assertIn("editor.getRaySceneIntersection", text)
        self.assertIn("ref:dropToSurface(false, direction)", text)
        self.assertIn("local snapshot = history.getMultiSelectChange(refs)", text)
        self.assertIn("history.addAction(snapshot)", text)
        self.assertIn("registry.generate(item.element)", text)
        self.assertIn("rewriteSerializedRefs", text)
        self.assertIn("handlers.save_roots", text)
        self.assertIn("handlers.reload_root", text)


class LogV05Tests(unittest.TestCase):
    def test_log_discovery_tail_and_issue_filter(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "Cyberpunk 2077"
            wb = root / "bin/x64/plugins/cyber_engine_tweaks/mods/entSpawner"
            wb.mkdir(parents=True)
            (wb / "entSpawner.log").write_text("ready\nWARNING bad outline\nnormal\nERROR failed spawn\n", encoding="utf-8")
            cet = root / "bin/x64/plugins/cyber_engine_tweaks"
            (cet / "cyber_engine_tweaks.log").write_text("CET ready\n", encoding="utf-8")

            self.assertEqual(normalize_game_root(wb), root.resolve())
            found = dict(discover_logs(root))
            self.assertIn("WorldBuilder", found)
            self.assertIn("CyberEngineTweaks", found)

            result = read_logs(wb, tail=3, issues_only=True)
            self.assertEqual(result["gameRoot"], str(root.resolve()))
            world = next(log for log in result["logs"] if log["name"] == "WorldBuilder")
            self.assertEqual(world["lines"], ["WARNING bad outline", "ERROR failed spawn"])

    def test_mcp_log_tool(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "red4ext/logs"
            p.mkdir(parents=True)
            (p / "red4ext.log").write_text("ok\nFatal: test\n", encoding="utf-8")
            result = call_tool("wb_logs", {"game_root": str(root), "issues_only": True})
            self.assertEqual(result["found"], 1)
            self.assertEqual(result["logs"][0]["lines"], ["Fatal: test"])


if __name__ == "__main__":
    unittest.main()
