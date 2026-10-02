"""AzerothCoreCOA local dashboard: tiny stdlib-only HTTP server.

Serves the dashboard UI and a small REST API that starts/stops the three
services, tails their console log files, accepts typed input for World/Auth
(GM console) and ad-hoc SQL for MySQL, reads/writes config files, manages
accounts/bans/tickets/realmlist, and launches the game client. Paths are
user-editable in Settings and persisted to dashboard_settings.json next to
this script. Everything runs locally on 127.0.0.1.

World/Auth/MySQL are all launched the same way -- via their .bat launcher,
in their own real console window (os.startfile, exactly like double-
clicking). AzerothCore's CLI reader misbehaves (and can silently shut the
server down) if its stdin/stdout aren't a real console, so we never
redirect them. Typed console input is instead injected into the target
process's own console via the Win32 console APIs (AttachConsole +
WriteConsoleInput) -- same effect as a human typing into that window,
without touching its stdio handles.
"""

import ctypes
import ctypes.wintypes as wintypes
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

import item_tips

mimetypes.add_type("image/webp", ".webp")
mimetypes.add_type("application/manifest+json", ".webmanifest")

DASHBOARD_DIR = (os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, "frozen", False)
                  else os.path.dirname(os.path.abspath(__file__)))
SETTINGS_PATH = os.path.join(DASHBOARD_DIR, "dashboard_settings.json")

_DEFAULT_INSTALL_DIR = os.path.dirname(DASHBOARD_DIR)
_DEFAULT_AZEROTHCORE_DIR = os.path.dirname(os.path.dirname(_DEFAULT_INSTALL_DIR))
DEFAULT_SETTINGS = {
    "install_dir": _DEFAULT_INSTALL_DIR,
    "configs_dir": os.path.join(_DEFAULT_INSTALL_DIR, "configs"),
    "mysql_dir": os.path.join(_DEFAULT_AZEROTHCORE_DIR, "mysql-8.4.11"),
    "mysql_data_dir": os.path.join(_DEFAULT_AZEROTHCORE_DIR, "mysql-data"),
    "client_exe": r"H:\Simon\WoW Server Stuff\Ascension Client+Data\Ascension.exe",
    "mysql_user": "acore",
    "mysql_password": "acore",
    "mysql_host": "127.0.0.1",
    "mysql_port": "3306",
    # Optional ExilesDB module (modules/exilesdb); empty path = module unused.
    "exilesdb_path": "",
    "exilesdb_port": "8081",
    # Override the authserver.exe / worldserver.exe location; empty = <install_dir>\<name>.exe.
    "authserver_exe": "",
    "worldserver_exe": "",
    # A second realm's worldserver.exe, wherever it lives; empty = feature hidden entirely.
    "worldserver2_exe": "",
    # "bat" (default) = launch via the .bat wrapper (console title/color, MySQL wait-for-port
    # logic on Authserver). "exe" = os.startfile the service's own .exe directly, skipping
    # the wrapper entirely -- for installs that don't have (or don't want) the .bat files.
    "launch_mode": "bat",
}

MODULE_CONFIGS = [
    {"key": "world", "label": "worldserver.conf", "rel": "worldserver.conf", "base": "configs_dir"},
    {"key": "auth", "label": "authserver.conf", "rel": "authserver.conf", "base": "configs_dir"},
    {"key": "mysql", "label": "MySQL (my.ini)", "rel": "my.ini", "base": "mysql_dir"},
]


def load_settings():
    settings = dict(DEFAULT_SETTINGS)
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            settings.update({k: v for k, v in saved.items() if k in DEFAULT_SETTINGS})
        except Exception:
            pass
    return settings


def save_settings(settings):
    clean = {k: settings.get(k, DEFAULT_SETTINGS[k]) for k in DEFAULT_SETTINGS}
    # Merge onto the file's raw contents (not just DEFAULT_SETTINGS) so extra
    # top-level keys that live in the same file but aren't part of the normal
    # settings form -- e.g. "auto_start" -- survive an ordinary Settings-page save.
    raw = {}
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            raw = {}
    raw.update(clean)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2)
    return clean


def load_auto_start():
    """Per-service auto-start flags, stored under the "auto_start" key in the
    same dashboard_settings.json file but kept out of DEFAULT_SETTINGS/
    save_settings' key set so it isn't clobbered by the generic Settings-page
    save. Defaults to off for every service."""
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
            val = raw.get("auto_start")
            if isinstance(val, dict):
                return {k: bool(v) for k, v in val.items()}
        except Exception:
            pass
    return {}


def save_auto_start(auto_start):
    raw = {}
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            raw = {}
    raw["auto_start"] = auto_start
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2)


SETTINGS = load_settings()
AUTO_START = load_auto_start()


