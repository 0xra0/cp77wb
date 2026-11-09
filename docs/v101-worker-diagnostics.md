# v1.0.1 worker diagnostics and deferred compatibility test

The v1.0 .NET worker is still capability-gated. v1.0.1 adds diagnostics so a real WolvenKit runtime test can be deferred until the target machine is convenient.

## Build with a full log

```bash
cp77wb worker-build --run --log-file ~/cp77wb-worker-build.log
```

The log is written even when `dotnet publish` fails.

## Inspect the discovered API surface

```bash
cp77wb worker-inspect --worker /path/to/cp77wb-wkit-worker
```

This command does not require the CR2W round-trip self-test to pass. It reports:

- WolvenKit assembly names, versions and locations;
- discovered `RedJsonSerializer` and `CR2WWriter` types;
- serializer serialize/deserialize signatures;
- CR2W writer constructors and write-method signatures;
- RED type count;
- .NET framework, OS and process architecture;
- `apiProfile`, a SHA-256 fingerprint of the relevant reflection signatures.

A changed `apiProfile` is a useful signal when a WolvenKit update changes the worker-facing API surface.

## Authoritative runtime test

```bash
cp77wb worker-preflight --worker /path/to/cp77wb-wkit-worker
```

Only `ready: true` and `authoritativeNative: true` permit direct worker conversion.

## Support bundle

```bash
cp77wb worker-doctor \
  --worker /path/to/cp77wb-wkit-worker \
  --output ~/cp77wb-worker-doctor.zip
```

The bundle contains `diagnostics.json`, dotnet diagnostic text, and the exact bundled worker source/project used by cp77wb. It does not collect World Builder project files or Cyberpunk game data.

The recommended later-test sequence is: build → inspect → preflight → doctor. If preflight succeeds, continue with a small one-sector `worker-import --run` before using the worker for a large build.
