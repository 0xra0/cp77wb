# cp77wb — Cyberpunk 2077 World Builder Automation & Tooling

[![Project Status: WIP (Paused)](https://img.shields.io/badge/status-WIP%20%2F%20Paused-orange.svg)](#project-status)
[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-107%2F107%20passing-brightgreen.svg)](#testing--verification)
[![MCP Tools](https://img.shields.io/badge/mcp%20tools-94%20registered-purple.svg)](#claude-code--ai-mcp-integration)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Cyberpunk 2077](https://img.shields.io/badge/game-Cyberpunk%202077-yellow.svg)](https://www.cyberpunk.net/)

`cp77wb` is an external, non-invasive automation layer, procedural construction suite, and Model Context Protocol (MCP) server for Cyberpunk 2077 **World Builder** (`entSpawner`).

While World Builder serves as the in-game visual editor, `cp77wb` provides Linux-friendly offline project management, high-performance SQLite asset catalogs, procedural math (spline placement, 2D/3D scatters, room/corridor generation), automated device and elevator wiring, end-to-end mod build orchestration (.NET 10 native WolvenKit worker & WScript fallbacks), an optional history-safe Cyber Engine Tweaks (CET) live bridge, and **94 native MCP tools** for AI pair programming with Claude Code, Cursor, and LLM agents.

---

> [!IMPORTANT]
> ### ⚠️ Project Status: Work In Progress (WIP) — Currently Paused
> **Notice**: Active feature development on `cp77wb` is currently **paused/on hold**.
> - The codebase is fully functional, complete, and verified (all **107 unit tests** pass, Ruff and Pyright static checks pass with 0 errors, and the bundled C# .NET 10 worker builds cleanly).
> - You can install, run, fork, or adapt `cp77wb` for your Cyberpunk 2077 modding workflows.
> - Pull requests, bug reports, and forks are welcome, but no active roadmap milestones are being actively developed by the original author at this time.

---

## Table of Contents

- [Key Features](#key-features)
- [Architecture & Workflow](#architecture--workflow)
- [System Requirements](#system-requirements)
- [Installation](#installation)
  - [Method 1: User Install (`install.sh`)](#method-1-user-install-installsh)
  - [Method 2: Python Package (`pip`)](#method-2-python-package-pip)
  - [Method 3: Portable / In-Place Execution](#method-3-portable--in-place-execution)
  - [CET Live Bridge Installation](#cet-live-bridge-installation)
  - [Building the .NET 10 WolvenKit Worker](#building-the-net-10-wolvenkit-worker)
- [Quick Start](#quick-start)
- [Comprehensive CLI Usage](#comprehensive-cli-usage)
  - [Build Inspection & Validation](#build-inspection--validation)
  - [Asset Catalog & Semantic Search](#asset-catalog--semantic-search)
  - [Procedural Path & Spline Placement](#procedural-path--spline-placement)
  - [Polygon & Volume 3D Scatter](#polygon--volume-3d-scatter)
  - [Weighted Asset Pools & Native RNG Groups](#weighted-asset-pools--native-rng-groups)
  - [Procedural Generators (Rooms, Corridors, Markets)](#procedural-generators-rooms-corridors-markets)
  - [Device & Elevator Wiring Automation](#device--elevator-wiring-automation)
  - [AI Construction Plans (`cp77wb-plan/1`)](#ai-construction-plans-cp77wb-plan1)
  - [World Builder Compatibility Scanner](#world-builder-compatibility-scanner)
  - [Mod Packaging & Build Pipeline](#mod-packaging--build-pipeline)
  - [.NET 10 Worker Diagnostics](#net-10-worker-diagnostics)
- [Claude Code & AI MCP Integration](#claude-code--ai-mcp-integration)
- [Optional CET Live Bridge](#optional-cet-live-bridge)
- [Safety Guarantees & Philosophy](#safety-guarantees--philosophy)
- [Testing & Verification](#testing--verification)
- [Documentation Directory](#documentation-directory)
- [License & Acknowledgements](#license--acknowledgements)

---

## Key Features

- **Non-Invasive Architecture**: Never modifies core game binaries, never redistributes copyrighted game assets, and does not fork World Builder. Preserves unknown JSON fields and creates timestamped backups on write.
- **Offline Saved-Build Editing**: Inspect, translate, rotate, scale, align, distribute, and duplicate nodes within World Builder `Build.json` files offline on Linux without launching the game.
- **Deterministic Asset Catalog**: Indexes over 50,000+ game assets directly from your local `entSpawner` installation into an SQLite3 database with deterministic hash IDs (`#75857`) and semantic tagging.
- **Procedural Level Design**:
  - Polyline and cubic Bezier curve spline placement with tangent interpolation.
  - 2D polygon bounding and 3D volume scatters (box, sphere, cylinder) with collision clearance guards.
  - Room shell, corridor connector, and open market layout generators.
  - Parameterized JSON prefab templates.
- **Device & Elevator Wiring**: Connects security areas to controllers and automates complex multi-floor elevator terminal setups, generating unique persistent `NodeRef`s and component schemas.
- **Full Mod Packaging Pipeline**:
  - Inspects World Builder export files.
  - Generates WolvenKit projects with ArchiveXL `.xl` definitions.
  - High-performance .NET 10 worker backend for direct RED JSON to CR2W conversion.
  - Automatic fallback to v0.9 template CLI conversion or upstream WolvenKit WScript execution.
  - Safe archive packing via `cp77tools` or WolvenKit CLI, distribution layout creation, and conflict-checked game deployment.
- **In-Game CET Live Bridge**: Optional file-RPC companion mod for Cyber Engine Tweaks providing camera raycasting, surface snapping to real REDengine collision geometry, and unified undo history integration.
- **94 Native MCP Tools**: First-class support for AI agents (Claude Code, Cursor) to inspect, generate, modify, and build Cyberpunk 2077 environments autonomously.

---

## Architecture & Workflow

```
┌────────────────────────────────────────────────────────┐
│               Cyberpunk 2077 Game                      │
│   (Cyber Engine Tweaks + World Builder / entSpawner)   │
└───────────────────────▲────────────────────────────────┘
                        │ File-RPC (Live Bridge)
                        ▼
┌────────────────────────────────────────────────────────┐
│                        cp77wb                          │
│  ┌───────────────────┐        ┌─────────────────────┐  │
│  │  CLI & MCP Tools  │ ◄────► │ Asset Catalog (DB)  │  │
│  │   (94 AI Tools)   │        │ (SQLite3 / Semantic)│  │
│  └─────────┬─────────┘        └─────────────────────┘  │
│            │                                           │
│            ▼                                           │
│  ┌───────────────────┐        ┌─────────────────────┐  │
│  │ Procedural Engine │        │ Construction Plans  │  │
│  │ (Splines/Scatter) │        │   (cp77wb-plan/1)   │  │
│  └─────────┬─────────┘        └─────────────────────┘  │
└────────────┼───────────────────────────────────────────┘
             │ Build / Export
             ▼
┌────────────────────────────────────────────────────────┐
│              Mod Compilation Pipeline                  │
│  ┌──────────────────────────────────────────────────┐  │
│  │ .NET 10 WolvenKit Worker / WScript Native Engine │  │
│  └─────────────────────────┬────────────────────────┘  │
│                            ▼                           │
│  ┌──────────────────────────────────────────────────┐  │
│  │ cp77tools / WolvenKit CLI Archive Packing        │  │
│  └─────────────────────────┬────────────────────────┘  │
│                            ▼                           │
│         Final Distributable Mod (.archive + .xl)       │
└────────────────────────────────────────────────────────┘
```

---

## System Requirements

| Component | Minimum Requirement | Notes |
| :--- | :--- | :--- |
| **Operating System** | Linux, macOS, or Windows (WSL2) | Developed and tested natively on Linux |
| **Python** | Python 3.11+ | Zero external pip dependencies for core CLI |
| **Cyberpunk 2077** | Version 2.0+ (Phantom Liberty supported) | Required for in-game editor & CET bridge |
| **World Builder** | entSpawner mod installed in CP77 | Visual editor & export source |
| **Cyber Engine Tweaks** | CET 1.30+ | Required only if using live bridge |
| **.NET SDK (Optional)** | .NET 10 SDK | Required to build native WolvenKit worker |
| **WolvenKit (Optional)** | WolvenKit CLI or cp77tools | Required for final `.archive` packing |

---

## Installation

### Method 1: User Install (`install.sh`)

The included zero-dependency installer installs `cp77wb` and `cp77wb-mcp` into your user path (default: `~/.local/bin`):

```bash
git clone https://github.com/0xra0/cp77wb.git
cd cp77wb
./install.sh --prefix "$HOME/.local"
```

Verify your installation:
```bash
cp77wb --version
# Output: cp77wb 1.0.1
```

*(Ensure `$HOME/.local/bin` is in your `$PATH`)*

### Method 2: Python Package (`pip`)

You can install `cp77wb` directly into your current Python environment:

```bash
cd cp77wb
pip install -e .
```

### Method 3: Portable / In-Place Execution

Run `cp77wb` directly from the cloned repository without installing anything:

```bash
./bin/cp77wb --version
./bin/cp77wb-mcp --help
```

### CET Live Bridge Installation

If you want real-time live manipulation in the game:

```bash
./extras/install-cet-bridge.sh \
  "/path/to/Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods"
```

### Building the .NET 10 WolvenKit Worker

To use the high-performance native CR2W conversion backend:

```bash
# Using cp77wb helper:
cp77wb worker-build --run

# Or building directly with dotnet:
./extras/cp77wb_wkit_worker/build.sh
```

---

## Quick Start

### 1. Validate an Existing Saved Build
Inspect any World Builder `Build.json` file offline:
```bash
cp77wb validate /path/to/Build.json
cp77wb tree /path/to/Build.json
```

### 2. Build the Asset Catalog
Index all World Builder assets from your game directory into a local fast SQLite3 database:
```bash
cp77wb assets-build "/path/to/Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods/entSpawner"
```

### 3. Search Assets
Find assets with deterministic IDs:
```bash
cp77wb assets-search ~/.local/share/cp77wb/assets.sqlite3 "neon sign" --variant Mesh
# Results return unique IDs like #14022
```

### 4. Procedurally Place Objects
Place lamps along a curved road using cubic Bezier interpolation:
```bash
cp77wb path-array Build.json /Build/StreetLamp \
  --points '[[0,0,0],[15,2,0],[30,10,0]]' \
  --spacing 3.0 \
  --write
```

---

## Comprehensive CLI Usage

All mutation commands are **dry-run by default**. Pass `--write` or `--apply` only after reviewing the diff output.

### Build Inspection & Validation

```bash
# Validate structural integrity, NodeRef uniqueness, and component references
cp77wb validate Build.json

# Display hierarchical tree view of node groups
cp77wb tree Build.json

# List all node paths in the build
cp77wb paths Build.json

# Inspect details of a specific node
cp77wb inspect Build.json /Build/MyNode
```

### Asset Catalog & Semantic Search

```bash
# Build the SQLite asset catalog from World Builder entSpawner files
cp77wb assets-build /path/to/entSpawner --output assets.sqlite3

# Search by keyword and asset type
cp77wb assets-search assets.sqlite3 "arasaka crate" --variant Mesh

# Build semantic facets (style, role, scale heuristic)
cp77wb semantic-build assets.sqlite3

# Query semantic catalog
cp77wb semantic-search assets.sqlite3 "industrial barrier" --role wall --style industrial
```

### Procedural Path & Spline Placement

```bash
# Follow existing World Builder marker group with Bezier tangents
cp77wb path-array Build.json /Build/LightPole \
  --marker-group /Build/SplinePath \
  --spacing 4.0 \
  --curve-samples 16 \
  --write

# Supply arbitrary 3D polyline coordinates
cp77wb path-array Build.json /Build/Barrier \
  --points '[[0,0,0],[10,0,0],[20,5,1]]' \
  --spacing 1.5 \
  --yaw-offset 90 \
  --write
```

### Polygon & Volume 3D Scatter

```bash
# Scatter objects inside a 2D boundary polygon on the ground
cp77wb polygon-scatter Build.json /Build/Debris \
  --points '[[0,0,0],[10,0,0],[10,10,0],[0,10,0]]' \
  --count 25 --seed 2077 \
  --write

# Scatter objects in a 3D cylindrical volume (e.g. particles, dust, floating drones)
cp77wb volume-scatter Build.json /Build/Drone \
  --shape cylinder --count 15 \
  --center-x 50 --center-y 100 --center-z 10 \
  --size-x 10 --size-z 6 --seed 42 \
  --write
```

### Weighted Asset Pools & Native RNG Groups

Create a weighted asset pool configuration (`market_pool.json`):
```json
{
  "entries": [
    {"asset": "#1201", "weight": 5, "name": "Food Stall Common"},
    {"asset": "#1770", "weight": 1, "name": "Tech Vendor Rare"}
  ]
}
```

Spawn items according to weights:
```bash
cp77wb asset-pool-spawn Build.json /Build/Market \
  --catalog assets.sqlite3 \
  --pool market_pool.json \
  --count 10 --seed 77 \
  --half-x 15 --half-y 8 \
  --write
```

Generate native World Builder randomized groups that can still be edited in-game:
```bash
cp77wb rng-create Build.json /Build "Loot RNG" \
  --seed 1337 --rule fixed --fixed-mode total --total 3 \
  --write
```

### Procedural Generators (Rooms, Corridors, Markets)

```bash
# Generate a room enclosure with modular wall and floor segments
cp77wb generate-room Build.json /Build \
  --catalog assets.sqlite3 \
  --wall-asset '#1234' \
  --floor-asset '#4321' \
  --width 12 --depth 8 --segment 2 \
  --write

# Generate a hallway corridor
cp77wb generate-corridor Build.json /Build \
  --catalog assets.sqlite3 \
  --wall-asset '#1234' \
  --length 24 --width 4 --segment 2 \
  --write

# Generate a grid-based market area
cp77wb generate-market Build.json /Build \
  --catalog assets.sqlite3 \
  --pool market_pool.json \
  --rows 3 --columns 4 --spacing-x 4 --spacing-y 6 \
  --write
```

### Device & Elevator Wiring Automation

```bash
# Connect security terminal to its controller
cp77wb device-connect Build.json \
  /Build/SecurityCamera \
  /Build/SecurityController \
  --device-class-name SecurityAreaControllerPS \
  --write

# Automatically wire an elevator with multi-floor terminals and markers
cp77wb elevator-wire Build.json /Build/Elevator \
  --terminal /Build/Floor0_Terminal --marker /Build/Floor0_Marker --floor-name 'LocKey#100' \
  --terminal /Build/Floor1_Terminal --marker /Build/Floor1_Marker --floor-name 'LocKey#101' \
  --noderef-prefix my_mod/elevator \
  --write
```

### AI Construction Plans (`cp77wb-plan/1`)

Declarative JSON specifications for entire procedural scenes:

```bash
# Compile and validate plan
cp77wb plan-compile examples/construction-plan.json --catalog assets.sqlite3

# Preview against an existing build with collision detection
cp77wb plan-preview Build.json examples/construction-plan.json --catalog assets.sqlite3

# Apply changes after preview review
cp77wb plan-apply Build.json examples/construction-plan.json --catalog assets.sqlite3 --write
```

### World Builder Compatibility Scanner

Check whether a project or export matches your installed World Builder version:
```bash
cp77wb compat-scan "/path/to/Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods/entSpawner" \
  --project Build.json
```

### Mod Packaging & Build Pipeline

Take an export from World Builder and produce an installable `.archive` mod:

```bash
# 1. Inspect the exported file
cp77wb export-inspect project_exported.json

# 2. Prepare a WolvenKit project workspace
cp77wb build-prepare project_exported.json ~/cp77-projects --world-builder-root /path/to/entSpawner

# 3. Import via native worker (or fallback to WolvenKit CLI / WScript)
cp77wb worker-import project_exported.json ~/cp77-projects/my_project/source --run

# 4. Check workspace compilation readiness
cp77wb build-status ~/cp77-projects/my_project

# 5. Pack into game archive
cp77wb build-pack ~/cp77-projects/my_project --cli cp77tools --run

# 6. Package into distributable ZIP with ArchiveXL layout
cp77wb build-package ~/cp77-projects/my_project \
  --archive ~/cp77-projects/my_project/packed/archive/pc/mod/my_project.archive \
  --output ~/cp77-projects/my_project/dist \
  --zip ~/cp77-projects/my_project/my_project.zip

# 7. Deploy to game with conflict checking and automated backups
cp77wb build-deploy ~/cp77-projects/my_project/dist "/path/to/Cyberpunk 2077" --apply
```

### .NET 10 Worker Diagnostics

```bash
# Build the worker and capture diagnostic build logs
cp77wb worker-build --run --log-file ~/worker-build.log

# Inspect discovered WolvenKit assemblies and API fingerprint
cp77wb worker-inspect --worker extras/cp77wb_wkit_worker/publish/cp77wb-wkit-worker

# Run self-tests for native serialization and CR2W magic header verification
cp77wb worker-preflight --worker extras/cp77wb_wkit_worker/publish/cp77wb-wkit-worker

# Generate a diagnostic report bundle for debugging
cp77wb worker-doctor --output ~/cp77wb-doctor.zip
```

---

## Claude Code & AI MCP Integration

`cp77wb` provides an MCP (Model Context Protocol) server exposing **94 unique tools** to AI coding agents.

### Adding to Claude Code
```bash
claude mcp add cp77wb -- cp77wb-mcp
```

### Adding to Claude Desktop / Cursor (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "cp77wb": {
      "command": "cp77wb-mcp"
    }
  }
}
```

### MCP Tool Categories

| Tool Domain | Example MCP Tools | Function |
| :--- | :--- | :--- |
| **Inspection & Validation** | `wb_validate`, `wb_tree`, `wb_paths`, `wb_inspect` | Inspect and check saved projects |
| **Asset Discovery** | `wb_asset_search`, `wb_semantic_search`, `wb_bounds_info` | Query 50K+ game assets and bounding boxes |
| **Procedural Layout** | `wb_path_array`, `wb_polygon_scatter`, `wb_volume_scatter` | Polyline, spline, and volume distribution |
| **Generators** | `wb_generate_room`, `wb_generate_corridor`, `wb_generate_fence` | Architectural element synthesis |
| **AI Planner** | `wb_plan_compile`, `wb_plan_preview`, `wb_plan_apply` | Declarative `cp77wb-plan/1` scene execution |
| **Build & Packaging** | `wb_build_prepare`, `wb_build_pack`, `wb_build_deploy` | Complete pipeline orchestration |
| **Native Worker** | `wb_worker_inspect`, `wb_worker_preflight`, `wb_worker_doctor` | .NET 10 WolvenKit backend management |
| **Live Bridge** | `wb_live_ping`, `wb_live_raycast`, `wb_live_snap`, `wb_live_spawn` | Real-time in-game engine interaction |

---

## Optional CET Live Bridge

The included `extras/cp77wb_bridge` mod enables real-time bidirectional communication between `cp77wb` and the running game using a safe file-based RPC protocol:

- **History Protection**: Reads the active World Builder undo singleton and refuses live operations if history state has diverged.
- **True Engine Raycasting**: Casts collision rays directly in REDengine to accurately snap objects to terrain, floors, and walls.
- **In-Game Live Spawning**: Spawns assets in real time without restarting or reloading the save.

To test connectivity while Cyberpunk 2077 is running:
```bash
RPC="/path/to/Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods/cp77wb_bridge/rpc"
cp77wb live "$RPC" ping
cp77wb live "$RPC" raycast --ray-mode camera
```

---

## Safety Guarantees & Philosophy

1. **Dry-Run by Default**: Offline modifications require `--write` and live modifications require `--apply`. Without these flags, tools output a preview diff.
2. **Schema Integrity**: Unknown JSON properties present in upstream World Builder versions are preserved verbatim without data loss.
3. **Collision Clearance**: Procedural scattering checks asset bounds to avoid overlapping geometry.
4. **Non-Invasive**: No game DLL hooks, no binary memory injection, and no asset redistribution.
5. **Atomic Writes**: Saved files are written to temporary files and atomically moved with timestamped `.bak` copies.

---

## Testing & Verification

The repository includes a comprehensive test suite covering all modules:

```bash
# Run test suite with pytest:
pytest

# Or with standard library unittest:
python3 -m unittest discover -s tests -v

# Run full multi-language static analysis (Python, Ruff, Pyright, Shell, Lua, C#):
./static-check.sh
```

**Verification Status:**
- **107/107 Python unit tests passing**
- **0 errors** in Ruff linter checks
- **0 errors** in Pyright static type checks
- **Shell and Lua syntax checks passing**
- **C# .NET 10 worker builds with 0 errors**

---

## Documentation Directory

Deep dive guides are available in the [`docs/`](docs/) directory:

- [`docs/index.md`](docs/index.md) — Documentation index & overview
- [`docs/cli.md`](docs/cli.md) — Exhaustive command-line flag and argument reference
- [`docs/mcp.md`](docs/mcp.md) — Model Context Protocol tools and schemas
- [`docs/saved-build-format.md`](docs/saved-build-format.md) — Analysis of World Builder JSON structure
- [`docs/worldbuilder-source-map.md`](docs/worldbuilder-source-map.md) — Upstream code mapping
- [`docs/live-bridge.md`](docs/live-bridge.md) — CET file-RPC protocol and command format
- [`docs/v07-ai-planner.md`](docs/v07-ai-planner.md) — AI Construction Planner specification
- [`docs/v08-build-orchestration.md`](docs/v08-build-orchestration.md) — Export to mod packaging pipeline
- [`docs/v09-native-conversion.md`](docs/v09-native-conversion.md) — RED template capture and conversion
- [`docs/v10-native-worker.md`](docs/v10-native-worker.md) — .NET 10 WolvenKit native worker
- [`docs/v101-worker-diagnostics.md`](docs/v101-worker-diagnostics.md) — API profile and diagnostic bundles
- [`docs/claude-code.md`](docs/claude-code.md) — Claude Code agent workflow guide
- [`docs/upstream-compatibility.md`](docs/upstream-compatibility.md) — Compatibility and forward-migration rules

---

## License & Acknowledgements

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

### Acknowledgements & Community Credits
- **World Builder (`entSpawner`)**: Created by the amazing Cyberpunk 2077 modding community.
- **WolvenKit**: Developed by the REDmodding team for REDengine asset handling.
- **Cyber Engine Tweaks (CET)**: Essential Lua scripting platform for Cyberpunk 2077.
- **CD Projekt Red**: Cyberpunk 2077 is a registered trademark of CD PROJEKT S.A.

*This project is an unofficial community tool and is not affiliated with, endorsed by, or associated with CD PROJEKT RED.*
