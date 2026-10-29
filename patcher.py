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
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

__version__ = "1.0.0"

# Byte signatures (Exact length match is mandatory)
SIG_REGION_FROM = b"ineligible"   # 10 bytes
SIG_REGION_TO = b"inexigible"     # 10 bytes

SIG_PROXY_FROM = b"https_proxy"    # 11 bytes
SIG_PROXY_TO = b"AGY_U_PROXY"      # 11 bytes

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
    BADGE_NOT_FOUND = f"{RED}[Not Found]{RESET}"
    BADGE_ERROR = f"{RED}[Error]{RESET}"


# ============================================================================
# Keyboard Input Handler (Windows msvcrt / Linux termios)
# ============================================================================

class KeyReader:
    def __init__(self):
        self.is_win = is_windows()
        if not self.is_win:
            import termios
            import tty
            self.termios = termios
            self.tty = tty

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
                ch = sys.stdin.read(1)
                if ch == "\x1b":
                    # Escape sequence
                    seq = sys.stdin.read(2)
                    if seq == "[A":
                        return "UP"
                    elif seq == "[B":
                        return "DOWN"
                    elif seq == "[C":
                        return "RIGHT"
                    elif seq == "[D":
                        return "LEFT"
                    return "QUIT"
                elif ch in ("\n", "\r"):
                    return "ENTER"
                elif ch == " ":
                    return "SPACE"
                elif ch in ("q", "Q"):
                    return "QUIT"
                return ch
            finally:
                self.termios.tcsetattr(fd, self.termios.TCSADRAIN, old_settings)


# ============================================================================
# Environment Variable Management
# ============================================================================

