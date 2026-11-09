# v0.9 native conversion backend

v0.9 adds a conditional cross-platform backend for the World Builder Object Spawner conversion step. It does **not** implement CR2W serialization in Python. Instead it separates the two responsibilities hidden inside the upstream WolvenKit WScript importer:

1. obtain default WolvenKit JSON instances for the RED classes the export needs;
2. serialize finished WolvenKit JSON into CR2W.

cp77wb handles the importer logic between those boundaries. A captured template bundle supplies step 1, while an installed WolvenKit CLI with `convert deserialize` supplies step 2.

## Pipeline

```text
World Builder *_exported.json
        │
        ├─ cp77wb build-prepare
        │       └─ automation/capture_cp77wb_templates_<name>.wscript
        │
        ├─ run capture script once in a compatible WolvenKit session
        │       └─ cp77wb_templates_<name>.json
        │
        ├─ cp77wb native-template-verify
        │
        ├─ cp77wb native-preflight --cli <WolvenKit CLI>
        │
        ├─ cp77wb build-native-import [preview]
        │       ├─ mirror upstream Object Spawner import
        │       └─ produce WolvenKit JSON intermediates
        │
        ├─ cp77wb build-native-import --run
        │       └─ CLI convert deserialize → CR2W
        │
        ├─ strict CR2W output verification
        │
        └─ ordinary build-status → pack → package → verify → deploy
```

## Prepare a workspace

```bash
cp77wb build-prepare \
  MyWorld_exported.json \
  ./build/MyWorld \
  --world-builder-root /path/to/entSpawner \
```

The workspace contains both the original importer fallback and a generated template-capture script. The capture script calls WolvenKit's `CreateInstanceAsJSON` only for the types required by the current export.

## Capture the templates

Run the generated script in a WolvenKit environment capable of executing WScript:

```text
automation/capture_cp77wb_templates_MyWorld.wscript
```

The result is a JSON bundle with schema:

```text
cp77wb-wkit-templates/1
```

A bundle can be reused by other exports when it contains all required types. Re-capture after a WolvenKit change if verification reports missing/incompatible templates.

Verify before conversion:

```bash
cp77wb native-template-verify \
  MyWorld_exported.json \
  cp77wb_templates_MyWorld.json
```

## Probe the real CLI

Never infer Linux support from a package version alone:

```bash
cp77wb native-preflight --cli /path/to/cp77tools
```

or:

```bash
cp77wb native-preflight --cli /path/to/WolvenKit.CLI
```

The probe runs the supplied executable and requires working `convert deserialize` help. A failed probe keeps the native backend unavailable and the WScript importer remains the fallback.

## Preview the native import

```bash
cp77wb build-native-import \
  ./build/MyWorld \
  cp77wb_templates_MyWorld.json \
  --cli /path/to/cp77tools
```

Preview mode checks the template coverage and CLI capabilities without producing CR2W files.

Run only after the preview is correct:

```bash
cp77wb build-native-import \
  ./build/MyWorld \
  cp77wb_templates_MyWorld.json \
  --cli /path/to/cp77tools \
  --run
```

On success cp77wb updates the workspace manifest with:

```text
lastImportBackend = template-json+wkit-convert-deserialize
```

and ordinary `build-status` must still report `importComplete=true`.

## Standalone commands

Generate only the capture script:

```bash
cp77wb native-template-plan MyWorld_exported.json ./capture.wscript
```

Generate WolvenKit JSON without CR2W conversion:

```bash
cp77wb native-json \
  MyWorld_exported.json \
  cp77wb_templates_MyWorld.json \
  ./native-json
```

Preview/execute conversion of that manifest:

```bash
cp77wb native-convert ./native-json ./native-output --cli /path/to/cp77tools
cp77wb native-convert ./native-json ./native-output --cli /path/to/cp77tools --run
```

Or perform both stages:

```bash
cp77wb native-import \
  MyWorld_exported.json \
  cp77wb_templates_MyWorld.json \
  ./native-output \
  --cli /path/to/cp77tools \
  --run
```

Verify independently:

```bash
cp77wb native-verify ./native-output
```

By default verification requires every expected output to start with `CR2W`; a successful child-process exit code is not enough.

## What cp77wb mirrors

The Python importer follows the supplied World Builder importer structure for:

- world streaming sectors;
- world node data and indices;
- sector descriptors and variants;
- streaming block assembly;
- NodeRef/hash-derived fields used by the importer;
- optional device resources;
- optional persistent-state resources;
- instance-data ordering/reformatting expected by WolvenKit JSON.

The generated WolvenKit JSON remains inspectable before serialization.

## Safety and compatibility

- template capture is a bootstrap step, not silently synthesized data;
- no native conversion executes without `--run`;
- `native-preflight` probes the executable supplied on the current machine;
- generated CR2W output is checked for real `CR2W` magic;
- `build-status` remains the authority for expected World Builder outputs;
- the v0.8 upstream WScript importer stays available as fallback;
- a bundle is rejected if required RED class templates are missing.

## Current verification boundary

The cp77wb release test environment does not contain a real WolvenKit CLI or .NET runtime. v0.9 therefore tests CLI invocation through a contract-compatible test executable and independently verifies output shape/magic. The first real-machine step should always be:

```bash
cp77wb native-preflight --cli /path/to/your/actual/WolvenKit.CLI
```

Do not treat the backend as available on a particular Linux/WolvenKit installation until that command succeeds.
