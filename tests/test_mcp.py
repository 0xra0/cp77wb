from __future__ import annotations

import json
import unittest
from pathlib import Path

from cp77wb.mcp_server import MODERN_PROTOCOL, call_tool, handle_message

FIXTURE = Path(__file__).parent / "data" / "sample.json"


class McpTests(unittest.TestCase):
    def test_legacy_initialize_and_tools(self):
        response = handle_message({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}},
        })
        assert response is not None
        self.assertEqual(response["result"]["protocolVersion"], "2025-11-25")
        listing = handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        assert listing is not None
        names = {tool["name"] for tool in listing["result"]["tools"]}
        self.assertIn("wb_array", names)
        self.assertIn("wb_validate", names)

    def test_modern_discover(self):
        response = handle_message({
            "jsonrpc": "2.0", "id": 1, "method": "server/discover",
            "params": {"_meta": {"io.modelcontextprotocol/protocolVersion": MODERN_PROTOCOL}},
        })
        assert response is not None
        self.assertIn(MODERN_PROTOCOL, response["result"]["supportedVersions"])
        self.assertEqual(response["result"]["resultType"], "complete")
        self.assertIn("io.modelcontextprotocol/serverInfo", response["result"]["_meta"])

    def test_tool_call_readonly(self):
        result = call_tool("wb_validate", {"file": str(FIXTURE)})
        self.assertEqual([i for i in result if i["severity"] == "error"], [])

    def test_tool_call_mutation_defaults_to_dry_run(self):
        before = FIXTURE.read_text()
        result = call_tool("wb_move", {"file": str(FIXTURE), "path": "/Demo/DeviceA", "x": 1})
        self.assertFalse(result["written"])
        self.assertIn("DeviceA", result["diff"])
        self.assertEqual(FIXTURE.read_text(), before)

    def test_tools_call_envelope(self):
        response = handle_message({
            "jsonrpc": "2.0", "id": 7, "method": "tools/call",
            "params": {"name": "wb_get", "arguments": {"file": str(FIXTURE)}, "_meta": {"io.modelcontextprotocol/protocolVersion": MODERN_PROTOCOL}},
        })
        assert response is not None
        self.assertFalse(response["result"]["isError"])
        self.assertEqual(response["result"]["resultType"], "complete")
        payload = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual(payload["name"], "Demo")