def _load_optional_module(name):
    """Import modules/<name>/module.py if that folder exists, else None.

    Modules are optional add-ons: deleting the folder removes the feature and
    the dashboard keeps working (the UI hides whatever /api/modules omits).
    """
    import importlib.util
    path = os.path.join(DASHBOARD_DIR, "modules", name, "module.py")
    if not os.path.isfile(path):
        return None
    try:
        spec = importlib.util.spec_from_file_location("dashboard_module_" + name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception as e:
        print(f"Module '{name}' failed to load: {e}", flush=True)
        return None


EXILESDB = _load_optional_module("exilesdb")
SQUIDBOTS = _load_optional_module("squidbots")


def resolved_exe(setting_key: str, default_name: str) -> str:
    """The exe path from SETTINGS[setting_key] if set, else <install_dir>/<default_name>."""
    explicit = (SETTINGS.get(setting_key) or "").strip()
    return explicit or os.path.join(SETTINGS["install_dir"], default_name)


def services():
    install = SETTINGS["install_dir"]
    auth_exe = resolved_exe("authserver_exe", "authserver.exe")
    world_exe = resolved_exe("worldserver_exe", "worldserver.exe")
    world2_exe = (SETTINGS.get("worldserver2_exe") or "").strip()
    auth_dir, world_dir = os.path.dirname(auth_exe), os.path.dirname(world_exe)
    out = {
        "mysql": {
            "label": "MySQL",
            "process": "mysqld.exe",
            "start_script": os.path.join(install, "start-mysql.bat"),
            "log": None,
        },
        "auth": {
            "label": "Authserver",
            "process": "authserver.exe",
            "start_script": os.path.join(auth_dir, "start-authserver.bat"),
            "log": os.path.join(auth_dir, "Auth.log"),
            "exe": auth_exe,
        },
        "world": {
            "label": "Worldserver",
            "process": "worldserver.exe",
            "start_script": os.path.join(world_dir, "start-worldserver.bat"),
            "log": os.path.join(world_dir, "Server.log"),
            "exe": world_exe,
        },
    }
    # A second realm's worldserver.exe is entirely optional -- most installs have just one,
    # so the key (and with it the UI's card/tab) only exists once a path is actually set.
    if world2_exe:
        world2_dir = os.path.dirname(world2_exe)
        bat2 = os.path.join(world2_dir, "start-worldserver2.bat")
        out["world2"] = {
            "label": "Worldserver (Realm 2)",
            "process": "worldserver.exe",
            "start_script": bat2 if os.path.isfile(bat2) else os.path.join(world2_dir, "start-worldserver.bat"),
            "log": os.path.join(world2_dir, "Server.log"),
            "exe": world2_exe,
        }
    return out


def resolve_config_path(cfg):
    base = SETTINGS[cfg["base"]]
    return os.path.normpath(os.path.join(base, cfg["rel"]))


def all_configs():
    """world/auth/mysql plus every *.conf found in <configs_dir>/modules, scanned fresh on every call:
    a new module's conf shows up on its own, and one renamed (e.g. to .obsolete) or deleted drops out on its own.
    Discovered entries get the key "mod-<file name>"; only files directly inside that folder are ever offered."""
    out = list(MODULE_CONFIGS)
    known = {os.path.normcase(resolve_config_path(c)) for c in out}
    folder = os.path.join(SETTINGS["configs_dir"], "modules")
    try:
        names = sorted(os.listdir(folder), key=str.lower)
    except OSError:
        return out
    for name in names:
        path = os.path.normpath(os.path.join(folder, name))
        if name.lower().endswith(".conf") and os.path.isfile(path) and os.path.normcase(path) not in known:
            out.append({"key": "mod-" + name, "label": name, "rel": "modules/" + name, "base": "configs_dir"})
    return out


def mysql_log_path():
    data_dir = SETTINGS["mysql_data_dir"]
    try:
        for name in os.listdir(data_dir):
            if name.lower().endswith(".err"):
                return os.path.join(data_dir, name)
    except OSError:
        pass
    return None


def _run(cmd, **kwargs):
    """subprocess.run wrapper: always gives the child its own stdin.
    Sending a console command (send_console_keys) briefly detaches this
    process from its own console, which can leave our inherited stdin
    handle invalid afterwards -- explicit DEVNULL means every subprocess
    call here is unaffected by that, instead of inheriting a handle that
    might have gone stale.

    CREATE_NO_WINDOW stops each call (tasklist/taskkill/mysql -e, run on
    every 5s status poll) from flashing its own console window -- these
    are background introspection calls, not the real service consoles
    (those are opened separately via os.startfile in start_service)."""
    kwargs.setdefault("stdin", subprocess.DEVNULL)
    kwargs.setdefault("creationflags", subprocess.CREATE_NO_WINDOW)
    return subprocess.run(cmd, **kwargs)


def get_pid(process_name: str, exe_path: str = None):
    """Finds a running process by image name. When two instances share the
    same image name (e.g. two worldserver.exe, one per realm), pass exe_path
    to disambiguate: only a process whose own executable path matches is
    returned. Without exe_path this returns whichever instance tasklist
    lists first -- fine for single-instance services (mysql/auth), wrong
    for a multi-instance one."""
    if exe_path:
        return get_pid_by_path(exe_path)
    try:
        out = _run(
            ["tasklist", "/FI", f"IMAGENAME eq {process_name}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
    except Exception:
        return None
    if not out or out.lower().startswith("info:"):
        return None
    first = out.splitlines()[0]
    parts = [p.strip('"') for p in first.split('","')]
    if len(parts) < 2:
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def get_pid_by_path(exe_path: str):
    """Matches a process by its own full executable path, via WMI --
    tasklist has no path filter, and IMAGENAME alone can't tell two
    same-named worldserver.exe instances (one per realm) apart."""
    exe_norm = os.path.normcase(os.path.normpath(exe_path))
    name = os.path.basename(exe_path)
    try:
        out = _run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             f"Get-CimInstance Win32_Process -Filter \"Name='{name}'\" | "
             "Select-Object ProcessId,ExecutablePath | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except Exception:
        return None
    if not out:
        return None
    try:
        data = json.loads(out)
    except Exception:
        return None
    if isinstance(data, dict):
        data = [data]
    for p in data:
        ep = p.get("ExecutablePath") or ""
        if os.path.normcase(os.path.normpath(ep)) == exe_norm:
            return p.get("ProcessId")
    return None


def is_running(process_name: str, exe_path: str = None) -> bool:
    return get_pid(process_name, exe_path) is not None


def service_pid(key: str):
    """PID lookup that uses each service's own exe path when the service
    dict has one (world/world2) so two same-named worldserver.exe instances
    never get confused for each other; falls back to plain image-name
    lookup for single-instance services (mysql/auth)."""
    svc = services()[key]
    return get_pid(svc["process"], svc.get("exe"))


def service_running(key: str) -> bool:
    return service_pid(key) is not None


def start_service(key: str):
    """Launch a service exactly like double-clicking its .bat: its own real
    console window, no redirected stdio. AzerothCore's CLI reader needs a
    real console -- redirecting it is what causes silent shutdowns/hangs.

    With launch_mode == "exe", skips the .bat wrapper and os.startfile()s the
    service's own .exe directly instead (still its own real console window --
    os.startfile behaves the same for a .exe as double-clicking it). Loses the
    .bat's console title/color and Authserver's wait-for-MySQL-port logic, but
    needs nothing but the .exe to exist."""
    if SETTINGS.get("launch_mode") == "exe":
        exe = _service_exe_path(key)
        os.startfile(exe, cwd=os.path.dirname(exe))
        return
    os.startfile(services()[key]["start_script"])


def stop_service(key: str):
    """mysqld/authserver/worldserver don't register for a graceful
    WM_CLOSE-style shutdown, so plain `taskkill` fails outright with
    "can only be terminated forcefully" -- /F is required. Also check the
    result: taskkill exiting non-zero must surface as an error instead of
    silently reporting success while the process keeps running.

    Services with an "exe" path (world/world2) kill by that specific PID --
    two worldserver.exe processes (one per realm) share an image name, so
    `taskkill /IM worldserver.exe` would kill whichever one it found first,
    possibly the wrong realm."""
    svc = services()[key]
    if svc.get("exe"):
        pid = get_pid_by_path(svc["exe"])
        if pid is None:
            return
        result = _run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, text=True, timeout=10)
    else:
        result = _run(["taskkill", "/F", "/IM", svc["process"]], capture_output=True, text=True, timeout=10)
    if result.returncode != 0 and service_running(key):
        raise RuntimeError((result.stderr or result.stdout or "taskkill failed").strip())


def restart_service(key: str, timeout: float = 30.0):
    """Stops the service and waits for its process to actually disappear
    (taskkill just requests termination, it doesn't wait) before starting it
    again -- starting too early would launch a second instance racing the
    first one for the same port/data files."""
    svc = services()[key]
    if service_running(key):
        stop_service(key)
        deadline = time.monotonic() + timeout
        while service_running(key):
            if time.monotonic() > deadline:
                raise RuntimeError(f"{svc['label']} did not stop within {int(timeout)}s -- check its console window")
            time.sleep(0.5)
    start_service(key)


def tail_file(path: str, lines: int = 300) -> str:
    if not path or not os.path.exists(path):
        return "(no log file yet -- start this service first)"
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block = 8192
            data = b""
            pos = size
            newline_count = 0
            while pos > 0 and newline_count <= lines:
                step = min(block, pos)
                pos -= step
                f.seek(pos)
                chunk = f.read(step)
                data = chunk + data
                newline_count += chunk.count(b"\n")
        text = data.decode("utf-8", errors="replace")
        return "\n".join(text.splitlines()[-lines:])
    except Exception as e:
        return f"(could not read log: {e})"


def get_console_text(key: str):
    if key == "mysql":
        with MYSQL_LOCK:
            text = "\n".join(MYSQL_TRANSCRIPT) or "(no SQL run yet -- type a query below and press Send)"
        return text, is_running("mysqld.exe")
    svc = services()[key]
    # Authserver's console doesn't process typed commands in this build --
    # only Worldserver's does. Keep Auth's console read-only to avoid a
    # "Send" button that silently does nothing.
    writable = key in ("world", "world2") and service_running(key)
    if key in ("world", "world2") and writable:
        # Worldserver prints command echoes/results straight to its own
        # console -- that text doesn't necessarily land in Server.log (which
        # is a separate logging sink), so tailing the log file makes typed
        # commands invisible here even though they show up in the real
        # window. Read the console's actual screen buffer instead so this
        # view matches the real window exactly.
        pid = service_pid(key)
        if pid:
            try:
                return read_console_screen(pid), writable
            except Exception as e:
                return tail_file(svc["log"]) + f"\n\n(live console read failed: {e} -- showing Server.log instead)", writable
    return tail_file(svc["log"]), writable


# ---- console input injection (World/Auth) ----------------------------------
# AzerothCore's CLI console reads real keyboard input from its own console
# window. To "type" into it from here without touching its stdio (which
# breaks its console-vs-pipe detection), we temporarily attach *our*
# process to *its* console and post synthetic key events -- exactly what
# a human typing into that window would produce.

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
STD_INPUT_HANDLE = -10
ATTACH_PARENT_PROCESS = 0xFFFFFFFF
KEY_EVENT = 0x0001
_console_io_lock = threading.Lock()

# Explicit signatures: ctypes defaults to a 32-bit int return type, which
# would truncate a real (64-bit) HANDLE on Win64 and corrupt every call
# that follows -- these must be set before any of these are called.
_k32.AttachConsole.argtypes = [wintypes.DWORD]
_k32.AttachConsole.restype = wintypes.BOOL
_k32.FreeConsole.argtypes = []
_k32.FreeConsole.restype = wintypes.BOOL
_k32.CreateFileW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
    wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
]
_k32.CreateFileW.restype = wintypes.HANDLE
_k32.WriteConsoleInputW.argtypes = [
    wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
]
_k32.WriteConsoleInputW.restype = wintypes.BOOL
_k32.CloseHandle.argtypes = [wintypes.HANDLE]
_k32.CloseHandle.restype = wintypes.BOOL


class _KeyEventChar(ctypes.Union):
    _fields_ = [("UnicodeChar", wintypes.WCHAR), ("AsciiChar", ctypes.c_char)]


class _KeyEventRecord(ctypes.Structure):
    _fields_ = [
        ("bKeyDown", wintypes.BOOL),
        ("wRepeatCount", wintypes.WORD),
        ("wVirtualKeyCode", wintypes.WORD),
        ("wVirtualScanCode", wintypes.WORD),
        ("uChar", _KeyEventChar),
        ("dwControlKeyState", wintypes.DWORD),
    ]


class _InputRecordEvent(ctypes.Union):
    _fields_ = [("KeyEvent", _KeyEventRecord)]


class _InputRecord(ctypes.Structure):
    _fields_ = [("EventType", wintypes.WORD), ("Event", _InputRecordEvent)]


def _key_record(ch: str, down: bool, vk: int = 0) -> _InputRecord:
    rec = _InputRecord()
    rec.EventType = KEY_EVENT
    rec.Event.KeyEvent.bKeyDown = down
    rec.Event.KeyEvent.wRepeatCount = 1
    rec.Event.KeyEvent.wVirtualKeyCode = vk
    rec.Event.KeyEvent.wVirtualScanCode = 0
    rec.Event.KeyEvent.uChar.UnicodeChar = ch
    rec.Event.KeyEvent.dwControlKeyState = 0
    return rec


def send_console_keys(pid: int, text: str):
    """Types `text` + Enter into the console owned by process `pid`."""
    VK_RETURN = 0x0D
    chars = list(text) + ["\r"]
    records = []
    for ch in chars:
        vk = VK_RETURN if ch == "\r" else 0
        records.append(_key_record(ch, True, vk))
        records.append(_key_record(ch, False, vk))
    arr = (_InputRecord * len(records))(*records)

    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    OPEN_EXISTING = 3
    INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

    with _console_io_lock:
        _k32.FreeConsole()
        try:
            if not _k32.AttachConsole(pid):
                err = ctypes.get_last_error()
                raise RuntimeError(f"could not attach to that console (win32 error {err}) -- is it a real console window?")
            handle = None
            try:
                # GetStdHandle can be stale after AttachConsole; open the
                # newly-attached console's input buffer directly instead.
                handle = _k32.CreateFileW(
                    "CONIN$", GENERIC_READ | GENERIC_WRITE,
                    FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None,
                )
                if handle == INVALID_HANDLE_VALUE:
                    raise RuntimeError(f"could not open CONIN$ (win32 error {ctypes.get_last_error()})")
                written = wintypes.DWORD(0)
                ok = _k32.WriteConsoleInputW(handle, arr, len(records), ctypes.byref(written))
                if not ok:
                    raise RuntimeError(f"WriteConsoleInput failed (win32 error {ctypes.get_last_error()})")
            finally:
                if handle:
                    _k32.CloseHandle(handle)
                _k32.FreeConsole()
        finally:
            _k32.AttachConsole(ATTACH_PARENT_PROCESS)


# ---- console output reading (World) -----------------------------------
# Server.log is a separate logging sink -- text AzerothCore's CLI prints
# straight to its own console (command echoes, command results) doesn't
# necessarily get duplicated into it. Reading the console's actual screen
# buffer instead shows exactly what the real window shows, live.

class _COORD(ctypes.Structure):
    _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]


class _SMALL_RECT(ctypes.Structure):
    _fields_ = [
        ("Left", ctypes.c_short), ("Top", ctypes.c_short),
        ("Right", ctypes.c_short), ("Bottom", ctypes.c_short),
    ]


class _CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
    _fields_ = [
        ("dwSize", _COORD),
        ("dwCursorPosition", _COORD),
        ("wAttributes", ctypes.c_ushort),
        ("srWindow", _SMALL_RECT),
        ("dwMaximumWindowSize", _COORD),
    ]


_k32.GetConsoleScreenBufferInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_CONSOLE_SCREEN_BUFFER_INFO)]
_k32.GetConsoleScreenBufferInfo.restype = wintypes.BOOL
_k32.ReadConsoleOutputCharacterW.argtypes = [
    wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, _COORD, ctypes.POINTER(wintypes.DWORD),
]
_k32.ReadConsoleOutputCharacterW.restype = wintypes.BOOL


def read_console_screen(pid: int, lines: int = 300) -> str:
    """Reads the last `lines` rows straight out of the target process's own
    console screen buffer -- i.e. exactly what's currently on screen there,
    including text that never gets written to any log file. Same
    attach/detach dance as send_console_keys, guarded by the same lock."""
    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    OPEN_EXISTING = 3
    INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

    with _console_io_lock:
        _k32.FreeConsole()
        try:
            if not _k32.AttachConsole(pid):
                err = ctypes.get_last_error()
                raise RuntimeError(f"could not attach to that console (win32 error {err})")
            handle = None
            try:
                handle = _k32.CreateFileW(
                    "CONOUT$", GENERIC_READ | GENERIC_WRITE,
                    FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None,
                )
                if handle == INVALID_HANDLE_VALUE:
                    raise RuntimeError(f"could not open CONOUT$ (win32 error {ctypes.get_last_error()})")
                info = _CONSOLE_SCREEN_BUFFER_INFO()
                if not _k32.GetConsoleScreenBufferInfo(handle, ctypes.byref(info)):
                    raise RuntimeError(f"GetConsoleScreenBufferInfo failed (win32 error {ctypes.get_last_error()})")
                width = info.dwSize.X
                cursor_y = info.dwCursorPosition.Y
                start_row = max(0, cursor_y - lines + 1)
                row_count = cursor_y - start_row + 1
                buf = ctypes.create_unicode_buffer(width * row_count)
                read = wintypes.DWORD(0)
                ok = _k32.ReadConsoleOutputCharacterW(
                    handle, buf, width * row_count, _COORD(0, start_row), ctypes.byref(read),
                )
                if not ok:
                    raise RuntimeError(f"ReadConsoleOutputCharacterW failed (win32 error {ctypes.get_last_error()})")
                text = buf.value
            finally:
                if handle:
                    _k32.CloseHandle(handle)
                _k32.FreeConsole()
        finally:
            _k32.AttachConsole(ATTACH_PARENT_PROCESS)

    rows = [text[i * width:(i + 1) * width].rstrip() for i in range(row_count)]
    return "\n".join(rows).rstrip("\n")


def send_input(key: str, text: str):
    if key not in ("world", "world2"):
        raise RuntimeError("only Worldserver's console accepts typed commands")
    svc = services()[key]
    pid = service_pid(key)
    if not pid:
        raise RuntimeError(f"{svc['label']} isn't running -- start it first")
    send_console_keys(pid, text)


# ---- process health: CPU / RAM / GPU ---------------------------------------

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_PROCESS_VM_READ = 0x0010
_NUM_CPUS = os.cpu_count() or 1


class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", wintypes.DWORD),
        ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_uint64),
        ("ullAvailPhys", ctypes.c_uint64),
        ("ullTotalPageFile", ctypes.c_uint64),
        ("ullAvailPageFile", ctypes.c_uint64),
        ("ullTotalVirtual", ctypes.c_uint64),
        ("ullAvailVirtual", ctypes.c_uint64),
        ("ullAvailExtendedVirtual", ctypes.c_uint64),
    ]


