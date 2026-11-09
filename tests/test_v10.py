from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cp77wb import __version__
from cp77wb.build import build_worker_import, prepare_build_workspace
from cp77wb.mcp_server import TOOLS, call_tool
from cp77wb.worker import WORKER_PROTOCOL, build_worker, worker_create_bundle, worker_import, worker_preflight
from tests.test_v08 import write_export


def write_fake_worker(path: Path, *, protocol: str = WORKER_PROTOCOL) -> Path:
    path.write_text(f'''#!/usr/bin/env python3
import json,sys,pathlib
PROTOCOL={protocol!r}
def out(x): print(json.dumps(x,separators=(",",":")))
cmd=sys.argv[1] if len(sys.argv)>1 else "help"
if cmd=="selftest":
 out({{"protocol":PROTOCOL,"ready":True,"apiProfile":"fake-profile","wolvenKitVersion":"9.0.1","dotnetVersion":"10.0.0","capabilities":{{"createTemplates":True,"jsonToCr2w":True}}}});sys.exit(0)
if cmd=="inspect":
 out({{"protocol":PROTOCOL,"apiProfile":"fake-profile","wolvenKitVersion":"9.0.1","dotnetVersion":"10.0.0","discovery":{{"serializer":"Fake.RedJsonSerializer","writer":"Fake.CR2WWriter","serializerMethods":["Serialize(Fake)"],"writerMethods":["Write(Fake)"]}}}});sys.exit(0)
if cmd=="templates":
 a=sys.argv; types=json.loads(pathlib.Path(a[a.index("--types")+1]).read_text()); target=pathlib.Path(a[a.index("--output")+1])
 base={{
 "worldStreamingSector":{{"nodes":[],"nodeRefs":[],"nodeData":{{}}}},
 "gameDeviceResource":{{}},"gamePersistentStateDataResource":{{}},"worldStreamingBlock":{{"descriptors":[]}},
 "worldStreamingSectorDescriptor":{{"category":"Exterior","level":255,"numNodeRanges":1,"streamingBox":{{"Max":{{"X":0,"Y":0,"Z":0}},"Min":{{"X":0,"Y":0,"Z":0}}}},"data":{{"DepotPath":{{"$type":"ResourcePath","$storage":"uint64","$value":"0"}}}},"questPrefabNodeRef":{{"$type":"NodeRef","$storage":"uint64","$value":"0"}},"variants":[]}},
 "worldStreamingSectorVariant":{{"enabledByDefault":False,"name":{{"$type":"CName","$storage":"string","$value":""}},"nodeRef":{{"$type":"NodeRef","$storage":"uint64","$value":"0"}},"rangeIndex":0,"variantId":0}},
 "worldStaticMeshNode":{{"debugName":{{"$type":"CName","$storage":"string","$value":""}}}}
 }}
 target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps({{"schema":"cp77wb-wkit-templates/1","generatedBy":"fake-worker","wolvenKitVersion":"9.0.1","types":{{t:base.get(t,{{}}) for t in types}}}}))
 out({{"protocol":PROTOCOL,"ok":True,"output":str(target),"count":len(types)}});sys.exit(0)
if cmd=="deserialize":
 a=sys.argv; target=pathlib.Path(a[a.index("--output")+1]);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b"CR2WFAKE")
 out({{"protocol":PROTOCOL,"ok":True,"output":str(target)}});sys.exit(0)
out({{"protocol":PROTOCOL,"error":"unsupported"}});sys.exit(2)
''', encoding='utf-8')
    path.chmod(0o755)
    return path


class WorkerV10Tests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(__version__, "1.0.1")

    def test_worker_preflight_authoritative(self):
        with tempfile.TemporaryDirectory() as td:
            worker=write_fake_worker(Path(td)/"cp77wb-wkit-worker")
            pf=worker_preflight(worker=worker)
            self.assertTrue(pf["ready"])
            self.assertTrue(pf["authoritativeNative"])
            self.assertEqual(pf["wolvenKitVersion"],"9.0.1")

    def test_worker_protocol_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            worker=write_fake_worker(Path(td)/"worker",protocol="wrong/1")
            pf=worker_preflight(worker=worker)
            self.assertFalse(pf["ready"])
            self.assertIn("protocol mismatch",pf["reason"])

    def test_worker_bundle_eliminates_wscript_capture(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            exp=write_export(root/"demo_world_exported.json")
            worker=write_fake_worker(root/"worker")
            preview=worker_create_bundle(exp,root/"bundle.json",worker=worker,run=False)
            self.assertTrue(preview["ready"])
            self.assertFalse((root/"bundle.json").exists())
            done=worker_create_bundle(exp,root/"bundle.json",worker=worker,run=True)
            self.assertTrue(done["created"])
            data=json.loads((root/"bundle.json").read_text())
            self.assertIn("worldStaticMeshNode",data["types"])

    def test_worker_import_produces_verified_cr2w(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            exp=write_export(root/"demo_world_exported.json")
            worker=write_fake_worker(root/"worker")
            preview=worker_import(exp,root/"archive",worker=worker,run=False)
            self.assertTrue(preview["ready"])
            self.assertFalse((root/"archive").exists())
            done=worker_import(exp,root/"archive",worker=worker,run=True)
            self.assertTrue(done["native"])
            self.assertTrue(done["authoritativeNative"])
            self.assertTrue((root/"archive/demo_world/all.streamingblock").read_bytes().startswith(b"CR2W"))

    def test_build_worker_import_updates_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            exp=write_export(root/"demo_world_exported.json",devices=False)
            worker=write_fake_worker(root/"worker")
            prep=prepare_build_workspace(exp,root/"work")
            preview=build_worker_import(prep["workspace"],worker=worker,run=False)
            self.assertTrue(preview["ready"])
            done=build_worker_import(prep["workspace"],worker=worker,run=True)
            self.assertTrue(done["ready"])
            manifest=json.loads((Path(prep["workspace"])/".cp77wb-build.json").read_text())
            self.assertEqual(manifest["cp77wbVersion"],"1.0.1")
            self.assertEqual(manifest["lastImportBackend"],"dotnet-wolvenkit-worker")

    def test_worker_build_preview_is_safe(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            fake_dotnet=root/"dotnet"
            fake_dotnet.write_text("#!/bin/sh\nexit 0\n")
            fake_dotnet.chmod(0o755)
            project=Path(__file__).resolve().parents[1]/"extras/cp77wb_wkit_worker/cp77wb-wkit-worker.csproj"
            result=build_worker(source=project,output=root/"publish",dotnet=fake_dotnet,run=False)
            self.assertTrue(result["ready"])
            self.assertFalse((root/"publish").exists())
            self.assertIn("publish",result["command"])


class McpV10Tests(unittest.TestCase):
    def test_v10_worker_tools_and_preview(self):
        names={t["name"] for t in TOOLS}
        expected={"wb_worker_build","wb_worker_preflight","wb_worker_bundle","wb_worker_import","wb_build_worker_import"}
        self.assertTrue(expected <= names)
        self.assertEqual(len(names),94)
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            exp=write_export(root/"demo_world_exported.json")
            worker=write_fake_worker(root/"worker")
            result=call_tool("wb_worker_bundle",{"export_file":str(exp),"output":str(root/"bundle.json"),"worker":str(worker)})
            self.assertTrue(result["ready"])
            self.assertFalse((root/"bundle.json").exists())


if __name__ == "__main__":
    unittest.main()
