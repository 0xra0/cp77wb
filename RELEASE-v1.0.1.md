# cp77wb v1.0.1

v1.0.1 is a compatibility/hardening patch for the .NET 10 WolvenKit worker. It is designed so the real Void Linux worker test can be performed later without losing the evidence needed to diagnose an API mismatch.

## Added

- `worker-inspect` — prints the discovered WolvenKit API surface and `apiProfile` fingerprint without requiring CR2W round-trip success.
- `worker-doctor` — captures platform, Python, .NET SDK/runtime, worker inspect and worker preflight data; `--output` writes a support ZIP.
- `worker-build --log-file FILE` — preserves complete `dotnet publish` output.
- worker `inspect` command with WolvenKit assembly/version/location inventory, RED type count, serializer signatures, writer constructors and writer signatures.
- API-profile fingerprint propagated into worker self-test/preflight output.
- MCP: `wb_worker_inspect`, `wb_worker_doctor`.

## Deferred test

This release intentionally does not claim a real WolvenKit worker run in the packaging container. On the target Void Linux system, run `worker-build`, `worker-inspect`, `worker-preflight`, then `worker-doctor --output ...`. The older v0.9 template+CLI and upstream World Builder WScript backends remain available if the worker is not authoritative.

## Verification

- 107/107 Python tests pass.
- 94/94 MCP tools are unique.
- Python package compile check passes.
- CET Lua bridge syntax check passes.
- Worker source-level diagnostics and API-profile contract are covered by synthetic worker tests.
