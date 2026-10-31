#!/usr/bin/env python3
"""
Antigravity Lightweight Patcher & Proxy Manager.

Interactive Terminal UI (TUI) and CLI tool to:
1. Bypass regional restrictions ('ineligible' -> 'inexigible').
2. Isolate proxy lookups ('https_proxy' -> 'AGY_U_PROXY').
3. Configure independent AGY_U_PROXY and HTTPS_PROXY environment variables.
"""

import argparse
import ctypes
import os
import platform
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

__version__ = "1.2.0"

# Byte signatures (Exact length match is mandatory)
SIG_REGION_FROM = b"ineligible"   # 10 bytes
SIG_REGION_TO = b"inexigible"     # 10 bytes

SIG_PROXY_FROM = b"https_proxy"    # 11 bytes
SIG_PROXY_TO = b"AGY_U_PROXY"      # 11 bytes

# Known alternative/legacy proxy names
KNOWN_ALT_PROXIES = [
    b"AG_LS_PROXY",                # 11 bytes (used by antigravity-upstream / AGUnlocker)
]

DEFAULT_PROXY_URL = "http://127.0.0.1:10808"
ENV_VAR_AG = "AGY_U_PROXY"
ENV_VAR_HTTPS = "HTTPS_PROXY"

LOCKED_PROCESSES_WIN = [
    "language_server.exe",
    "language_server_windows_x64.exe",
    "agy.exe",
]


class AppCategory:
    DESKTOP = "Antigravity (Desktop)"
    IDE = "Antigravity IDE"
    CLI = "Antigravity CLI (agy)"


ALL_CATEGORIES = [
    AppCategory.DESKTOP,
    AppCategory.IDE,
    AppCategory.CLI,
]


def is_windows() -> bool:
    return platform.system() == "Windows"


# ============================================================================
# ANSI Color & Console Support
# ============================================================================

def enable_virtual_terminal():
    """Enable VT100 / ANSI escape processing on Windows consoles and set UTF-8 codepage."""
    if is_windows():
        try:
            kernel32 = ctypes.windll.kernel32
            # Set console codepage to UTF-8
            kernel32.SetConsoleOutputCP(65001)
            kernel32.SetConsoleCP(65001)

            # Try GetStdHandle first
            for handle_id in (-11, -12):
                h = kernel32.GetStdHandle(handle_id)
                mode = ctypes.c_ulong()
                if kernel32.GetConsoleMode(h, ctypes.byref(mode)):
                    kernel32.SetConsoleMode(h, mode.value | 0x0004 | 0x0008)

            # Also open CONOUT$ directly to ensure mode is applied
            h_conout = kernel32.CreateFileW("CONOUT$", 0xC0000000, 3, None, 3, 0, None)
            if h_conout != -1:
                mode = ctypes.c_ulong()
                if kernel32.GetConsoleMode(h_conout, ctypes.byref(mode)):
                    kernel32.SetConsoleMode(h_conout, mode.value | 0x0004 | 0x0008)
                kernel32.CloseHandle(h_conout)
        except Exception:
            pass


if is_windows():
    class COORD(ctypes.Structure):
        _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

    class CONSOLE_CURSOR_INFO(ctypes.Structure):
        _fields_ = [("dwSize", ctypes.c_ulong), ("bVisible", ctypes.c_bool)]


def set_cursor_visible(visible: bool):
    """Show or hide console cursor to eliminate visual cursor flicker."""
    if is_windows():
        try:
            kernel32 = ctypes.windll.kernel32
            h = kernel32.GetStdHandle(-11)
            cci = CONSOLE_CURSOR_INFO()
            if kernel32.GetConsoleCursorInfo(h, ctypes.byref(cci)):
                cci.bVisible = visible
                kernel32.SetConsoleCursorInfo(h, ctypes.byref(cci))
                return
        except Exception:
            pass
    sys.stdout.write("\033[?25h" if visible else "\033[?25l")
    sys.stdout.flush()


def move_cursor_home():
    """Move cursor to top-left (0,0) without clearing screen buffer (no flicker)."""
    if is_windows():
        try:
            kernel32 = ctypes.windll.kernel32
            h = kernel32.GetStdHandle(-11)
            if kernel32.SetConsoleCursorPosition(h, COORD(0, 0)):
                return
        except Exception:
            pass
    sys.stdout.write("\033[H")
    sys.stdout.flush()


def clear_screen():
    """Clear terminal screen once (at startup or after text input)."""
    if is_windows():
        os.system("cls")
    else:
        sys.stdout.write("\033[H\033[2J\033[3J")
        sys.stdout.flush()


enable_virtual_terminal()


class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GRAY = "\033[90m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

    # Unified status badges (Clean ASCII - no emojis or unicode glyphs)
    BADGE_ENABLED = f"{GREEN}[Enabled]{RESET}"
    BADGE_DISABLED = f"{GRAY}[Disabled]{RESET}"
    BADGE_PARTIAL = f"{YELLOW}[Partial]{RESET}"
    BADGE_SCANNING = f"{YELLOW}[Scanning]{RESET}"
    BADGE_NOT_FOUND = f"{RED}[Not Found]{RESET}"
    BADGE_ERROR = f"{RED}[Error]{RESET}"


SPINNER_FRAMES = ("|", "/", "-", "\\")


def _format_size(num_bytes: int) -> str:
    """Format byte size into human-readable string (e.g., 212.8 MB)."""
    val = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if val < 1024.0 or unit == "GB":
            return f"{int(val)} B" if unit == "B" else f"{val:.1f} {unit}"
        val /= 1024.0
    return f"{val:.1f} GB"


class CliSpinner:
    """Lightweight animated ASCII spinner for CLI operations."""
    def __init__(self, initial_msg: str = "Working..."):
        self.msg = initial_msg
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._is_tty = sys.stdout.isatty()
        self._lock = threading.Lock()

    def update(self, msg: str) -> None:
        with self._lock:
            self.msg = msg

    def _spin(self) -> None:
        idx = 0
        while not self._stop_event.is_set():
            frame = SPINNER_FRAMES[idx % len(SPINNER_FRAMES)]
            with self._lock:
                cur_msg = self.msg
            sys.stdout.write(f"\r  {Colors.CYAN}[{frame}]{Colors.RESET} {cur_msg}\033[K")
            sys.stdout.flush()
            idx += 1
            self._stop_event.wait(0.08)

    def start(self) -> "CliSpinner":
        if self._is_tty:
            set_cursor_visible(False)
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()
        return self

    def finish(self, done_msg: Optional[str] = None, ok: bool = True) -> None:
        if not self._is_tty:
            return
        self._stop_event.set()
        if self._thread:
            self._thread.join()
        if done_msg:
            badge = f"{Colors.GREEN}[OK]{Colors.RESET}" if ok else f"{Colors.RED}[!]{Colors.RESET}"
            sys.stdout.write(f"\r  {badge} {done_msg}\033[K")
            sys.stdout.flush()
            time.sleep(0.5)
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()
        set_cursor_visible(True)