def set_env_var(name: str, value: Optional[str]) -> bool:
    """Set or remove persistent user environment variable across Windows/Linux."""
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
        # Linux: write drop-in to ~/.config/environment.d and apply via systemctl
        home = Path.home()
        env_d = home / ".config" / "environment.d"
        conf_file = env_d / "agy-patcher.conf"
        try:
            if value is None:
                if conf_file.exists():
                    lines = conf_file.read_text(encoding="utf-8").splitlines()
                    new_lines = [l for l in lines if not l.startswith(f"{name}=")]
                    if new_lines:
                        conf_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
                    else:
                        conf_file.unlink()
                subprocess.run(
                    ["systemctl", "--user", "unset-environment", name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False
                )
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
                subprocess.run(
                    ["systemctl", "--user", "set-environment", f"{name}={value}"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False
                )
            return True
        except Exception as e:
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
        conf_file = Path.home() / ".config" / "environment.d" / "agy-patcher.conf"
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
        home = Path.home()
        bases = ["/opt", "/usr/share", "/usr/lib", "/usr/local/share"]
        names = ["Antigravity", "Antigravity IDE", "antigravity", "antigravity-ide"]
        for base in bases:
            b = Path(base)
            for n in names:
                candidates.append(b / n)

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


def find_target_binaries(root: Optional[Path] = None) -> List[Path]:
    """Find all language server and CLI binaries in given root or standard dirs."""
    roots = [root] if root else get_candidate_install_dirs()
    targets: Set[Path] = set()

    for r in roots:
        if r.is_file():
            if _is_candidate_filename(r.name):
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
                if item.is_file() and _is_candidate_filename(item.name):
                    targets.add(item.resolve())

    return sorted(list(targets))


def _is_candidate_filename(name: str) -> bool:
    lower = name.lower()
    if lower.endswith((".agtmp", ".tmp", ".bak", ".log", ".json", ".md")):
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


def patch_file(path: Path, unpatch: bool = False) -> PatchResult:
    """Perform in-place byte replacement on a binary file."""
    res = PatchResult(path)
    from_region, to_region = (SIG_REGION_TO, SIG_REGION_FROM) if unpatch else (SIG_REGION_FROM, SIG_REGION_TO)
    from_proxy, to_proxy = (SIG_PROXY_TO, SIG_PROXY_FROM) if unpatch else (SIG_PROXY_FROM, SIG_PROXY_TO)

    try:
        data = path.read_bytes()
    except Exception as e:
        res.error = f"Failed to read file: {e}"
        return res

    region_count = data.count(from_region)
    proxy_count = data.count(from_proxy)

    target_region_count = data.count(to_region)
    target_proxy_count = data.count(to_proxy)

    if region_count == 0 and proxy_count == 0:
        if target_region_count > 0 or target_proxy_count > 0:
            res.already_patched = True
            return res
        res.error = "Signatures not found"
        return res

    new_data = data
    if region_count > 0:
        new_data = new_data.replace(from_region, to_region)
        res.region_replaced = region_count

    if proxy_count > 0:
        new_data = new_data.replace(from_proxy, to_proxy)
        res.proxy_replaced = proxy_count

    assert len(new_data) == len(data), "Critical error: File size modified after replacement!"

    tmp_path = path.with_suffix(f".{os.getpid()}.agtmp")
    try:
        tmp_path.write_bytes(new_data)
        if not is_windows():
            mode = path.stat().st_mode
            tmp_path.chmod(mode)

        try:
            tmp_path.replace(path)
        except (PermissionError, OSError):
            kill_locking_processes()
            time.sleep(0.3)
            tmp_path.replace(path)
    except Exception as e:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        res.error = f"Write error: {e}"

    return res


def get_binary_status(path: Path) -> dict:
    """Read binary and return structured patch status."""
    try:
        content = path.read_bytes()
        has_reg_mod = SIG_REGION_TO in content
        has_reg_orig = SIG_REGION_FROM in content
        has_prx_mod = SIG_PROXY_TO in content
        has_prx_orig = SIG_PROXY_FROM in content

        is_patched = has_reg_mod and has_prx_mod
        is_unpatched = has_reg_orig and has_prx_orig
        is_partial = not is_patched and not is_unpatched and (has_reg_mod or has_prx_mod)

        reg_text = f"{Colors.GREEN}Unlocked{Colors.RESET}" if has_reg_mod else (f"{Colors.GRAY}Blocked{Colors.RESET}" if has_reg_orig else "Unknown")
        prx_text = f"{Colors.GREEN}{ENV_VAR_AG}{Colors.RESET}" if has_prx_mod else (f"{Colors.GRAY}https_proxy{Colors.RESET}" if has_prx_orig else "Unknown")

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
            "error": None
        }
    except Exception as e:
        return {
            "badge": Colors.BADGE_ERROR,
            "is_patched": False,
            "region": "Error",
            "proxy": "Error",
            "error": str(e)
        }


# ============================================================================
# Interactive Terminal User Interface (TUI)
# ============================================================================

class AppState:
    """In-memory cache for environment variables and binary inspection results."""
    def __init__(self, root_path: Optional[Path] = None):
        self.root_path = root_path
        self.ag_env = None
        self.https_env = None
        self.ag_saved_url = DEFAULT_PROXY_URL
        self.https_saved_url = DEFAULT_PROXY_URL
        self.apps = {}
        self.custom_paths: Dict[str, Path] = {}
        self.refresh()

    def refresh(self):
        """Perform disk scan and registry queries only when explicitly requested."""
        self.ag_env = get_current_env_var(ENV_VAR_AG)
        self.https_env = get_current_env_var(ENV_VAR_HTTPS)
        if self.ag_env:
            self.ag_saved_url = self.ag_env
        if self.https_env:
            self.https_saved_url = self.https_env

        grouped = get_categorized_targets(self.root_path)
        self.apps = {}
        for cat in ALL_CATEGORIES:
            targets = grouped.get(cat, [])
            if not targets and cat in self.custom_paths:
                cp = self.custom_paths[cat]
                if cp and cp.exists():
                    targets = [cp]
            if targets:
                t = targets[0]
                st = get_binary_status(t)
                self.apps[cat] = {"target": t, "status": st}
            else:
                self.apps[cat] = {"target": None, "status": None}


def run_interactive_tui(root_path: Optional[Path] = None):
    """Full-featured interactive TUI engine with in-memory caching and zero-flicker redraw."""
    reader = KeyReader()
    state = AppState(root_path)

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

    # Clear screen ONCE at startup and hide cursor for smooth redraw
    clear_screen()
    set_cursor_visible(False)

    try:
        while True:
            # Build compact buffer (fits comfortably in 24-line console with zero scroll)
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
                if not app_info or not app_info["target"]:
                    buf.append(f"{c_str}{t_col}{cat:<23}{Colors.RESET}: {Colors.BADGE_NOT_FOUND}")
                else:
                    st = app_info["status"]
                    b_badge = st["badge"] if st else Colors.BADGE_ERROR
                    target_path = str(app_info["target"])
                    buf.append(f"{c_str}{t_col}{cat:<23}{Colors.RESET}: {b_badge}  {Colors.GRAY}{target_path}{Colors.RESET}")

            buf.append("")
            buf.append(f"  {Colors.BOLD}--- [ ACTIONS ] ---{Colors.RESET}")
            for idx in [5, 6, 7, 8]:
                item = items[idx]
                is_cur = (selected_idx == idx)
                c_str = f"{Colors.CYAN}>{Colors.RESET} " if is_cur else "  "
                t_col = f"{Colors.CYAN}{Colors.BOLD}" if is_cur else Colors.WHITE
                buf.append(f"{c_str}{t_col}{item['title']}{Colors.RESET}")

            buf.append("-" * 72)
            buf.append("  [Up/Down] Navigate  |  [Space/Enter] Select  |  [Q] Exit")

            # Reposition to top-left and write buffer (instant, zero flicker, zero I/O)
            move_cursor_home()
            out_str = "\n".join([line + "\033[K" for line in buf]) + "\n"
            sys.stdout.write(out_str)
            sys.stdout.flush()

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
                        # Toggle: currently enabled -> disable
                        set_env_var(ENV_VAR_AG, None)
                        state.refresh()
                    else:
                        # Toggle: currently disabled -> prompt for address and enable
                        set_cursor_visible(True)
                        print(f"\nEnter proxy address for {ENV_VAR_AG} [default: {state.ag_saved_url}]: ", end="", flush=True)
                        try:
                            val = input().strip()
                            target_url = val if val else state.ag_saved_url
                            set_env_var(ENV_VAR_AG, target_url)
                        except Exception:
                            pass
                        state.refresh()
                        set_cursor_visible(False)
                        clear_screen()

                elif t == "proxy_https":
                    if state.https_env:
                        # Toggle: currently enabled -> disable
                        set_env_var(ENV_VAR_HTTPS, None)
                        state.refresh()
                    else:
                        # Toggle: currently disabled -> prompt for address and enable
                        set_cursor_visible(True)
                        print(f"\nEnter proxy address for {ENV_VAR_HTTPS} [default: {state.https_saved_url}]: ", end="", flush=True)
                        try:
                            val = input().strip()
                            target_url = val if val else state.https_saved_url
                            set_env_var(ENV_VAR_HTTPS, target_url)
                        except Exception:
                            pass
                        state.refresh()
                        set_cursor_visible(False)
                        clear_screen()

                elif t == "app":
                    cat = curr["category"]
                    app_data = state.apps.get(cat)
                    if app_data and app_data["target"]:
                        target = app_data["target"]
                        st = app_data["status"]
                        target_unpatch = st["is_patched"] if st else False
                        patch_file(target, unpatch=target_unpatch)
                        state.refresh()
                    else:
                        # Prompt user for custom path if not found
                        set_cursor_visible(True)
                        print(f"\n{cat} binary not found automatically.")
                        print("Enter path to executable binary or directory (press Enter to cancel): ", end="", flush=True)
                        try:
                            val = input().strip()
                            if val:
                                p = Path(val.strip('\'"')).resolve()
                                candidate: Optional[Path] = None
                                if p.is_file() and p.exists():
                                    candidate = p
                                elif p.is_dir() and p.exists():
                                    bins = find_target_binaries(p)
                                    if bins:
                                        matched = [b for b in bins if classify_binary(b) == cat]
                                        candidate = matched[0] if matched else bins[0]
                                if candidate:
                                    state.custom_paths[cat] = candidate
                                    state.refresh()
                                    app_data = state.apps.get(cat)
                                    if app_data and app_data["target"]:
                                        patch_file(app_data["target"], unpatch=False)
                                else:
                                    print(f"{Colors.RED}No valid binary found at specified path.{Colors.RESET}")
                                    time.sleep(1.5)
                        except Exception as e:
                            print(f"{Colors.RED}Error: {e}{Colors.RESET}")
                            time.sleep(1.5)
                        state.refresh()
                        set_cursor_visible(False)
                        clear_screen()

                elif t == "patch_all":
                    all_targets = [v["target"] for v in state.apps.values() if v and v["target"]]
                    for target in all_targets:
                        patch_file(target, unpatch=False)
                    state.refresh()

                elif t == "revert_all":
                    all_targets = [v["target"] for v in state.apps.values() if v and v["target"]]
                    for target in all_targets:
                        patch_file(target, unpatch=True)
                    state.refresh()

                elif t == "refresh":
                    state.refresh()

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
        if set_env_var(ENV_VAR_AG, None):
            print(f"[+] Removed {ENV_VAR_AG} from environment.")
        else:
            print(f"[-] Failed to remove {ENV_VAR_AG}.")
        return

    if args.set_proxy:
        url = args.proxy.strip()
        if set_env_var(ENV_VAR_AG, url):
            print(f"[+] Set {ENV_VAR_AG}={url}")
        else:
            print(f"[-] Failed to set {ENV_VAR_AG}.")
        return

    grouped = get_categorized_targets(root_path)
    cur_ag = get_current_env_var(ENV_VAR_AG)
    cur_https = get_current_env_var(ENV_VAR_HTTPS)

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
                    st = get_binary_status(t)
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
        res = patch_file(t, unpatch=args.unpatch)
        if res.error:
            print(f"  [-] {t.name}: Error ({res.error})")
        elif res.already_patched:
            state = "original" if args.unpatch else "patched"
            print(f"  [=] {t.name}: Already in {state} state.")
        else:
            print(f"  [+] {t.name}: Success (region: {res.region_replaced}, proxy: {res.proxy_replaced})")

    if not args.no_env and not args.unpatch:
        url = args.proxy.strip()
        if set_env_var(ENV_VAR_AG, url):
            print(f"\n[+] Environment variable {ENV_VAR_AG} configured: {url}")


if __name__ == "__main__":
    main()
