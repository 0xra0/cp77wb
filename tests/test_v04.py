from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from cp77wb import __version__
from cp77wb.assets import build_catalog, search_catalog
from cp77wb.live import LIVE_PROTOCOL, LiveBridgeClient
from cp77wb.mcp_server import TOOLS, call_tool
from cp77wb.project import build_spawnable_node
from tests.test_v03 import make_wb_root


class ProjectV04Tests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(__version__, "1.0.1")

    def test_build_spawnable_node_for_live_bridge(self):
        node = build_spawnable_node(
            module_path="mesh/mesh",
            data_type="Static Mesh",
            spawn_data="base\\environment\\architecture\\wall.mesh",
            template={"scale": {"x": 2, "y": 2, "z": 2}},
            position=(1, 2, 3),
            rotation=(4, 5, 6),
        )
        self.assertEqual(node["modulePath"], "modules/classes/editor/spawnableElement")
        self.assertEqual(node["name"], "wall")
        self.assertEqual(node["spawnable"]["modulePath"], "mesh/mesh")
        self.assertEqual(node["spawnable"]["position"]["z"], 3.0)
        self.assertEqual(node["spawnable"]["scale"]["x"], 2)
        self.assertEqual(node["spawnable"]["nodeRef"], "")


class LiveV04Tests(unittest.TestCase):
    def test_live_mutation_is_preview_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            client = LiveBridgeClient(Path(td) / "rpc")
            result = client.select_paths(["/Demo/DeviceA"], apply=False)
            self.assertFalse(result["applied"])
            self.assertEqual(result["operation"], "select_paths")
            self.assertFalse((Path(td) / "rpc" / "requests").exists())

    def test_applied_move_uses_v2_and_confirm(self):
        with tempfile.TemporaryDirectory() as td:
            rpc = Path(td) / "rpc"
            client = LiveBridgeClient(rpc)
            captured = {}

            def fake_bridge():
                requests = rpc / "requests"
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    files = list(requests.glob("*.json")) if requests.exists() else []
                    if files:
                        req_path = files[0]
                        req = json.loads(req_path.read_text())
                        captured.update(req)
                        response = rpc / "responses" / f"{req['id']}.json"
                        response.parent.mkdir(parents=True, exist_ok=True)
                        response.write_text(json.dumps({
                            "id": req["id"], "protocol": LIVE_PROTOCOL, "ok": True,
                            "result": {"applied": True, "changed": 1},
                        }))
                        req_path.unlink()
                        return
                    time.sleep(0.01)

            thread = threading.Thread(target=fake_bridge)
            thread.start()
            result = client.move_selection(1, 2, 3, apply=True, timeout=1.5)
            thread.join(timeout=1)
            self.assertTrue(result["applied"])
            self.assertEqual(captured["protocol"], LIVE_PROTOCOL)
            self.assertEqual(captured["method"], "move_selection")
            self.assertTrue(captured["params"]["confirm"])
            self.assertEqual(captured["params"]["z"], 3.0)

    def test_live_spawn_asset_mcp_preview_requires_no_game(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_wb_root(Path(td))
            db = Path(td) / "assets.sqlite3"
            build_catalog(root, db)
            asset = search_catalog(db, "arasaka wall", variant="Mesh")[0]
            result = call_tool("wb_live_spawn_asset", {
                "rpc_dir": str(Path(td) / "rpc"),
                "catalog": str(db),
                "asset": f"#{asset.id}",
                "placement": "camera",
            })
            self.assertFalse(result["applied"])
            self.assertEqual(result["operation"], "spawn_serialized")
            self.assertEqual(result["placement"], "camera")
            self.assertEqual(result["asset"]["id"], asset.id)
            self.assertEqual(result["data"]["spawnable"]["spawnData"], asset.spawn_data)

    def test_v04_mcp_tools_registered(self):
        names = {tool["name"] for tool in TOOLS}
        for name in {
            "wb_live_history", "wb_live_paths", "wb_live_select", "wb_live_move",
            "wb_live_rotate", "wb_live_duplicate", "wb_live_delete",
            "wb_live_spawn_asset", "wb_live_undo", "wb_live_redo",
        }:
            self.assertIn(name, names)
        self.assertEqual(len(names), len(TOOLS))
        self.assertGreaterEqual(len(names), 37)

    def test_bridge_source_requires_shared_history_singleton(self):
        bridge = Path(__file__).parents[1] / "extras" / "cp77wb_bridge" / "init.lua"
        text = bridge.read_text(encoding="utf-8")
        self.assertIn('package.loaded["modules/utils/history"]', text)
        self.assertIn("history.spawnedUI ~= sUI", text)
        self.assertIn("local snapshot = history.getMultiSelectChange(refs)", text)
        self.assertIn("history.addAction(snapshot)", text)
        self.assertIn("live mutation requires confirm=true", text)


if __name__ == "__main__":
    unittest.main()