# ============================================================================
# Keyboard Input Handler (Windows msvcrt / Linux termios)
# ============================================================================

def ensure_interactive_stdin() -> bool:
    """Ensure sys.stdin is connected to an interactive terminal (reopens /dev/tty if piped)."""
    if sys.stdin.isatty():
        return True
    if not is_windows():
        try:
            sys.stdin = open("/dev/tty", "r", encoding="utf-8", errors="ignore")
            return sys.stdin.isatty()
        except Exception:
            return False
    return False


class KeyReader:
    def __init__(self):
        self.is_win = is_windows()
        if not self.is_win:
            import select
            import termios
            import tty
            self.select = select
            self.termios = termios
            self.tty = tty
            ensure_interactive_stdin()

    def read_key(self) -> str:
        """Read a single key or key sequence (handles arrow keys)."""
        if self.is_win:
            import msvcrt
            ch = msvcrt.getch()
            if ch in (b"\x00", b"\xe0"):
                sub = msvcrt.getch()
                if sub == b"H":
                    return "UP"
                elif sub == b"P":
                    return "DOWN"
                elif sub == b"K":
                    return "LEFT"
                elif sub == b"M":
                    return "RIGHT"
                return "SPECIAL"
            elif ch == b"\r":
                return "ENTER"
            elif ch == b" ":
                return "SPACE"
            elif ch in (b"\x1b", b"q", b"Q"):
                return "QUIT"
            elif ch == b"\x03":
                raise KeyboardInterrupt
            try:
                return ch.decode("utf-8", errors="ignore")
            except Exception:
                return ""
        else:
            fd = sys.stdin.fileno()
            old_settings = self.termios.tcgetattr(fd)
            try:
                self.tty.setcbreak(fd)
                b = os.read(fd, 1)
                if not b:
                    return "QUIT"
                ch = b.decode("utf-8", errors="ignore")
                if ch == "\x1b":
                    # Non-blocking check on raw fd for arrow key escape sequence vs standalone ESC.
                    # Must use os.read(fd, ...) rather than sys.stdin.read(1) because Python's
                    # buffered stdin slurps the entire multi-byte sequence from the kernel buffer at once,
                    # leaving fd empty for select().
                    if self.select.select([fd], [], [], 0.05)[0]:
                        seq1 = os.read(fd, 1).decode("utf-8", errors="ignore")
                        if seq1 in ("[", "O") and self.select.select([fd], [], [], 0.05)[0]:
                            seq2 = os.read(fd, 1).decode("utf-8", errors="ignore")
                            if seq2 == "A":
                                return "UP"
                            elif seq2 == "B":
                                return "DOWN"
                            elif seq2 == "C":
                                return "RIGHT"
                            elif seq2 == "D":
                                return "LEFT"
                        # Drain any remaining bytes of an unhandled escape sequence (e.g. PgUp/PgDn)
                        while self.select.select([fd], [], [], 0.01)[0]:
                            os.read(fd, 1)
                        return "SPECIAL"
                    return "QUIT"
                elif ch in ("\n", "\r"):
                    return "ENTER"
                elif ch == " ":
                    return "SPACE"
                elif ch in ("q", "Q"):
                    return "QUIT"
                elif ch == "\x03":
                    raise KeyboardInterrupt
                return ch
            finally:
                self.termios.tcsetattr(fd, self.termios.TCSADRAIN, old_settings)


# ============================================================================
# Environment Variable Management
# ============================================================================

def _get_linux_home_dirs() -> List[Path]:
    """Return active user home directory plus Termux/PRoot shared home if present."""
    homes: List[Path] = [Path.home()]
    for extra in (Path("/data/data/com.termux/files/home"), Path("/root")):
        try:
            if extra.exists() and extra.is_dir() and extra not in homes:
                homes.append(extra)
        except Exception:
            pass
    return homes


def _ensure_shell_sources_env_conf(home: Path) -> None:
    """Ensure shell startup files load ~/.config/environment.d/agy-patcher.conf on non-systemd setups."""
    marker = "# agy-patcher environment loader"
    snippet = (
        f"\n{marker}\n"
        'if [ -f "$HOME/.config/environment.d/agy-patcher.conf" ]; then\n'
        '    set -a; . "$HOME/.config/environment.d/agy-patcher.conf"; set +a\n'
        "fi\n"
    )
    for rc_name in (".bashrc", ".zshrc"):
        rc_path = home / rc_name
        try:
            if rc_path.is_file() and not rc_path.is_symlink():
                content = rc_path.read_text(encoding="utf-8", errors="ignore")
                if "agy-patcher.conf" not in content:
                    rc_path.write_text(content.rstrip() + "\n" + snippet, encoding="utf-8")
        except Exception:
            pass


