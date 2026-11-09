#!/usr/bin/env bash
set -uo pipefail
ROOT="${1:-.}"
cd "$ROOT" || exit 2
fail=0

section() { printf '\n== %s ==\n' "$1"; }

section 'Python py_compile'
python3 - <<'PY' || fail=1
from pathlib import Path
import py_compile
files = sorted(Path('.').rglob('*.py'))
errors=[]
for f in files:
    try: py_compile.compile(str(f), doraise=True)
    except Exception as e: errors.append((f,e))
print(f'checked={len(files)} errors={len(errors)}')
for f,e in errors: print(f'{f}: {e}')
raise SystemExit(bool(errors))
PY

section 'Ruff'
if command -v ruff >/dev/null 2>&1; then
  ruff check . || fail=1
else
  echo 'SKIP: ruff not found'
fi

section 'Pyright'
if command -v pyright >/dev/null 2>&1; then
  pyright cp77wb tests || fail=1
elif command -v npx >/dev/null 2>&1; then
  echo 'SKIP: pyright not installed (install it first; avoiding implicit network download)'
else
  echo 'SKIP: pyright not found'
fi

section 'Python unit tests'
python3 -m unittest discover -v || fail=1

section 'Shell syntax'
while IFS= read -r -d '' f; do
  bash -n "$f" || fail=1
  sh -n "$f" || fail=1
done < <(find . -type f -name '*.sh' -print0)

section 'Lua syntax'
if command -v texluac >/dev/null 2>&1; then
  while IFS= read -r -d '' f; do texluac -p "$f" || fail=1; done < <(find . -type f -name '*.lua' -print0)
else
  echo 'SKIP: texluac not found'
fi

section 'JSON/TOML/XML syntax'
python3 - <<'PY' || fail=1
from pathlib import Path
import json, tomllib, xml.etree.ElementTree as ET
for f in Path('.').rglob('*.json'): json.loads(f.read_text(encoding='utf-8'))
for f in Path('.').rglob('*.toml'): tomllib.loads(f.read_text(encoding='utf-8'))
for f in Path('.').rglob('*.csproj'): ET.parse(f)
print('OK')
PY

section 'C# compile'
proj='extras/cp77wb_wkit_worker/cp77wb-wkit-worker.csproj'
if command -v dotnet >/dev/null 2>&1; then
  dotnet build "$proj" -c Release || fail=1
elif command -v csc >/dev/null 2>&1; then
  echo 'csc found, but this project depends on WolvenKit NuGet references; use dotnet build for authoritative validation.'
  fail=1
elif command -v csharp-ls >/dev/null 2>&1; then
  echo 'csharp-ls found; use your LSP client diagnostics. No dotnet compiler is available for an authoritative project build.'
  fail=1
else
  echo 'SKIP: no dotnet/csc/csharp-ls available'
fi

section 'Merge markers'
if grep -RInE '^(<<<<<<<|=======|>>>>>>>)' --include='*.py' --include='*.cs' --include='*.sh' .; then
  fail=1
else
  echo 'none'
fi

exit "$fail"
