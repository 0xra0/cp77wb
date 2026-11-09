from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cp77wb import __version__
from cp77wb.build import (
    archive_xl_config, backend_scan, build_pack, build_package, build_status,
    deploy_layout, inspect_export, prepare_build_workspace, verify_package, build_doctor,
)
from cp77wb.mcp_server import TOOLS, call_tool

HERE = Path(__file__).parent


def write_export(path: Path, *, duplicate_ref: bool = False, devices: bool = True) -> Path:
    nodes = [
        {
            "name": "Wall", "type": "worldStaticMeshNode", "nodeRef": "$/demo/#wall",
            "position": {"x": 1, "y": 2, "z": 3},
            "rotation": {"i": 0, "j": 0, "k": 0, "r": 1},
            "scale": {"x": 1, "y": 1, "z": 1},
            "primaryRange": 100, "secondaryRange": 50, "uk10": 0, "uk11": 0,
            "data": {"debugName": {"$type": "CName", "$storage": "string", "$value": "Wall"}},
        },
        {
            "name": "Lamp", "type": "worldStaticMeshNode", "nodeRef": "$/demo/#wall" if duplicate_ref else "$/demo/#lamp",
            "position": {"x": 4, "y": 5, "z": 6},
            "rotation": {"i": 0, "j": 0, "k": 0, "r": 1},
            "scale": {"x": 1, "y": 1, "z": 1},
            "primaryRange": 100, "secondaryRange": 50, "uk10": 0, "uk11": 0,
            "data": {"debugName": {"$type": "CName", "$storage": "string", "$value": "Lamp"}},
        },
    ]
    data = {
        "name": "demo_world", "xlFormat": 1, "version": "1.0.4",
        "sectors": [{"name": "sector_a", "min": {"x":0,"y":0,"z":0}, "max": {"x":10,"y":10,"z":10}, "category":"Exterior", "level":255, "variantIndices":[0], "variants":[], "nodes": nodes}],
        "devices": ({"123": {"hash":"123","children":[],"parents":[],"className":"DevicePS","nodePosition":{"x":1,"y":2,"z":3}}} if devices else {}),
        "psEntries": ({"456": {"PSID":"456","instanceData":{"$type":"gamePersistentStateDataResource"}}} if devices else {}),
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def write_wb_importer(root: Path) -> Path:
    script = root / "script" / "import_object_spawner.wscript"
    script.parent.mkdir(parents=True)
    script.write_text('''const inputFilePathInRawFolder = "new_project_exported.json"\nconst version = "1.0.4"\nwkit.CreateInstanceAsJSON("x"); wkit.HashString("x","fnv1a64"); wkit.JsonToCR2W("{}"); wkit.SaveToProject("a", "b"); wkit.SaveToResources("x","y");\n''', encoding="utf-8")
    return script


class ExportBuildV08Tests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(__version__, "1.0.1")

    def test_export_inspection_and_duplicate_noderef(self):
        with tempfile.TemporaryDirectory() as td:
            p=write_export(Path(td)/"demo_exported.json")
            ok=inspect_export(p)
            self.assertTrue(ok["valid"])
            self.assertEqual(ok["nodes"],2)
            bad=write_export(Path(td)/"bad_exported.json", duplicate_ref=True)
            result=inspect_export(bad)
            self.assertFalse(result["valid"])
            self.assertTrue(any(i["code"]=="duplicate-noderef" for i in result["issues"]))

    def test_archive_xl_matches_importer_behavior(self):
        with tempfile.TemporaryDirectory() as td:
            p=write_export(Path(td)/"demo_exported.json")
            cfg=archive_xl_config(json.loads(p.read_text()))
            self.assertEqual(cfg["streaming"]["blocks"],["demo_world/all.streamingblock"])
            self.assertIn("demo_world/custom_devices.devices", cfg["resource"]["patch"])
            self.assertIn("demo_world/custom_devices.psrep", cfg["resource"]["patch"])

    def test_prepare_workspace_and_status(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            exp=write_export(root/"demo_world_exported.json")
            wb=root/"entSpawner"
            write_wb_importer(wb)
            result=prepare_build_workspace(exp, root/"work", world_builder_root=wb, author="Tester")
            proj=Path(result["workspace"])
            self.assertTrue((proj/"demo_world.cpmodproj").is_file())
            self.assertTrue((proj/"source/raw/demo_world_exported.json").is_file())
            self.assertIn('demo_world_exported.json', (proj/"automation/import_object_spawner_demo_world.wscript").read_text())
            status=build_status(proj)
            self.assertFalse(status["importComplete"])
            for rel in json.loads((proj/".cp77wb-build.json").read_text())["expectedArchiveFiles"]:
                out=proj/rel
                out.parent.mkdir(parents=True,exist_ok=True)
                out.write_bytes(b"RED4")
            status=build_status(proj)
            self.assertTrue(status["importComplete"])
            self.assertTrue(status["exportUnchanged"])

    def test_backend_scan_describes_native_boundary(self):
        with tempfile.TemporaryDirectory() as td:
            wb=Path(td)/"entSpawner"
            write_wb_importer(wb)
            result=backend_scan(world_builder_root=wb)
            self.assertFalse(result["capabilities"]["linuxNativeObjectSpawnerConversion"])
            self.assertIn("CreateInstanceAsJSON", result["scriptApiCalls"])
            self.assertIn("JsonToCR2W", result["scriptApiCalls"])

    def test_pack_preview_and_fake_cli_run(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            exp=write_export(root/"demo_world_exported.json", devices=False)
            res=prepare_build_workspace(exp, root/"work")
            proj=Path(res["workspace"])
            for rel in json.loads((proj/".cp77wb-build.json").read_text())["expectedArchiveFiles"]:
                out=proj/rel
                out.parent.mkdir(parents=True,exist_ok=True)
                out.write_bytes(b"RED4")
            fake=root/"cp77tools"
            fake.write_text('#!/bin/sh\nout=""\nwhile [ "$#" -gt 0 ]; do if [ "$1" = "-o" ]; then shift; out="$1"; fi; shift; done\nmkdir -p "$out"\nprintf REDARCHIVE > "$out/archive.archive"\n',encoding="utf-8")
            fake.chmod(0o755)
            preview=build_pack(proj,cli=fake,run=False)
            self.assertFalse(preview["ran"])
            self.assertIn("pack",preview["command"])
            ran=build_pack(proj,cli=fake,run=True)
            self.assertTrue(ran["ran"])
            self.assertTrue(Path(ran["archive"]).name=="demo_world.archive")

    def test_package_verify_and_deploy_safety(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            exp=write_export(root/"demo_world_exported.json",devices=False)
            res=prepare_build_workspace(exp,root/"work",scaffold_tweak=True)
            proj=Path(res["workspace"])
            archive=root/"demo_world.archive"
            archive.write_bytes(b"archive")
            pkg=build_package(proj,archive=archive,output=root/"dist",zip_output=root/"demo.zip")
            self.assertTrue(pkg["ready"])
            self.assertTrue((root/"dist/archive/pc/mod/demo_world.archive").is_file())
            self.assertTrue((root/"dist/archive/pc/mod/demo_world.xl").is_file())
            self.assertTrue((root/"dist/r6/tweaks/demo_world.yaml").is_file())
            self.assertTrue((root/"demo.zip").is_file())
            verify=verify_package(root/"dist")
            self.assertTrue(verify["valid"])
            game=root/"game"
            game.mkdir()
            preview=deploy_layout(root/"dist",game,apply=False)
            self.assertFalse(preview["apply"])
            self.assertFalse((game/"archive/pc/mod/demo_world.archive").exists())
            deploy_layout(root/"dist",game,apply=True)
            self.assertTrue((game/"archive/pc/mod/demo_world.archive").is_file())
            (game/"archive/pc/mod/demo_world.archive").write_bytes(b"other")
            with self.assertRaises(FileExistsError):
                deploy_layout(root/"dist",game,apply=True,overwrite=False)
            done=deploy_layout(root/"dist",game,apply=True,overwrite=True)
            self.assertTrue(done["backup"])
            doctor=build_doctor(root/"dist",game_root=game)
            self.assertTrue(doctor["package"]["valid"])
            self.assertIn(doctor["status"], {"ok","review"})


class McpV08Tests(unittest.TestCase):
    def test_v08_tools_registered(self):
        names={t["name"] for t in TOOLS}
        expected={"wb_export_inspect","wb_export_xl","wb_build_prepare","wb_build_status","wb_build_backends","wb_build_pack","wb_build_package","wb_build_verify","wb_build_deploy","wb_build_doctor"}
        self.assertTrue(expected <= names)
        self.assertGreaterEqual(len(names),79)

    def test_mcp_prepare_defaults_to_preview(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            exp=write_export(root/"demo_world_exported.json")
            result=call_tool("wb_build_prepare",{"export_file":str(exp),"workspace":str(root/"work")})
            self.assertFalse(result["written"])
            self.assertFalse((root/"work/demo_world").exists())
            result=call_tool("wb_build_prepare",{"export_file":str(exp),"workspace":str(root/"work"),"write":True})
            self.assertTrue(result["written"])
            self.assertTrue((root/"work/demo_world/.cp77wb-build.json").is_file())


if __name__ == "__main__":
    unittest.main()
