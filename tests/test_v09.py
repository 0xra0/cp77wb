from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cp77wb import __version__
from cp77wb.build import backend_scan, prepare_build_workspace
from cp77wb.mcp_server import TOOLS, call_tool
from cp77wb.native import (
    TEMPLATE_SCHEMA, make_template_capture_script, native_convert, native_import,
    native_preflight, prepare_native_json, required_template_types,
    verify_native_outputs, verify_template_bundle,
)
from tests.test_v08 import write_export, write_wb_importer


def write_bundle(path: Path) -> Path:
    types = {
        "worldStreamingSector": {"nodes": [], "nodeRefs": [], "nodeData": {}},
        "gameDeviceResource": {},
        "gamePersistentStateDataResource": {},
        "worldStreamingBlock": {"descriptors": []},
        "worldStreamingSectorDescriptor": {
            "category": "Exterior", "level": 255, "numNodeRanges": 1,
            "streamingBox": {"Max": {"X": 0, "Y": 0, "Z": 0}, "Min": {"X": 0, "Y": 0, "Z": 0}},
            "data": {"DepotPath": {"$type": "ResourcePath", "$storage": "uint64", "$value": "0"}},
            "questPrefabNodeRef": {"$type": "NodeRef", "$storage": "uint64", "$value": "0"},
            "variants": [],
        },
        "worldStreamingSectorVariant": {
            "enabledByDefault": False,
            "name": {"$type": "CName", "$storage": "string", "$value": ""},
            "nodeRef": {"$type": "NodeRef", "$storage": "uint64", "$value": "0"},
            "rangeIndex": 0, "variantId": 0,
        },
        "worldStaticMeshNode": {"debugName": {"$type": "CName", "$storage": "string", "$value": ""}},
    }
    path.write_text(json.dumps({"schema": TEMPLATE_SCHEMA, "wolvenKitVersion": "9.0.1", "types": types}), encoding="utf-8")
    return path


def write_fake_cli(path: Path) -> Path:
    path.write_text(r'''#!/bin/sh
if [ "$1" = "--version" ]; then echo "WolvenKit.CLI 9.0.1"; exit 0; fi
if [ "$1" = "convert" ] && [ "$2" = "deserialize" ] && [ "$3" = "--help" ]; then
  echo "deserialize: Create a CR2W file from json"; exit 0
fi
if [ "$1" = "convert" ] && [ "$2" = "deserialize" ]; then
  src="$3"; shift 3; out=""
  while [ "$#" -gt 0 ]; do
    if [ "$1" = "--outpath" ] || [ "$1" = "-o" ]; then shift; out="$1"; fi
    shift
  done
  mkdir -p "$out"
  base=$(basename "$src" .json)
  printf 'CR2WFAKE' > "$out/$base"
  exit 0
fi
echo "unsupported" >&2
exit 2
''', encoding="utf-8")
    path.chmod(0o755)
    return path


