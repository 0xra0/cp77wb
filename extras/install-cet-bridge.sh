#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 /path/to/Cyberpunk2077/bin/x64/plugins/cyber_engine_tweaks/mods" >&2
    exit 2
fi

DEST=$1
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SRC="$ROOT/cp77wb_bridge"
TARGET="$DEST/cp77wb_bridge"

[ -d "$DEST" ] || { echo "CET mods directory does not exist: $DEST" >&2; exit 2; }
mkdir -p "$TARGET/rpc/requests" "$TARGET/rpc/responses"
cp "$SRC/init.lua" "$TARGET/init.lua"
cp "$SRC/README.md" "$TARGET/README.md"
printf '%s\n' "Installed cp77wb_bridge to $TARGET" "RPC directory: $TARGET/rpc"
