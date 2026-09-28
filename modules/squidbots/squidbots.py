"""
squidbots.py - a local dashboard for the bots of a Conquest of Azeroth server.

Serves a small web page on http://localhost:8088, reachable from this machine only:
  /            the page (index.html)
  /api/stats   the figures as JSON, worked out again at most every 20 seconds

The figures come from the server database, so they follow how often characters are saved
(PlayerSaveInterval, 15 minutes by default) rather than every kill as it happens.
"""
import datetime
import glob
import hashlib
import http.server
import json
import os
import re
import struct
import subprocess
import sys
import threading
import time
import urllib.parse

HERE = (os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, "frozen", False)
        else os.path.dirname(os.path.abspath(__file__)))
# Optional dashboard.json next to this file: {"repack": ..., "publishDir": ..., "uptimeSince": ...}.
# A second instance for another server can also set "mysqlArgs" (mysql.exe arguments instead of the repack's root
# login), "coaLog", "crashesDir" and "worldserverPath" (the worldserver.exe it follows), plus "port".
# "countFrom" ("YYYY-MM-DD HH:MM:SS") makes every figure start there instead of at the bots' creation: kills and
# quests since then, bot actions and crashes since then (a test run on a server that already has old bots).
# Without it the dashboard expects to sit in <repack>\Dashboard and publishes nothing.
SETTINGS_FILE = os.path.join(HERE, "dashboard.json")
SETTINGS = json.load(open(SETTINGS_FILE, encoding="utf-8-sig")) if os.path.exists(SETTINGS_FILE) else {}
# Optional build.json next to this file: which core and which pull requests this server is running.
# Only a test realm has one; without it the page is exactly what it always was.
BUILD_FILE = os.path.join(HERE, "build.json")

# By absolute path: a scheduled task or a service runs with a thin PATH, where "powershell" alone is
# not found and every lookup fails with "the system cannot find the file specified".
POWERSHELL = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                          "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
if not os.path.exists(POWERSHELL):
    POWERSHELL = "powershell"
def find_repack():
    # <repack>\Dashboard or <repack>\CoA-Bots\Dashboard: the first parent holding the repack settings.
    folder = os.path.dirname(HERE)
    for _ in range(2):
        if os.path.exists(os.path.join(folder, "Settings", "database.json")):
            return folder
        folder = os.path.dirname(folder)
    return os.path.dirname(HERE)


ROOT = SETTINGS.get("repack") or find_repack()
BUILDS = next((p for p in (os.path.join(HERE, "coa-level-builds.json"), r"C:\CoA-Build\coa-level-builds.json")
               if os.path.exists(p)), os.path.join(HERE, "coa-level-builds.json"))
PORT = int(os.environ.get("COA_DASHBOARD_PORT") or SETTINGS.get("port") or 8088)

# Bot settings the dashboard can edit. The .conf files are read by the server at
# startup, so editing them while it is stopped is the simplest way to configure a
# realm: no reload, no restart beyond the one you were going to do anyway.
#
# The repack runs this with its bundled Python, which is an embedded distribution:
# python3xx._pth takes full control of sys.path and the script's own directory is
# never added, so a plain "import botconfig" fails there. Add it explicitly.
import sys

if HERE not in sys.path:
    sys.path.insert(0, HERE)
import botconfig


def find_config_dir():
    # The bots server keeps its own module configs; prefer those, fall back to the
    # base server's so a repack without CoA-Bots still gets a usable panel.
    for bots in (True, False):
        folder = botconfig.config_dir(ROOT, bots=bots)
        if os.path.isdir(folder):
            return folder
    return botconfig.config_dir(ROOT, bots=True)


CONFIG_DIR = SETTINGS.get("configDir") or find_config_dir()
CONFIG_BACKUPS = os.path.join(HERE, "config-backups")
STATIC_TYPES = {".css": "text/css; charset=utf-8", ".js": "application/javascript; charset=utf-8",
                ".woff2": "font/woff2", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".webp": "image/webp"}
# The game databases. A second realm on the same MySQL (a test realm, say) names its own in
# dashboard.json: {"databases": {"auth": "dev_auth", "characters": "dev_characters", "world": "dev_world"}}.
DB = dict({"auth": "acore_auth", "characters": "acore_characters", "world": "acore_world"},
          **(SETTINGS.get("databases") or {}))
for _name in DB.values():
    if not re.match(r"^[A-Za-z0-9_]+$", _name):
        raise SystemExit("dashboard.json: %r is not a database name" % _name)
CACHE_SECONDS = 20
HISTORY_FILE = os.path.join(HERE, "history.json")
HISTORY_EVERY = 10 * 60        # one point every 10 minutes
HISTORY_KEEP = 7 * 24 * 3600   # a week of points
# Experience of every bot, once an hour, to work out who gains the most over a day.
XP_FILE = os.path.join(HERE, "xp-history.json")
LEVELS_FILE = os.path.join(HERE, "levels.json")
XP_EVERY = 3600
XP_KEEP = 25 * 3600
# Optional public copy: a folder a web server serves, on a NAS or anywhere else. The dashboard only
# writes files there, so nothing on this machine is reachable from outside. Unset: no copy.
PUBLISH_DIR = SETTINGS.get("publishDir")
PUBLISH_EVERY = 60
# Usage report of the CoA bot actions, written by the worldserver every 10 minutes (counts since its start).
COA_LOG = SETTINGS.get("coaLog") or os.path.join(ROOT, "Core", "Logs", "CoaBots.log")
USAGE_RE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) coa usage since start \(cast/tried\): (.*)$")
# Chat of the players and the bots, written by the worldserver when ChatLog.Enable = 1 and the
# chat.* loggers point at a Chat.log appender. Absent: the dashboard simply shows no talkers.
CHAT_LOG = SETTINGS.get("chatLog") or os.path.join(os.path.dirname(COA_LOG), "Chat.log")
CHAT_RE = re.compile(r"^(?:(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\s+)?Player (\S+) (.*)$")
CHAT_TAIL = 16 * 1024 * 1024   # only the end of the file is read: a day of chat is far smaller
SPELLS_RE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) coa (interrupt|dispel) spells: (.*)$")
COUNT_RE = re.compile(r"([a-z ]+?) (\d+)/(\d+)")
SPELL_RE = re.compile(r"\s*([^,]+?) \((\d+)\) x(\d+)")  # entries are separated by ", "


