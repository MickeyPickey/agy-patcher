#!/usr/bin/env bash
# Antigravity Patcher - one-command remote installer & launcher on Linux
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/MickeyPickey/agy-patcher/main/run.sh | bash
#   curl -fsSL https://raw.githubusercontent.com/MickeyPickey/agy-patcher/main/run.sh | bash -s -- --status

set -eu

REPO="${AGY_REPO:-MickeyPickey/agy-patcher}"
BRANCH="${AGY_BRANCH:-main}"

INSTALL_DIR="$HOME/.local/share/agy-patcher"
BIN_DIR="$HOME/.local/bin"
INSTALLED_BIN="$BIN_DIR/agy-patcher"
INSTALLED_SCRIPT="$INSTALL_DIR/patcher.py"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

URL="https://raw.githubusercontent.com/$REPO/$BRANCH/patcher.py?cb=$(date +%s)"

is_tty() {
    [ -e /dev/tty ] && ( : < /dev/tty ) 2>/dev/null
}

ask_prompt() {
    local prompt="$1"
    local default_ans="${2:-Y}"
    if ! is_tty; then
        echo "$default_ans"
        return
    fi
    local reply=""
    printf "%s" "$prompt" > /dev/tty
    read -r reply < /dev/tty
    if [ -z "$reply" ]; then
        reply="$default_ans"
    fi
    echo "$reply"
}

ensure_path() {
    case ":${PATH}:" in
        *:"$BIN_DIR":*) ;;
        *)
            export PATH="$BIN_DIR:$PATH"
            for rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
                if [ -f "$rc" ]; then
                    if ! grep -q "export PATH=.*$BIN_DIR" "$rc" 2>/dev/null; then
                        printf "\n# agy-patcher PATH\nexport PATH=\"\$HOME/.local/bin:\$PATH\"\n" >> "$rc"
                    fi
                fi
            done
            ;;
    esac
}

install_local() {
    local src="$1"
    mkdir -p "$INSTALL_DIR" "$BIN_DIR"
    cp -f "$src" "$INSTALLED_SCRIPT"
    chmod 644 "$INSTALLED_SCRIPT"

    cat << 'EOF' > "$INSTALLED_BIN"
#!/usr/bin/env bash
SCRIPT_DIR="$HOME/.local/share/agy-patcher"
if [ ! -f "$SCRIPT_DIR/patcher.py" ]; then
    echo "[-] Error: $SCRIPT_DIR/patcher.py not found." >&2
    exit 1
fi
exec python3 "$SCRIPT_DIR/patcher.py" "$@"
EOF
    chmod +x "$INSTALLED_BIN"
    ensure_path
}

get_version_from_file() {
    local f="$1"
    grep -m1 '__version__' "$f" 2>/dev/null | cut -d'"' -f2 || echo "0.0.0"
}

version_greater() {
    # Returns 0 (true) if $1 > $2
    [ "$1" != "$2" ] && [ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | tail -n1)" = "$1" ]
}

# -----------------------------------------------------------------------------
# Main Execution Flow
# -----------------------------------------------------------------------------

# If arguments were passed or stdin is not a terminal, bypass prompts
if [ "$#" -gt 0 ] || ! is_tty; then
    if [ -x "$INSTALLED_BIN" ] && [ -f "$INSTALLED_SCRIPT" ]; then
        ensure_path
        if is_tty; then
            exec "$INSTALLED_BIN" "$@" < /dev/tty
        else
            exec "$INSTALLED_BIN" "$@"
        fi
    else
        echo "Downloading Antigravity Patcher from $REPO..."
        curl -fsSL "$URL" -o "$TMP/patcher.py"
        if is_tty; then
            exec python3 "$TMP/patcher.py" "$@" < /dev/tty
        else
            exec python3 "$TMP/patcher.py" "$@"
        fi
    fi
fi

# Interactive mode without arguments
if [ -x "$INSTALLED_BIN" ] && [ -f "$INSTALLED_SCRIPT" ]; then
    ensure_path
    local_ver=$(get_version_from_file "$INSTALLED_SCRIPT")
    echo "Checking for updates..."
    if curl -fsSL --connect-timeout 5 "$URL" -o "$TMP/patcher.py" 2>/dev/null; then
        remote_ver=$(get_version_from_file "$TMP/patcher.py")
        if version_greater "$remote_ver" "$local_ver"; then
            ans=$(ask_prompt "[*] New version available (v$local_ver -> v$remote_ver). Update now? [Y/n]: " "Y")
            case "$ans" in
                [yY]|[yY][eE][sS])
                    cp -f "$TMP/patcher.py" "$INSTALLED_SCRIPT"
                    echo "[+] Updated agy-patcher to v$remote_ver."
                    ;;
                *)
                    echo "[*] Continuing with current version v$local_ver."
                    ;;
            esac
        fi
    fi
    exec "$INSTALLED_BIN" "$@" < /dev/tty
else
    # Not installed locally
    ans=$(ask_prompt "[?] agy-patcher is not installed. Would you like to install it to your system? [Y/n]: " "Y")
    case "$ans" in
        [yY]|[yY][eE][sS])
            echo "Downloading and installing agy-patcher..."
            curl -fsSL "$URL" -o "$TMP/patcher.py"
            install_local "$TMP/patcher.py"
            echo "[+] agy-patcher successfully installed to $INSTALLED_BIN"
            echo "[*] You can run it anytime with the command: agy-patcher"
            exec "$INSTALLED_BIN" "$@" < /dev/tty
            ;;
        *)
            echo "[*] Skipping installation. Running temporarily..."
            echo "Downloading Antigravity Patcher from $REPO..."
            curl -fsSL "$URL" -o "$TMP/patcher.py"
            exec python3 "$TMP/patcher.py" "$@" < /dev/tty
            ;;
    esac
fi
