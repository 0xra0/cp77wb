#!/bin/sh
set -eu

PREFIX=${PREFIX:-"$HOME/.local"}
PYTHON=${PYTHON:-python3}

usage() {
    echo "Usage: ./install.sh [--prefix PATH]" >&2
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --prefix)
            [ "$#" -ge 2 ] || { usage; exit 2; }
            PREFIX=$2
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            usage
            exit 2
            ;;
    esac
done

"$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else "cp77wb requires Python 3.11+")'

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
LIBROOT="$PREFIX/lib/cp77wb-tools"
BINDIR="$PREFIX/bin"

mkdir -p "$LIBROOT" "$BINDIR"
rm -rf "$LIBROOT/cp77wb" "$LIBROOT/extras"
cp -R "$ROOT/cp77wb" "$LIBROOT/cp77wb"
mkdir -p "$LIBROOT/extras"
cp -R "$ROOT/extras/cp77wb_wkit_worker" "$LIBROOT/extras/cp77wb_wkit_worker"

cat > "$BINDIR/cp77wb" <<EOF
#!/bin/sh
set -eu
PYTHON=\${PYTHON:-$PYTHON}
PYTHONPATH="$LIBROOT\${PYTHONPATH:+:\$PYTHONPATH}" exec "\$PYTHON" -m cp77wb "\$@"
EOF

cat > "$BINDIR/cp77wb-mcp" <<EOF
#!/bin/sh
set -eu
PYTHON=\${PYTHON:-$PYTHON}
PYTHONPATH="$LIBROOT\${PYTHONPATH:+:\$PYTHONPATH}" exec "\$PYTHON" -m cp77wb.mcp_server "\$@"
EOF

chmod +x "$BINDIR/cp77wb" "$BINDIR/cp77wb-mcp"

echo "Installed cp77wb to $LIBROOT"
echo "Launchers:"
echo "  $BINDIR/cp77wb"
echo "  $BINDIR/cp77wb-mcp"
echo "WolvenKit worker source: $LIBROOT/extras/cp77wb_wkit_worker"
case ":$PATH:" in
    *":$BINDIR:"*) ;;
    *) echo "Add $BINDIR to PATH if it is not already present." ;;
esac