def action_usage(hours=24):
    """Casts and tries of each bot action over the last `hours`, from CoaBots.log.

    Counts in the log restart at every worldserver start: the gain between two reports of the
    same run is added up, and a report whose counts went down starts a new run.
    """
    if not os.path.exists(COA_LOG):
        return None
    since = time.time() - hours * 3600
    totals, previous, first = {}, None, None
    runs, spells = [], {}
    for raw in open(COA_LOG, encoding="utf-8", errors="replace"):
        line = raw.strip()
        match = USAGE_RE.match(line)
        if match:
            stamp = time.mktime(time.strptime(match.group(1), "%Y-%m-%d %H:%M:%S"))
            counts = {name.strip(): (int(cast), int(tried)) for name, cast, tried in COUNT_RE.findall(match.group(2))}
            restarted = previous is None or any(counts.get(name, (0, 0))[1] < tried
                                                for name, (_, tried) in previous.items())
            if restarted and spells:
                runs.append(spells)
                spells = {}
            if stamp >= since:
                first = first or stamp
                for name, (cast, tried) in counts.items():
                    base_cast, base_tried = (0, 0) if restarted else previous.get(name, (0, 0))
                    total = totals.setdefault(name, [0, 0])
                    total[0] += max(0, cast - base_cast)
                    total[1] += max(0, tried - base_tried)
            previous = counts
            continue
        match = SPELLS_RE.match(line)
        if match and time.mktime(time.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")) >= since:
            # The latest list of a run holds that run's totals.
            spells[match.group(2)] = {name: int(n) for name, _, n in SPELL_RE.findall(match.group(3))}
    if spells:
        runs.append(spells)

    def top(kind):
        merged = {}
        for run in runs:
            for name, n in run.get(kind, {}).items():
                merged[name] = merged.get(name, 0) + n
        return [{"name": name, "count": n} for name, n in sorted(merged.items(), key=lambda kv: kv[1], reverse=True)[:8]]

    return {
        "hours": hours,
        "since": round(first) if first else None,
        "rows": [{"key": name, "cast": cast, "tried": tried} for name, (cast, tried) in totals.items()],
        "interrupts": top("interrupt"),
        "dispels": top("dispel"),
    }

def chat_stats(hours=24, limit=12, bots=None):
    """Who talked and how much over the last `hours`, from Chat.log.

    With `bots` (a set of bot names), "bots" holds the same tally restricted to lines those bots said:
    that is the only part the public copy may carry, since real players are never published.

    Lines look like "Player Name says (language 0): ..." or "Player Name tells channel Zone: ...".
    A line with no date is kept: the appender writes one, and an old file simply reads as recent.
    """
    if not os.path.exists(CHAT_LOG):
        return None
    since = time.time() - hours * 3600
    tallies = {"all": ({}, {}), "bots": ({}, {})}
    first = None
    with open(CHAT_LOG, "rb") as handle:
        handle.seek(0, os.SEEK_END)
        handle.seek(max(0, handle.tell() - CHAT_TAIL))
        raw = handle.read().decode("utf-8", "replace")
    for line in raw.splitlines()[1:]:               # the first line may be cut in half
        match = CHAT_RE.match(line.strip())
        if not match:
            continue
        stamp, name, rest = match.groups()
        if stamp:
            when = time.mktime(time.strptime(stamp, "%Y-%m-%d %H:%M:%S"))
            if when < since:
                continue
            first = when if first is None else min(first, when)
        kind = ("channel" if rest.startswith("tells channel ") else "whisper" if rest.startswith("tells ")
                else "say" if rest.startswith("says") else "yell" if rest.startswith("yells")
                else "emote" if rest.startswith("emotes") else "group")
        for scope in ("all", "bots") if bots is not None and name in bots else ("all",):
            talkers, kinds = tallies[scope]
            talker = talkers.setdefault(name, {"name": name, "messages": 0, "channel": 0})
            talker["messages"] += 1
            if kind == "channel":
                talker["channel"] += 1
            kinds[kind] = kinds.get(kind, 0) + 1

    def summary(talkers, kinds):
        ordered = sorted(talkers.values(), key=lambda t: t["messages"], reverse=True)
        return {
            "hours": hours,
            "since": round(first) if first else None,
            "messages": sum(kinds.values()),
            "talkers": len(talkers),
            "kinds": [{"kind": k, "count": n} for k, n in sorted(kinds.items(), key=lambda kv: kv[1], reverse=True)],
            "top": ordered[:limit],
        }
    out = summary(*tallies["all"])
    if bots is not None:
        out["bots"] = summary(*tallies["bots"])
    return out


# The live chat feed. Formats, after the appender's "YYYY-MM-DD HH:MM:SS " prefix:
#   AzerothCore chat_log.cpp (only with ChatLog.Enable = 1 and the chat.* loggers on the Chat appender):
#     Player A says (language 0): ...          Player A yells (language 0): ...
#     Player A emotes (language 0): ...        Player A whisper B: ...
#     Player A tells party with leader B: ...  (also raid, bg; "Leader player A ..." for the leader;
#                                               "Player A sends raid warning raid with leader B: ...")
#     Player A tells guild "Name": ...         Player A tells guild.officer "Name": ...
#     Player A tells channel General - Elwynn Forest: ...
#   mod-bot-minds off-screen conversations (playerbots.chat):
#     Player A says to B: ...
CHAT_KINDS = ("say", "yell", "whisper", "party", "guild", "channel", "offscreen", "other")
CHAT_LINE_RE = re.compile(r"^(?:(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\s+)?(?:Leader player|Player) (\S+) (.+)$")
CHAT_FORMS = [
    # (pattern on the rest of the line, kind, channel: fixed text or a function of the match)
    (re.compile(r"^says to ([^\s:]+): (.*)$"), "offscreen", None),
    (re.compile(r"^says \(language \d+\): (.*)$"), "say", None),
    (re.compile(r"^yells \(language \d+\): (.*)$"), "yell", None),
    (re.compile(r"^emotes \(language \d+\): (.*)$"), "other", "emote"),
    (re.compile(r"^whisper (\S+): (.*)$"), "whisper", None),
    (re.compile(r"^tells (party|raid|bg) with leader \S+: (.*)$"), "party", lambda m: m.group(1)),
    (re.compile(r"^sends raid warning raid with leader \S+: (.*)$"), "party", "raid warning"),
    (re.compile(r'^tells guild "(.*?)": (.*)$'), "guild", lambda m: m.group(1)),
    (re.compile(r'^tells guild\.officer "(.*?)": (.*)$'), "guild", lambda m: m.group(1) + " officers"),
    (re.compile(r"^tells channel ([^:]+): (.*)$"), "channel", lambda m: m.group(1)),
    (re.compile(r"^tells ([^\s:]+): (.*)$"), "whisper", None),     # older cores' whisper form
]
CHAT_FIRST_READ = 2 * 1024 * 1024
# The client's link and colour codes: "|cffffff00|Hquest:123:4|h[Name]|h|r" reads "[Name]".
CHAT_CODES_RE = re.compile(r"\|c[0-9a-fA-F]{8}|\|r|\|H[^|]*\|h|\|h")


def parse_chat_line(line):
    """One Chat.log line as {"at", "speaker", "kind", "channel", "target", "text"}, or None.

    "at" is None for a line with no date; a line that is not somebody talking (a message that ran
    over a newline, anything else) is None.
    """
    match = CHAT_LINE_RE.match(line.strip())
    if not match:
        return None
    stamp, speaker, rest = match.groups()
    entry = {"at": stamp, "speaker": speaker, "kind": "other", "channel": None, "target": None, "text": rest}
    for pattern, kind, channel in CHAT_FORMS:
        form = pattern.match(rest)
        if not form:
            continue
        entry["kind"] = kind
        entry["text"] = form.group(form.lastindex)
        if kind in ("offscreen", "whisper"):
            entry["target"] = form.group(1)
        if channel is not None:
            entry["channel"] = channel(form) if callable(channel) else channel
        break
    entry["text"] = CHAT_CODES_RE.sub("", entry["text"])
    return entry


def chat_filter(kind=None, q=None, bot=None):
    """A test on parsed lines: `kind` one kind or several joined by commas, `q` a case-insensitive
    search on speaker, target and text, `bot` lines said by that character or to it."""
    kinds = {k.strip().lower() for k in kind.split(",") if k.strip()} if kind else None
    wanted = q.strip().lower() if q and q.strip() else None
    who = bot.strip().lower() if bot and bot.strip() else None

    def keep(entry):
        if kinds is not None and entry["kind"] not in kinds:
            return False
        if who and who not in (entry["speaker"].lower(), (entry["target"] or "").lower()):
            return False
        if wanted and not any(wanted in (entry[key] or "").lower() for key in ("speaker", "target", "text")):
            return False
        return True
    return keep


def read_chat_tail(path, limit=100, keep=None, start=CHAT_FIRST_READ, cap=CHAT_TAIL):
    """The last `limit` lines of the chat log that pass `keep`, newest first.

    Only the end of the file is read: `start` bytes first, doubled while too few lines match,
    never more than `cap`. A line the window cuts in half is left out.
    """
    if not os.path.exists(path):
        return []
    with open(path, "rb") as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        window = min(start, cap)
        while True:
            window = min(window, size, cap)
            handle.seek(size - window)
            lines = handle.read(window).decode("utf-8", "replace").splitlines()
            if window < size:
                lines = lines[1:]                  # the first line may be cut in half
            found = []
            for line in reversed(lines):
                entry = parse_chat_line(line)
                if entry and (keep is None or keep(entry)):
                    found.append(entry)
                    if len(found) >= limit:
                        return found
            if window >= size or window >= cap:
                return found
            window *= 2


def chat_feed(limit=100, kind=None, q=None, bot=None, path=None):
    """GET /api/chat: the newest chat lines, filtered, at most 500."""
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 100
    limit = max(1, min(500, limit))
    return {"lines": read_chat_tail(path or CHAT_LOG, limit, chat_filter(kind, q, bot))}


# Zone names, from the worldserver's own AreaTable.dbc: characters.zone holds an area id.
DBC_DIR = SETTINGS.get("dbcDir") or next(
    (p for p in (os.path.join(ROOT, "data", "dbc"), os.path.join(ROOT, "Core", "data", "dbc")) if os.path.isdir(p)),
    os.path.join(ROOT, "Core", "data", "dbc"))


def zone_names():
    path = os.path.join(DBC_DIR, "AreaTable.dbc")
    if not os.path.exists(path):
        return {}
    raw = open(path, "rb").read()
    magic, records, fields, size, _ = struct.unpack("<4siiii", raw[:20])
    if magic != b"WDBC" or fields < 12:
        return {}
    body, block = raw[20:20 + records * size], raw[20 + records * size:]
    names = {}
    for i in range(records):
        row = struct.unpack_from("<%dI" % fields, body, i * size)
        end = block.index(b"\0", row[11])          # field 11 is the English name
        name = block[row[11]:end].decode("utf-8", "replace")
        if name:
            names[row[0]] = name
    return names


# Rare finds, written by the bot module when worldserver.conf points "playerbots.loot" at an appender.
LOOT_LOG = SETTINGS.get("lootLog") or os.path.join(os.path.dirname(COA_LOG), "BotLoot.log")
LOOT_RE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\s+(\S+) \(class (\d+) level (\d+)\) looted "
                     r"(.+?) \((\d+)\) quality (\d+) ilvl (\d+) x(\d+)$")