class NativeV09Tests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(__version__, "1.0.1")

    def test_template_plan_and_coverage(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            exp = write_export(root/"demo_world_exported.json")
            bundle = write_bundle(root/"templates.json")
            required = required_template_types(exp)
            self.assertIn("worldStaticMeshNode", required)
            self.assertIn("worldStreamingSector", required)
            plan = make_template_capture_script(exp, root/"capture.wscript")
            text = Path(plan["script"]).read_text()
            self.assertIn("CreateInstanceAsJSON", text)
            self.assertIn("worldStaticMeshNode", text)
            coverage = verify_template_bundle(exp, bundle)
            self.assertTrue(coverage["valid"])
            self.assertEqual(coverage["usableCount"], len(required))

    def test_native_json_reproduces_importer_shape(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            exp = write_export(root/"demo_world_exported.json")
            bundle = write_bundle(root/"templates.json")
            result = prepare_native_json(exp, bundle, root/"native-json")
            self.assertEqual(result["count"], 4)
            sector = json.loads((root/"native-json/demo_world/sectors/sector_a.streamingsector.json").read_text())
            chunk = sector["Data"]["RootChunk"]
            self.assertEqual(len(chunk["nodes"]), 2)
            self.assertEqual(len(chunk["nodeData"]["Data"]), 2)
            self.assertEqual(chunk["nodes"][0]["Data"]["debugName"]["$value"], "Wall")
            block = json.loads((root/"native-json/demo_world/all.streamingblock.json").read_text())
            self.assertEqual(block["Data"]["RootChunk"]["descriptors"][0]["data"]["DepotPath"]["$value"], "demo_world/sectors/sector_a.streamingsector")

    def test_cli_preflight_convert_and_verify(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            exp=write_export(root/"demo_world_exported.json")
            bundle=write_bundle(root/"templates.json")
            cli=write_fake_cli(root/"cp77tools")
            prep=prepare_native_json(exp,bundle,root/"json")
            pf=native_preflight(cli=cli)
            self.assertTrue(pf["ready"])
            self.assertTrue(pf["convertDeserialize"])
            preview=native_convert(root/"json",root/"archive",cli=cli,run=False)
            self.assertFalse(preview["run"])
            done=native_convert(root/"json",root/"archive",cli=cli,run=True)
            self.assertTrue(done["verification"]["valid"])
            self.assertTrue((root/"archive/demo_world/all.streamingblock").read_bytes().startswith(b"CR2W"))
            verify=verify_native_outputs(root/"archive",[x["target"] for x in prep["files"]])
            self.assertTrue(verify["valid"])

    def test_native_import_and_backend_scan(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            exp=write_export(root/"demo_world_exported.json",devices=False)
            bundle=write_bundle(root/"templates.json")
            cli=write_fake_cli(root/"cp77tools")
            done=native_import(exp,bundle,root/"archive",cli=cli,run=True)
            self.assertTrue(done["native"])
            scan=backend_scan(cli=cli)
            self.assertTrue(scan["capabilities"]["wkitJsonToCr2w"])
            self.assertTrue(scan["capabilities"]["linuxNativeObjectSpawnerConversion"])
            self.assertTrue(scan["capabilities"]["nativeRequiresTemplateBundle"])

    def test_build_prepare_includes_capture_script(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            exp=write_export(root/"demo_world_exported.json")
            wb=root/"entSpawner"
            write_wb_importer(wb)
            result=prepare_build_workspace(exp,root/"work",world_builder_root=wb)
            capture=Path(result["nativeTemplateCapture"])
            self.assertTrue(capture.is_file())
            self.assertIn("worldStaticMeshNode", capture.read_text())
            manifest=json.loads((Path(result["workspace"])/".cp77wb-build.json").read_text())
            self.assertEqual(manifest["cp77wbVersion"],"1.0.1")
            self.assertIn("nativeRequiredTypes",manifest)


class McpV09Tests(unittest.TestCase):
    def test_v09_tools_registered(self):
        names={t["name"] for t in TOOLS}
        expected={"wb_native_template_plan","wb_native_template_verify","wb_native_json","wb_native_preflight","wb_native_convert","wb_native_import","wb_native_verify","wb_build_native_import"}
        self.assertTrue(expected <= names)
        self.assertEqual(len(names),94)

    def test_native_json_mcp_is_preview_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            exp=write_export(root/"demo_world_exported.json")
            bundle=write_bundle(root/"templates.json")
            result=call_tool("wb_native_json",{"export_file":str(exp),"bundle":str(bundle),"output":str(root/"native")})
            self.assertFalse(result["written"])
            self.assertFalse((root/"native").exists())
            result=call_tool("wb_native_json",{"export_file":str(exp),"bundle":str(bundle),"output":str(root/"native"),"write":True})
            self.assertTrue(result["written"])
            self.assertTrue((root/"native/.cp77wb-native-json.json").is_file())

    def test_build_native_import_populates_workspace(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            exp=write_export(root/"demo_world_exported.json",devices=False)
            bundle=write_bundle(root/"templates.json")
            cli=write_fake_cli(root/"cp77tools")
            prep=prepare_build_workspace(exp,root/"work")
            from cp77wb.build import build_native_import
            preview=build_native_import(prep["workspace"],bundle,cli=cli,run=False)
            self.assertTrue(preview["ready"])
            self.assertFalse((Path(prep["workspace"])/"source/archive/demo_world/all.streamingblock").exists())
            done=build_native_import(prep["workspace"],bundle,cli=cli,run=True)
            self.assertTrue(done["ready"])
            self.assertTrue(done["status"]["importComplete"])
            manifest=json.loads((Path(prep["workspace"])/".cp77wb-build.json").read_text())
            self.assertEqual(manifest["lastImportBackend"],"template-json+wkit-convert-deserialize")


if __name__ == "__main__":
    unittest.main()
