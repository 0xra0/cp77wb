from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cp77wb import __version__
from cp77wb.assets import build_catalog, search_catalog
from cp77wb.compat import scan_worldbuilder
from cp77wb.devices import connect_device, wire_elevator
from cp77wb.mcp_server import TOOLS, call_tool
from cp77wb.procedural import (
    generate_corridor,
    generate_market,
    generate_room,
    marker_group_points,
    place_along_path,
    polygon_scatter,
    spawn_weighted_pool,
    volume_scatter,
)
from cp77wb.project import WorldBuilderProject, build_group_node, build_spawnable_node
from cp77wb.templates import parse_parameter_assignments, render_value
from cp77wb.validate import validate


HERE = Path(__file__).parent


def sample_project() -> WorldBuilderProject:
    return WorldBuilderProject.load(HERE / "data" / "sample.json")


def mini_wb(root: Path) -> tuple[Path, Path]:
    wb = root / "entSpawner"
    meshes = wb / "data/spawnables/mesh/all"
    meshes.mkdir(parents=True)
    (meshes / "meshes.txt").write_text(
        "base\\environment\\wall_a.mesh\nbase\\environment\\floor_a.mesh\nbase\\environment\\stall_a.mesh\nbase\\environment\\stall_b.mesh\n",
        encoding="utf-8",
    )
    (wb / "modules/ui").mkdir(parents=True)
    (wb / "modules/ui/baseUI.lua").write_text(
        'local CodewareVersion = "1.16.0"\nlocal ArchiveXLVersion = "1.23.0"\nlocal ModVersion = "1.0.81"\n', encoding="utf-8"
    )
    (wb / "modules/ui/exportUI.lua").write_text('local minScriptVersion = "1.0.4"\n', encoding="utf-8")
    (wb / "modules/classes/editor").mkdir(parents=True)
    (wb / "modules/classes/editor/positionableGroup.lua").write_text('o.modulePath = "modules/classes/editor/positionableGroup"\n', encoding="utf-8")
    (wb / "modules/classes/editor/spawnableElement.lua").write_text('o.modulePath = "modules/classes/editor/spawnableElement"\n', encoding="utf-8")
    (wb / "modules/classes/editor/randomizedGroup.lua").write_text('o.modulePath = "modules/classes/editor/randomizedGroup"\n', encoding="utf-8")
    (wb / "modules/classes/editor/scatteredGroup.lua").write_text('o.modulePath = "modules/classes/editor/scatteredGroup"\n', encoding="utf-8")
    (wb / "modules/classes/spawn/mesh").mkdir(parents=True)
    (wb / "modules/classes/spawn/mesh/mesh.lua").write_text('o.modulePath = "mesh/mesh"\n', encoding="utf-8")
    (wb / "modules/utils").mkdir(parents=True)
    for name in ("nodeRefRegistry.lua", "history.lua"):
        (wb / "modules/utils" / name).write_text("-- test\n", encoding="utf-8")
    db = root / "assets.sqlite3"
    build_catalog(wb, db)
    return wb, db


class ProceduralV06Tests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(__version__, "1.0.1")

    def test_group_builder_native_rng_fields(self):
        node = build_group_node(name="Trash RNG", module_path="modules/classes/editor/randomizedGroup", seed=42, randomization_rule=1, fixed_amount_rule=1, fixed_amount_total=2)
        self.assertEqual(node["seed"], 42)
        self.assertEqual(node["fixedAmountTotal"], 2)
        self.assertEqual(node["modulePath"], "modules/classes/editor/randomizedGroup")

    def test_marker_group_path_array(self):
        p = sample_project()
        points = marker_group_points(p, "/Demo/Outline")
        result = place_along_path(p, "/Demo/DeviceA", points, count=4, orient_to_path=True)
        self.assertEqual(len(result["created"]), 4)
        self.assertEqual(len(p.node_refs()), 7)  # original three + four remapped clones
        self.assertFalse(any(i.code == "duplicate-noderef" for i in validate(p)))

    def test_polygon_scatter_is_deterministic(self):
        polygon = [(0,0,0),(10,0,0),(10,10,0),(0,10,0)]
        p1 = sample_project()
        p2 = sample_project()
        r1 = polygon_scatter(p1, "/Demo/DeviceA", polygon, count=4, seed=2077, random_yaw=True)
        r2 = polygon_scatter(p2, "/Demo/DeviceA", polygon, count=4, seed=2077, random_yaw=True)
        self.assertEqual([x["position"] for x in r1["created"]], [x["position"] for x in r2["created"]])

    def test_volume_scatter_sphere_bounds(self):
        p = sample_project()
        result = volume_scatter(p, "/Demo/DeviceA", shape="sphere", count=10, center=(1,2,3), size=(2,3,4), seed=3)
        self.assertEqual(len(result["created"]), 10)
        for item in result["created"]:
            pos = item["position"]
            dx=(pos["x"]-1)/2
            dy=(pos["y"]-2)/3
            dz=(pos["z"]-3)/4
            self.assertLessEqual(dx*dx+dy*dy+dz*dz, 1.000001)

    def test_weighted_pool_and_generators_use_real_catalog_records(self):
        with tempfile.TemporaryDirectory() as td:
            wb, db = mini_wb(Path(td))
            mesh = search_catalog(db, "wall_a", variant="Mesh", limit=1)[0]
            floor = search_catalog(db, "floor_a", variant="Mesh", limit=1)[0]
            stall_a = search_catalog(db, "stall_a", variant="Mesh", limit=1)[0]
            stall_b = search_catalog(db, "stall_b", variant="Mesh", limit=1)[0]
            p = sample_project()
            pool = [{"asset": f"#{stall_a.id}", "weight": 3}, {"asset": f"#{stall_b.id}", "weight": 1}]
            pooled = spawn_weighted_pool(p, "/Demo", catalog=db, pool=pool, count=5, seed=9)
            self.assertEqual(len(pooled["created"]), 5)
            room = generate_room(p, "/Demo", catalog=db, wall_asset=f"#{mesh.id}", floor_asset=f"#{floor.id}", width=6, depth=4, segment=2, name="Room")
            self.assertTrue(room["walls"])
            corridor = generate_corridor(p, "/Demo", catalog=db, wall_asset=f"#{mesh.id}", length=6, width=2, segment=2, name="Corridor")
            self.assertTrue(corridor["walls"])
            market = generate_market(p, "/Demo", catalog=db, pool=pool, rows=2, columns=3, spacing_x=2, spacing_y=3, seed=5)
            self.assertEqual(len(market["created"]), 6)

    def test_native_rng_add_group(self):
        p = sample_project()
        path = p.add_group("/Demo", name="RNG", module_path="modules/classes/editor/randomizedGroup", seed=99, randomization_rule=1, fixed_amount_percentage=0.75)
        node = p.get(path).node
        self.assertEqual(node["seed"], 99)
        self.assertEqual(node["fixedAmountPercentage"], 0.75)