def loot_feed(limit=12, hours=48):
    """The last epic (or better) items the bots brought back, most recent first."""
    if not os.path.exists(LOOT_LOG):
        return None
    since = time.time() - hours * 3600
    found = []
    with open(LOOT_LOG, "rb") as handle:
        handle.seek(0, os.SEEK_END)
        handle.seek(max(0, handle.tell() - 2 * 1024 * 1024))
        raw = handle.read().decode("utf-8", "replace")
    for line in raw.splitlines()[1:]:
        match = LOOT_RE.match(line.strip())
        if not match:
            continue
        stamp, name, cls, level, item, item_id, quality, ilvl, count = match.groups()
        when = time.mktime(time.strptime(stamp, "%Y-%m-%d %H:%M:%S"))
        if when < since:
            continue
        found.append({"ts": round(when), "bot": name, "cls": int(cls), "level": int(level), "item": item,
                      "itemId": int(item_id), "quality": int(quality), "ilvl": int(ilvl), "count": int(count)})
    return {"hours": hours, "total": len(found), "rows": found[::-1][:limit]}


# Optional live snapshot of every online bot (bot-status.json), written every few seconds by
# mod-playerbots when AiPlayerbot.CoaStatusFile names it. Unlike the characters table it is current,
# and it carries what each bot is doing, so the map's hover cards read it. Without it the map and
# the roster fall back to the characters table, which follows the save interval.
STATUS_FILE = SETTINGS.get("botStatusFile") or os.path.join(os.path.dirname(COA_LOG), "bot-status.json")
STATUS_STALE = 60   # seconds; older than this the server has stopped writing it


# The last snapshot read: (mtime_ns, size), its "at", and its bots already encoded, so the file is
# parsed once per snapshot however many pages ask for it.
_LIVE_CACHE = {"key": None, "at": 0, "parsed": [], "bots": b"[]"}
_LIVE_LOCK = threading.Lock()


def _answer(payload):
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def load_live():
    """(at, bots, bots encoded) of the current snapshot, or, when there is none to show, the answer
    saying why: {"bots": [], "absent": true} on a realm with no such module (the usual case: nothing
    in the repack writes it), {"bots": [], "missing": reason} when the file is unreadable."""
    try:
        stat = os.stat(STATUS_FILE)
    except FileNotFoundError:
        return {"bots": [], "absent": True}
    except OSError as error:
        return {"bots": [], "missing": "status file unreadable: %s" % error}
    key = (stat.st_mtime_ns, stat.st_size)
    with _LIVE_LOCK:
        if _LIVE_CACHE["key"] != key:
            # The writer renames a new copy over the file; on Windows an open that lands during that
            # swap is refused, so a refused open is tried again a moment later before the card says so.
            for attempt in range(3):
                try:
                    with open(STATUS_FILE, "rb") as handle:
                        data = json.loads(handle.read().decode("utf-8", errors="replace"))
                    break
                except PermissionError as error:
                    if attempt == 2:
                        return {"bots": [], "missing": "status file unreadable: %s" % error}
                    time.sleep(0.05)
                except (OSError, ValueError) as error:
                    return {"bots": [], "missing": "status file unreadable: %s" % error}
            bots = data.get("bots") or []
            _LIVE_CACHE.update(key=key, at=data.get("at") or 0, parsed=bots, bots=_answer(bots))
        return _LIVE_CACHE["at"], _LIVE_CACHE["parsed"], _LIVE_CACHE["bots"]


def live_status_body():
    """The /api/live answer, as JSON bytes: {"at", "age", "bots"} from the module's snapshot, or
    load_live()'s reason, or {"bots": [], "missing": reason} when the snapshot is stale."""
    live = load_live()
    if isinstance(live, dict):
        return _answer(live)
    at, _parsed, bots = live
    age = max(0, round(time.time() - float(at)))
    if age > STATUS_STALE:
        return _answer({"bots": [], "missing": "status file is %d s old; is the server running?" % age})
    return b'{"at": %d, "age": %d, "bots": ' % (int(at), age) + bots + b"}"


# The public page's live view: live.json beside it, every LIVE_PUBLISH_EVERY seconds. Only the
# fields the map and the cards show, and never a real player's name: a group led by a player loses
# its leader's name, and a fight with a player reads "Fighting a player".
LIVE_PUBLISH_EVERY = 12
PUBLIC_LIVE_FIELDS = ("n", "l", "hp", "pt", "pw", "m", "x", "y", "zone", "combat", "dead", "grp", "lead",
                      "task", "quests")
_PLAYERS = {"at": 0.0, "names": set()}


def real_player_names():
    """Names of the characters that are not bots, read again every five minutes."""
    if time.time() - _PLAYERS["at"] > 300:
        rows = mysql("SELECT c.name FROM {characters}.characters c JOIN {auth}.account a ON a.id = c.account "
                     "WHERE a.username NOT LIKE 'RNDBOT%'".format(**DB))
        _PLAYERS.update(at=time.time(), names={row[0] for row in rows})
    return _PLAYERS["names"]


def public_live(bots, players):
    out = []
    for bot in bots:
        shown = {key: bot[key] for key in PUBLIC_LIVE_FIELDS if key in bot}
        if shown.get("lead") in players:
            del shown["lead"]
        task = shown.get("task") or ""
        if task.startswith("Fighting ") and task[len("Fighting "):] in players:
            shown["task"] = "Fighting a player"
        out.append(shown)
    return out


