from __future__ import annotations

import unittest
from pathlib import Path

from cp77wb.project import WorldBuilderProject
from cp77wb.validate import validate

FIXTURE = Path(__file__).parent / "data" / "sample.json"


class ProjectTests(unittest.TestCase):
    def load(self):
        return WorldBuilderProject.load(FIXTURE)

    def test_tree_and_paths(self):
        p = self.load()
        self.assertEqual(p.get("/Demo/DeviceA").node["name"], "DeviceA")
        self.assertEqual(p.get("DeviceA").path, "/Demo/DeviceA")
        self.assertTrue(any("Outline" in line for line in p.tree_lines()))

    def test_validate_sample(self):
        issues = validate(self.load())
        self.assertEqual([i for i in issues if i.severity == "error"], [])

    def test_translate_refreshes_area_markers(self):
        p = self.load()
        p.translate("/Demo/Outline", 10, 0, 2)
        marker = p.get("/Demo/Outline/M1").node["spawnable"]["position"]
        self.assertEqual(marker["x"], 10)
        self.assertEqual(marker["z"], 2)
        area = p.get("/Demo/Area").node["spawnable"]
        self.assertEqual(len(area["markers"]), 3)
        self.assertEqual(area["markers"][0]["x"], 10)
        self.assertEqual(area["height"], 3)

    def test_rename_repairs_outline_path(self):
        p = self.load()
        p.rename("/Demo/Outline", "Outline2")
        self.assertEqual(p.get("/Demo/Area").node["spawnable"]["outlinePath"], "/Demo/Outline2")

    def test_set_noderef_updates_device_connection(self):
        p = self.load()
        old, count = p.set_node_ref("/Demo/DeviceB", "$/demo/#b2")
        self.assertEqual(old, "$/demo/#b")
        self.assertEqual(count, 1)
        conn = p.get("/Demo/DeviceA").node["spawnable"]["deviceConnections"][0]
        self.assertEqual(conn["nodeRef"], "$/demo/#b2")

    def test_duplicate_noderef(self):
        p = self.load()
        p.get("/Demo/DeviceB").node["spawnable"]["nodeRef"] = "$/demo/#a"
        codes = [i.code for i in validate(p)]
        self.assertIn("duplicate_noderef", codes)


if __name__ == "__main__":
    unittest.main()
