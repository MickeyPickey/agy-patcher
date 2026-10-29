#!/usr/bin/env bash
# Antigravity Minimal Patcher - one-command launch on Linux
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/MickeyPickey/agy-patcher/main/run.sh | bash

set -eu

REPO="${AGY_REPO:-MickeyPickey/agy-patcher}"
BRANCH="${AGY_BRANCH:-main}"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

URL="https://raw.githubusercontent.com/$REPO/$BRANCH/patcher.py"

echo "Downloading Antigravity Patcher from $REPO..."
curl -fsSL "$URL" -o "$TMP/patcher.py"

python3 "$TMP/patcher.py" "$@"