def live_publish_loop():
    last_error = None
    while True:
        try:
            live = load_live()
            if isinstance(live, dict):
                body = {"at": 0, "bots": [], "absent": True} if live.get("absent") else {"at": 0, "bots": []}
            else:
                at, bots, _encoded = live
                age = max(0, round(time.time() - float(at)))
                body = {"at": int(at), "age": age,
                        "bots": [] if age > STATUS_STALE else public_live(bots, real_player_names())}
            write_atomic(os.path.join(PUBLISH_DIR, "live.json"),
                         json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
            last_error = None
        except Exception as error:  # the NAS may be asleep: said once, tried again
            if str(error) != last_error:
                print("Public live view failed:", error, flush=True)
                last_error = str(error)
        time.sleep(LIVE_PUBLISH_EVERY)


# Journal of the watcher (Surveiller-Et-Relancer.ps1): restarts and freezes, most recent first.
INCIDENTS_FILE = SETTINGS.get("incidentsLog")


def incidents(limit=6):
    if not INCIDENTS_FILE or not os.path.exists(INCIDENTS_FILE):
        return None
    lines = []
    for raw in open(INCIDENTS_FILE, encoding="utf-8", errors="replace"):
        line = raw.strip()
        if not line or "surveillance demarree" in line:
            continue
        lines.append(line)
    out = []
    for line in lines[-limit:][::-1]:
        when, _, what = line.partition("  ")
        out.append({"at": when.strip(), "what": what.strip()})
    return out


# Server uptime is counted from this date (on this PC: the switch to 1000 bots), else from the first start.
UPTIME_SINCE = SETTINGS.get("uptimeSince", "2000-01-01 00:00:00")
COUNT_FROM = time.mktime(time.strptime(SETTINGS["countFrom"], "%Y-%m-%d %H:%M:%S")) if SETTINGS.get("countFrom") else None

# Human, Dwarf, Night Elf, Gnome, Draenei; every other race is Horde.
ALLIANCE_RACES = {1, 3, 4, 7, 11}

HEAL = {6, 31, 37, 40, 43, 51, 98, 101}
TANK = {9, 17, 21, 22, 48, 52, 57, 60, 96, 97, 99, 100}


def mysql(query):
    if SETTINGS.get("mysqlArgs"):
        # Without "mysqlExe", look for the client inside the repack rather than at a path that only
        # exists on the machine this was written on: a server with its own bundled MySQL has no other.
        exe = SETTINGS.get("mysqlExe") or next(
            glob.iglob(os.path.join(ROOT, "**", "mysql.exe"), recursive=True),
            "C:/Program Files/MySQL/MySQL Server 8.4/bin/mysql.exe")
        login = list(SETTINGS["mysqlArgs"])
    else:
        password = json.load(open(os.path.join(ROOT, "Settings", "database.json"), encoding="utf-8"))["rootPassword"]
        exe = next(glob.iglob(os.path.join(ROOT, "**", "mysql.exe"), recursive=True))
        repack = os.path.join(ROOT, "Settings", "repack.json")
        port = json.load(open(repack, encoding="utf-8-sig")).get("mysqlPort", 3307) if os.path.exists(repack) else 3307
        login = ["--host=127.0.0.1", "--port=%d" % port, "-uroot", "-p" + password]
    out = subprocess.run([exe] + login + ["-N", "-B", "-e", query],
                         capture_output=True, text=True, encoding="utf-8", timeout=30)
    if out.returncode:
        raise RuntimeError(out.stderr.strip())
    return [line.split("\t") for line in out.stdout.splitlines() if line]


def role_of(spec):
    if not spec:
        return "none"
    return "heal" if spec in HEAL else "tank" if spec in TANK else "dps"


def server_state():
    state = {"running": False, "ramMo": None, "crashes24h": 0, "lastCrash": None}
    try:
        if SETTINGS.get("worldserverPath"):
            # Several worldservers run on this PC: follow the one at that path.
            out = subprocess.run([POWERSHELL, "-NoProfile", "-Command",
                                  "Get-Process worldserver -ErrorAction SilentlyContinue | Where-Object Path -eq '%s' | "
                                  "ForEach-Object { [int]($_.WorkingSet64 / 1MB) }" % SETTINGS["worldserverPath"]],
                                 capture_output=True, text=True, timeout=15).stdout.split()
            if out:
                state["running"], state["ramMo"] = True, int(out[0])
            raise StopIteration
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq worldserver.exe", "/FO", "CSV", "/NH"],
                             capture_output=True, text=True, timeout=10).stdout
        for line in out.splitlines():
            if line.lower().startswith('"worldserver.exe"'):
                state["running"] = True
                memory = line.rsplit('","', 1)[-1]
                digits = re.sub(r"\D", "", memory)
                if digits:
                    state["ramMo"] = int(digits) // 1024
    except (OSError, subprocess.SubprocessError, StopIteration, ValueError):
        pass
    since = COUNT_FROM or time.time() - 24 * 3600
    # The worldserver writes crash reports under the folder it runs in: Core, or CoA-Bots\Core with CoA Bots.
    folders = [SETTINGS["crashesDir"]] if SETTINGS.get("crashesDir") else [os.path.join(ROOT, "Core", "Crashes"),
                                                                        os.path.join(ROOT, "CoA-Bots", "Core", "Crashes")]
    crashes = [f for folder in folders
               for f in glob.glob(os.path.join(glob.escape(folder), "*.txt")) if os.path.getmtime(f) > since]
    state["crashes24h"] = len(crashes)
    if crashes:
        state["lastCrash"] = datetime.datetime.fromtimestamp(max(os.path.getmtime(f) for f in crashes)).strftime("%d/%m %H:%M")
    return state