def set_env_var(name: str, value: Optional[str], progress_cb: Optional[Callable[[str], None]] = None) -> bool:
    """Set or remove persistent user environment variable across Windows/Linux."""
    if progress_cb:
        action = "Removing" if value is None else "Setting"
        progress_cb(f"{action} {name} in user environment...")

    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value

    if is_windows():
        import winreg

        reg_path = r"Environment"
        try:
            access = winreg.KEY_SET_VALUE if value is not None else (winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE)
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, access) as key:
                if value is None:
                    try:
                        winreg.DeleteValue(key, name)
                    except FileNotFoundError:
                        pass
                else:
                    winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)

            if progress_cb:
                progress_cb(f"Broadcasting environment update ({name})...")

            # Broadcast WM_SETTINGCHANGE
            HWND_BROADCAST = 0xFFFF
            WM_SETTINGCHANGE = 0x001A
            SMTO_ABORTIFHUNG = 0x0002
            result = ctypes.c_ulong()
            ctypes.windll.user32.SendMessageTimeoutW(
                HWND_BROADCAST,
                WM_SETTINGCHANGE,
                0,
                "Environment",
                SMTO_ABORTIFHUNG,
                3000,
                ctypes.byref(result)
            )
            return True
        except Exception:
            if progress_cb:
                progress_cb(f"Applying {name} via PowerShell fallback...")
            # Fallback to PowerShell
            ps_cmd = (
                f"[Environment]::SetEnvironmentVariable('{name}', $null, 'User')"
                if value is None
                else f"[Environment]::SetEnvironmentVariable('{name}', '{value}', 'User')"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False
            )
            return res.returncode == 0
    else:
        # Linux: write drop-in to ~/.config/environment.d, hook shell rc, and apply via systemctl if available
        try:
            for home in _get_linux_home_dirs():
                env_d = home / ".config" / "environment.d"
                conf_file = env_d / "agy-patcher.conf"
                if value is None:
                    if conf_file.exists():
                        lines = conf_file.read_text(encoding="utf-8").splitlines()
                        new_lines = [l for l in lines if not l.startswith(f"{name}=")]
                        if new_lines:
                            conf_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
                        else:
                            conf_file.unlink()
                else:
                    env_d.mkdir(parents=True, exist_ok=True)
                    existing = ""
                    if conf_file.exists():
                        lines = [l for l in conf_file.read_text(encoding="utf-8").splitlines() if not l.startswith(f"{name}=")]
                        existing = "\n".join(lines).strip()
                    new_content = f"{name}={value}\n"
                    if existing:
                        new_content = existing + "\n" + new_content
                    conf_file.write_text(new_content, encoding="utf-8")
                    _ensure_shell_sources_env_conf(home)

            if progress_cb:
                progress_cb(f"Syncing {name} with systemd user environment...")
            try:
                if value is None:
                    subprocess.run(
                        ["systemctl", "--user", "unset-environment", name],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False
                    )
                else:
                    subprocess.run(
                        ["systemctl", "--user", "set-environment", f"{name}={value}"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False
                    )
            except FileNotFoundError:
                pass
            return True
        except Exception:
            return False


def get_current_env_var(name: str) -> Optional[str]:
    """Retrieve the current value of the user environment variable."""
    if is_windows():
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_READ) as key:
                val, _ = winreg.QueryValueEx(key, name)
                return str(val).strip()
        except FileNotFoundError:
            return None
        except Exception:
            return os.environ.get(name)
    else:
        for home in _get_linux_home_dirs():
            conf_file = home / ".config" / "environment.d" / "agy-patcher.conf"
            if conf_file.is_file():
                try:
                    for line in conf_file.read_text(encoding="utf-8").splitlines():
                        if line.startswith(f"{name}="):
                            return line.split("=", 1)[1].strip()
                except Exception:
                    pass
        return os.environ.get(name)


# ============================================================================
# Binary Discovery & Classification
# ============================================================================

def classify_binary(path: Path) -> str:
    """Classify binary path into Desktop, IDE, or CLI."""
    path_str = str(path).lower()
    name = path.name.lower()
    if name in ("agy.exe", "agy") or "\\agy\\" in path_str or "/agy/" in path_str:
        return AppCategory.CLI
    if "antigravity ide" in path_str or "extensions" in path_str:
        return AppCategory.IDE
    return AppCategory.DESKTOP


def get_candidate_install_dirs() -> List[Path]:
    """Return common installation directories for Antigravity on current OS."""
    candidates: List[Path] = []

    if is_windows():
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        prog_files = os.environ.get("PROGRAMFILES", "")
        prog_files_x86 = os.environ.get("PROGRAMFILES(X86)", "")

        if local_appdata:
            la = Path(local_appdata)
            candidates.extend([
                la / "Programs" / "Antigravity",
                la / "Programs" / "Antigravity IDE",
                la / "Antigravity",
                la / "Antigravity IDE",
                la / "agy" / "bin",
                la / "agy",
            ])
        if prog_files:
            pf = Path(prog_files)
            candidates.extend([
                pf / "Antigravity",
                pf / "Antigravity IDE",
            ])
        if prog_files_x86:
            pfx = Path(prog_files_x86)
            candidates.extend([
                pfx / "Antigravity",
                pfx / "Antigravity IDE",
            ])
    else:
        bases = ["/opt", "/usr/share", "/usr/lib", "/usr/local/share"]
        names = ["Antigravity", "Antigravity IDE", "antigravity", "antigravity-ide"]
        for base in bases:
            b = Path(base)
            for n in names:
                candidates.append(b / n)

        homes = _get_linux_home_dirs()
        # Also include PRoot distro rootfs homes when running from native Termux
        proot_rootfs = Path("/data/data/com.termux/files/usr/var/lib/proot-distro/installed-rootfs")
        try:
            if proot_rootfs.is_dir():
                for distro_dir in proot_rootfs.iterdir():
                    root_home = distro_dir / "root"
                    if root_home.is_dir() and root_home not in homes:
                        homes.append(root_home)
        except Exception:
            pass

        for home in homes:
            candidates.extend([
                home / ".local" / "share" / "Antigravity",
                home / ".local" / "share" / "Antigravity IDE",
                home / "Antigravity",
                home / "Antigravity IDE",
                home / ".local" / "bin",
                home / ".agy" / "bin",
                home / ".agy",
                home / ".local" / "share" / "agy" / "bin",
            ])

    return [p for p in candidates if p.exists() and p.is_dir()]


def _is_candidate_binary(path: Path) -> bool:
    """Return True if path is a real compiled target binary (ignoring shell wrapper scripts)."""
    if not _is_candidate_filename(path.name):
        return False
    try:
        st = path.stat()
        # Skip tiny shell wrapper scripts (< 64 KB) or scripts starting with '#!'
        if st.st_size < 65536:
            with path.open("rb") as f:
                head = f.read(2)
            if head == b"#!" or st.st_size < 4096:
                return False
    except Exception:
        return False
    return True


def find_target_binaries(root: Optional[Path] = None) -> List[Path]:
    """Find all language server and CLI binaries in given root or standard dirs."""
    roots = [root] if root else get_candidate_install_dirs()
    targets: Set[Path] = set()

    for r in roots:
        if r.is_file():
            if _is_candidate_binary(r):
                targets.add(r.resolve())
            continue

        search_dirs = [
            r,
            r / "resources" / "bin",
            r / "resources" / "app" / "extensions" / "antigravity" / "bin",
            r / "bin",
        ]

        for d in search_dirs:
            if not d.is_dir():
                continue
            for item in d.iterdir():
                if item.is_file() and _is_candidate_binary(item):
                    targets.add(item.resolve())

    return sorted(list(targets))