class DevicesV06Tests(unittest.TestCase):
    def _device_project(self) -> WorldBuilderProject:
        p = sample_project()
        root = p.data["childs"]
        elevator = build_spawnable_node(module_path="entity/device", data_type="Device", spawn_data="lift.ent", name="Lift")
        elevator["spawnable"].update({"deviceConnections": [], "deviceClassName": "LiftControllerPS"})
        root.append(elevator)
        for idx in (1,2):
            terminal = build_spawnable_node(module_path="entity/device", data_type="Device", spawn_data="terminal.ent", name=f"Terminal{idx}")
            terminal["spawnable"].update({
                "deviceConnections": [], "deviceClassName": "ElevatorFloorTerminalControllerPS", "persistent": False,
                "defaultComponentData": {"0": {"persistentState": {"elevatorFloorSetup": {"floorDisplayName": "old", "floorMarker": "old"}}}},
                "instanceDataChanges": {},
            })
            marker = build_spawnable_node(module_path="meta/staticMarker", data_type="Static Marker", name=f"Marker{idx}")
            root.extend([terminal, marker])
        return p

    def test_device_connect_generates_target_noderef(self):
        p = self._device_project()
        result = connect_device(p, "/Demo/Lift", "/Demo/Terminal1", device_class_name="ElevatorFloorTerminalControllerPS", node_ref_prefix="test")
        self.assertTrue(result["connection"]["nodeRef"].startswith("$/test/"))

    def test_elevator_wire_connections_persistency_and_instance_data(self):
        p = self._device_project()
        result = wire_elevator(p, "/Demo/Lift", ["/Demo/Terminal1","/Demo/Terminal2"], ["/Demo/Marker1","/Demo/Marker2"], floor_names=["LocKey#1","LocKey#2"], node_ref_prefix="elevator")
        self.assertEqual(result["instanceDataPatched"], 2)
        lift = p.get("/Demo/Lift").node["spawnable"]
        self.assertEqual(len(lift["deviceConnections"]), 2)
        t1 = p.get("/Demo/Terminal1").node["spawnable"]
        self.assertTrue(t1["persistent"])
        setup = t1["instanceDataChanges"]["0"]["persistentState"]["elevatorFloorSetup"]
        self.assertEqual(setup["floorDisplayName"], "LocKey#1")
        self.assertTrue(str(setup["floorMarker"]).startswith("$/elevator/"))


class CompatibilityAndTemplateV06Tests(unittest.TestCase):
    def test_compat_scanner_extracts_versions_and_features(self):
        with tempfile.TemporaryDirectory() as td:
            wb, _ = mini_wb(Path(td))
            result = scan_worldbuilder(wb)
            self.assertEqual(result["versions"]["worldBuilder"], "1.0.81")
            self.assertEqual(result["versions"]["archiveXLRequired"], "1.23.0")
            self.assertTrue(result["features"]["randomizedGroups"])

    def test_template_preserves_types_for_full_placeholder(self):
        params = parse_parameter_assignments(["count=4", "name=Lobby"])
        rendered = render_value({"count":"${count}","label":"${name} ${count}"}, params)
        self.assertEqual(rendered["count"], 4)
        self.assertEqual(rendered["label"], "Lobby 4")

    def test_v06_mcp_tools_registered(self):
        names = {tool["name"] for tool in TOOLS}
        expected = {
            "wb_path_array", "wb_polygon_scatter", "wb_volume_scatter", "wb_asset_pool_spawn",
            "wb_rng_create", "wb_generate_room", "wb_generate_corridor", "wb_generate_market",
            "wb_device_connect", "wb_elevator_wire", "wb_compat_scan", "wb_prefab_render",
        }
        self.assertTrue(expected <= names)
        self.assertGreaterEqual(len(names), 57)

    def test_mcp_prefab_render(self):
        with tempfile.TemporaryDirectory() as td:
            template = Path(td) / "t.json"
            template.write_text('{"name":"${name}","count":"${count}"}', encoding="utf-8")
            result = call_tool("wb_prefab_render", {"template": str(template), "parameters": {"name":"Test","count":3}})
            self.assertEqual(result["rendered"], {"name":"Test","count":3})


if __name__ == "__main__":
    unittest.main()