class Stats:
    def __init__(self):
        self.lock = threading.Lock()
        self.cached_at = 0.0
        self.data = None
        self.baseline = None
        self.level_ups = json.load(open(LEVELS_FILE, encoding="utf-8")) if os.path.exists(LEVELS_FILE) else {}
        self.specs = {}
        self.classes = {}
        self.xp_levels = {}
        self.zones = None
        self.history = json.load(open(HISTORY_FILE, encoding="utf-8")) if os.path.exists(HISTORY_FILE) else []
        self.xp_history = json.load(open(XP_FILE, encoding="utf-8")) if os.path.exists(XP_FILE) else []

    def load_names(self):
        if not self.specs:
            # BUILDS is the author's own private build-name list, not part of this repo -- like
            # LEVELS_FILE/HISTORY_FILE/XP_FILE above, missing just means no names yet, not an error.
            if os.path.exists(BUILDS):
                for key, build in json.load(open(BUILDS, encoding="utf-8")).items():
                    self.specs[key] = build["spec"]
        if not self.classes:
            for cls, name in mysql("SELECT class, client_name FROM %s.ascension_custom_class" % DB["world"]):
                self.classes[int(cls)] = name
        if self.zones is None:
            self.zones = zone_names()
        if not self.xp_levels:
            # Experience needed to reach each level, so that levels and experience compare as one number.
            total = 0
            for level, needed in mysql("SELECT Level, Experience FROM %s.player_xp_for_level ORDER BY Level" % DB["world"]):
                self.xp_levels[int(level)] = total
                total += int(needed)
            self.xp_levels[max(self.xp_levels) + 1] = total

    def get(self):
        with self.lock:
            if self.data is None or time.time() - self.cached_at > CACHE_SECONDS:
                try:
                    self.data = self.collect()
                except Exception as error:  # keep the last good data, report the problem
                    data = dict(self.data or {})
                    data["error"] = str(error)
                    self.data = data
                self.cached_at = time.time()
            return self.data

    def collect(self):
        self.load_names()
        rows = mysql(
            "SELECT c.name, c.class, c.level, c.xp, c.online, TRIM(IFNULL(s.data, '0')), IFNULL(k.counter, 0), "
            "IFNULL(q.n, 0), c.totaltime, c.race, c.money, c.health, c.zone, "
            "c.map, c.position_x, c.position_y "
            "FROM {characters}.characters c JOIN {auth}.account a ON a.id = c.account "
            "LEFT JOIN {characters}.character_settings s ON s.guid = c.guid AND s.source = 'core.ascension_active_spec' "
            "LEFT JOIN {characters}.character_achievement_progress k ON k.guid = c.guid AND k.criteria = 5529 "
            "LEFT JOIN (SELECT guid, COUNT(*) n FROM {characters}.character_queststatus_rewarded GROUP BY guid) q "
            "ON q.guid = c.guid "
            # Only CoA's own custom classes (12+): Blizzard's original eleven (1-11) are excluded
            # everywhere this feeds (leaderboard, class ranking, roster, XP rate, roles, ...), same
            # filter the previous dashboard's bots_stats.py used.
            "WHERE a.username LIKE 'RNDBOT%' AND c.class > 11".format(**DB))
        bots = []
        for (name, cls, level, xp, online, spec, kills, quests, totaltime, race, money, health,
             zone, cmap, pos_x, pos_y) in rows:
            cls, spec, level, xp = int(cls), int(spec or 0), int(level), int(xp)
            bots.append({
                "name": name, "cls": self.classes.get(cls, str(cls)), "level": level, "xp": xp,
                "online": online == "1", "spec": self.specs.get("%d:%d" % (cls, spec), "") if spec else "",
                "role": role_of(spec), "kills": int(kills), "quests": int(quests), "hours": int(totaltime) / 3600.0,
                "faction": "alliance" if int(race) in ALLIANCE_RACES else "horde",
                "totalXp": self.xp_levels.get(level, 0) + xp,
                "gold": int(money) / 10000.0, "dead": int(health) == 0, "zone": int(zone),
                # Where the bot stands, for the map. These follow the character save
                # interval like every other figure here, so they lag live movement.
                "map": int(cmap), "x": float(pos_x), "y": float(pos_y),
            })

        online = [b for b in bots if b["online"]]
        totals = {
            "bots": len(bots),
            "online": len(online),
            "avgLevelOnline": round(sum(b["level"] for b in online) / len(online), 2) if online else 0,
            "maxLevel": max((b["level"] for b in bots), default=0),
            "lvl10": sum(1 for b in bots if b["level"] >= 10),
            "kills": sum(b["kills"] for b in bots),
            "quests": sum(b["quests"] for b in bots),
            "hours": round(sum(b["hours"] for b in bots)),
        }
        # Starting point of the "gains since" figures, kept on disk so restarting the dashboard does not reset it.
        # Delete baseline.json to start a new session.
        baseline_file = os.path.join(HERE, "baseline.json")
        if self.baseline is None and os.path.exists(baseline_file):
            self.baseline = json.load(open(baseline_file, encoding="utf-8"))
        if self.baseline is None:
            self.baseline = {"at": datetime.datetime.now().strftime("%d/%m %H:%M"), "ts": time.time(),
                             "kills": totals["kills"], "quests": totals["quests"],
                             "levels": sum(b["level"] for b in bots)}
            json.dump(self.baseline, open(baseline_file, "w", encoding="utf-8"))
        session = {
            "since": self.baseline["at"],
            "hours": round((time.time() - self.baseline["ts"]) / 3600.0, 3),
            "kills": totals["kills"] - self.baseline["kills"],
            "quests": totals["quests"] - self.baseline["quests"],
            "levels": sum(b["level"] for b in bots) - self.baseline["levels"],
        }
        if COUNT_FROM:
            # Test run: the big figures are the gains since the baseline, not the bots' whole lives.
            totals["kills"], totals["quests"] = session["kills"], session["quests"]

        # Hours the worldserver ran since the 1000-bot setup, from AzerothCore's own uptime table. The
        # table is written every 10 minutes: the running start is counted up to now instead.
        starts = mysql("SELECT starttime, uptime FROM %s.uptime "
                       "WHERE starttime >= UNIX_TIMESTAMP('%s') ORDER BY starttime" % (DB["auth"], UPTIME_SINCE))
        uptime_seconds = sum(int(up) for _, up in starts)
        if starts and server_state()["running"]:
            started, recorded = int(starts[-1][0]), int(starts[-1][1])
            uptime_seconds += max(0, int(time.time()) - started - recorded)
        uptime = {"hours": round(uptime_seconds / 3600.0, 1)}

        # Levels gained since the worldserver started, added up one level-up at a time: the sum of the
        # bots' levels also moves when level brackets send bots down, or far up, which is not play.
        server_start = int(starts[-1][0]) if starts else 0
        if self.level_ups.get("start") != server_start:
            # "total" goes on across restarts: it feeds the curves and the 24-hour comparison.
            self.level_ups = {"start": server_start, "gained": 0, "last": {}, "total": self.level_ups.get("total", 0)}
        self.level_ups.setdefault("total", self.level_ups["gained"])   # a levels.json from before the total
        last = self.level_ups["last"]
        for b in bots:
            before = last.get(b["name"])
            if before is not None and 0 < b["level"] - before <= 3:
                self.level_ups["gained"] += b["level"] - before
                self.level_ups["total"] = self.level_ups.get("total", 0) + b["level"] - before
            last[b["name"]] = b["level"]
        json.dump(self.level_ups, open(LEVELS_FILE, "w", encoding="utf-8"))
        session["levels"] = self.level_ups["gained"]
        session["levelHours"] = round((time.time() - server_start) / 3600.0, 3) if server_start else 0

        # Points for the curves, kept on disk so they survive a restart of the dashboard.
        now = time.time()
        if not self.history or now - self.history[-1]["ts"] >= HISTORY_EVERY:
            self.history.append({"ts": round(now), "kills": totals["kills"], "quests": totals["quests"],
                                 "levels": sum(b["level"] for b in bots), "levelUps": self.level_ups.get("total", 0),
                                 "avg": totals["avgLevelOnline"],
                                 "online": totals["online"],
                                 "dead": sum(1 for b in online if b["dead"])})
            self.history = [p for p in self.history if now - p["ts"] <= HISTORY_KEEP]
            json.dump(self.history, open(HISTORY_FILE, "w", encoding="utf-8"))

        # Experience of every bot once an hour: the gain over the last day is what the ranking uses.
        if not self.xp_history or now - self.xp_history[-1]["ts"] >= XP_EVERY:
            self.xp_history.append({"ts": round(now), "xp": {b["name"]: b["totalXp"] for b in bots}})
            self.xp_history = [p for p in self.xp_history if now - p["ts"] <= XP_KEEP]
            json.dump(self.xp_history, open(XP_FILE, "w", encoding="utf-8"))

        gains, stuck, oldest = [], None, self.xp_history[0] if self.xp_history else None
        if oldest and now - oldest["ts"] >= 600:      # under ten minutes the rate means nothing yet
            span = (now - oldest["ts"]) / 3600.0
            for b in bots:
                before = oldest["xp"].get(b["name"])
                if before is None or b["totalXp"] <= before:
                    continue
                gains.append({"name": b["name"], "cls": b["cls"], "spec": b["spec"], "role": b["role"],
                              "level": b["level"], "online": b["online"], "faction": b["faction"],
                              "xpPerHour": round((b["totalXp"] - before) / span)})
            gains.sort(key=lambda g: g["xpPerHour"], reverse=True)
            # A bot that is logged in, under the level cap and has not earned a single point of
            # experience over that whole span is stuck on something: that is what to go and look at.
            # Under an hour the figure means nothing - a bot can simply be walking to its next fight.
            if now - oldest["ts"] >= 3600:
                stuck = [b for b in bots if b["online"] and b["level"] < 60
                         and oldest["xp"].get(b["name"]) == b["totalXp"]]

        zone_counts = {}
        for b in online:
            zone_counts[b["zone"]] = zone_counts.get(b["zone"], 0) + 1

        # The last 24 hours against the 24 before them, from the same curve the page draws.
        def between(start, end, key):
            inside = [p for p in self.history if start <= p["ts"] <= end and key in p]
            return (inside[-1][key] - inside[0][key]) if len(inside) > 1 else None

        compare = {}
        # Levels from the level-up count: the sum of levels drops whenever brackets send bots back to level 1.
        for key, source in (("kills", "kills"), ("quests", "quests"), ("levels", "levelUps")):
            today = between(now - 24 * 3600, now, source)
            before = between(now - 48 * 3600, now - 24 * 3600, source)
            compare[key] = {"today": today, "before": before}

        def top(key, extra=None):
            ordered = sorted(bots, key=key, reverse=True)[:10]
            return [{k: b[k] for k in ("name", "cls", "spec", "role", "level", "xp", "kills", "quests", "online")}
                    for b in ordered]

        by_class = {}
        for b in bots:
            c = by_class.setdefault(b["cls"], {"name": b["cls"], "bots": 0, "levels": 0, "kills": 0, "best": None})
            c["bots"] += 1
            c["levels"] += b["level"]
            c["kills"] += b["kills"]
            c.setdefault("members", []).append(b)
            if c["best"] is None or (b["level"], b["xp"]) > (c["best"]["level"], c["best"]["xp"]):
                c["best"] = {"name": b["name"], "level": b["level"], "xp": b["xp"]}
        for c in by_class.values():
            ranked = sorted(c.pop("members"), key=lambda m: (m["level"], m["xp"]), reverse=True)
            # The three highest of the class, experience included so equal levels still separate.
            c["podium"] = [{"name": m["name"], "level": m["level"], "xp": m["xp"], "spec": m["spec"],
                            "role": m["role"], "online": m["online"], "faction": m["faction"]}
                           for m in ranked[:3]]
            # The same top-ten cut as the leaderboard, but within this one class -- the class ranking's
            # own drilldown (ported from the previous dashboard's per-class tabs).
            c["top"] = [{"name": m["name"], "level": m["level"], "kills": m["kills"], "quests": m["quests"],
                        "online": m["online"], "faction": m["faction"], "role": m["role"]}
                       for m in ranked[:10]]
        classes = sorted(({"name": c["name"], "bots": c["bots"], "avgLevel": round(c["levels"] / c["bots"], 2),
                           "kills": c["kills"], "best": c["best"], "podium": c["podium"], "top": c["top"]}
                          for c in by_class.values()),
                         key=lambda c: c["avgLevel"], reverse=True)

        levels = {}
        for b in online:
            levels[b["level"]] = levels.get(b["level"], 0) + 1
        specs = {}
        for b in bots:
            if b["spec"]:
                k = (b["cls"], b["spec"], b["role"])
                specs[k] = specs.get(k, 0) + 1

        build = None
        if os.path.exists(BUILD_FILE):
            try:
                build = json.load(open(BUILD_FILE, encoding="utf-8-sig"))
            except (OSError, ValueError):
                build = None

        return {
            "build": build,
            "generatedAt": datetime.datetime.now().strftime("%H:%M:%S"),
            "generatedTs": round(time.time()),
            "server": server_state(),
            "totals": totals,
            "session": session,
            "uptime": uptime,
            "history": self.history,
            "actions": action_usage((time.time() - COUNT_FROM) / 3600.0) if COUNT_FROM else action_usage(),
            "top": {
                "xp": top(lambda b: (b["level"], b["xp"])),
                "kills": top(lambda b: b["kills"]),
                "quests": top(lambda b: b["quests"]),
            },
            "roles": {r: sum(1 for b in online if b["role"] == r) for r in ("tank", "heal", "dps", "none")},
            "factions": {
                "online": {f: sum(1 for b in online if b["faction"] == f) for f in ("alliance", "horde")},
                "all": {f: sum(1 for b in bots if b["faction"] == f) for f in ("alliance", "horde")},
                "levelOnline": {f: round(sum(b["level"] for b in online if b["faction"] == f) /
                                         max(1, sum(1 for b in online if b["faction"] == f)), 1)
                                for f in ("alliance", "horde")},
            },
            "xpRate": {"hours": round((now - oldest["ts"]) / 3600.0, 1) if oldest else 0, "top": gains[:10]},
            "chat": chat_stats(bots={b["name"] for b in bots}),
            "watch": {
                "deadNow": sum(1 for b in online if b["dead"]),
                "stuck": None if stuck is None else len(stuck),
                "stuckNames": None if stuck is None else [b["name"] for b in sorted(
                    stuck, key=lambda b: b["level"])[:8]],
                "incidents": incidents(),
            },
            "zones": [{"name": self.zones.get(zone, "Zone %d" % zone), "count": n,
                       "alliance": sum(1 for b in online if b["zone"] == zone and b["faction"] == "alliance")}
                      for zone, n in sorted(zone_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]],
            "compare": compare,
            # "footer" in dashboard.json replaces the page's own line, and "" removes it: a server
            # that shares its page before it is ready may not want to point at its sources yet.
            "footer": SETTINGS.get("footer"),
            "classNames": {str(k): v for k, v in self.classes.items()},
            "bots": [{"n": b["name"], "c": b["cls"], "s": b["spec"], "r": b["role"], "l": b["level"],
                      "k": b["kills"], "q": b["quests"], "g": round(b["gold"], 1), "o": b["online"],
                      "f": b["faction"], "z": self.zones.get(b["zone"], ""), "h": round(b["hours"], 1),
                      "m": b["map"], "x": round(b["x"], 1), "y": round(b["y"], 1), "d": b["dead"]}
                     for b in bots],
            "loot": loot_feed(),
            "classes": classes,
            "levels": [{"level": lvl, "count": levels[lvl]} for lvl in sorted(levels)],
            "specs": [{"cls": c, "spec": s, "role": r, "count": n}
                      for (c, s, r), n in sorted(specs.items(), key=lambda item: item[1], reverse=True)],
        }