def _is_candidate_filename(name: str) -> bool:
    lower = name.lower()
    if lower.endswith((".agtmp", ".tmp", ".bak", ".log", ".json", ".md", ".agold", ".old")):
        return False
    if lower.startswith("language_server"):
        return True
    if lower in ("agy.exe", "agy"):
        return True
    return False


def get_categorized_targets(root: Optional[Path] = None) -> Dict[str, List[Path]]:
    """Group all found binaries by application category."""
    raw_targets = find_target_binaries(root)
    grouped: Dict[str, List[Path]] = {cat: [] for cat in ALL_CATEGORIES}
    for t in raw_targets:
        cat = classify_binary(t)
        grouped[cat].append(t)
    return grouped


# ============================================================================
# Process Management
# ============================================================================

def kill_locking_processes():
    """Terminate running language server / CLI processes to allow file modification."""
    if is_windows():
        for proc in LOCKED_PROCESSES_WIN:
            subprocess.run(
                ["taskkill", "/F", "/IM", proc],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False
            )
    else:
        for pat in ["language_server", "/agy"]:
            subprocess.run(
                ["pkill", "-f", pat],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False
            )
    time.sleep(0.5)


# ============================================================================
# Patch Operations
# ============================================================================

class PatchResult:
    def __init__(self, path: Path):
        self.path = path
        self.region_replaced = 0
        self.proxy_replaced = 0
        self.already_patched = False
        self.error: Optional[str] = None


def detect_proxy_variable(data: bytes) -> Tuple[Optional[bytes], str]:
    """
    Detect the proxy variable name configured in the binary.
    Returns (variable_name_bytes, kind) where kind is:
      - 'ours': Matches SIG_PROXY_TO (AGY_U_PROXY)
      - 'stock': Matches SIG_PROXY_FROM (https_proxy)
      - 'foreign': Matches a known or dynamically detected 11-byte proxy variable
      - 'unknown': Neither found nor detected
    """
    if SIG_PROXY_TO in data:
        return SIG_PROXY_TO, "ours"
    if SIG_PROXY_FROM in data:
        return SIG_PROXY_FROM, "stock"

    # Known alternative/legacy proxy names
    for alt in KNOWN_ALT_PROXIES:
        if alt in data:
            return alt, "foreign"

    # Dynamic heuristic detection:
    # In Go httpproxy, getEnvAny("HTTPS_PROXY", "https_proxy") compiles into
    # a literal table where the lowercase proxy name precedes HTTPS_PROXY.
    candidates = re.findall(rb"([A-Za-z0-9_]{11})HTTPS_PROXY", data)
    for c in candidates:
        if c == b"HTTPS_PROXY":
            continue
        # Validate that candidate looks like a proxy variable or occurs exactly 2 times
        cnt = data.count(c)
        if cnt == 2 or c.upper().endswith(b"PROXY"):
            return c, "foreign"

    return None, "unknown"


def patch_file(
    path: Path,
    unpatch: bool = False,
    progress_cb: Optional[Callable[[str], None]] = None
) -> PatchResult:
    """Perform in-place byte replacement on a binary file."""
    res = PatchResult(path)

    try:
        sz_str = _format_size(path.stat().st_size)
        if progress_cb:
            progress_cb(f"Reading {path.name} ({sz_str})...")
        data = path.read_bytes()
    except Exception as e:
        res.error = f"Failed to read file: {e}"
        return res

    if progress_cb:
        progress_cb(f"Scanning signatures in {path.name} ({sz_str})...")

    new_data = data

    # 1. Handle Region patch (ineligible <-> inexigible)
    if unpatch:
        reg_count = new_data.count(SIG_REGION_TO)
        if reg_count > 0:
            if progress_cb:
                progress_cb(f"Reverting region signature in {path.name}...")
            new_data = new_data.replace(SIG_REGION_TO, SIG_REGION_FROM)
            res.region_replaced = reg_count
    else:
        reg_count = new_data.count(SIG_REGION_FROM)
        if reg_count > 0:
            if progress_cb:
                progress_cb(f"Patching region signature in {path.name}...")
            new_data = new_data.replace(SIG_REGION_FROM, SIG_REGION_TO)
            res.region_replaced = reg_count

    # 2. Handle Proxy patch
    proxy_sig, proxy_kind = detect_proxy_variable(new_data)

    if unpatch:
        # Revert proxy back to stock 'https_proxy'
        if proxy_kind in ("ours", "foreign") and proxy_sig:
            prx_count = new_data.count(proxy_sig)
            if prx_count > 0:
                if progress_cb:
                    progress_cb(f"Reverting proxy signature in {path.name}...")
                new_data = new_data.replace(proxy_sig, SIG_PROXY_FROM)
                res.proxy_replaced = prx_count
    else:
        # Apply proxy patch: migrate stock or foreign -> 'AGY_U_PROXY'
        if proxy_kind in ("stock", "foreign") and proxy_sig:
            prx_count = new_data.count(proxy_sig)
            if prx_count > 0:
                if progress_cb:
                    progress_cb(f"Patching proxy signature in {path.name}...")
                new_data = new_data.replace(proxy_sig, SIG_PROXY_TO)
                res.proxy_replaced = prx_count

    # Check if any modifications were made
    if res.region_replaced == 0 and res.proxy_replaced == 0:
        if unpatch:
            if SIG_REGION_FROM in data or SIG_PROXY_FROM in data:
                res.already_patched = True
                return res
        else:
            if SIG_REGION_TO in data and SIG_PROXY_TO in data:
                res.already_patched = True
                return res

        res.error = "Signatures not found or unrecognized"
        return res

    assert len(new_data) == len(data), "Critical error: File size modified after replacement!"

    tmp_path = path.with_suffix(f".{os.getpid()}.agtmp")
    try:
        if progress_cb:
            progress_cb(f"Writing temporary binary for {path.name} ({sz_str})...")
        tmp_path.write_bytes(new_data)
        if not is_windows():
            mode = path.stat().st_mode
            tmp_path.chmod(mode)

        if progress_cb:
            progress_cb(f"Replacing {path.name} on disk...")

        try:
            tmp_path.replace(path)
        except (PermissionError, OSError):
            # Attempt non-disruptive rename dance on Windows before resorting to process kill
            replaced = False
            old_path = path.with_suffix(f".{os.getpid()}.agold")
            if is_windows():
                try:
                    path.rename(old_path)
                    tmp_path.replace(path)
                    replaced = True
                except Exception:
                    pass

            if not replaced:
                if progress_cb:
                    progress_cb(f"Stopping locking processes for {path.name}...")
                kill_locking_processes()
                time.sleep(0.3)
                if progress_cb:
                    progress_cb(f"Replacing {path.name} on disk...")
                tmp_path.replace(path)

            if old_path.exists():
                try:
                    old_path.unlink(missing_ok=True)
                except Exception:
                    pass
    except Exception as e:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        res.error = f"Write error: {e}"

    return res


