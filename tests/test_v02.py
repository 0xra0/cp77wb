from __future__ import annotations

import copy
import unittest
from pathlib import Path

from cp77wb.naming import generate_copy_name, sanitize_filename
from cp77wb.project import WorldBuilderProject
from cp77wb.validate import validate

FIXTURE = Path(__file__).parent / "data" / "sample.json"


class V02Tests(unittest.TestCase):
    def load(self):
        return WorldBuilderProject.load(FIXTURE)

    def test_worldbuilder_naming_compatibility(self):
        self.assertEqual(sanitize_filename("A B/C:'D*?"), "A_B_C__D__")
        self.assertEqual(generate_copy_name("Thing"), "Thing_1")
        self.assertEqual(generate_copy_name("Thing_9"), "Thing_10")
        self.assertEqual(generate_copy_name("$/demo/#thing_9"), "$/demo/#thing_10")

    def test_generate_noderef_matches_worldbuilder_pattern(self):
        p = self.load()
        p.get("/Demo/DeviceB").node["spawnable"]["nodeRef"] = ""
        old, new, updated = p.generate_node_ref("/Demo/DeviceB", prefix="my_mod")
        self.assertEqual(old, "")
        self.assertEqual(new, "$/my_mod/demo/#demo_deviceb")
        self.assertEqual(updated, 0)

    def test_duplicate_regenerates_noderef_and_offsets(self):
        p = self.load()
        paths = p.duplicate("/Demo/DeviceB", count=2, offset=(10, 0, 0))
        self.assertEqual(paths, ["/Demo/DeviceB_1", "/Demo/DeviceB_2"])
        self.assertEqual(p.position(paths[0]), (12.0, 2.0, 3.0))
        self.assertEqual(p.position(paths[1]), (22.0, 2.0, 3.0))
        self.assertEqual(p.get(paths[0]).node["spawnable"]["nodeRef"], "$/demo/#demo_deviceb_1")
        self.assertEqual(p.get(paths[1]).node["spawnable"]["nodeRef"], "$/demo/#demo_deviceb_2")
        self.assertFalse(any(i.code == "duplicate_noderef" for i in validate(p)))

    def test_duplicate_group_repairs_internal_outline_path(self):
        p = self.load()
        root = p.data
        outline = copy.deepcopy(p.get("/Demo/Outline").node)
        area = copy.deepcopy(p.get("/Demo/Area").node)
        outline["name"] = "OutlineLocal"
        area["spawnable"]["outlinePath"] = "/Demo/Zone/OutlineLocal"
        zone = {
            "name": "Zone",
            "modulePath": "modules/classes/editor/positionableGroup",
            "pos": {"x": 0, "y": 0, "z": 0},
            "origin": {"x": 0, "y": 0, "z": 0},
            "rotation": {"roll": 0, "pitch": 0, "yaw": 0},
            "childs": [outline, area],
        }
        root["childs"].append(zone)
        paths = p.duplicate("/Demo/Zone")
        self.assertEqual(paths, ["/Demo/Zone_1"])
        self.assertEqual(
            p.get("/Demo/Zone_1/Area").node["spawnable"]["outlinePath"],
            "/Demo/Zone_1/OutlineLocal",
        )

    def test_generic_reference_rewrite(self):
        p = self.load()
        guard = {
            "name": "Guard",
            "modulePath": "modules/classes/editor/spawnableElement",
            "pos": {"x": 0, "y": 0, "z": 0},
            "childs": [],
            "spawnable": {
                "modulePath": "area/guardArea",
                "position": {"x": 0, "y": 0, "z": 0, "w": 0},
                "rotation": {"roll": 0, "pitch": 0, "yaw": 0},
                "nodeRef": "",
                "pursuitArea": "$/demo/#b",
                "communityEntries": [{"communityRef": "$/demo/#b", "names": []}],
                "workspots": ["$/demo/#b"],
            },
        }
        p.data["childs"].append(guard)
        old, updated = p.set_node_ref("/Demo/DeviceB", "$/demo/#b2")
        self.assertEqual(old, "$/demo/#b")
        self.assertEqual(updated, 4)  # DeviceA connection + 3 Guard refs
        spawn = p.get("/Demo/Guard").node["spawnable"]
        self.assertEqual(spawn["pursuitArea"], "$/demo/#b2")
        self.assertEqual(spawn["communityEntries"][0]["communityRef"], "$/demo/#b2")
        self.assertEqual(spawn["workspots"][0], "$/demo/#b2")

    def test_rotate_group_about_origin(self):
        p = self.load()
        p.rotate("/Demo/Outline", yaw=90)
        m2 = p.position("/Demo/Outline/M2")
        m3 = p.position("/Demo/Outline/M3")
        self.assertAlmostEqual(m2[0], 0.0, places=7)
        self.assertAlmostEqual(m2[1], 5.0, places=7)
        self.assertAlmostEqual(m3[0], -5.0, places=7)
        self.assertAlmostEqual(m3[1], 0.0, places=7)
        area_markers = p.get("/Demo/Area").node["spawnable"]["markers"]
        self.assertAlmostEqual(area_markers[1]["y"], 5.0, places=7)

    def test_scale_group_geometry(self):
        p = self.load()
        p.scale("/Demo/Outline", 2, 3, 1)
        self.assertEqual(p.position("/Demo/Outline/M2"), (10.0, 0.0, 0.0))
        self.assertEqual(p.position("/Demo/Outline/M3"), (0.0, 15.0, 0.0))

    def test_linear_array_count_includes_source(self):
        p = self.load()
        paths = p.linear_array("/Demo/DeviceB", count=3, step=(2, 0, 0))
        self.assertEqual(len(paths), 2)
        self.assertEqual(p.position(paths[0]), (4.0, 2.0, 3.0))
        self.assertEqual(p.position(paths[1]), (6.0, 2.0, 3.0))

    def test_radial_array_orbits_and_rotates(self):
        p = self.load()
        paths = p.radial_array("/Demo/DeviceA", count=4, pivot=(0, 0, 3))
        self.assertEqual(len(paths), 3)
        first = p.position(paths[0])
        self.assertAlmostEqual(first[0], -2.0, places=7)
        self.assertAlmostEqual(first[1], 1.0, places=7)
        yaw = p.get(paths[0]).node["spawnable"]["rotation"]["yaw"]
        self.assertAlmostEqual(yaw, 90.0, places=7)

    def test_align_and_distribute(self):
        p = self.load()
        p.align(["/Demo/DeviceA", "/Demo/DeviceB"], axis="y", mode="value", value=7)
        self.assertEqual(p.position("/Demo/DeviceA")[1], 7)
        self.assertEqual(p.position("/Demo/DeviceB")[1], 7)

        p.linear_array("/Demo/DeviceB", count=3, step=(4, 0, 0))
        # Positions are 2, 6, 10. Distort middle then distribute back to 6.
        p.translate("/Demo/DeviceB_1", 1, 0, 0)
        result = p.distribute(["/Demo/DeviceB", "/Demo/DeviceB_1", "/Demo/DeviceB_2"], axis="x")
        self.assertEqual(result["spacing"], 4)
        self.assertEqual(p.position("/Demo/DeviceB_1")[0], 6)