STATS = Stats()


def write_atomic(path, body):
    # Visitors never read a half-written file: write aside, then swap.
    temporary = path + ".tmp"
    with open(temporary, "wb") as handle:
        handle.write(body)
    os.replace(temporary, path)


# What pclab.fr/bots and any other public copy may carry, key by key. A key added to the stats
# later stays on this machine until it is listed here: the public copy is chosen, not filtered.
PUBLIC_KEYS = ("build", "generatedAt", "generatedTs", "totals", "session", "uptime", "history", "actions",
               "top", "roles", "factions", "xpRate", "zones", "compare", "footer", "classNames", "bots",
               "loot", "classes", "levels", "specs")


def public_copy(data):
    """Stats for the public page. Never: real players' chat, memory, crashes, the watch journal,
    paths, configuration or error text."""
    public = {key: data[key] for key in PUBLIC_KEYS if key in data}
    public["server"] = {"running": bool((data.get("server") or {}).get("running"))}
    watch = data.get("watch") or {}
    public["watch"] = {key: watch.get(key) for key in ("deadNow", "stuck", "stuckNames")}
    # Only what bots said, counted: no line of text, and no real player's name.
    public["chat"] = (data.get("chat") or {}).get("bots")
    # The bots online only: the map and the roster show nothing else, and the offline ones were two
    # thirds of the file. A name of an offline bot in a ranking is then shown, not linked.
    public["bots"] = [bot for bot in data.get("bots") or [] if bot.get("o")]
    return public


