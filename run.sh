#!/usr/bin/env bash
# Antigravity Minimal Patcher - one-command launch on Linux
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/MickeyPickey/agy-patcher/main/run.sh | bash
#   curl -fsSL https://raw.githubusercontent.com/MickeyPickey/agy-patcher/main/run.sh | bash -s -- --status

set -eu

REPO="${AGY_REPO:-MickeyPickey/agy-patcher}"
BRANCH="${AGY_BRANCH:-main}"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

URL="https://raw.githubusercontent.com/$REPO/$BRANCH/patcher.py"

echo "Downloading Antigravity Patcher from $REPO..."
curl -fsSL "$URL" -o "$TMP/patcher.py"

# When piped via `curl ... | bash`, stdin (fd 0) is the pipe rather than the terminal.
# Reattach stdin to /dev/tty if available so interactive TUI and prompts work properly.
if [ ! -t 0 ] && [ -e /dev/tty ] && ( : < /dev/tty ) 2>/dev/null; then
    python3 "$TMP/patcher.py" "$@" < /dev/tty
else
    python3 "$TMP/patcher.py" "$@"
fi
