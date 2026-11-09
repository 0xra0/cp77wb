# cp77wb v0.9.0

v0.9 introduces a template-driven, runtime-probed conversion backend for the World Builder Object Spawner import stage while retaining the exact upstream WScript importer as fallback.

## Highlights

- `cp77wb-wkit-templates/1` RED default-instance bundles.
- Generated capture WScript containing only the RED classes required by a specific export.
- Python mirror of the supplied World Builder Object Spawner importer into inspectable WolvenKit JSON.
- Runtime probe for `convert deserialize` on the exact supplied WolvenKit CLI/cp77tools executable.
- Preview-first native conversion; external execution requires `--run`.
- Verification of expected `.streamingsector`, `.streamingblock`, optional `.devices`/`.psrep`, plus CR2W magic.
- `build-native-import` integration with the v0.8 build workspace.
- 87 unique Claude Code MCP tools.
- 92 automated tests.

## Recommended workflow

```bash
cp77wb build-prepare \
  MyWorld_exported.json \
  ./build/MyWorld \
  --world-builder-root /path/to/entSpawner \
```

Run the generated `automation/capture_cp77wb_templates_MyWorld.wscript` once in a compatible WolvenKit WScript session, then:

```bash
cp77wb native-template-verify \
  MyWorld_exported.json \
  cp77wb_templates_MyWorld.json

cp77wb native-preflight --cli /path/to/cp77tools

cp77wb build-native-import \
  ./build/MyWorld \
  cp77wb_templates_MyWorld.json \
  --cli /path/to/cp77tools

cp77wb build-native-import \
  ./build/MyWorld \
  cp77wb_templates_MyWorld.json \
  --cli /path/to/cp77tools \
  --run

cp77wb build-status ./build/MyWorld
```

Only continue to `build-pack`, `build-package`, `build-verify` and deployment if `build-status` reports the expected native import outputs.

## Why template capture exists

The upstream World Builder importer relies on WolvenKit `CreateInstanceAsJSON` for default RED class instances before filling fields and serializing them. v0.9 does not fabricate those defaults. Instead it captures trustworthy defaults once into a versioned bundle, reproduces the importer logic in Python, and delegates final WolvenKit JSON→CR2W serialization to a probed CLI.

A template bundle can be reused when it covers all RED types required by another export. Re-capture when a newer WolvenKit version changes the relevant defaults or verification reports missing types.

## Safety

- Template coverage is verified before conversion.
- Native CLI availability is established by an actual subprocess probe, not a version assumption.
- Conversion commands are preview-only unless `--run` is supplied.
- A successful CLI exit is insufficient; cp77wb verifies output paths and CR2W magic.
- The exact World Builder WScript importer remains available as fallback.
- Build manifests record the backend used for a completed native import.

## Verification boundary

The cp77wb release environment does **not** have a real WolvenKit CLI/.NET installation. The v0.9 tests exercise the CLI contract with a compatible test executable and independently verify resulting CR2W-marked outputs. Therefore a real Linux installation must pass:

```bash
cp77wb native-preflight --cli /path/to/actual/WolvenKit.CLI
```

before the native backend is considered usable there. This limitation is deliberate and reported rather than hidden.
