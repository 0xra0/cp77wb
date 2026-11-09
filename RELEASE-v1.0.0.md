# cp77wb v1.0.0

v1.0 promotes the cross-platform Object Spawner path to a versioned .NET 10 WolvenKit worker architecture while retaining all v0.9 fallbacks.

## Highlights

- bundled `cp77wb-wkit-worker` .NET 10 project;
- pinned WolvenKit 9.0.1 package references;
- `cp77wb-wkit-worker/1` machine-readable protocol;
- runtime discovery/self-test rather than assuming a WolvenKit internal API profile;
- `worker-build`, `worker-preflight`, `worker-bundle`, `worker-import`, `build-worker-import`;
- no mandatory WScript template capture when the worker self-test passes;
- direct CR2W output verification remains mandatory;
- v0.9 template+CLI and upstream WScript importer remain supported;
- 92 unique MCP tools;
- 100 automated tests.

## Verification boundary

The release environment has no .NET SDK/runtime, so a real WolvenKit 9.0.1 worker build could not be executed here. v1.0 therefore does **not** label the worker authoritative merely because the source is present. `worker-preflight` must pass on the target machine and prove both RED default serialization and CR2W writing before cp77wb selects it.