_k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_k32.OpenProcess.restype = wintypes.HANDLE
_k32.GetProcessTimes.argtypes = [
    wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME),
    ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME),
]
_k32.GetProcessTimes.restype = wintypes.BOOL
_k32.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(_MEMORYSTATUSEX)]
_k32.GlobalMemoryStatusEx.restype = wintypes.BOOL

_psapi = ctypes.WinDLL("psapi", use_last_error=True)
_psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
_psapi.GetProcessMemoryInfo.restype = wintypes.BOOL

_TOTAL_RAM_BYTES = None


def _total_ram_bytes() -> int:
    global _TOTAL_RAM_BYTES
    if _TOTAL_RAM_BYTES is None:
        stat = _MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
        _TOTAL_RAM_BYTES = stat.ullTotalPhys if _k32.GlobalMemoryStatusEx(ctypes.byref(stat)) else 0
    return _TOTAL_RAM_BYTES


def _filetime_to_ticks(ft) -> int:
    return (ft.dwHighDateTime << 32) | ft.dwLowDateTime


_cpu_samples = {}
_cpu_lock = threading.Lock()


def get_process_health(service_key: str, pid: int):
    """Returns (cpu_percent, ram_bytes), either of which may be None if it
    couldn't be read. CPU needs two samples to compute a rate -- like
    psutil's non-blocking cpu_percent(), the first call for a given pid
    (e.g. right after the service (re)starts) returns None; the dashboard
    polls /api/status every 5s, so the next call already has a prior sample
    to diff against, with no added latency."""
    handle = _k32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION | _PROCESS_VM_READ, False, pid)
    if not handle:
        return None, None
    try:
        ram = None
        mem = _PROCESS_MEMORY_COUNTERS()
        mem.cb = ctypes.sizeof(mem)
        if _psapi.GetProcessMemoryInfo(handle, ctypes.byref(mem), mem.cb):
            ram = mem.WorkingSetSize

        cpu_percent = None
        creation, exit_, kernel, user = (wintypes.FILETIME() for _ in range(4))
        if _k32.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(exit_), ctypes.byref(kernel), ctypes.byref(user)):
            total_ticks = _filetime_to_ticks(kernel) + _filetime_to_ticks(user)
            now = time.monotonic()
            with _cpu_lock:
                prev = _cpu_samples.get(service_key)
                _cpu_samples[service_key] = (pid, total_ticks, now)
            if prev and prev[0] == pid:
                _, prev_ticks, prev_time = prev
                elapsed = now - prev_time
                if elapsed > 0:
                    cpu_seconds = (total_ticks - prev_ticks) / 1e7
                    cpu_percent = round(min(100.0, max(0.0, cpu_seconds / elapsed / _NUM_CPUS * 100)), 1)
        return cpu_percent, ram
    finally:
        _k32.CloseHandle(handle)


# ---- service icons (extracted straight from the real .exe files) ----------

ICON_CACHE_DIR = os.path.join(DASHBOARD_DIR, "icon_cache")


LAUNCHER_EXE = r"E:\Games\Ascension\Ascension Launcher.exe"


def _service_exe_path(key: str) -> str:
    if key == "launcher":
        return SETTINGS.get("launcher_exe") or LAUNCHER_EXE
    if key == "mysql":
        return os.path.join(SETTINGS["mysql_dir"], "bin", "mysqld.exe")
    return services()[key].get("exe") or os.path.join(SETTINGS["install_dir"], services()[key]["process"])


def _ps_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def extract_icon_png(exe_path: str, out_path: str) -> bool:
    """Pulls the embedded icon out of a .exe and saves it as a PNG, via a
    one-off PowerShell call into .NET's System.Drawing -- no extra Python
    packages needed to decode a .ico/.exe icon resource."""
    if not os.path.exists(exe_path):
        return False
    script = (
        "Add-Type -AssemblyName System.Drawing; "
        f"$icon = [System.Drawing.Icon]::ExtractAssociatedIcon({_ps_quote(exe_path)}); "
        "if ($null -eq $icon) { exit 1 }; "
        "$bmp = $icon.ToBitmap(); "
        f"$bmp.Save({_ps_quote(out_path)}, [System.Drawing.Imaging.ImageFormat]::Png); "
        "$bmp.Dispose(); $icon.Dispose()"
    )
    try:
        result = _run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=15,
        )
        return result.returncode == 0 and os.path.exists(out_path)
    except Exception:
        return False


