from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cp77wb import __version__
from cp77wb.assets import build_catalog, search_catalog
from cp77wb.mcp_server import TOOLS, call_tool
from cp77wb.planner import apply_compiled_plan, compile_plan, preview_plan
from cp77wb.project import WorldBuilderProject
from cp77wb.semantics import build_semantic_index, semantic_search
from cp77wb.spatial import Bounds, boxes_overlap, bounds_info, import_bounds, placement_box, scan_project_collisions, set_asset_bounds
from cp77wb.structures import generate_cable_chain, generate_fence, generate_road
from cp77wb.validate import validate

HERE = Path(__file__).parent


def sample_project() -> WorldBuilderProject:
    return WorldBuilderProject.load(HERE / "data" / "sample.json")


def mini_catalog(root: Path) -> Path:
    wb = root / "entSpawner"
    d = wb / "data/spawnables/mesh/all"
    d.mkdir(parents=True)
    (d / "meshes.txt").write_text(
        "base\\environment\\architecture\\arasaka\\industrial_wall_clean.mesh\n"
        "base\\environment\\architecture\\industrial_floor_metal.mesh\n"
        "base\\environment\\architecture\\industrial_door_metal.mesh\n"
        "base\\environment\\decoration\\warehouse_crate_dirty.mesh\n"
        "base\\environment\\architecture\\street_fence_metal.mesh\n"
        "base\\environment\\architecture\\fence_post_metal.mesh\n"
        "base\\environment\\architecture\\road_tile_concrete.mesh\n"
        "base\\environment\\architecture\\curb_edge_concrete.mesh\n"
        "base\\environment\\decoration\\utility_cable_black.mesh\n",
        encoding="utf-8",
    )
    db = root / "assets.sqlite3"
    build_catalog(wb, db)
    return db


class SemanticV07Tests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(__version__, "1.0.1")

    def test_semantic_index_and_facets(self):
        with tempfile.TemporaryDirectory() as td:
            db = mini_catalog(Path(td))
            info = build_semantic_index(db)
            self.assertGreater(info["assets"], 0)
            rows = semantic_search(db, "arasaka industrial wall", role="wall", style="arasaka", variant="Mesh")
            self.assertTrue(rows)
            self.assertIn("wall", rows[0]["roles"])
            self.assertIn("industrial", rows[0]["styles"])
            self.assertIn("metal", semantic_search(db, "industrial floor", material="metal", variant="Mesh")[0]["materials"])

    def test_semantic_override(self):
        with tempfile.TemporaryDirectory() as td:
            db = mini_catalog(Path(td))
            wall = search_catalog(db, "industrial wall", variant="Mesh", limit=1)[0]
            overrides = Path(td) / "overrides.json"
            overrides.write_text('{"overrides":[{"asset":"#%d","tags":["hero_asset"],"styles":["custom_style"]}]}' % wall.id, encoding="utf-8")
            build_semantic_index(db, overrides)
            rows = semantic_search(db, "hero asset", style="custom_style", variant="Mesh")
            self.assertEqual(rows[0]["id"], wall.id)


class SpatialV07Tests(unittest.TestCase):
    def test_explicit_bounds_and_import(self):
        with tempfile.TemporaryDirectory() as td:
            db = mini_catalog(Path(td))
            wall = search_catalog(db, "industrial wall", variant="Mesh", limit=1)[0]
            result = set_asset_bounds(db, wall.id, (3.5, .25, 3.2), source="measured")
            self.assertEqual(result["bounds"]["source"], "measured")
            self.assertEqual(bounds_info(db, wall.id)["effective"]["x"], 3.5)
            crate = search_catalog(db, "crate", variant="Mesh", limit=1)[0]
            import_bounds(db, [{"asset": f"#{crate.id}", "size": [1, 1.2, .8], "confidence": .9}])
            self.assertAlmostEqual(bounds_info(db, crate.id)["explicit"]["confidence"], .9)

    def test_rotated_oriented_box_collision(self):
        b = Bounds(4, 1, 2, "test", 1)
        a = placement_box("a", (0,0,0), 45, b)
        near = placement_box("b", (1,0,0), -45, b)
        far = placement_box("c", (10,0,0), 0, b)
        self.assertTrue(boxes_overlap(a, near))
        self.assertFalse(boxes_overlap(a, far))

    def test_project_collision_scan_uses_catalog(self):
        with tempfile.TemporaryDirectory() as td:
            db = mini_catalog(Path(td))
            crate = search_catalog(db, "crate", variant="Mesh", limit=1)[0]
            set_asset_bounds(db, crate.id, (2,2,2))
            p = sample_project()
            p.add_spawnable("/Demo", module_path=crate.module_path, data_type=crate.data_type, spawn_data=crate.spawn_data, name="CrateA", position=(50,50,1))
            p.add_spawnable("/Demo", module_path=crate.module_path, data_type=crate.data_type, spawn_data=crate.spawn_data, name="CrateB", position=(50.5,50,1))
            result = scan_project_collisions(p, db)
            self.assertGreaterEqual(result["count"], 1)
            self.assertFalse(result["collisions"][0]["approximate"])


