# v1.0.1 static-analysis fixes

This corrected package addresses the failures reported by a real Ruff/Pyright/.NET run.

## Fixed

- Ruff: 476 reported findings (E701/E702/F401/F841) corrected in source.
- Pyright: 54 reported type errors corrected by explicit Optional narrowing, accurate return types, and covariant Sequence APIs for geometry points.
- C#: 5 CS8801 errors fixed by moving worker protocol/schema constants into `WkitBridge`; the two related unused-symbol warnings were removed.
- Unit-test discovery in `static-check.sh` now explicitly uses `python3 -m unittest discover -s tests -v`.
- `static-check.sh` treats missing `ruff`, `pyright`, or `dotnet` as a failed/incomplete validation instead of silently passing.

## Run the authoritative check

```bash
./static-check.sh .
```

A successful run requires all requested tools to be installed and returns exit status 0 only when every check passes.