# Code between these markers only works against the local server (settings, map extraction, the live chat
# feed, live status). The public copy is built without it, so it is absent there, not just hidden.
PRIVATE_JS = re.compile(r"/\* private:start \*/.*?/\* private:end \*/", re.S)
PRIVATE_HTML = re.compile(r"<!-- private:start -->.*?<!-- private:end -->", re.S)
# Nothing of the kind may survive into a public file; publishing stops if one does.
PRIVATE_LEFT = re.compile(r"/api/|private:(?:start|end)|id=\"(?:settings|feedCard|artPrompt|artPanel)\"")


def public_files():
    """{relative path: bytes} of the public page, checked for private leftovers."""
    def read(*parts):
        return open(os.path.join(HERE, *parts), "rb").read()

    script = PRIVATE_JS.sub("", read("static", "dashboard.js").decode("utf-8"))
    script = script.replace('const API = "/api/stats";', 'const API = "stats.json";', 1)                    .replace("const PUBLIC = false;", "const PUBLIC = true;", 1)
    style = read("static", "dashboard.css")
    page = PRIVATE_HTML.sub("", read("index.html").decode("utf-8"))
    # A visitor's browser keeps the old script and style otherwise: name each by its content.
    for name, body in (("dashboard.js", script.encode("utf-8")), ("dashboard.css", style)):
        page = page.replace('"static/%s"' % name,
                            '"static/%s?v=%s"' % (name, hashlib.sha1(body).hexdigest()[:10]), 1)
    for name, text in (("index.html", page), ("dashboard.js", script)):
        left = PRIVATE_LEFT.search(text)
        if left:
            raise RuntimeError("private code left in the public %s: %r" % (name, left.group(0)))
    if "const PUBLIC = true;" not in script:
        raise RuntimeError("the public dashboard.js is not switched to its public mode")

    files = {"index.html": page.encode("utf-8"), "static/dashboard.js": script.encode("utf-8"),
             "static/dashboard.css": style}
    if os.path.exists(os.path.join(HERE, "worldmap.json")):
        files["worldmap.json"] = read("worldmap.json")          # zone outlines only, no game art
    fonts = os.path.join(HERE, "static", "fonts")
    for name in os.listdir(fonts):
        files["static/fonts/" + name] = read("static", "fonts", name)
    return files


def publish_static():
    """Copy the public page to PUBLISH_DIR, unchanged files left alone."""
    for relative, body in public_files().items():
        target = os.path.join(PUBLISH_DIR, *relative.split("/"))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        try:
            if open(target, "rb").read() == body:
                continue
        except OSError:
            pass
        write_atomic(target, body)


MAP_FILE = re.compile(r"^(?:[0-9]+|zones/[A-Za-z0-9]+)\.png$")