class PlannerV07Tests(unittest.TestCase):
    def test_compile_room_with_door_opening_and_exact_assets(self):
        with tempfile.TemporaryDirectory() as td:
            db = mini_catalog(Path(td))
            wall = search_catalog(db, "industrial wall", variant="Mesh", limit=1)[0]
            floor = search_catalog(db, "industrial floor", variant="Mesh", limit=1)[0]
            door = search_catalog(db, "industrial door", variant="Mesh", limit=1)[0]
            spec = {
                "schema":"cp77wb-plan/1", "name":"Lab", "parent":"/Demo", "origin":[10,20,0],
                "room":{"width":8,"depth":6,"wallStep":2,"wall":{"asset":f"#{wall.id}"},"floor":{"asset":f"#{floor.id}"},"floorStep":2,
                        "doors":[{"side":"north","offset":0,"width":2.1,"asset":f"#{door.id}","name":"North Door"}]}
            }
            compiled = compile_plan(spec, db)
            self.assertEqual(compiled["schema"], "cp77wb-compiled-plan/1")
            self.assertTrue(any(op.get("role") == "door" for op in compiled["operations"]))
            north_walls = [op for op in compiled["operations"] if op.get("name") == "Wall North"]
            self.assertFalse(any(abs(op["position"][0]-10) < .01 for op in north_walls))

    def test_semantic_autoselect_is_explicit(self):
        with tempfile.TemporaryDirectory() as td:
            db = mini_catalog(Path(td))
            build_semantic_index(db)
            spec={"schema":"cp77wb-plan/1","name":"Semantic","parent":"/Demo","placements":[{"semanticQuery":"dirty warehouse crate","autoSelect":True,"role":"container","position":[1,2,3]}]}
            compiled=compile_plan(spec,db)
            self.assertEqual(len(compiled["operations"]),1)
            self.assertEqual(compiled["assetSelections"][0]["reason"],"semantic-best-explicit-autoselect")
            bad={"schema":"cp77wb-plan/1","name":"Bad","parent":"/Demo","placements":[{"semanticQuery":"crate","position":[0,0,0]}]}
            with self.assertRaises(ValueError):
                compile_plan(bad,db)

    def test_preview_and_apply_validate(self):
        with tempfile.TemporaryDirectory() as td:
            db = mini_catalog(Path(td))
            crate = search_catalog(db, "crate", variant="Mesh", limit=1)[0]
            spec={"schema":"cp77wb-plan/1","name":"Props","parent":"/Demo","placements":[{"asset":f"#{crate.id}","position":[100,100,0]}]}
            p=sample_project()
            preview=preview_plan(p,spec,db)
            self.assertTrue(preview["valid"])
            compiled=compile_plan(spec,db)
            result=apply_compiled_plan(p,compiled,db)
            self.assertEqual(result["count"],1)
            self.assertFalse(any(i.severity=="error" for i in validate(p)))

    def test_collision_aware_scatter(self):
        with tempfile.TemporaryDirectory() as td:
            db=mini_catalog(Path(td))
            crate=search_catalog(db,"crate",variant="Mesh",limit=1)[0]
            set_asset_bounds(db,crate.id,(1,1,1))
            spec={"schema":"cp77wb-plan/1","name":"Scatter","parent":"/Demo","scatter":[{"asset":f"#{crate.id}","count":5,"seed":7,"clearance":.2,"region":{"center":[0,0,0],"halfExtents":[5,5,0]}}]}
            compiled=compile_plan(spec,db)
            self.assertEqual(len(compiled["operations"]),5)
            self.assertEqual(compiled["summary"]["collisions"],0)


class StructuresV07Tests(unittest.TestCase):
    def test_fence_road_cable_generators(self):
        with tempfile.TemporaryDirectory() as td:
            db=mini_catalog(Path(td))
            p=sample_project()
            pts=[(0,0,0),(10,0,0)]
            fence=search_catalog(db,"street fence",variant="Mesh",limit=1)[0]
            post=search_catalog(db,"fence post",variant="Mesh",limit=1)[0]
            road=search_catalog(db,"road tile",variant="Mesh",limit=1)[0]
            edge=search_catalog(db,"curb edge",variant="Mesh",limit=1)[0]
            cable=search_catalog(db,"utility cable",variant="Mesh",limit=1)[0]
            fr=generate_fence(p,"/Demo",catalog=db,segment_asset=f"#{fence.id}",post_asset=f"#{post.id}",points=pts,spacing=2,name="Fence")
            rr=generate_road(p,"/Demo",catalog=db,tile_asset=f"#{road.id}",edge_asset=f"#{edge.id}",points=pts,spacing=2,width=4,name="Road")
            cr=generate_cable_chain(p,"/Demo",catalog=db,segment_asset=f"#{cable.id}",points=pts,spacing=2,name="Cable")
            self.assertTrue(fr["segments"])
            self.assertEqual(len(rr["edges"]),2*rr["samples"])
            self.assertTrue(cr["segments"])


class McpV07Tests(unittest.TestCase):
    def test_v07_tools_registered(self):
        names={t["name"] for t in TOOLS}
        expected={"wb_semantic_build","wb_semantic_search","wb_bounds_set","wb_bounds_import","wb_bounds_info","wb_collisions","wb_plan_compile","wb_plan_preview","wb_plan_apply","wb_generate_fence","wb_generate_road","wb_generate_cable"}
        self.assertTrue(expected <= names)
        self.assertGreaterEqual(len(names),69)

    def test_mcp_semantic_and_plan_compile(self):
        with tempfile.TemporaryDirectory() as td:
            db=mini_catalog(Path(td))
            call_tool("wb_semantic_build",{"database":str(db)})
            rows=call_tool("wb_semantic_search",{"database":str(db),"query":"arasaka industrial wall","role":"wall","variant":"Mesh"})
            self.assertTrue(rows)
            plan={"schema":"cp77wb-plan/1","name":"One","parent":"/Demo","placements":[{"asset":f"#{rows[0]['id']}","position":[1,2,3]}]}
            result=call_tool("wb_plan_compile",{"catalog":str(db),"plan":plan})
            self.assertEqual(result["summary"]["operations"],1)


if __name__ == "__main__":
    unittest.main()
