#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
MAKE_BIN=${MAKE_BIN:-make}

cd "$REPO_ROOT"
exec "$MAKE_BIN" local-operational-readiness
