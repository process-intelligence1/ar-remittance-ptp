#!/bin/sh
# Trim an installed Python library folder for the container image (used in the Dockerfile build stage).
#   trim.sh <folder>
# - removes test suites shipped inside libraries (never used at run time)
# - strips debug symbols from compiled libraries (*.so) - the code itself is unchanged
# - pre-compiles .py files with hash-based .pyc: the same input always gives the same bytes, so an
#   unchanged library folder gives the same image layer (shared between image versions in GHCR)
set -eu
dir="$1"
find "$dir" -mindepth 2 -type d \( -name tests -o -name testing \) -prune -exec rm -rf {} +
find "$dir" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$dir" -type f -name "*.so*" -exec strip --strip-unneeded {} + 2>/dev/null || true
python -m compileall -q -j 0 --invalidation-mode unchecked-hash "$dir" > /dev/null