def get_binary_status(path: Path, progress_cb: Optional[Callable[[str], None]] = None) -> dict:
    """Read binary and return structured patch status."""
    try:
        if progress_cb:
            sz_str = _format_size(path.stat().st_size)
            progress_cb(f"Inspecting {path.name} ({sz_str})...")
        content = path.read_bytes()
        if progress_cb:
            progress_cb(f"Checking signatures in {path.name}...")
        has_reg_mod = SIG_REGION_TO in content
        has_reg_orig = SIG_REGION_FROM in content

        proxy_sig, proxy_kind = detect_proxy_variable(content)
        has_prx_mod = (proxy_kind == "ours")
        has_prx_orig = (proxy_kind == "stock")
        has_prx_foreign = (proxy_kind == "foreign")

        is_patched = has_reg_mod and has_prx_mod
        is_unpatched = has_reg_orig and has_prx_orig
        is_partial = not is_patched and not is_unpatched and (has_reg_mod or has_prx_mod or has_prx_foreign)

        reg_text = f"{Colors.GREEN}Unlocked{Colors.RESET}" if has_reg_mod else (f"{Colors.GRAY}Blocked{Colors.RESET}" if has_reg_orig else "Unknown")

        if has_prx_mod:
            prx_text = f"{Colors.GREEN}{ENV_VAR_AG}{Colors.RESET}"
        elif has_prx_orig:
            prx_text = f"{Colors.GRAY}https_proxy{Colors.RESET}"
        elif has_prx_foreign and proxy_sig:
            sig_name = proxy_sig.decode(errors="ignore")
            prx_text = f"{Colors.YELLOW}{sig_name} (foreign){Colors.RESET}"
        else:
            prx_text = "Unknown"

        if is_patched:
            badge = Colors.BADGE_ENABLED
        elif is_unpatched:
            badge = Colors.BADGE_DISABLED
        elif is_partial:
            badge = Colors.BADGE_PARTIAL
        else:
            badge = Colors.BADGE_DISABLED

        return {
            "badge": badge,
            "is_patched": is_patched,
            "region": reg_text,
            "proxy": prx_text,
            "proxy_sig": proxy_sig.decode(errors="ignore") if proxy_sig else None,
            "proxy_kind": proxy_kind,
            "error": None
        }
    except Exception as e:
        return {
            "badge": Colors.BADGE_ERROR,
            "is_patched": False,
            "region": "Error",
            "proxy": "Error",
            "proxy_sig": None,
            "proxy_kind": "error",
            "error": str(e)
        }


# ============================================================================
# Interactive Terminal User Interface (TUI)
# ============================================================================

class AppState:
    """In-memory cache for environment variables and binary inspection results."""
    def __init__(self, root_path: Optional[Path] = None, auto_refresh: bool = True):
        self.root_path = root_path
        self.ag_env = None
        self.https_env = None
        self.ag_saved_url = DEFAULT_PROXY_URL
        self.https_saved_url = DEFAULT_PROXY_URL
        self.apps: Dict[str, dict] = {
            cat: {"target": None, "status": None, "scanning": not auto_refresh}
            for cat in ALL_CATEGORIES
        }
        self.custom_paths: Dict[str, Path] = {}
        if auto_refresh:
            self.refresh()

    def refresh(self, progress_cb: Optional[Callable[[str], None]] = None):
        """Perform disk scan and registry queries only when explicitly requested."""
        if progress_cb:
            progress_cb("Reading proxy environment variables...")
        self.ag_env = get_current_env_var(ENV_VAR_AG)
        self.https_env = get_current_env_var(ENV_VAR_HTTPS)
        if self.ag_env:
            self.ag_saved_url = self.ag_env
        if self.https_env:
            self.https_saved_url = self.https_env

        if progress_cb:
            progress_cb("Scanning installation directories for binaries...")
        grouped = get_categorized_targets(self.root_path)
        for cat in ALL_CATEGORIES:
            targets = grouped.get(cat, [])
            if not targets and cat in self.custom_paths:
                cp = self.custom_paths[cat]
                if cp and cp.exists():
                    targets = [cp]
            if targets:
                t = targets[0]
                st = get_binary_status(t, progress_cb=progress_cb)
                self.apps[cat] = {"target": t, "status": st, "scanning": False}
            else:
                self.apps[cat] = {"target": None, "status": None, "scanning": False}