def map_files():
    """The maps the page can show: one per continent of worldmap.json and one per zone in it."""
    try:
        world = json.load(open(os.path.join(HERE, "worldmap.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    names = {"%s.png" % key for key in world.get("continents", {})}
    names |= {"zones/%s.png" % z["name"] for c in world.get("continents", {}).values() for z in c.get("zones", [])}
    names |= {"zones/%s.png" % z["name"] for z in world.get("offworld", [])}
    return names


def publish_maps():
    """Copy the maps the page shows (extracted from the client into maps/) beside the public page.
    About 70 MB: a file is copied only when it is new or its size or date changed, never re-read."""
    source = os.path.join(HERE, "maps")
    if not os.path.isdir(source):
        return
    wanted = map_files()
    for folder, _dirs, names in os.walk(source):
        for name in names:
            path = os.path.join(folder, name)
            relative = os.path.relpath(path, source).replace(os.sep, "/")
            if not MAP_FILE.match(relative) or relative not in wanted:
                continue
            target = os.path.join(PUBLISH_DIR, "maps", *relative.split("/"))
            here = os.stat(path)
            try:
                there = os.stat(target)
                if there.st_size == here.st_size and int(there.st_mtime) == int(here.st_mtime):
                    continue
            except OSError:
                pass
            os.makedirs(os.path.dirname(target), exist_ok=True)
            write_atomic(target, open(path, "rb").read())
            os.utime(target, (here.st_atime, here.st_mtime))


def publish_loop():
    while True:
        try:
            data = STATS.get()
            os.makedirs(PUBLISH_DIR, exist_ok=True)
            publish_static()
            publish_maps()
            write_atomic(os.path.join(PUBLISH_DIR, "stats.json"),
                         json.dumps(public_copy(data), ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        except Exception as error:  # the NAS may be asleep or unreachable: retry next minute
            print("Public copy failed:", error, flush=True)
        time.sleep(PUBLISH_EVERY)


def config_payload():
    """Current bot settings, plus whether the server is up.

    This never touches the database, so the settings panel works with the server
    stopped, which is when it is most useful.
    """
    settings = botconfig.read_settings(CONFIG_DIR)
    notes = []
    # Say so when the LLM chat module's config is not there, rather than leaving a
    # gap the user has to guess at.
    if any(not s["present"] for s in settings if s["file"] == botconfig.BOTMINDS):
        notes.append("LLM chat settings appear once mod-bot-minds is installed "
                     "and its mod_bot_minds.conf is in the modules folder.")
    return {
        "settings": settings,
        "warnings": botconfig.override_warnings(settings),
        "overrides": botconfig.OVERRIDES,
        "recipes": botconfig.RECIPES,
        "configDir": CONFIG_DIR,
        "serverRunning": server_state().get("running", False),
        "notes": notes,
    }


# The maps: tools/gen_art.py reads the player's own client and writes maps/ (maps only,
# no interface art).
# The page's button runs it here, in a child process with this same Python, so nothing
# needs installing. One run at a time; its progress is kept for GET /api/art.
ART_TOOL = os.path.join(HERE, "tools", "gen_art.py")
ART_LOCK = threading.Lock()
ART_JOB = {"running": False, "step": 0, "total": 0, "label": "", "log": [], "error": None,
           "finished": None, "client": None}


def guess_client():
    """A game client folder near the repack: one holding Data/common.MPQ. `gameClient` in
    dashboard.json wins; otherwise the repack's own folder, its children and its
    siblings are looked at, which covers the usual repack-beside-client layout."""
    if SETTINGS.get("gameClient"):
        return SETTINGS["gameClient"]
    if not ROOT:
        return None
    parent = os.path.dirname(os.path.abspath(ROOT))
    places = [ROOT]
    for folder in (ROOT, parent):
        try:
            places += [os.path.join(folder, name) for name in sorted(os.listdir(folder))]
        except OSError:
            pass
    for place in places:
        if os.path.isfile(os.path.join(place, "Data", "common.MPQ")):
            return place
    return None


def art_status():
    """What maps are on disk, the current or last run, and a client folder to suggest."""
    maps = glob.glob(os.path.join(HERE, "maps", "*.png")) + glob.glob(os.path.join(HERE, "maps", "zones", "*.png"))
    with ART_LOCK:
        job = dict(ART_JOB, log=ART_JOB["log"][-12:])
    return {
        "maps": len(maps),
        "job": job,
        "suggestedClient": guess_client(),
        "dbcDir": DBC_DIR,
    }


def run_art(client):
    """Run tools/gen_art.py to the end, keeping ART_JOB current. Runs on its own thread."""
    art_exe = os.path.join(HERE, "tools", "gen_art.exe")
    if os.path.isfile(art_exe):
        command = [art_exe, "--client", client, "--dbc", DBC_DIR, "--root", HERE]
    else:
        command = [sys.executable, "-B", ART_TOOL, "--client", client, "--dbc", DBC_DIR, "--root", HERE]
    try:
        child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, encoding="utf-8", errors="replace",
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for line in child.stdout:
            line = line.rstrip()
            with ART_LOCK:
                match = re.match(r"^STEP (\d+)/(\d+) (.*)$", line)
                if match:
                    ART_JOB["step"], ART_JOB["total"] = int(match.group(1)), int(match.group(2))
                    ART_JOB["label"] = match.group(3)
                else:
                    ART_JOB["log"].append(line)
                    if line.startswith("ERROR "):
                        ART_JOB["error"] = line[len("ERROR "):]
        code = child.wait()
        with ART_LOCK:
            if code and not ART_JOB["error"]:
                ART_JOB["error"] = (ART_JOB["log"] or ["the tool stopped with code %d" % code])[-1]
    except OSError as error:
        with ART_LOCK:
            ART_JOB["error"] = "could not start the tool: %s" % error
    with ART_LOCK:
        ART_JOB["running"] = False
        ART_JOB["finished"] = time.time()


def start_art(client):
    """Start a run; returns None, or why it cannot start."""
    client = (client or "").strip().strip('"')
    if not client:
        return "Give the game client folder."
    if not os.path.isfile(os.path.join(client, "Data", "common.MPQ")):
        return "No Data\\common.MPQ in %s: pick the folder the game itself is installed in." % client
    if not DBC_DIR or not os.path.isfile(os.path.join(DBC_DIR, "ChrClasses.dbc")):
        return "The server's dbc folder was not found; set dbcDir in dashboard.json."
    with ART_LOCK:
        if ART_JOB["running"]:
            return "Already running."
        ART_JOB.update({"running": True, "step": 0, "total": 0, "label": "Starting", "log": [],
                        "error": None, "finished": None, "client": client})
    threading.Thread(target=run_art, args=(client,), daemon=True).start()
    return None


class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, body, content_type, status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload, status=200):
        self._send(json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8", status)

    # The server binds to 127.0.0.1, but a web page open in the same browser can still reach it:
    # a foreign site can POST a form to localhost (CSRF), or point its own name at 127.0.0.1 and
    # read the answers (DNS rebinding). So every request must name this server in Host, and a
    # write must also come from this page (Origin) with a JSON body, which no form can send.
    def _allowed_hosts(self):
        return {"%s:%d" % (name, PORT) for name in ("127.0.0.1", "localhost", "[::1]")}

    def _own_host(self):
        if (self.headers.get("Host") or "").lower() in self._allowed_hosts():
            return True
        self._json({"error": "unknown host"}, 403)
        return False

    def _local_only(self):
        origin = (self.headers.get("Origin") or "").lower()
        content_type = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if self.client_address[0] not in ("127.0.0.1", "::1"):
            self._json({"error": "writes are allowed from this machine only"}, 403)
            return False
        if origin and origin not in {"http://" + host for host in self._allowed_hosts()}:
            self._json({"error": "writes are allowed from this dashboard's own page only"}, 403)
            return False
        if content_type != "application/json":
            self._json({"error": "expected Content-Type: application/json"}, 415)
            return False
        return True

    def do_GET(self):
        if not self._own_host():
            return
        path = self.path.split("?")[0]
        if path == "/api/stats":
            self._json(STATS.get())
        elif path == "/api/config":
            self._json(config_payload())
        elif path == "/api/art":
            self._json(art_status())
        elif path == "/api/live":
            self._send(live_status_body(), "application/json; charset=utf-8")
        elif path == "/api/chat":
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            first = lambda key: (query.get(key) or [None])[0]  # noqa: E731
            self._json(chat_feed(first("limit") or 100, first("kind"), first("q"), first("bot")))
        elif path == "/worldmap.json":
            target = os.path.join(HERE, "worldmap.json")
            if not os.path.exists(target):
                self._json({"error": "worldmap.json has not been generated"}, 404)
                return
            self._send(open(target, "rb").read(), "application/json; charset=utf-8")
        elif path.startswith("/maps/"):
            # The stitched continent and zone maps, extracted from the client by
            # tools/gen_mapart.py. Only "<id>.png" and "zones/<Folder>.png" are served.
            leaf = path[len("/maps/"):]
            if not re.match(r"^(?:[0-9]+|zones/[A-Za-z0-9]+)\.png$", leaf):
                self.send_error(404)
                return
            target = os.path.join(HERE, "maps", *leaf.split("/"))
            if not os.path.exists(target):
                self.send_error(404)
                return
            body = open(target, "rb").read()
            stamp = time.strftime("%a, %d %b %Y %H:%M:%S GMT",
                                  time.gmtime(os.path.getmtime(target)))
            if self.headers.get("If-Modified-Since") == stamp:
                self.send_response(304)
                self.send_header("Last-Modified", stamp)
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            # Revalidate rather than cache hard: regenerating the art must show up
            # immediately, and a 304 costs nothing.
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Last-Modified", stamp)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path.startswith("/static/"):
            leaf = path[len("/static/"):]
            kind = STATIC_TYPES.get(os.path.splitext(leaf)[1])
            if not kind or not re.match(
                r"^(?:[a-z0-9-]+\.(?:css|js|woff2)"
                r"|fonts/[a-z0-9-]+\.woff2"
                r"|race-portraits/[a-z0-9_-]+\.(?:png|jpg|jpeg|webp)"
                r"|race-icons/[A-Za-z0-9_-]+\.(?:png|jpg|jpeg|webp))$", leaf):
                self.send_error(404)
                return
            target = os.path.join(HERE, "static", *leaf.split("/"))
            if not os.path.exists(target):
                self.send_error(404)
                return
            self._send(open(target, "rb").read(), kind)
        elif path in ("/", "/index.html"):
            self._send(open(os.path.join(HERE, "index.html"), "rb").read(),
                       "text/html; charset=utf-8")
        else:
            self.send_error(404)

    def do_POST(self):
        if not self._own_host():
            return
        path = self.path.split("?")[0]
        if path == "/api/art":
            if not self._local_only():
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            except ValueError:
                self._json({"error": "expected a JSON object"}, 400)
                return
            problem = start_art(body.get("client") if isinstance(body, dict) else None)
            if problem:
                self._json({"error": problem}, 400)
                return
            self._json(art_status())
            return
        if path != "/api/config":
            self.send_error(404)
            return
        if not self._local_only():
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            changes = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            if not isinstance(changes, dict) or not changes:
                self._json({"error": "expected a JSON object of settings"}, 400)
                return
            written, backups, errors = botconfig.apply_settings(
                CONFIG_DIR, changes, CONFIG_BACKUPS)
            if errors:
                self._json({"errors": errors}, 400)
                return
            running = server_state().get("running", False)
            self._json({
                "written": written,
                "backups": [os.path.basename(b) for b in backups],
                "serverRunning": running,
                # Read at startup, so a stopped server needs nothing further.
                "note": ("The server is running, so settings marked restart will not take "
                         "effect until it is restarted."
                         if running else
                         "The server is stopped, so these take effect the next time it starts."),
                "settings": botconfig.read_settings(CONFIG_DIR),
            })
        except Exception as error:               # noqa: BLE001 - report, never 500 blindly
            self._json({"error": "%s: %s" % (type(error).__name__, error)}, 500)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print("SquidBots dashboard: http://localhost:%d  (Ctrl+C to stop)" % PORT, flush=True)
    if PUBLISH_DIR:
        threading.Thread(target=publish_loop, daemon=True).start()
        threading.Thread(target=live_publish_loop, daemon=True).start()
        print("Public copy refreshed every minute in %s (live view every %d s)" % (PUBLISH_DIR, LIVE_PUBLISH_EVERY),
              flush=True)
    server.serve_forever()
