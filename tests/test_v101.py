from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from cp77wb import __version__
from cp77wb.mcp_server import TOOLS, call_tool
from cp77wb.worker import build_worker, worker_doctor, worker_inspect, worker_preflight
from tests.test_v10 import write_fake_worker


class WorkerV101Tests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(__version__, "1.0.1")

    def test_worker_inspect_reports_api_profile(self):
        with tempfile.TemporaryDirectory() as td:
            worker = write_fake_worker(Path(td) / "worker")
            result = worker_inspect(worker=worker)
            self.assertTrue(result["inspectAvailable"])
            self.assertEqual(result["apiProfile"], "fake-profile")
            self.assertEqual(result["inspect"]["discovery"]["writer"], "Fake.CR2WWriter")

    def test_preflight_propagates_api_profile(self):
        with tempfile.TemporaryDirectory() as td:
            worker = write_fake_worker(Path(td) / "worker")
            result = worker_preflight(worker=worker)
            self.assertTrue(result["ready"])
            self.assertEqual(result["apiProfile"], "fake-profile")

    def test_worker_doctor_writes_support_zip(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            worker = write_fake_worker(root / "worker")
            fake_dotnet = root / "dotnet"
            fake_dotnet.write_text('#!/bin/sh\necho "fake dotnet $*"\nexit 0\n', encoding='utf-8')
            fake_dotnet.chmod(0o755)
            result = worker_doctor(worker=worker, dotnet=fake_dotnet, output=root / "support.zip")
            self.assertTrue(result["ready"])
            support = Path(result["supportBundle"])
            self.assertTrue(support.is_file())
            with zipfile.ZipFile(support) as zf:
                names = set(zf.namelist())
                self.assertIn("diagnostics.json", names)
                data = json.loads(zf.read("diagnostics.json"))
                self.assertEqual(data["schema"], "cp77wb-worker-doctor/1")
                self.assertEqual(data["inspect"]["apiProfile"], "fake-profile")

    def test_build_worker_can_preserve_full_publish_log(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake_dotnet = root / "dotnet"
            fake_dotnet.write_text('#!/bin/sh\necho "SYNTHETIC PUBLISH FAILURE DETAILS"\nexit 7\n', encoding='utf-8')
            fake_dotnet.chmod(0o755)
            project = Path(__file__).resolve().parents[1] / "extras/cp77wb_wkit_worker/cp77wb-wkit-worker.csproj"
            log = root / "publish.log"
            result = build_worker(source=project, output=root / "publish", dotnet=fake_dotnet, run=True, log_file=log)
            self.assertFalse(result["ready"])
            self.assertEqual(result["exitCode"], 7)
            self.assertIn("SYNTHETIC PUBLISH FAILURE DETAILS", log.read_text())

    def test_worker_source_exposes_inspect_and_profile(self):
        src = (Path(__file__).resolve().parents[1] / "extras/cp77wb_wkit_worker/Program.cs").read_text()
        self.assertIn('cmd == "inspect"', src)
        self.assertIn("ApiProfile()", src)
        self.assertIn("serializerMethods", src)
        self.assertIn("writerConstructors", src)


class McpV101Tests(unittest.TestCase):
    def test_v101_tools(self):
        names = {t["name"] for t in TOOLS}
        self.assertEqual(len(names), 94)
        self.assertIn("wb_worker_inspect", names)
        self.assertIn("wb_worker_doctor", names)
        with tempfile.TemporaryDirectory() as td:
            worker = write_fake_worker(Path(td) / "worker")
            result = call_tool("wb_worker_inspect", {"worker": str(worker)})
            self.assertEqual(result["apiProfile"], "fake-profile")


if __name__ == "__main__":
    unittest.main()