def run_interactive_tui(root_path: Optional[Path] = None):
    """Full-featured interactive TUI engine with in-memory caching and zero-flicker redraw."""
    if not is_windows() and not ensure_interactive_stdin():
        print("[!] Interactive terminal (/dev/tty) is not available. Run with --status or --patch for CLI mode.")
        return

    reader = KeyReader()
    state = AppState(root_path, auto_refresh=False)

    items = [
        {"type": "proxy_ag", "name": ENV_VAR_AG},
        {"type": "proxy_https", "name": ENV_VAR_HTTPS},
        {"type": "app", "category": AppCategory.DESKTOP},
        {"type": "app", "category": AppCategory.IDE},
        {"type": "app", "category": AppCategory.CLI},
        {"type": "patch_all", "title": "Patch All Detected Applications"},
        {"type": "revert_all", "title": "Revert All Detected Applications"},
        {"type": "refresh", "title": "Refresh Status"},
        {"type": "exit", "title": "Exit"},
    ]

    selected_idx = 0

    def render_frame(activity_line: str = "") -> None:
        """Render the TUI frame at top-left (0,0) with an optional activity footer line."""
        buf = [
            "=" * 72,
            f"               {Colors.BOLD}Antigravity Patcher & Proxy Manager v{__version__}{Colors.RESET}",
            "=" * 72,
            "",
            f"  {Colors.BOLD}--- [ PROXY ENVIRONMENT VARIABLES ] ---{Colors.RESET}",
        ]

        # 0: AGY_U_PROXY
        is_cur = (selected_idx == 0)
        c_str = f"{Colors.CYAN}>{Colors.RESET} " if is_cur else "  "
        ag_active = bool(state.ag_env)
        badge = Colors.BADGE_ENABLED if ag_active else Colors.BADGE_DISABLED
        t_col = f"{Colors.BOLD}{Colors.WHITE}" if is_cur else Colors.WHITE
        ag_detail = f"  {state.ag_env}" if ag_active else ""
        buf.append(f"{c_str}{t_col}{ENV_VAR_AG:<23}{Colors.RESET}: {badge}{ag_detail}")

        # 1: HTTPS_PROXY
        is_cur = (selected_idx == 1)
        c_str = f"{Colors.CYAN}>{Colors.RESET} " if is_cur else "  "
        https_active = bool(state.https_env)
        badge = Colors.BADGE_ENABLED if https_active else Colors.BADGE_DISABLED
        t_col = f"{Colors.BOLD}{Colors.WHITE}" if is_cur else Colors.WHITE
        https_detail = f"  {state.https_env}" if https_active else ""
        buf.append(f"{c_str}{t_col}{ENV_VAR_HTTPS:<23}{Colors.RESET}: {badge}{https_detail}")

        buf.append("")
        buf.append(f"  {Colors.BOLD}--- [ BINARY PATCHES ] ---{Colors.RESET}")

        # Apps: 2 (Desktop), 3 (IDE), 4 (CLI)
        for idx, cat in enumerate([AppCategory.DESKTOP, AppCategory.IDE, AppCategory.CLI], start=2):
            is_cur = (selected_idx == idx)
            c_str = f"{Colors.CYAN}>{Colors.RESET} " if is_cur else "  "
            t_col = f"{Colors.BOLD}{Colors.WHITE}" if is_cur else Colors.WHITE
            app_info = state.apps.get(cat)
            if app_info and app_info.get("scanning"):
                buf.append(f"{c_str}{t_col}{cat:<23}{Colors.RESET}: {Colors.BADGE_SCANNING}")
            elif not app_info or not app_info["target"]:
                buf.append(f"{c_str}{t_col}{cat:<23}{Colors.RESET}: {Colors.BADGE_NOT_FOUND}")
            else:
                st = app_info["status"]
                b_badge = st["badge"] if st else Colors.BADGE_ERROR
                sub_info = f"  Reg:{st['region']} {Colors.GRAY}|{Colors.RESET} Prx:{st['proxy']}" if st else ""
                target_path = str(app_info["target"])
                buf.append(f"{c_str}{t_col}{cat:<23}{Colors.RESET}: {b_badge}{sub_info}  {Colors.GRAY}{target_path}{Colors.RESET}")

        buf.append("")
        buf.append(f"  {Colors.BOLD}--- [ ACTIONS ] ---{Colors.RESET}")
        for idx in [5, 6, 7, 8]:
            item = items[idx]
            is_cur = (selected_idx == idx)
            c_str = f"{Colors.CYAN}>{Colors.RESET} " if is_cur else "  "
            t_col = f"{Colors.CYAN}{Colors.BOLD}" if is_cur else Colors.WHITE
            buf.append(f"{c_str}{t_col}{item['title']}{Colors.RESET}")

        # Dedicated status/activity footer slot above keybind hints
        buf.append(activity_line)
        buf.append("-" * 72)
        buf.append("  [Up/Down] Navigate  |  [Space/Enter] Select  |  [Q] Exit")

        move_cursor_home()
        out_str = "\n".join([line + "\033[K" for line in buf]) + "\n"
        sys.stdout.write(out_str)
        sys.stdout.flush()

    def run_with_spinner(
        initial_msg: str,
        task_fn: Callable[[Callable[[str], None]], Optional[Tuple[bool, str]]]
    ) -> None:
        """Execute task_fn in a worker thread while animating the footer spinner, then flash completion."""
        step_lock = threading.Lock()
        current_step = [initial_msg]
        outcome: List[Optional[Tuple[bool, str]]] = [None]

        def update_step(msg: str) -> None:
            with step_lock:
                current_step[0] = msg

        def worker() -> None:
            try:
                outcome[0] = task_fn(update_step)
            except Exception as exc:
                outcome[0] = (False, f"Error: {exc}")

        t = threading.Thread(target=worker, daemon=True)
        t.start()

        frame_idx = 0
        while t.is_alive():
            frame = SPINNER_FRAMES[frame_idx % len(SPINNER_FRAMES)]
            with step_lock:
                msg = current_step[0]
            render_frame(f"  {Colors.CYAN}[{frame}]{Colors.RESET} {msg}")
            frame_idx += 1
            t.join(timeout=0.08)

        res = outcome[0]
        if res is not None:
            ok, done_msg = res
            badge = f"{Colors.GREEN}[OK]{Colors.RESET}" if ok else f"{Colors.RED}[!]{Colors.RESET}"
            render_frame(f"  {badge} {done_msg}")
            time.sleep(0.5)

    # Clear screen ONCE at startup, hide cursor, and immediately render frame while scanning
    clear_screen()
    set_cursor_visible(False)

    try:
        run_with_spinner(
            "Initializing and scanning binaries...",
            lambda cb: (state.refresh(progress_cb=cb), (True, "Status scan complete."))[1]
        )

        while True:
            render_frame()

            # Read key
            try:
                key = reader.read_key()
            except KeyboardInterrupt:
                break

            if key in ("UP", "w", "W", "k", "K"):
                selected_idx = (selected_idx - 1) % len(items)
            elif key in ("DOWN", "s", "S", "j", "J"):
                selected_idx = (selected_idx + 1) % len(items)
            elif key in ("QUIT", "q", "Q"):
                break
            elif key in ("SPACE", "ENTER"):
                curr = items[selected_idx]
                t = curr["type"]

                if t == "proxy_ag":
                    if state.ag_env:
                        def _disable_ag(cb: Callable[[str], None]) -> Tuple[bool, str]:
                            ok = set_env_var(ENV_VAR_AG, None, progress_cb=cb)
                            state.refresh(progress_cb=cb)
                            return (ok, f"Disabled {ENV_VAR_AG}." if ok else f"Failed to disable {ENV_VAR_AG}.")
                        run_with_spinner(f"Disabling {ENV_VAR_AG}...", _disable_ag)
                    else:
                        set_cursor_visible(True)
                        print(f"\nEnter proxy address for {ENV_VAR_AG} [default: {state.ag_saved_url}]: ", end="", flush=True)
                        target_url: Optional[str] = None
                        try:
                            val = input().strip()
                            target_url = val if val else state.ag_saved_url
                        except Exception:
                            pass
                        set_cursor_visible(False)
                        clear_screen()
                        if target_url:
                            def _enable_ag(cb: Callable[[str], None]) -> Tuple[bool, str]:
                                ok = set_env_var(ENV_VAR_AG, target_url, progress_cb=cb)
                                state.refresh(progress_cb=cb)
                                return (ok, f"Set {ENV_VAR_AG} = {target_url}" if ok else f"Failed to set {ENV_VAR_AG}.")
                            run_with_spinner(f"Setting {ENV_VAR_AG}...", _enable_ag)

                elif t == "proxy_https":
                    if state.https_env:
                        def _disable_https(cb: Callable[[str], None]) -> Tuple[bool, str]:
                            ok = set_env_var(ENV_VAR_HTTPS, None, progress_cb=cb)
                            state.refresh(progress_cb=cb)
                            return (ok, f"Disabled {ENV_VAR_HTTPS}." if ok else f"Failed to disable {ENV_VAR_HTTPS}.")
                        run_with_spinner(f"Disabling {ENV_VAR_HTTPS}...", _disable_https)
                    else:
                        set_cursor_visible(True)
                        print(f"\nEnter proxy address for {ENV_VAR_HTTPS} [default: {state.https_saved_url}]: ", end="", flush=True)
                        target_url_h: Optional[str] = None
                        try:
                            val = input().strip()
                            target_url_h = val if val else state.https_saved_url
                        except Exception:
                            pass
                        set_cursor_visible(False)
                        clear_screen()
                        if target_url_h:
                            def _enable_https(cb: Callable[[str], None]) -> Tuple[bool, str]:
                                ok = set_env_var(ENV_VAR_HTTPS, target_url_h, progress_cb=cb)
                                state.refresh(progress_cb=cb)
                                return (ok, f"Set {ENV_VAR_HTTPS} = {target_url_h}" if ok else f"Failed to set {ENV_VAR_HTTPS}.")
                            run_with_spinner(f"Setting {ENV_VAR_HTTPS}...", _enable_https)

                elif t == "app":
                    cat = curr["category"]
                    app_data = state.apps.get(cat)
                    if app_data and app_data["target"]:
                        target = app_data["target"]
                        st = app_data["status"]
                        target_unpatch = st["is_patched"] if st else False
                        verb = "Reverting" if target_unpatch else "Patching"

                        def _toggle_app(cb: Callable[[str], None]) -> Tuple[bool, str]:
                            res = patch_file(target, unpatch=target_unpatch, progress_cb=cb)
                            cb(f"Verifying {target.name}...")
                            state.refresh(progress_cb=cb)
                            if res.error:
                                return (False, f"{target.name}: {res.error}")
                            done_verb = "Reverted" if target_unpatch else "Patched"
                            return (True, f"{done_verb} {target.name} (reg:{res.region_replaced}, prx:{res.proxy_replaced})")

                        run_with_spinner(f"{verb} {target.name}...", _toggle_app)
                    else:
                        # Prompt user for custom path if not found
                        set_cursor_visible(True)
                        print(f"\n{cat} binary not found automatically.")
                        print("Enter path to executable binary or directory (press Enter to cancel): ", end="", flush=True)
                        custom_val = ""
                        try:
                            custom_val = input().strip()
                        except Exception:
                            pass
                        set_cursor_visible(False)
                        clear_screen()
                        if custom_val:
                            def _custom_patch(cb: Callable[[str], None]) -> Tuple[bool, str]:
                                cb(f"Searching for binary in {custom_val}...")
                                p = Path(custom_val.strip('\'"')).resolve()
                                candidate: Optional[Path] = None
                                if p.is_file() and p.exists():
                                    candidate = p
                                elif p.is_dir() and p.exists():
                                    bins = find_target_binaries(p)
                                    if bins:
                                        matched = [b for b in bins if classify_binary(b) == cat]
                                        candidate = matched[0] if matched else bins[0]
                                if not candidate:
                                    return (False, "No valid binary found at specified path.")
                                state.custom_paths[cat] = candidate
                                res = patch_file(candidate, unpatch=False, progress_cb=cb)
                                cb(f"Verifying {candidate.name}...")
                                state.refresh(progress_cb=cb)
                                if res.error:
                                    return (False, f"{candidate.name}: {res.error}")
                                return (True, f"Patched {candidate.name}")

                            run_with_spinner("Locating custom binary...", _custom_patch)

                elif t == "patch_all":
                    all_targets = [v["target"] for v in state.apps.values() if v and v["target"]]
                    if not all_targets:
                        run_with_spinner("Checking targets...", lambda cb: (False, "No detected binaries to patch."))
                    else:
                        def _patch_all(cb: Callable[[str], None]) -> Tuple[bool, str]:
                            ok_count = 0
                            for idx_t, target in enumerate(all_targets, 1):
                                res = patch_file(
                                    target,
                                    unpatch=False,
                                    progress_cb=lambda msg, i=idx_t, n=len(all_targets): cb(f"[{i}/{n}] {msg}")
                                )
                                if not res.error:
                                    ok_count += 1
                            cb("Verifying all binaries...")
                            state.refresh(progress_cb=cb)
                            return (ok_count == len(all_targets), f"Patched {ok_count}/{len(all_targets)} binaries.")

                        run_with_spinner("Patching all detected applications...", _patch_all)

                elif t == "revert_all":
                    all_targets = [v["target"] for v in state.apps.values() if v and v["target"]]
                    if not all_targets:
                        run_with_spinner("Checking targets...", lambda cb: (False, "No detected binaries to revert."))
                    else:
                        def _revert_all(cb: Callable[[str], None]) -> Tuple[bool, str]:
                            ok_count = 0
                            for idx_t, target in enumerate(all_targets, 1):
                                res = patch_file(
                                    target,
                                    unpatch=True,
                                    progress_cb=lambda msg, i=idx_t, n=len(all_targets): cb(f"[{i}/{n}] {msg}")
                                )
                                if not res.error:
                                    ok_count += 1
                            cb("Verifying all binaries...")
                            state.refresh(progress_cb=cb)
                            return (ok_count == len(all_targets), f"Reverted {ok_count}/{len(all_targets)} binaries.")

                        run_with_spinner("Reverting all detected applications...", _revert_all)

                elif t == "refresh":
                    run_with_spinner(
                        "Refreshing status...",
                        lambda cb: (state.refresh(progress_cb=cb), (True, "Status refreshed."))[1]
                    )

                elif t == "exit":
                    break
    finally:
        set_cursor_visible(True)
        print("\nExiting.")