def browse_path(kind: str, title: str, start: str = "", filter_: str = "Programs (*.exe)|*.exe"):
    """Native Windows folder/file picker via a one-off PowerShell WinForms dialog -- same
    no-extra-packages trick as extract_icon_png. WinForms needs an STA thread, which
    powershell.exe isn't by default, hence -sta. Blocks until the user picks or cancels
    (fine: this only ever runs from a single button click awaited by the browser).
    Returns the chosen path, or None if canceled/failed."""
    start_expr = _ps_quote(start) if start and os.path.isdir(start) else "[Environment]::GetFolderPath('MyComputer')"
    if kind == "folder":
        script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$d = New-Object System.Windows.Forms.FolderBrowserDialog; "
            f"$d.Description = {_ps_quote(title)}; "
            f"try {{ $d.SelectedPath = {start_expr} }} catch {{}}; "
            "$d.ShowNewFolderButton = $false; "
            "if ($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $d.SelectedPath }"
        )
    else:
        start_dir = _ps_quote(start if start and os.path.isdir(start) else "")
        script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$d = New-Object System.Windows.Forms.OpenFileDialog; "
            f"$d.Title = {_ps_quote(title)}; $d.Filter = {_ps_quote(filter_)}; "
            f"$d.InitialDirectory = {start_dir}; "
            "if ($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $d.FileName }"
        )
    try:
        result = _run(
            ["powershell", "-sta", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=120,
        )
        path = (result.stdout or "").strip()
        return path or None
    except Exception:
        return None


def detect_setup(current: dict):
    """Best-effort guesses for first-run setup, layered on top of whatever is already saved --
    never overwrites a value the user (or a previous run) already set. Only looks at paths
    already on disk; never fabricates one."""
    out = dict(current)
    install = out.get("install_dir") or DEFAULT_SETTINGS["install_dir"]
    if os.path.isfile(os.path.join(install, "worldserver.exe")):
        out["install_dir"] = install
        out.setdefault("configs_dir", os.path.join(install, "configs"))
    if not out.get("mysql_dir") or not os.path.isfile(os.path.join(out["mysql_dir"], "bin", "mysql.exe")):
        # Look one level above the install dir for a sibling "mysql-*" folder (how this
        # project ships MySQL alongside the server -- see azerothcore_coa_fork memory).
        parent = os.path.dirname(install)
        try:
            for name in sorted(os.listdir(parent)):
                if name.lower().startswith("mysql") and os.path.isfile(os.path.join(parent, name, "bin", "mysql.exe")):
                    out["mysql_dir"] = os.path.join(parent, name)
                    out.setdefault("mysql_data_dir", os.path.join(parent, "mysql-data"))
                    break
        except OSError:
            pass
    return out


def setup_status(settings: dict):
    """What the setup wizard still needs, checked against the actual filesystem/DB -- not
    just whether a settings file exists, so a settings.json with stale/moved paths is also
    caught (the whole point: a page silently failing later is worse than one clear checklist)."""
    install = settings.get("install_dir") or ""
    mysql_dir = settings.get("mysql_dir") or ""
    auth_exe = (settings.get("authserver_exe") or "").strip() or os.path.join(install, "authserver.exe")
    world_exe = (settings.get("worldserver_exe") or "").strip() or os.path.join(install, "worldserver.exe")
    checks = {
        "install_dir": os.path.isfile(world_exe) and os.path.isfile(auth_exe),
        "mysql_dir": os.path.isfile(os.path.join(mysql_dir, "bin", "mysql.exe")),
        "client_exe": os.path.isfile(settings.get("client_exe") or ""),
    }
    return {"ok": all(checks.values()), "checks": checks}


def test_mysql_connection(mysql_dir, host, port, user, password):
    mysql_exe = os.path.join(mysql_dir, "bin", "mysql.exe")
    if not os.path.isfile(mysql_exe):
        return {"ok": False, "error": "mysql.exe not found in that folder (expected <folder>\\bin\\mysql.exe)"}
    try:
        result = _run(
            [mysql_exe, f"-h{host}", f"-P{port}", f"-u{user}", f"-p{password}", "-e", "SELECT 1"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return {"ok": True}
        return {"ok": False, "error": (result.stderr or "connection failed").strip().splitlines()[-1]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_icon_path(key: str):
    os.makedirs(ICON_CACHE_DIR, exist_ok=True)
    out_path = os.path.join(ICON_CACHE_DIR, f"{key}.png")
    exe_path = _service_exe_path(key)
    try:
        stale = os.path.exists(exe_path) and (
            not os.path.exists(out_path) or os.path.getmtime(exe_path) > os.path.getmtime(out_path)
        )
    except OSError:
        stale = not os.path.exists(out_path)
    if (stale or not os.path.exists(out_path)) and not extract_icon_png(exe_path, out_path):
        return out_path if os.path.exists(out_path) else None
    return out_path if os.path.exists(out_path) else None


# ---- MySQL ad-hoc SQL (console tab + admin helpers) ------------------------

MYSQL_TRANSCRIPT = []
MYSQL_TRANSCRIPT_MAX = 400
MYSQL_LOCK = threading.Lock()


def _mysql_exe():
    return os.path.join(SETTINGS["mysql_dir"], "bin", "mysql.exe")


def query_rows(database: str, sql: str):
    """Runs SQL against `database` via the mysql CLI in batch mode and returns
    a list of dicts (tab-separated output, first line = column names)."""
    cmd = [
        _mysql_exe(),
        f"-h{SETTINGS['mysql_host']}",
        f"-P{SETTINGS['mysql_port']}",
        f"-u{SETTINGS['mysql_user']}",
        f"-p{SETTINGS['mysql_password']}",
        "--batch", "--raw",
        "-D", database,
        "-e", sql,
    ]
    result = _run(cmd, capture_output=True, text=True, timeout=20)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "mysql query failed")
    lines = result.stdout.splitlines()
    if not lines:
        return []
    headers = lines[0].split("\t")
    rows = []
    for line in lines[1:]:
        values = line.split("\t")
        row = {}
        for i, h in enumerate(headers):
            v = values[i] if i < len(values) else None
            row[h] = None if v == "NULL" else v
        rows.append(row)
    return rows


def exec_sql(database: str, sql: str):
    cmd = [
        _mysql_exe(),
        f"-h{SETTINGS['mysql_host']}",
        f"-P{SETTINGS['mysql_port']}",
        f"-u{SETTINGS['mysql_user']}",
        f"-p{SETTINGS['mysql_password']}",
        "-D", database,
        "-e", sql,
    ]
    result = _run(cmd, capture_output=True, text=True, timeout=20)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "mysql statement failed")


def run_sql(query: str) -> str:
    mysql_exe = _mysql_exe()
    cmd = [
        mysql_exe,
        f"-h{SETTINGS['mysql_host']}",
        f"-P{SETTINGS['mysql_port']}",
        f"-u{SETTINGS['mysql_user']}",
        f"-p{SETTINGS['mysql_password']}",
        "-e", query,
    ]
    try:
        result = _run(cmd, capture_output=True, text=True, timeout=20)
        out = (result.stdout or "") + (result.stderr or "")
    except Exception as e:
        out = f"(failed to run mysql client: {e})"
    with MYSQL_LOCK:
        MYSQL_TRANSCRIPT.append(f">>> {query}")
        MYSQL_TRANSCRIPT.extend(out.rstrip("\n").splitlines())
        del MYSQL_TRANSCRIPT[:-MYSQL_TRANSCRIPT_MAX]
    return out


# ---- Server Admin helpers --------------------------------------------------

def list_bans():
    account = query_rows(
        "acore_auth",
        "SELECT ab.id, a.username, ab.bandate, ab.unbandate, ab.bannedby, ab.banreason "
        "FROM account_banned ab LEFT JOIN account a ON a.id = ab.id WHERE ab.active = 1 ORDER BY ab.bandate DESC",
    )
    ip = query_rows(
        "acore_auth",
        "SELECT ip, bandate, unbandate, bannedby, banreason FROM ip_banned "
        "WHERE unbandate = bandate OR unbandate > UNIX_TIMESTAMP() ORDER BY bandate DESC",
    )
    character = query_rows(
        "acore_characters",
        "SELECT cb.guid, c.name, cb.bandate, cb.unbandate, cb.bannedby, cb.banreason "
        "FROM character_banned cb LEFT JOIN characters c ON c.guid = cb.guid WHERE cb.active = 1 ORDER BY cb.bandate DESC",
    )
    muted = query_rows(
        "acore_auth",
        "SELECT am.guid, a.username, am.mutedate, am.mutetime, am.mutedby, am.mutereason "
        "FROM account_muted am LEFT JOIN account a ON a.id = am.guid ORDER BY am.mutedate DESC",
    )
    return {"account": account, "ip": ip, "character": character, "muted": muted}


def unban(ban_type: str, key: str):
    if ban_type == "account":
        exec_sql("acore_auth", f"UPDATE account_banned SET active = 0 WHERE id = {int(key)}")
    elif ban_type == "ip":
        safe_ip = key.replace("'", "")
        exec_sql("acore_auth", f"DELETE FROM ip_banned WHERE ip = '{safe_ip}'")
    elif ban_type == "character":
        exec_sql("acore_characters", f"UPDATE character_banned SET active = 0 WHERE guid = {int(key)}")
    else:
        raise ValueError("unknown ban type")


def unmute(guid: str):
    exec_sql("acore_auth", f"DELETE FROM account_muted WHERE guid = {int(guid)}")


_PERMANENT_MUTE_SECONDS = 10 * 365 * 24 * 3600  # account_muted.mutetime is a duration, not an expiry
                                                 # date, so there's no "unbandate == bandate" trick for
                                                 # permanent like ban tables have -- 10 years stands in.


def add_mute(username: str, reason: str, duration_seconds: int, muted_by: str = "Dashboard"):
    rows = query_rows("acore_auth", f"SELECT id FROM account WHERE username = '{username.replace(chr(39), '')}'")
    if not rows:
        raise ValueError("account not found")
    acc_id = rows[0]["id"]
    reason_esc = reason.replace("'", "''")
    by_esc = muted_by.replace("'", "''")
    dur = int(duration_seconds) or _PERMANENT_MUTE_SECONDS
    exec_sql(
        "acore_auth",
        f"REPLACE INTO account_muted (guid, mutedate, mutetime, mutedby, mutereason) "
        f"VALUES ({acc_id}, UNIX_TIMESTAMP(), {dur}, '{by_esc}', '{reason_esc}')",
    )


def add_ban(target_type: str, name: str, reason: str, duration_seconds: int, banned_by: str = "Dashboard"):
    reason_esc = reason.replace("'", "''")
    by_esc = banned_by.replace("'", "''")
    dur = int(duration_seconds)
    if target_type == "account":
        rows = query_rows("acore_auth", f"SELECT id FROM account WHERE username = '{name.replace(chr(39), '')}'")
        if not rows:
            raise ValueError("account not found")
        acc_id = rows[0]["id"]
        unban_expr = "UNIX_TIMESTAMP()" if dur == 0 else f"UNIX_TIMESTAMP() + {dur}"
        exec_sql(
            "acore_auth",
            f"INSERT INTO account_banned (id, bandate, unbandate, bannedby, banreason, active) "
            f"VALUES ({acc_id}, UNIX_TIMESTAMP(), {unban_expr}, '{by_esc}', '{reason_esc}', 1)",
        )
    elif target_type == "ip":
        ip_esc = name.replace("'", "")
        unban_expr = "bandate" if dur == 0 else f"UNIX_TIMESTAMP() + {dur}"
        exec_sql(
            "acore_auth",
            f"INSERT INTO ip_banned (ip, bandate, unbandate, bannedby, banreason) "
            f"VALUES ('{ip_esc}', UNIX_TIMESTAMP(), {unban_expr}, '{by_esc}', '{reason_esc}')",
        )
    elif target_type == "character":
        rows = query_rows("acore_characters", f"SELECT guid FROM characters WHERE name = '{name.replace(chr(39), '')}'")
        if not rows:
            raise ValueError("character not found")
        guid = rows[0]["guid"]
        unban_expr = "UNIX_TIMESTAMP()" if dur == 0 else f"UNIX_TIMESTAMP() + {dur}"
        exec_sql(
            "acore_characters",
            f"INSERT INTO character_banned (guid, bandate, unbandate, bannedby, banreason, active) "
            f"VALUES ({guid}, UNIX_TIMESTAMP(), {unban_expr}, '{by_esc}', '{reason_esc}', 1)",
        )
    else:
        raise ValueError("unknown target type")


def list_tickets(include_closed=False):
    where = "" if include_closed else "WHERE completed = 0"
    return query_rows(
        "acore_characters",
        f"SELECT id, name, description, createTime, completed, escalated FROM gm_ticket {where} ORDER BY createTime DESC",
    )


def close_ticket(ticket_id: int):
    exec_sql("acore_characters", f"UPDATE gm_ticket SET completed = 1 WHERE id = {int(ticket_id)}")


def set_gmlevel(username: str, gmlevel: int, realm_id: int = -1):
    rows = query_rows("acore_auth", f"SELECT id FROM account WHERE username = '{username.replace(chr(39), '')}'")
    if not rows:
        raise ValueError("account not found")
    acc_id = rows[0]["id"]
    exec_sql(
        "acore_auth",
        f"REPLACE INTO account_access (id, gmlevel, RealmID, comment) "
        f"VALUES ({acc_id}, {int(gmlevel)}, {int(realm_id)}, 'set via dashboard')",
    )


def list_realms():
    return query_rows("acore_auth", "SELECT id, name, address, port, flag, population, gamebuild FROM realmlist ORDER BY id")


def update_realm(realm_id: int, name: str, address: str, port: int, flag: int):
    name_esc = name.replace("'", "''")
    addr_esc = address.replace("'", "")
    exec_sql(
        "acore_auth",
        f"UPDATE realmlist SET name = '{name_esc}', address = '{addr_esc}', port = {int(port)}, flag = {int(flag)} WHERE id = {int(realm_id)}",
    )


ACCOUNT_PAGE_SIZE = 10


def _sql_text(value: str) -> str:
    return str(value).replace("\\", "").replace("'", "''")


def list_accounts(query: str = "", page: int = 1, include_bots: bool = False):
    """One page of accounts (10 per page) with GM level and character count. Bot accounts (RNDBOT...)
    are hidden unless asked for: a bot population would bury the real accounts."""
    where = []
    if query:
        like = _sql_text(query).replace("%", "").replace("_", "\\_")
        where.append(f"(a.username LIKE '%{like}%' OR a.email LIKE '%{like}%')")
    if not include_bots:
        where.append("a.username NOT LIKE 'RNDBOT%'")
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    total = int(query_rows("acore_auth", f"SELECT COUNT(*) AS n FROM account a {clause}")[0]["n"])
    pages = max(1, -(-total // ACCOUNT_PAGE_SIZE))
    page = min(max(1, page), pages)
    rows = query_rows(
        "acore_auth",
        "SELECT a.id, a.username, a.email, a.expansion, a.locked, a.online, a.last_login, a.last_ip, a.joindate, "
        "IFNULL((SELECT MAX(gmlevel) FROM account_access x WHERE x.id = a.id), 0) AS gmlevel, "
        "(SELECT COUNT(*) FROM acore_characters.characters c WHERE c.account = a.id) AS characters "
        f"FROM account a {clause} ORDER BY a.id LIMIT {ACCOUNT_PAGE_SIZE} OFFSET {(page - 1) * ACCOUNT_PAGE_SIZE}",
    )
    if not service_running("world"):
        # A crash leaves account.online = 1 behind: with the worldserver down nobody is online.
        for row in rows:
            row["online"] = "0"
    return {"rows": rows, "total": total, "page": page, "pages": pages, "pageSize": ACCOUNT_PAGE_SIZE}


def update_account(account_id: int, email: str, gmlevel: int, expansion: int, locked: int, password: str = ""):
    """Edits one account. The password goes through the worldserver console (it needs the SRP6 hash, which
    only the core computes), so it needs a running worldserver; it is checked first so nothing is half-saved."""
    rows = query_rows("acore_auth", f"SELECT username FROM account WHERE id = {int(account_id)}")
    if not rows:
        raise ValueError("account not found")
    username = rows[0]["username"]
    password = password.strip()
    if password:
        if " " in password:
            raise ValueError("the password cannot contain spaces")
        if not is_running("worldserver.exe"):
            raise ValueError("start the Worldserver to change a password (it is set through its console)")
    exec_sql(
        "acore_auth",
        f"UPDATE account SET email = '{_sql_text(email)}', expansion = {int(expansion)}, locked = {1 if int(locked) else 0} "
        f"WHERE id = {int(account_id)}",
    )
    if int(gmlevel) > 0:
        exec_sql(
            "acore_auth",
            f"REPLACE INTO account_access (id, gmlevel, RealmID, comment) "
            f"VALUES ({int(account_id)}, {int(gmlevel)}, -1, 'set via dashboard')",
        )
    else:
        exec_sql("acore_auth", f"DELETE FROM account_access WHERE id = {int(account_id)}")
    if password:
        send_input("world", f"account set password {username} {password} {password}")


ITEM_PAGE_SIZE = 10
ITEM_ICON_DIR = os.path.join(DASHBOARD_DIR, "item_icons")
_DISPLAY_ICONS = None


def display_icons():
    """displayid -> icon file name (lower case, no extension), from ItemDisplayInfo.dbc field 5."""
    global _DISPLAY_ICONS
    if _DISPLAY_ICONS is None:
        import struct
        _DISPLAY_ICONS = {}
        path = os.path.join(SETTINGS["install_dir"], "dbc", "ItemDisplayInfo.dbc")
        try:
            raw = open(path, "rb").read()
            magic, records, fields, size, _ = struct.unpack("<4siiii", raw[:20])
            if magic == b"WDBC":
                body, block = raw[20:20 + records * size], raw[20 + records * size:]
                for i in range(records):
                    row = i * size
                    offset = struct.unpack_from("<I", body, row + 20)[0]
                    if offset:
                        name = block[offset:block.index(b"\0", offset)].decode("utf-8", "replace").lower()
                        if name:
                            _DISPLAY_ICONS[struct.unpack_from("<I", body, row)[0]] = name
        except OSError:
            pass
    return _DISPLAY_ICONS
ITEM_CLASSES = {0: "Consumable", 1: "Container", 2: "Weapon", 3: "Gem", 4: "Armor", 5: "Reagent", 6: "Projectile",
                7: "Trade goods", 9: "Recipe", 11: "Quiver", 12: "Quest", 13: "Key", 15: "Misc", 16: "Glyph"}


def list_items(query: str = "", page: int = 1, quality: str = "", item_class: str = "", slot: str = "",
               min_level: str = "", max_level: str = "", hide_test: bool = True, sub: str = ""):
    """One page of item_template matches (10 per page). Everything is checked or cast to a number, and the
    search text is escaped, before it goes into the SQL."""
    where = []
    if query:
        if query.isdigit():
            where.append(f"entry = {int(query)}")
        else:
            like = _sql_text(query).replace("%", "").replace("_", "\\_")
            where.append(f"name LIKE '%{like}%'")
    for column, value in (("Quality", quality), ("class", item_class), ("InventoryType", slot)):
        if value != "":
            where.append(f"{column} = {int(value)}")
    if sub != "":  # "<class>:<subclass>", e.g. "2:7" = swords
        sub_class, sub_sub = sub.split(":")
        where.append(f"class = {int(sub_class)} AND subclass = {int(sub_sub)}")
    if min_level != "":
        where.append(f"RequiredLevel >= {int(min_level)}")
    if max_level != "":
        where.append(f"RequiredLevel <= {int(max_level)}")
    if hide_test:
        where.append("name NOT LIKE '%DEPRECATED%' AND name NOT LIKE '%\\_%' AND name <> ''")
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    total = int(query_rows("acore_world", f"SELECT COUNT(*) AS n FROM item_template {clause}")[0]["n"])
    pages = max(1, -(-total // ITEM_PAGE_SIZE))
    page = min(max(1, page), pages)
    prefix = ""
    if query and not query.isdigit():
        prefix = f"name LIKE '{_sql_text(query).replace('%', '').replace('_', chr(92) + '_')}%' DESC, "
    rows = query_rows(
        "acore_world",
        "SELECT entry, name, Quality, class, subclass, InventoryType, ItemLevel, RequiredLevel, stackable, displayid "
        f"FROM item_template {clause} ORDER BY {prefix}Quality DESC, ItemLevel DESC, entry "
        f"LIMIT {ITEM_PAGE_SIZE} OFFSET {(page - 1) * ITEM_PAGE_SIZE}",
    )
    for row in rows:
        row["type"] = ITEM_CLASSES.get(int(row["class"]), "Class %s" % row["class"])
        row["icon"] = display_icons().get(int(row.pop("displayid") or 0), "")
    return {"rows": rows, "total": total, "page": page, "pages": pages, "pageSize": ITEM_PAGE_SIZE}


def list_real_characters():
    return [r["name"] for r in query_rows(
        "acore_characters",
        "SELECT c.name FROM characters c JOIN acore_auth.account a ON a.id = c.account "
        "WHERE a.username NOT LIKE 'RNDBOT%' ORDER BY c.name")]


def give_item(character: str, item_id: int, count: int):
    """Mails the item to the character with the worldserver's `send items`: the console has no selected
    player, so `additem` cannot work from there. The character does not need to be online."""
    if not re.match(r"^[A-Za-z]+(?: [A-Za-z]+)?$", character):
        raise ValueError("invalid character name")
    if not query_rows("acore_characters", f"SELECT guid FROM characters WHERE name = '{_sql_text(character)}'"):
        raise ValueError(f"character {character} not found")
    item = query_rows("acore_world", f"SELECT name, stackable FROM item_template WHERE entry = {int(item_id)}")
    if not item:
        raise ValueError(f"item {item_id} not found")
    limit = max(1, int(item[0]["stackable"] or 1))
    count = min(max(1, int(count)), limit)
    if not service_running("world"):
        raise ValueError("the Worldserver isn't running -- start it first")
    send_input("world", f'send items "{character}" "Dashboard" "Sent from the dashboard" {int(item_id)}:{count}')
    return {"item": item[0]["name"], "count": count}


# The 19 real equipment slots (character_inventory.slot, bag=0) -- EQUIPMENT_SLOT_* in the core.
# Slots >= 19 with bag=0 are backpack/general inventory, not gear.
EQUIP_SLOTS = [
    (0, "Head"), (1, "Neck"), (2, "Shoulder"), (14, "Back"), (4, "Chest"), (3, "Shirt"), (18, "Tabard"),
    (8, "Wrist"), (9, "Hands"), (5, "Waist"), (6, "Legs"), (7, "Feet"),
    (10, "Finger 1"), (11, "Finger 2"), (12, "Trinket 1"), (13, "Trinket 2"),
    (15, "Main Hand"), (16, "Off Hand"), (17, "Ranged"),
]

# WoW's standard race IDs -> the lowercase folder name used under 3dmodels/ in the Armory tab's
# glTF model paths (matches the naming wow.export uses). Ascension's own races aren't in this
# base set (7-31+ range per bots_stats.py's BASE_CLASSES note) -- those fall back to "unknown".
RACE_NAMES = {1: "human", 2: "orc", 3: "dwarf", 4: "nightelf", 5: "undead", 6: "tauren",
             7: "gnome", 8: "troll", 10: "bloodelf", 11: "draenei"}

# Same split squidbots.py's own ALLIANCE_RACES uses (kept as a separate copy since this module
# doesn't import squidbots.py -- they're two independent processes): everything not in this set,
# including Ascension's own custom races, counts as Horde.
ALLIANCE_RACES = {1, 3, 4, 7, 11}

# Same spec-id sets as squidbots.py's own HEAL/TANK (role_of()): a character's role is derived
# purely from its active spec id, no spec *name* needed -- useful here since the private
# coa-level-builds.json that supplies spec names doesn't exist on every install (see
# list_characters()'s role filter, which works even without it).
HEAL_SPECS = {6, 31, 37, 40, 43, 51, 98, 101}
TANK_SPECS = {9, 17, 21, 22, 48, 52, 57, 60, 96, 97, 99, 100}


def _class_names():
    from bots_stats import BASE_CLASSES
    classes = dict(BASE_CLASSES)
    classes.update({int(r["class"]): r["client_name"]
                    for r in query_rows("acore_world", "SELECT class, client_name FROM ascension_custom_class")})
    return classes


def search_characters(query: str):
    """Any character -- bot or real player -- matching a name search, for the Armory page's
    picker. Bots (RNDBOT% accounts) are flagged so the UI can tell them apart, but nothing is
    filtered out: a real player can be any class, so unlike the old bot-only search this no
    longer restricts to CoA's custom classes (> 11)."""
    like = _sql_text(query).replace("%", "").replace("_", "\\_")
    rows = query_rows(
        "acore_characters",
        "SELECT c.name, c.level, c.class, c.online, (a.username LIKE 'RNDBOT%') AS is_bot "
        "FROM characters c JOIN acore_auth.account a ON a.id = c.account "
        f"WHERE c.name LIKE '%{like}%' "
        "ORDER BY c.online DESC, c.name LIMIT 20",
    )
    classes = _class_names()
    for r in rows:
        r["class"] = classes.get(int(r.pop("class")), "?")
        r["online"] = r["online"] == "1"
        r["bot"] = r.pop("is_bot") == "1"
    return rows


CHAR_PAGE_SIZE = 100


def list_characters(query: str = "", page: int = 1, min_level: str = "", max_level: str = "",
                     class_id: str = "", role: str = ""):
    """One page (100) of every character -- bot or real player -- optionally narrowed by a name
    search and by level range / class / role, for the Armory page's "browse all" panel. Complements
    search_characters(), which stays a small (20-row) live-typing autocomplete; this is the
    paginated full roster behind a separate "browse" button, per the user's ask for a way to see
    every character, not just search hits, and later to filter that list down."""
    where = []
    if query:
        like = _sql_text(query).replace("%", "").replace("_", "\\_")
        where.append(f"c.name LIKE '%{like}%'")
    if min_level != "":
        where.append(f"c.level >= {int(min_level)}")
    if max_level != "":
        where.append(f"c.level <= {int(max_level)}")
    if class_id != "":
        where.append(f"c.class = {int(class_id)}")
    # Role comes from the active spec id (character_settings, same source squidbots.py's own stats
    # read), not a stored column -- only join that table at all when a role filter is actually in
    # play, so the common case (no role filter) stays a plain two-table query.
    join = ""
    if role in ("tank", "heal", "dps", "none"):
        join = ("LEFT JOIN character_settings s ON s.guid = c.guid AND s.source = 'core.ascension_active_spec'")
        if role == "tank":
            where.append("s.data IN (%s)" % ",".join(str(n) for n in TANK_SPECS))
        elif role == "heal":
            where.append("s.data IN (%s)" % ",".join(str(n) for n in HEAL_SPECS))
        elif role == "dps":
            where.append("s.data IS NOT NULL AND s.data <> '0' AND s.data NOT IN (%s)"
                          % ",".join(str(n) for n in HEAL_SPECS | TANK_SPECS))
        elif role == "none":
            where.append("(s.data IS NULL OR s.data = '0')")
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    total = int(query_rows(
        "acore_characters",
        f"SELECT COUNT(*) AS n FROM characters c JOIN acore_auth.account a ON a.id = c.account {join} {clause}",
    )[0]["n"])
    pages = max(1, -(-total // CHAR_PAGE_SIZE))
    page = min(max(1, page), pages)
    rows = query_rows(
        "acore_characters",
        "SELECT c.name, c.level, c.class, c.race, c.gender, c.online, (a.username LIKE 'RNDBOT%') AS is_bot "
        f"FROM characters c JOIN acore_auth.account a ON a.id = c.account {join} "
        f"{clause} ORDER BY c.online DESC, c.name "
        f"LIMIT {CHAR_PAGE_SIZE} OFFSET {(page - 1) * CHAR_PAGE_SIZE}",
    )
    classes = _class_names()
    for r in rows:
        r["class"] = classes.get(int(r.pop("class")), "?")
        race = int(r.pop("race"))
        r["race"] = RACE_NAMES.get(race, "")
        r["gender"] = "female" if r.pop("gender") == "1" else "male"
        r["faction"] = "alliance" if race in ALLIANCE_RACES else "horde"
        r["online"] = r["online"] == "1"
        r["bot"] = r.pop("is_bot") == "1"
    return {"rows": rows, "total": total, "page": page, "pages": pages, "pageSize": CHAR_PAGE_SIZE,
            "classes": sorted(({"id": cid, "name": name} for cid, name in classes.items()), key=lambda c: c["name"])}


def random_bot():
    """One bot name, for the Armory page's default view -- prefers an online bot (so the default
    view isn't immediately the offline warning banner), falls back to any bot if none are online."""
    rows = query_rows(
        "acore_characters",
        "SELECT c.name FROM characters c JOIN acore_auth.account a ON a.id = c.account "
        "WHERE a.username LIKE 'RNDBOT%' AND c.class > 11 ORDER BY c.online DESC, RAND() LIMIT 1",
    )
    return rows[0]["name"] if rows else None


def character_gear(name: str):
    """A character's (bot or real player) currently equipped items, one row per real gear slot
    (see EQUIP_SLOTS), for the Armory page's paperdoll view. Empty slots are still returned
    (item: null) so the UI can draw all 19 boxes."""
    char = query_rows(
        "acore_characters",
        "SELECT c.guid, c.name, c.level, c.class, c.online, c.race, c.gender, (a.username LIKE 'RNDBOT%') AS is_bot "
        "FROM characters c JOIN acore_auth.account a ON a.id = c.account "
        f"WHERE c.name = '{_sql_text(name)}'",
    )
    if not char:
        raise ValueError(f"character {name} not found")
    char = char[0]
    cls = _class_names().get(int(char["class"]), "?")
    equipped = {int(r["slot"]): r for r in query_rows(
        "acore_characters",
        "SELECT ci.slot, it.entry, it.name, it.Quality, it.displayid, it.InventoryType "
        "FROM character_inventory ci "
        "JOIN item_instance ii ON ii.guid = ci.item "
        "JOIN acore_world.item_template it ON it.entry = ii.itemEntry "
        f"WHERE ci.guid = {int(char['guid'])} AND ci.bag = 0 AND ci.slot BETWEEN 0 AND 18",
    )}
    gear = []
    for slot_id, label in EQUIP_SLOTS:
        row = equipped.get(slot_id)
        item = None
        if row:
            item = {"entry": int(row["entry"]), "name": row["name"], "quality": int(row["Quality"]),
                    "icon": display_icons().get(int(row["displayid"] or 0), "")}
        gear.append({"slot": slot_id, "label": label, "item": item})
    return {"name": char["name"], "level": int(char["level"]), "class": cls,
            "online": char["online"] == "1", "gear": gear, "bot": char["is_bot"] == "1",
            "race": RACE_NAMES.get(int(char["race"]), "unknown"), "gender": "female" if char["gender"] == "1" else "male"}


# Fixed logo files served from the dashboard folder.
STATIC_IMAGES = {"/ascension_logo.webp": "image/webp", "/mysql_logo.png": "image/png",
                 "/sidebar_art.png": "image/png", "/bots_icon.png": "image/png", "/map_icon.png": "image/png"}
KITS_PATH = os.path.join(DASHBOARD_DIR, "kits.json")
MAX_MAIL_ITEMS = 12  # attachments per in-game mail


def load_kits():
    """User-made item kits + favourite items, stored in kits.json next to the dashboard."""
    try:
        with open(KITS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    return _clean_kits(data)


def _clean_kits(data):
    kits, seen = [], set()
    for kit in (data.get("kits") or []):
        name = re.sub(r"[^A-Za-z0-9 _\-]", "", str(kit.get("name", ""))).strip()[:40]
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        items = []
        for it in (kit.get("items") or []):
            try:
                items.append({"id": int(it["id"]), "count": min(max(1, int(it.get("count", 1))), 1000)})
            except (KeyError, TypeError, ValueError):
                continue
        kits.append({"name": name, "items": items})
    favorites = []
    for fid in (data.get("favorites") or []):
        try:
            if int(fid) not in favorites:
                favorites.append(int(fid))
        except (TypeError, ValueError):
            continue
    return {"kits": kits, "favorites": favorites}


def save_kits(data):
    clean = _clean_kits(data)
    with open(KITS_PATH, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2)
    return clean


def kits_with_info():
    """Kits + favourites plus name/quality/icon/stack size for every item id used (from the world DB)."""
    data = load_kits()
    ids = sorted({it["id"] for k in data["kits"] for it in k["items"]} | set(data["favorites"]))
    info = {}
    if ids:
        try:
            rows = query_rows("acore_world", "SELECT entry, name, Quality, stackable, displayid FROM item_template "
                                             f"WHERE entry IN ({','.join(str(i) for i in ids)})")
            icons = display_icons()
            for r in rows:
                info[str(r["entry"])] = {"name": r["name"], "quality": int(r["Quality"]),
                                         "stackable": int(r["stackable"] or 1),
                                         "icon": icons.get(int(r.get("displayid") or 0), "")}
        except Exception:
            pass  # DB down: the page falls back to showing ids
    return {**data, "info": info}


def give_kit(character: str, kit_name: str):
    """Mails every item of a kit (stack sizes respected, 12 attachments per mail)."""
    if not re.match(r"^[A-Za-z]+(?: [A-Za-z]+)?$", character):
        raise ValueError("invalid character name")
    kit = next((k for k in load_kits()["kits"] if k["name"].lower() == kit_name.lower()), None)
    if not kit:
        raise ValueError(f"kit {kit_name} not found")
    if not kit["items"]:
        raise ValueError("the kit is empty")
    if not query_rows("acore_characters", f"SELECT guid FROM characters WHERE name = '{_sql_text(character)}'"):
        raise ValueError(f"character {character} not found")
    ids = sorted({it["id"] for it in kit["items"]})
    rows = query_rows("acore_world", f"SELECT entry, stackable FROM item_template WHERE entry IN ({','.join(str(i) for i in ids)})")
    stack = {int(r["entry"]): max(1, int(r["stackable"] or 1)) for r in rows}
    missing = [i for i in ids if i not in stack]
    if missing:
        raise ValueError("items not found in the database: " + ", ".join(str(i) for i in missing))
    if not service_running("world"):
        raise ValueError("the Worldserver isn't running -- start it first")
    parts = []
    for it in kit["items"]:
        left = it["count"]
        while left > 0:
            n = min(left, stack[it["id"]])
            parts.append(f"{it['id']}:{n}")
            left -= n
    mails = 0
    for i in range(0, len(parts), MAX_MAIL_ITEMS):
        send_input("world", f'send items "{character}" "Dashboard" "Kit: {kit["name"]}" ' + " ".join(parts[i:i + MAX_MAIL_ITEMS]))
        mails += 1
    return {"kit": kit["name"], "items": len(kit["items"]), "mails": mails}


def create_account(username: str, password: str):
    safe_user = username.replace(" ", "")
    safe_pass = password.replace(" ", "")
    send_input("world", f"account create {safe_user} {safe_pass}")


_MAP_ZONES = None
_MAP_CLASSES = None


# CoA is scaled to vanilla: Eastern Kingdoms and Kalimdor only (no Outland 530, Northrend 571, Ebon Hold 609).
VANILLA_MAPS = {0, 1}
SHOW_ALL_MAPS = False  # set True to: list every map that has a picture (instances, dev maps, TBC/WotLK); set False to filter again


def _walkable_maps():
    """Open-world maps a player can actually stand on: Map.dbc InstanceType 0 and terrain files in maps/.
    Drops instances, battlegrounds and Ascension's dev/test maps (AdtDevMap, SpellDevMap, ...)."""
    import struct
    terrain = set()
    maps_dir = os.path.join(SETTINGS["install_dir"], "maps")
    if os.path.isdir(maps_dir):
        terrain = {int(f[:3]) for f in os.listdir(maps_dir) if f.endswith(".map") and f[:3].isdigit()}
    result = set()
    for folder in (os.path.join(SETTINGS["install_dir"], "data", "dbc"), os.path.join(SETTINGS["install_dir"], "dbc")):
        path = os.path.join(folder, "Map.dbc")
        if not os.path.exists(path):
            continue
        raw = open(path, "rb").read()
        magic, records, fields, size, _ = struct.unpack("<4siiii", raw[:20])
        if magic != b"WDBC":
            continue
        for i in range(records):
            u = struct.unpack_from("<%dI" % fields, raw, 20 + i * size)
            if u[2] == 0 and u[0] in terrain and u[0] in VANILLA_MAPS:
                result.add(u[0])
        break
    return result


def map_zones():
    """Zones that have a background image in sidekick/wf-maps, with their world-coordinate bounds
    from WorldMapArea.dbc (id, map, area, name, left, right, top, bottom, ...)."""
    global _MAP_ZONES
    if _MAP_ZONES is not None:
        return _MAP_ZONES
    import struct
    zones = {}
    img_dir = os.path.join(DASHBOARD_DIR, "worldmaps")
    have = {f[:-4] for f in os.listdir(img_dir) if f.endswith(".jpg")} if os.path.isdir(img_dir) else set()
    walkable = _walkable_maps()
    for folder in (os.path.join(SETTINGS["install_dir"], "data", "dbc"), os.path.join(SETTINGS["install_dir"], "dbc")):
        path = os.path.join(folder, "WorldMapArea.dbc")
        if not os.path.exists(path):
            continue
        raw = open(path, "rb").read()
        magic, records, fields, size, _ = struct.unpack("<4siiii", raw[:20])
        if magic != b"WDBC" or fields < 8:
            continue
        body, block = raw[20:20 + records * size], raw[20 + records * size:]
        for i in range(records):
            u = struct.unpack_from("<%dI" % fields, body, i * size)
            f = struct.unpack_from("<%df" % fields, body, i * size)
            key = ("c%d" % u[1]) if u[2] == 0 else str(u[2])
            if key in have and (SHOW_ALL_MAPS or u[1] in walkable) and f[4] != f[5] and f[6] != f[7]:
                name = block[u[3]:block.index(b"\0", u[3])].decode("utf-8", "replace")
                zones[key] = {"map": u[1], "name": name, "left": f[4], "right": f[5], "top": f[6], "bottom": f[7]}
        break
    _MAP_ZONES = zones
    return zones


_HEIGHT_GRIDS = {}


def ground_height(map_id: int, x: float, y: float):
    """Terrain height at world x/y from the server's maps/*.map files (bilinear over the 129x129 grid), or None."""
    import math
    import struct
    size = 533.33333
    gx, gy = int(32 - x / size), int(32 - y / size)
    key = (map_id, gx, gy)
    if key not in _HEIGHT_GRIDS:
        grid = None
        path = os.path.join(SETTINGS["install_dir"], "maps", "%03d%02d%02d.map" % key)
        if os.path.isfile(path):
            with open(path, "rb") as f:
                head = f.read(44)
                off = struct.unpack_from("<I", head, 20)[0]
                f.seek(off)
                _, flags, base, top = struct.unpack("<4sIff", f.read(16))
                if not flags & 1:
                    if flags & 2:
                        raw = struct.unpack("<%dH" % (129 * 129), f.read(129 * 129 * 2))
                        grid = [base + v * (top - base) / 65535 for v in raw]
                    elif flags & 4:
                        raw = f.read(129 * 129)
                        grid = [base + v * (top - base) / 255 for v in raw]
                    else:
                        grid = list(struct.unpack("<%df" % (129 * 129), f.read(129 * 129 * 4)))
        _HEIGHT_GRIDS[key] = grid
    grid = _HEIGHT_GRIDS[key]
    if grid is None:
        return None
    fx, fy = 128 * (32 - x / size), 128 * (32 - y / size)
    xi, yi = math.floor(fx), math.floor(fy)
    tx, ty = fx - xi, fy - yi
    xi, yi = xi & 127, yi & 127
    h00, h01 = grid[xi * 129 + yi], grid[xi * 129 + yi + 1]
    h10, h11 = grid[(xi + 1) * 129 + yi], grid[(xi + 1) * 129 + yi + 1]
    return (h00 * (1 - tx) + h10 * tx) * (1 - ty) + (h01 * (1 - tx) + h11 * tx) * ty


def teleport_to(character: str, map_id: int, x: float, y: float):
    """Teleports an online character to x/y on the map, at the terrain height. The worldserver console can only
    teleport to named locations, so one game_tele row ('DashboardTP') is rewritten and reloaded each time."""
    if not character.isalpha():
        raise ValueError("invalid character name")
    if map_id not in VANILLA_MAPS:
        raise ValueError("teleporting is only allowed on Eastern Kingdoms and Kalimdor")
    z = ground_height(map_id, x, y)
    if z is None or z < -300:
        raise ValueError("no terrain there (ocean or outside the map data)")
    if not service_running("world"):
        raise ValueError("the Worldserver isn't running -- start it first")
    exec_sql("acore_world", "REPLACE INTO game_tele (id, position_x, position_y, position_z, orientation, map, name) "
             "VALUES (99999, %.3f, %.3f, %.3f, 0, %d, 'DashboardTP')" % (x, y, z + 2, map_id))
    send_input("world", "reload game_tele")
    time.sleep(0.7)
    send_input("world", "tele name %s DashboardTP" % character)
    return {"z": round(z + 2, 1)}


_WF_MARKERS = None
CLIENT_MAP_AREAS = r"H:\Simon\WoW Server Stuff\Ascension Client+Data\Data\Content\WorldMapAreaData.json"


def wf_markers():
    """Worldforged item locations from the Sidekick mirror (sidekick/data.js, key "wf"), turned into world x/y.
    A location is {z: WorldMapArea.ID, x/y: 0..1 inside that zone's map picture}. Zone bounds come from the client's
    WorldMapAreaData.json first (it knows every Ascension zone id), then from the server's WorldMapArea.dbc."""
    global _WF_MARKERS
    if _WF_MARKERS is not None:
        return _WF_MARKERS
    import struct
    zones = {}
    for folder in (os.path.join(SETTINGS["install_dir"], "data", "dbc"), os.path.join(SETTINGS["install_dir"], "dbc")):
        path = os.path.join(folder, "WorldMapArea.dbc")
        if os.path.exists(path):
            raw = open(path, "rb").read()
            _, records, fields, size, _ = struct.unpack("<4siiii", raw[:20])
            for i in range(records):
                u = struct.unpack_from("<%dI" % fields, raw, 20 + i * size)
                f = struct.unpack_from("<%df" % fields, raw, 20 + i * size)
                zones[u[0]] = (u[1], f[4], f[5], f[6], f[7])
            break
    if os.path.isfile(CLIENT_MAP_AREAS):
        for r in json.load(open(CLIENT_MAP_AREAS, encoding="utf-8")):
            zones[r["ID"]] = (r["MapID"], r["LocLeft"], r["LocRight"], r["LocTop"], r["LocBottom"])
    text = open(os.path.join(DASHBOARD_DIR, "sidekick", "data.js"), encoding="utf-8").read()
    data, _ = json.JSONDecoder().raw_decode(text[text.index('"wf":{"items"') + 5:])
    items, markers = {}, []
    for it in data["items"].values():
        for loc in it.get("locations", []):
            zone = zones.get(loc["z"])
            if not zone or zone[0] not in VANILLA_MAPS or zone[1] == zone[2] or zone[3] == zone[4]:
                continue
            map_id, left, right, top, bottom = zone
            items[it["id"]] = [it["name"], it["quality"], it.get("icon") or "", it.get("slot") or "", it.get("subtype") or ""]
            markers.append([it["id"], map_id, round(top - loc["y"] * (top - bottom), 1), round(left - loc["x"] * (left - right), 1), loc.get("status", "")])
    _WF_MARKERS = {"items": items, "markers": markers}
    return _WF_MARKERS


def map_players():
    """Online characters with position. Positions in the DB are only as fresh as PlayerSaveInterval."""
    rows = query_rows(
        "acore_characters",
        "SELECT c.name, c.race, c.class, c.level, c.map, c.zone, c.position_x AS x, c.position_y AS y, "
        "(a.username LIKE 'RNDBOT%') AS bot FROM characters c JOIN acore_auth.account a ON a.id = c.account "
        "WHERE c.online = 1 AND (c.playerFlags & 8) = 0")  # 8 = PLAYER_FLAGS_GM (.gm on): hidden from the map
    global _MAP_CLASSES
    if _MAP_CLASSES is None:
        from bots_stats import BASE_CLASSES
        _MAP_CLASSES = dict(BASE_CLASSES)
        for r in query_rows("acore_world", "SELECT class, client_name FROM ascension_custom_class"):
            _MAP_CLASSES[int(r["class"])] = r["client_name"]
    for r in rows:
        r["cls"] = _MAP_CLASSES.get(int(r["class"]), "Class %s" % r["class"])
    img_dir = os.path.join(DASHBOARD_DIR, "worldmaps")
    ver = int(max((e.stat().st_mtime for e in os.scandir(img_dir)), default=0)) if os.path.isdir(img_dir) else 0
    real = [r["name"] for r in query_rows(
        "acore_characters",
        "SELECT c.name FROM characters c JOIN acore_auth.account a ON a.id = c.account "
        "WHERE c.online = 1 AND a.username NOT LIKE 'RNDBOT%' ORDER BY c.name")]   # includes GMs: they can still be teleported
    return {"players": rows, "zones": map_zones(), "time": time.time(), "ver": ver, "real": real}  # ver busts the browser cache of the map pictures


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _write(self, body):
        # The client can close its socket (tab closed, page navigated away, request
        # cancelled) while we're still writing the response body. That's not a server
        # error -- just drop it instead of letting it print a traceback to the console.
        try:
            self.wfile.write(body)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass

    def _json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self._write(body)

    def _cors(self):
        # The Gear tab lives in the squidbots module's iframe (its own port, so its own origin) but
        # calls back into these admin APIs -- only localhost origins get the header, never a wildcard,
        # since these routes can mail items and edit accounts.
        origin = self.headers.get("Origin", "")
        if re.match(r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$", origin):
            self.send_header("Access-Control-Allow-Origin", origin)

    def _text_file(self, path, content_type="text/html; charset=utf-8"):
        if not os.path.exists(path):
            self.send_response(404)
            self.end_headers()
            return
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        # This app's own .html/.js change constantly during development and
        # are tiny/local -- never let the browser serve a stale cached copy.
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.end_headers()
        self._write(body)

    def _sidekick_community(self, path, qs):
        # Read-only local copy of the site's community macro/WeakAura library.
        fp = os.path.join(DASHBOARD_DIR, "sidekick", "community_data.json")
        try:
            with open(fp, encoding="utf-8") as f:
                items = json.load(f)
        except Exception:
            items = []
        tail = path[len("/sidekick/api/community"):].strip("/")
        if tail == "list":
            q = lambda k: (qs.get(k) or [""])[0]
            res = [i for i in items if i.get("kind") == q("kind")]
            for k in ("scope", "cls", "spec", "category"):
                if q(k):
                    res = [i for i in res if i.get(k) == q(k)]
            needle = q("q").lower()
            if needle:
                res = [i for i in res if needle in " ".join(
                    str(i.get(k, "")) for k in ("title", "description", "author", "cls", "spec", "body")).lower()]
            if q("sort") == "new":
                res.sort(key=lambda i: i.get("createdAt", ""), reverse=True)
            else:
                res.sort(key=lambda i: (bool(i.get("featured")), i.get("votes", 0)), reverse=True)
            try:
                limit = max(1, min(100, int(q("limit") or 50)))
                offset = max(0, int(q("offset") or 0))
            except ValueError:
                limit, offset = 50, 0
            page = [{k: v for k, v in i.items() if not (k == "body" and i.get("kind") == "weakaura")}
                    for i in res[offset:offset + limit]]
            self._json({"items": page, "total": len(res), "limit": limit, "offset": offset})
            return
        if tail.startswith("item/"):
            iid = unquote(tail[5:])
            for i in items:
                if i.get("id") == iid:
                    self._json(i)
                    return
        self._json({"error": "not_found"}, 404)

    def _serve_sidekick(self, path):
        # Offline mirror of ascensionsidekick.com under /sidekick/. Any path
        # without a file extension is an SPA route -> index.html.
        root = os.path.realpath(os.path.join(DASHBOARD_DIR, "sidekick"))
        rel = unquote(path[len("/sidekick"):]).lstrip("/")
        if not rel or not os.path.splitext(rel)[1]:
            rel = "index.html"
        full = os.path.realpath(os.path.join(root, rel))
        if not (full == root or full.startswith(root + os.sep)) or not os.path.isfile(full):
            self.send_response(404)
            self.end_headers()
            return
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=3600" if ctype.startswith("image/") else "no-cache")
        self.end_headers()
        self._write(body)

    def _ascensiondb_manifest(self, root):
        # manifest.json maps a raw query string ("item=19019") to the mirrored page that answers
        # it ("pages/<hash>.html"). The background crawl (see ascensiondb/crawl.log) keeps appending
        # to it while the server is running, so we reload on mtime change instead of caching forever.
        mf = os.path.join(root, "manifest.json")
        try:
            mtime = os.path.getmtime(mf)
        except OSError:
            return {}
        cached = getattr(Handler, "_ascensiondb_manifest_cache", None)
        if cached and cached[0] == mtime:
            return cached[1]
        try:
            with open(mf, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        Handler._ascensiondb_manifest_cache = (mtime, data)
        return data

    def _serve_ascensiondb(self, path, query):
        # Offline mirror of db.ascension.gg under /ascensiondb/ (the live site sends
        # X-Frame-Options: DENY so it can never be iframed directly; this is a static
        # snapshot pulled from the Wayback Machine). A query string on "/ascensiondb/" or
        # "/ascensiondb/index.html" (e.g. "?item=19019", the shape the site's own links use)
        # is looked up in manifest.json for a matching mirrored page. No match -> a friendly
        # "not archived" page instead of silently falling back to the homepage.
        root = os.path.realpath(os.path.join(DASHBOARD_DIR, "ascensiondb"))
        rel = unquote(path[len("/ascensiondb"):]).lstrip("/")
        if not rel:
            rel = "index.html"
        full = os.path.realpath(os.path.join(root, rel))
        if not (full == root or full.startswith(root + os.sep)):
            self.send_response(404)
            self.end_headers()
            return
        if not os.path.isfile(full):
            full = os.path.join(root, "index.html")
        if rel in ("", "index.html") and query:
            manifest = self._ascensiondb_manifest(root)
            page = manifest.get(query)
            if page:
                candidate = os.path.realpath(os.path.join(root, page))
                if candidate == root or candidate.startswith(root + os.sep):
                    if os.path.isfile(candidate):
                        full = candidate
            else:
                not_archived = os.path.join(root, "not_archived.html")
                if os.path.isfile(not_archived):
                    full = not_archived
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=3600" if ctype.startswith("image/") else "no-cache")
        self.end_headers()
        self._write(body)

    def do_OPTIONS(self):
        # CORS preflight for the Gear tab's cross-port calls from the squidbots iframe (see _cors()).
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET, POST")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path.startswith("/sidekick/api/community"):
            self._sidekick_community(path, qs)
            return
        if path == "/sidekick" or path.startswith("/sidekick/"):
            self._serve_sidekick(path if path != "/sidekick" else "/sidekick/")
            return
        if path == "/ascensiondb" or path.startswith("/ascensiondb/"):
            self._serve_ascensiondb(path if path != "/ascensiondb" else "/ascensiondb/", parsed.query)
            return

        if path in ("/", "/index.html"):
            self._text_file(os.path.join(DASHBOARD_DIR, "index.html"))
            return
        if path == "/app.js":
            self._text_file(os.path.join(DASHBOARD_DIR, "app.js"), "application/javascript; charset=utf-8")
            return

        if path == "/api/status":
            result = {}
            for key, svc in services().items():
                pid = get_pid(svc["process"], svc.get("exe"))
                entry = {"label": svc["label"], "running": pid is not None,
                         "auto_start": bool(AUTO_START.get(key, False))}
                if pid is not None:
                    cpu, ram = get_process_health(key, pid)
                    entry["cpu_percent"] = cpu
                    entry["ram_bytes"] = ram
                    entry["ram_total_bytes"] = _total_ram_bytes()
                result[key] = entry
            self._json(result)
            return

        if path == "/api/map/worldforge":
            try:
                self._json(wf_markers())
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return
        if path == "/api/map":
            try:
                self._json(map_players())
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return
        if path in STATIC_IMAGES:
            fp = os.path.join(DASHBOARD_DIR, path[1:])
            if not os.path.isfile(fp):
                self.send_response(404)
                self.end_headers()
                return
            with open(fp, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", STATIC_IMAGES[path])
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self._write(body)
            return
        if path.startswith("/worldmaps/"):
            name = os.path.basename(unquote(path))
            file = os.path.join(DASHBOARD_DIR, "worldmaps", name)
            if not (re.fullmatch(r"(c?\d+|world)\.jpg", name) and os.path.isfile(file)):
                self.send_response(404)
                self.end_headers()
                return
            with open(file, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            self._write(body)
            return
        if path.startswith("/item_icons/"):
            name = os.path.basename(unquote(path))
            file = os.path.join(ITEM_ICON_DIR, name)
            if not (name.endswith(".png") and re.fullmatch(r"[a-z0-9_\-. ()']+", name[:-4] + "") and os.path.isfile(file)):
                self.send_response(404)
                self.end_headers()
                return
            with open(file, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            self._write(body)
            return

        if path == "/api/icon":
            key = qs.get("service", [""])[0]
            if key not in services() and key != "launcher":
                self.send_response(404)
                self.end_headers()
                return
            icon_path = get_icon_path(key)
            if not icon_path:
                self.send_response(404)
                self.end_headers()
                return
            with open(icon_path, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            self._write(body)
            return

        if path == "/api/log":
            key = qs.get("service", [""])[0]
            if key not in services():
                self._json({"error": "unknown service"}, 400)
                return
            text, writable = get_console_text(key)
            self._json({"log": text, "writable": writable})
            return

        if path == "/api/configs":
            out = []
            for c in all_configs():
                p = resolve_config_path(c)
                out.append({"key": c["key"], "label": c["label"], "exists": os.path.exists(p)})
            self._json(out)
            return

        if path == "/api/config":
            key = qs.get("name", [""])[0]
            cfg = next((c for c in all_configs() if c["key"] == key), None)
            if not cfg:
                self._json({"error": "unknown config"}, 400)
                return
            p = resolve_config_path(cfg)
            try:
                # newline="" keeps CRLF files as they are; the editor restores the file's own line ending on save.
                with open(p, "r", encoding="utf-8", errors="replace", newline="") as f:
                    content = f.read()
                self._json({"content": content, "path": p, "size": len(content.encode("utf-8"))})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/settings":
            self._json(SETTINGS)
            return

        if path == "/api/setup/status":
            self._json(setup_status(SETTINGS))
            return

        if path == "/api/setup/detect":
            self._json(detect_setup(SETTINGS))
            return

        if path == "/api/setup/check-path":
            p = qs.get("path", [""])[0]
            self._json({"exists": bool(p) and os.path.exists(p)})
            return

        if path == "/api/modules":
            # Only installed modules are listed; the UI hides the rest.
            mods = {}
            if EXILESDB:
                mods["exilesdb"] = EXILESDB.status(SETTINGS)
            if SQUIDBOTS:
                mods["squidbots"] = SQUIDBOTS.status(SETTINGS)
            self._json(mods)
            return

        if path == "/api/admin/bans":
            try:
                self._json(list_bans())
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/admin/accounts":
            try:
                self._json(list_accounts(
                    qs.get("q", [""])[0].strip(), int(qs.get("page", ["1"])[0]), qs.get("bots", ["0"])[0] == "1"))
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/admin/items":
            try:
                one = lambda key: qs.get(key, [""])[0].strip()
                self._json(list_items(one("q"), int(qs.get("page", ["1"])[0]), one("quality"), one("class"),
                                      one("slot"), one("min"), one("max"), qs.get("hide", ["1"])[0] == "1",
                                      one("sub")))
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/admin/item-tip":
            try:
                self._json(item_tips.item_tip(query_rows, SETTINGS["install_dir"], int(qs.get("id", ["0"])[0])))
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return
        if path == "/api/admin/kits":
            try:
                self._json(kits_with_info())
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return
        if path == "/api/admin/characters":
            try:
                self._json(list_real_characters())
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/admin/char-search":
            try:
                self._json(search_characters(qs.get("q", [""])[0].strip()))
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/admin/char-list":
            try:
                one = lambda key: qs.get(key, [""])[0].strip()
                self._json(list_characters(one("q"), int(qs.get("page", ["1"])[0]),
                                           one("min"), one("max"), one("class"), one("role")))
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/admin/char-gear":
            try:
                self._json(character_gear(qs.get("name", [""])[0].strip()))
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/admin/random-bot":
            try:
                self._json({"name": random_bot()})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/admin/tickets":
            try:
                self._json(list_tickets())
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/admin/realms":
            try:
                self._json(list_realms())
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""

        if path == "/api/start":
            key = qs.get("service", [""])[0]
            if key not in services():
                self._json({"error": "unknown service"}, 400)
                return
            try:
                start_service(key)
                MANUAL_STOPPED.discard(key)
                self._json({"ok": True})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/stop":
            key = qs.get("service", [""])[0]
            if key not in services():
                self._json({"error": "unknown service"}, 400)
                return
            try:
                stop_service(key)
                MANUAL_STOPPED.add(key)  # a deliberate Stop -- the watchdog must not auto-restart this
                self._json({"ok": True})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/restart":
            key = qs.get("service", [""])[0]
            if key not in services():
                self._json({"error": "unknown service"}, 400)
                return
            RESTARTING.add(key)  # the stop-then-start gap below must not look like a crash to the watchdog
            try:
                restart_service(key)
                MANUAL_STOPPED.discard(key)
                self._json({"ok": True})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            finally:
                RESTARTING.discard(key)
            return

        if path == "/api/input":
            key = qs.get("service", [""])[0]
            try:
                data = json.loads(body.decode("utf-8"))
                text = data.get("input", "")
                if key == "mysql":
                    output = run_sql(text)
                    self._json({"ok": True, "output": output})
                else:
                    send_input(key, text)
                    self._json({"ok": True})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/config":
            key = qs.get("name", [""])[0]
            cfg = next((c for c in all_configs() if c["key"] == key), None)
            if not cfg:
                self._json({"error": "unknown config"}, 400)
                return
            p = resolve_config_path(cfg)
            try:
                data = json.loads(body.decode("utf-8"))
                # Keep the file as it was before the dashboard first touched it (one backup, never overwritten).
                if os.path.exists(p) and not os.path.exists(p + ".dashboard.bak"):
                    shutil.copy2(p, p + ".dashboard.bak")
                with open(p, "w", encoding="utf-8", newline="") as f:
                    f.write(data["content"])
                self._json({"ok": True})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/setup/browse":
            try:
                data = json.loads(body.decode("utf-8"))
                result = browse_path(
                    data.get("kind", "folder"), data.get("title", "Choose a folder"),
                    data.get("start", ""), data.get("filter", "Programs (*.exe)|*.exe"),
                )
                self._json({"path": result})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/setup/test-mysql":
            try:
                data = json.loads(body.decode("utf-8"))
                self._json(test_mysql_connection(
                    data.get("mysql_dir", ""), data.get("mysql_host", "127.0.0.1"),
                    data.get("mysql_port", "3306"), data.get("mysql_user", ""), data.get("mysql_password", ""),
                ))
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/autostart":
            global AUTO_START
            key = qs.get("service", [""])[0]
            if key not in services():
                self._json({"error": "unknown service"}, 400)
                return
            try:
                data = json.loads(body.decode("utf-8"))
                AUTO_START[key] = bool(data.get("enabled"))
                save_auto_start(AUTO_START)
                self._json({"ok": True, "auto_start": AUTO_START})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/settings":
            global SETTINGS
            try:
                data = json.loads(body.decode("utf-8"))
                SETTINGS = save_settings(data)
                if EXILESDB:
                    EXILESDB.stop()  # path/port may have changed; the tab restarts it on next open
                if SQUIDBOTS:
                    SQUIDBOTS.stop()  # DB creds/paths may have changed; the tab restarts it on next open
                self._json({"ok": True, "settings": SETTINGS})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/modules/exilesdb/start":
            if not EXILESDB:
                self._json({"error": "module not installed"}, 404)
                return
            try:
                self._json(EXILESDB.start(SETTINGS))
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/modules/squidbots/start":
            if not SQUIDBOTS:
                self._json({"error": "module not installed"}, 404)
                return
            try:
                self._json(SQUIDBOTS.start(SETTINGS))
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/admin/unban":
            try:
                data = json.loads(body.decode("utf-8"))
                unban(data["type"], data["key"])
                self._json({"ok": True})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/admin/unmute":
            try:
                data = json.loads(body.decode("utf-8"))
                unmute(data["guid"])
                self._json({"ok": True})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/admin/ban":
            try:
                data = json.loads(body.decode("utf-8"))
                add_ban(data["type"], data["name"], data.get("reason", "no reason"), int(data.get("duration", 0)))
                self._json({"ok": True})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/admin/mute":
            try:
                data = json.loads(body.decode("utf-8"))
                add_mute(data["name"], data.get("reason", "no reason"), int(data.get("duration", 0)))
                self._json({"ok": True})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/admin/close-ticket":
            try:
                data = json.loads(body.decode("utf-8"))
                close_ticket(data["id"])
                self._json({"ok": True})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/admin/set-gmlevel":
            try:
                data = json.loads(body.decode("utf-8"))
                set_gmlevel(data["username"], int(data["gmlevel"]), int(data.get("realmid", -1)))
                self._json({"ok": True})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/admin/update-realm":
            try:
                data = json.loads(body.decode("utf-8"))
                update_realm(data["id"], data["name"], data["address"], int(data["port"]), int(data["flag"]))
                self._json({"ok": True})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/admin/update-account":
            try:
                data = json.loads(body.decode("utf-8"))
                update_account(int(data["id"]), data.get("email", ""), int(data["gmlevel"]), int(data["expansion"]),
                               int(data["locked"]), data.get("password", ""))
                self._json({"ok": True})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/admin/kits-save":
            try:
                save_kits(json.loads(body.decode("utf-8")))
                self._json({"ok": True})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return
        if path == "/api/admin/give-kit":
            try:
                data = json.loads(body.decode("utf-8"))
                self._json({"ok": True, **give_kit(data["character"].strip(), str(data["kit"]))})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return
        if path == "/api/map/teleport":
            try:
                data = json.loads(body.decode("utf-8"))
                self._json({"ok": True, **teleport_to(data["character"].strip(), int(data["map"]), float(data["x"]), float(data["y"]))})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/admin/give-item":
            try:
                data = json.loads(body.decode("utf-8"))
                self._json({"ok": True, **give_item(data["character"].strip(), int(data["item"]), int(data.get("count", 1)))})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/admin/create-account":
            try:
                data = json.loads(body.decode("utf-8"))
                create_account(data["username"], data["password"])
                self._json({"ok": True})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        if path == "/api/launch-client":
            try:
                # os.startfile() defaults to the dashboard's own cwd, not the
                # client's -- double-clicking in Explorer sets cwd to the
                # exe's own folder. Passing it explicitly matches that and
                # avoids the client having to fall back/retry relative-path
                # lookups at startup.
                client_exe = SETTINGS["client_exe"]
                os.startfile(client_exe, cwd=os.path.dirname(client_exe))
                self._json({"ok": True})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return

        self.send_response(404)
        self.end_headers()


def run_auto_start():
    """Starts every service flagged auto_start=True that isn't already running,
    in a fixed mysql -> auth/world order. Only matters for launch_mode "exe"
    (no .bat wrapper): the .bat wrapper already waits for MySQL's port itself,
    but starting mysql first and giving it a couple seconds' head start is
    cheap insurance either way, so it always runs in this order regardless of
    launch_mode. Runs on a background thread so it never delays the dashboard
    opening in the browser."""
    order = ["mysql", "auth", "world", "world2"]
    svcs = services()
    keys = [k for k in order if k in svcs] + [k for k in svcs if k not in order]
    for key in keys:
        if not AUTO_START.get(key):
            continue
        if service_running(key):
            continue
        try:
            start_service(key)
        except Exception as e:
            print(f"Auto-start of '{key}' failed: {e}", flush=True)
        if key == "mysql":
            time.sleep(2)


# Crash watchdog: tracks, per service, the moment it was first seen down while
# flagged auto_start -- WATCHDOG_DOWN_SINCE.pop(key) on any manual stop/restart
# keeps that action from being mistaken for a crash. MANUAL_STOPPED marks a
# service the user stopped on purpose, so the watchdog leaves it alone until
# they start/restart it again; RESTARTING marks one mid-restart so the brief
# stop-then-start window in restart_service() isn't treated as a crash either.
WATCHDOG_INTERVAL = 3
WATCHDOG_DELAY = 20
WATCHDOG_DOWN_SINCE = {}
MANUAL_STOPPED = set()
RESTARTING = set()


def watchdog_loop():
    while True:
        try:
            for key in services():
                if not AUTO_START.get(key) or key in MANUAL_STOPPED or key in RESTARTING:
                    WATCHDOG_DOWN_SINCE.pop(key, None)
                    continue
                if service_running(key):
                    WATCHDOG_DOWN_SINCE.pop(key, None)
                    continue
                first_seen = WATCHDOG_DOWN_SINCE.setdefault(key, time.monotonic())
                if time.monotonic() - first_seen >= WATCHDOG_DELAY:
                    print(f"Watchdog: '{key}' has been down {WATCHDOG_DELAY}s, auto-restarting", flush=True)
                    try:
                        start_service(key)
                    except Exception as e:
                        print(f"Watchdog restart of '{key}' failed: {e}", flush=True)
                    WATCHDOG_DOWN_SINCE.pop(key, None)
        except Exception as e:
            print(f"Watchdog loop error: {e}", flush=True)
        time.sleep(WATCHDOG_INTERVAL)


def main():
    port = 8877
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"AzerothCoreCOA dashboard running at {url}")
    print("Close this window to stop the dashboard (services keep running).")
    if any(AUTO_START.values()):
        threading.Thread(target=run_auto_start, daemon=True).start()
    threading.Thread(target=watchdog_loop, daemon=True).start()
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
