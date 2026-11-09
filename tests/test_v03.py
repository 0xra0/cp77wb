from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from cp77wb.assets import build_catalog, resolve_asset, search_catalog
from cp77wb.favorites import add_favorite, list_categories
from cp77wb.live import LiveBridgeClient
from cp77wb.mcp_server import call_tool
from cp77wb.project import WorldBuilderProject
from cp77wb.validate import validate

FIXTURE = Path(__file__).parent / "data" / "sample.json"


def make_wb_root(base: Path) -> Path:
    root = base / "entSpawner"
    (root / "data/spawnables/mesh/all").mkdir(parents=True)
    (root / "data/spawnables/entity/templates").mkdir(parents=True)
    (root / "data/spawnables/lights/staticLights").mkdir(parents=True)
    (root / "data/favorite").mkdir(parents=True)
    (root / "data/spawnables/mesh/all/paths_mesh.txt").write_text(
        "base\\environment\\architecture\\arasaka_wall_a.mesh\n"
        "base\\environment\\decoration\\neon_sign_a.mesh\n",
        encoding="utf-8",
    )
    (root / "data/spawnables/entity/templates/paths_ent.txt").write_text(
        "base\\gameplay\\devices\\elevators\\platform_elevator.ent\n",
        encoding="utf-8",
    )
    (root / "data/spawnables/lights/staticLights/Point.json").write_text(json.dumps({
        "name": "Point - Default",
        "type": "object",
        "spawnable": {
            "modulePath": "light/light",
            "dataType": "Static Light",
            "spawnData": "base\\spawner\\empty_entity.ent",
            "radius": 25,
            "intensity": 350,
            "lightType": 0,
        },
    }), encoding="utf-8")
    return root


class AssetCatalogTests(unittest.TestCase):
    def test_build_search_and_resolve(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_wb_root(Path(td))
            db = Path(td) / "assets.sqlite3"
            info = build_catalog(root, db)
            # Each mesh path is intentionally exposed as Mesh, Rotating Mesh and Proxy Mesh.
            self.assertEqual(info["assets"], 8)
            results = search_catalog(db, "arasaka wall", variant="Mesh")
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].module_path, "mesh/mesh")
            self.assertTrue(results[0].spawn_data.endswith("arasaka_wall_a.mesh"))
            exact = resolve_asset(db, f"#{results[0].id}")
            self.assertEqual(exact.id, results[0].id)
            light = search_catalog(db, "point default", limit=5)[0]
            self.assertEqual(light.source_kind, "template")
            assert light.template is not None
            self.assertEqual(light.template["intensity"], 350)

    def test_mcp_asset_search(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_wb_root(Path(td))
            db = Path(td) / "assets.sqlite3"
            build_catalog(root, db)
            results = call_tool("wb_assets_search", {"database": str(db), "query": "elevator"})
            self.assertEqual(results[0]["module_path"], "entity/entityTemplate")


class ProjectV03Tests(unittest.TestCase):
    def load(self) -> WorldBuilderProject:
        return WorldBuilderProject.load(FIXTURE)

    def test_add_spawnable_from_asset_payload(self):
        p = self.load()
        path = p.add_spawnable(
            "/Demo",
            module_path="mesh/mesh",
            data_type="Static Mesh",
            spawn_data="base\\environment\\test.mesh",
            template={"scale": {"x": 2, "y": 2, "z": 2}},
            position=(11, 22, 33),
            rotation=(0, 0, 45),
        )
        self.assertEqual(path, "/Demo/test")
        node = p.get(path).node
        self.assertEqual(node["spawnable"]["modulePath"], "mesh/mesh")
        self.assertEqual(node["spawnable"]["scale"]["x"], 2)
        self.assertEqual(p.position(path), (11.0, 22.0, 33.0))
        self.assertFalse(any(i.severity == "error" for i in validate(p)))

    def test_grid(self):
        p = self.load()
        paths = p.grid_array("/Demo/DeviceB", counts=(2, 2, 1), step=(10, 20, 0))
        self.assertEqual(len(paths), 3)
        positions = {p.position(path) for path in paths}
        self.assertEqual(positions, {(12.0, 2.0, 3.0), (2.0, 22.0, 3.0), (12.0, 22.0, 3.0)})

    def test_scatter_is_deterministic(self):
        p1 = self.load()
        p2 = self.load()
        r1 = p1.scatter("/Demo/DeviceB", count=4, half_extents=(2, 3, 0), seed=77)
        r2 = p2.scatter("/Demo/DeviceB", count=4, half_extents=(2, 3, 0), seed=77)
        self.assertEqual(r1["placements"], r2["placements"])
        self.assertEqual(len(r1["created"]), 3)


class FavoriteTests(unittest.TestCase):
    def test_add_group_as_native_worldbuilder_favorite(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_wb_root(Path(td))
            result = add_favorite(FIXTURE, "/Demo/Outline", root, category="Claude Prefabs", tags=["outline", "test"])
            self.assertTrue(Path(result["categoryFile"]).exists())
            categories = list_categories(root)
            self.assertEqual(categories[0]["name"], "Claude Prefabs")
            data = json.loads(Path(result["categoryFile"]).read_text())
            self.assertEqual(data["favorites"][0]["data"]["modulePath"], "modules/classes/editor/positionableGroup")
            self.assertTrue(data["favorites"][0]["tags"]["outline"])


class LiveBridgeClientTests(unittest.TestCase):
    def test_file_rpc_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            rpc = Path(td) / "rpc"
            client = LiveBridgeClient(rpc)

            def fake_bridge():
                requests = rpc / "requests"
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    files = list(requests.glob("*.json")) if requests.exists() else []
                    if files:
                        req_path = files[0]
                        req = json.loads(req_path.read_text())
                        response = rpc / "responses" / f"{req['id']}.json"
                        response.parent.mkdir(parents=True, exist_ok=True)
                        response.write_text(json.dumps({"id": req["id"], "ok": True, "result": {"bridgeVersion": "test"}}))
                        req_path.unlink()
                        return
                    time.sleep(0.01)

            thread = threading.Thread(target=fake_bridge)
            thread.start()
            result = client.ping(timeout=1.5)
            thread.join(timeout=1)
            self.assertEqual(result["bridgeVersion"], "test")


if __name__ == "__main__":
    unittest.main()