if __name__ == "__main__":
    unittest.main()

class V02ReferenceCloneTests(unittest.TestCase):
    def load(self):
        return WorldBuilderProject.load(FIXTURE)

    def test_duplicate_group_rewrites_internal_device_refs(self):
        p = self.load()
        group = {
            "name": "Devices",
            "modulePath": "modules/classes/editor/positionableGroup",
            "pos": {"x": 0, "y": 0, "z": 0},
            "origin": {"x": 0, "y": 0, "z": 0},
            "rotation": {"roll": 0, "pitch": 0, "yaw": 0},
            "childs": [copy.deepcopy(p.get("/Demo/DeviceA").node), copy.deepcopy(p.get("/Demo/DeviceB").node)],
        }
        p.data["childs"].append(group)
        # Make fixture valid before duplication by removing original siblings.
        p.data["childs"] = [c for c in p.data["childs"] if c.get("name") not in {"DeviceA", "DeviceB"}]
        path = p.duplicate("/Demo/Devices")[0]
        a = p.get(path + "/DeviceA").node["spawnable"]
        b = p.get(path + "/DeviceB").node["spawnable"]
        self.assertNotEqual(a["nodeRef"], "$/demo/#a")
        self.assertNotEqual(b["nodeRef"], "$/demo/#b")
        self.assertEqual(a["deviceConnections"][0]["nodeRef"], b["nodeRef"])
        self.assertFalse(any(i.code == "duplicate_noderef" for i in validate(p)))
