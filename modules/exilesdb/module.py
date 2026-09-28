"""Optional ExilesDB module: an offline copy of db.exil.es shown in the dashboard.

The archive itself (about 13 GB, ~500,000 files) is NOT part of the dashboard.
Users who want it point the "ExilesDB data folder" setting at a folder that
contains `data/` (mirror.sqlite + offline_site.sqlite) and `mirror/`. Users who
don't can delete this whole `modules/exilesdb` folder (or just never set the
path): the dashboard then shows no ExilesDB tab and uses no extra disk space.

offline_exiles.py runs as its own small local web server on its own port and
the dashboard shows it in an iframe, so the archived pages work unmodified.
It is only started when the tab is opened.
"""

import atexit
import os
import socket
import subprocess
import sys
import time
import urllib.request

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_SCRIPT = os.path.join(MODULE_DIR, "offline_exiles.py")
LOG_PATH = os.path.join(MODULE_DIR, "exilesdb.log")

_proc = None


def _port(settings):
    try:
        return int(settings.get("exilesdb_port") or 8081)
    except ValueError:
        return 8081


def _data_problem(root):
    """Return a human-readable reason the data folder is unusable, or None."""
    if not root:
        return "No data folder set. Choose it in Settings."
    if not os.path.isdir(root):
        return "Folder not found: " + root
    for rel in ("data/mirror.sqlite", "data/offline_site.sqlite", "mirror/db.exil.es"):
        if not os.path.exists(os.path.join(root, *rel.split("/"))):
            return "Missing " + rel + " in " + root
    return None


def _listening(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except OSError:
        return False


def _served_root(port):
    """Data folder the process on `port` was started with (None if unknown)."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/__exilesdb_root__", timeout=2) as r:
            return r.read().decode("utf-8")
    except Exception:
        return None


def _kill_stale(port):
    """Stop whatever archive server listens on `port` (only if it is offline_exiles.py)."""
    out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True,
                         stdin=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    for line in out.splitlines():
        cols = line.split()
        if len(cols) >= 5 and cols[3] == "LISTENING" and cols[1].endswith(":" + str(port)):
            pid = cols[4]
            cmd = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}').CommandLine"],
                capture_output=True, text=True, stdin=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
            if "offline_exiles.py" in cmd:
                subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, stdin=subprocess.DEVNULL,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    for _ in range(20):
        if not _listening(port):
            return
        time.sleep(0.25)


def status(settings):
    root = (settings.get("exilesdb_path") or "").strip()
    port = _port(settings)
    return {
        "installed": True,
        "problem": _data_problem(root),
        "running": _listening(port),
        "port": port,
    }


def start(settings):
    """Start the archive server if it isn't already up. Returns status()."""
    global _proc
    st = status(settings)
    if st["problem"]:
        stop()  # data folder removed/invalid: don't keep serving the old archive
        return dict(st, running=False)
    root = settings["exilesdb_path"].strip()
    if st["running"]:
        served = _served_root(st["port"])
        if served and os.path.normcase(os.path.normpath(served)) == os.path.normcase(os.path.normpath(root)):
            return st
        # Leftover server (older dashboard session, or the folder was moved): replace it.
        _kill_stale(st["port"])
        if _listening(st["port"]):
            return dict(st, problem=f"Port {st['port']} is used by another program. Change the ExilesDB port in Settings.")
    env = dict(os.environ, EXILESDB_ROOT=settings["exilesdb_path"].strip(), PYTHONUNBUFFERED="1")
    log = open(LOG_PATH, "ab")
    exe = os.path.join(MODULE_DIR, "exilesdb.exe")
    command = [exe] if os.path.isfile(exe) else [sys.executable, SERVER_SCRIPT]
    command += ["serve", "--port", str(st["port"])]
    _proc = subprocess.Popen(
        command,
        env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return status(settings)


def stop():
    global _proc
    if _proc and _proc.poll() is None:
        _proc.terminate()
    _proc = None


atexit.register(stop)
