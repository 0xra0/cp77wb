#!/usr/bin/env bash
set -uo pipefail

ROOT="${1:-.}"
cd "$ROOT" || exit 2
fail=0
missing=0

section() { printf '\n== %s ==\n' "$1"; }
need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: required checker '$1' is not installed or not on PATH" >&2
    missing=1
    fail=1
    return 1
  fi
}

section 'Python py_compile'
python3 - <<'PY' || fail=1
from pathlib import Path
import py_compile
files = sorted([*Path('cp77wb').rglob('*.py'), *Path('tests').rglob('*.py')])
errors = []
for f in files:
    try:
        py_compile.compile(str(f), doraise=True)
    except Exception as exc:
        errors.append((f, exc))
print(f'checked={len(files)} errors={len(errors)}')
for f, exc in errors:
    print(f'{f}: {exc}')
raise SystemExit(1 if errors else 0)
PY

section 'Ruff'
if need ruff; then
  ruff check cp77wb tests || fail=1
fi

section 'Pyright'
if need pyright; then
  pyright cp77wb tests || fail=1
fi

section 'Python unit tests'
python3 -m unittest discover -s tests -v || fail=1

section 'Shell syntax'
find . -type f -name '*.sh' -print -exec bash -n {} \; || fail=1
find . -type f -name '*.sh' -print -exec sh -n {} \; || fail=1

section 'Lua syntax'
if command -v texluac >/dev/null 2>&1; then
  find . -type f -name '*.lua' -print -exec texluac -p {} \; || fail=1
else
  echo 'INFO: texluac not found; Lua syntax check skipped'
fi

section 'JSON/TOML/XML syntax'
python3 - <<'PY' || fail=1
from pathlib import Path
import json
import tomllib
import xml.etree.ElementTree as ET
for f in Path('.').rglob('*.json'):
    json.loads(f.read_text(encoding='utf-8'))
for f in Path('.').rglob('*.toml'):
    with f.open('rb') as stream:
        tomllib.load(stream)
for f in Path('.').rglob('*.csproj'):
    ET.parse(f)
print('OK')
PY

section 'C# compile'
proj='extras/cp77wb_wkit_worker/cp77wb-wkit-worker.csproj'
if need dotnet; then
  dotnet build "$proj" -c Release || fail=1
fi

section 'Merge markers'
if grep -RInE '^(<<<<<<<|=======|>>>>>>>)' \
    --include='*.py' --include='*.cs' --include='*.sh' \
    cp77wb tests extras static-check.sh; then
  fail=1
else
  echo 'none'
fi

if [ "$missing" -ne 0 ]; then
  echo
  echo 'One or more REQUIRED static-analysis tools were missing. This run is NOT a complete validation.' >&2
fi
exit "$fail"