# ============================================================================
# CLI Command Line Mode
# ============================================================================

def main():
    if len(sys.argv) == 1:
        run_interactive_tui()
        return

    parser = argparse.ArgumentParser(
        description="Antigravity Minimal Patcher: Granular Desktop, IDE, CLI control and AGY_U_PROXY isolation."
    )
    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version=f"Antigravity Patcher v{__version__}"
    )
    parser.add_argument(
        "--target",
        "-t",
        choices=["desktop", "ide", "cli", "all"],
        default="all",
        help="Target application to patch/revert (default: all)"
    )
    parser.add_argument(
        "--proxy",
        "-p",
        default=DEFAULT_PROXY_URL,
        help=f"Proxy URL to configure (default: {DEFAULT_PROXY_URL})"
    )
    parser.add_argument(
        "--set-proxy",
        action="store_true",
        help="Set AGY_U_PROXY variable to OS environment and exit"
    )
    parser.add_argument(
        "--unset-proxy",
        action="store_true",
        help="Remove AGY_U_PROXY variable from OS environment and exit"
    )
    parser.add_argument(
        "--path",
        help="Custom path to Antigravity directory or executable binary"
    )
    parser.add_argument(
        "--patch",
        action="store_true",
        help="Apply patches for selected target"
    )
    parser.add_argument(
        "--unpatch",
        "-u",
        action="store_true",
        help="Revert patches for selected target"
    )
    parser.add_argument(
        "--no-env",
        action="store_true",
        help="Do not modify environment variables"
    )
    parser.add_argument(
        "--status",
        "-s",
        action="store_true",
        help="Print status of all applications and proxy variables without changes"
    )
    parser.add_argument(
        "--tui",
        "-m",
        action="store_true",
        help="Open interactive Terminal User Interface"
    )

    args = parser.parse_args()

    root_path = Path(args.path).resolve() if args.path else None

    if args.tui:
        run_interactive_tui(root_path)
        return

    if args.unset_proxy:
        sp = CliSpinner(f"Removing {ENV_VAR_AG}...").start()
        ok = set_env_var(ENV_VAR_AG, None, progress_cb=sp.update)
        sp.finish(f"Removed {ENV_VAR_AG}." if ok else f"Failed to remove {ENV_VAR_AG}.", ok=ok)
        if ok:
            print(f"[+] Removed {ENV_VAR_AG} from environment.")
        else:
            print(f"[-] Failed to remove {ENV_VAR_AG}.")
        return

    if args.set_proxy:
        url = args.proxy.strip()
        sp = CliSpinner(f"Setting {ENV_VAR_AG}...").start()
        ok = set_env_var(ENV_VAR_AG, url, progress_cb=sp.update)
        sp.finish(f"Set {ENV_VAR_AG}={url}" if ok else f"Failed to set {ENV_VAR_AG}.", ok=ok)
        if ok:
            print(f"[+] Set {ENV_VAR_AG}={url}")
        else:
            print(f"[-] Failed to set {ENV_VAR_AG}.")
        return

    sp_scan = CliSpinner("Scanning installation directories...").start()
    grouped = get_categorized_targets(root_path)
    sp_scan.update("Reading proxy environment variables...")
    cur_ag = get_current_env_var(ENV_VAR_AG)
    cur_https = get_current_env_var(ENV_VAR_HTTPS)
    sp_scan.finish()

    print("=" * 68)
    print(f"         Antigravity Patcher & Proxy Manager v{__version__}")
    print("=" * 68)
    print(f"[*] {ENV_VAR_AG}:    {cur_ag or '<Not Set>'}")
    print(f"[*] {ENV_VAR_HTTPS}: {cur_https or '<Not Set>'}")

    if args.status:
        for cat in ALL_CATEGORIES:
            targets = grouped.get(cat, [])
            if not targets:
                print(f"\n[-] {cat}: Not Installed")
            else:
                for t in targets:
                    sp = CliSpinner(f"Inspecting {t.name}...").start()
                    st = get_binary_status(t, progress_cb=sp.update)
                    sp.finish(f"Inspected {t.name}", ok=(st.get("error") is None))
                    print(f"\n[*] {cat}: {st['badge']}")
                    print(f"    File:    {t}")
                    print(f"    Details: Region = {st['region']} | Proxy = {st['proxy']}")
        return

    # Process CLI target
    selected_targets: List[Path] = []
    if args.target == "desktop":
        selected_targets = grouped.get(AppCategory.DESKTOP, [])
    elif args.target == "ide":
        selected_targets = grouped.get(AppCategory.IDE, [])
    elif args.target == "cli":
        selected_targets = grouped.get(AppCategory.CLI, [])
    else:
        selected_targets = [t for sub in grouped.values() for t in sub]

    if not selected_targets:
        print(f"\n[!] No binaries found for target: {args.target}")
        sys.exit(1)

    action_text = "Reverting" if args.unpatch else "Patching"
    print(f"\n[*] {action_text} {args.target.upper()} ({len(selected_targets)} files)...")

    for t in selected_targets:
        sp = CliSpinner(f"{action_text} {t.name}...").start()
        res = patch_file(t, unpatch=args.unpatch, progress_cb=sp.update)
        sp.finish(
            f"{t.name}: {'Failed' if res.error else 'Done'}",
            ok=(res.error is None)
        )
        if res.error:
            print(f"  [-] {t.name}: Error ({res.error})")
        elif res.already_patched:
            state = "original" if args.unpatch else "patched"
            print(f"  [=] {t.name}: Already in {state} state.")
        else:
            print(f"  [+] {t.name}: Success (region: {res.region_replaced}, proxy: {res.proxy_replaced})")

    if not args.no_env and not args.unpatch:
        url = args.proxy.strip()
        sp = CliSpinner(f"Setting {ENV_VAR_AG}...").start()
        ok = set_env_var(ENV_VAR_AG, url, progress_cb=sp.update)
        sp.finish(f"Configured {ENV_VAR_AG}" if ok else f"Failed to configure {ENV_VAR_AG}", ok=ok)
        if ok:
            print(f"\n[+] Environment variable {ENV_VAR_AG} configured: {url}")


if __name__ == "__main__":
    main()
