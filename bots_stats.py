"""Bot statistics for the Bots page, adapted from Zyth45/squidbots-dashboard.

Read-only: everything comes from one SQL query against the game databases, so the
figures follow how often characters are saved (PlayerSaveInterval), not every kill.
`query` is dashboard_server.query_rows (database, sql) -> list of dicts.
"""

import json
import os
import struct
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(HERE, "bots_history.json")
HISTORY_EVERY = 10 * 60          # one curve point every 10 minutes
HISTORY_KEEP = 7 * 24 * 3600     # a week of points
XP_FILE = os.path.join(HERE, "bots_xp_history.json")
XP_EVERY = 3600                  # experience of every bot once an hour
XP_KEEP = 25 * 3600
# Active-spec ids (character_settings core.ascension_active_spec) that count as healer / tank, as in SquidBots.
HEAL = {6, 31, 37, 40, 43, 51, 98, 101}
TANK = {9, 17, 21, 22, 48, 52, 57, 60, 96, 97, 99, 100}

CACHE_SECONDS = 20

# Human, Dwarf, Night Elf, Gnome, Draenei; every other race is Horde.
ALLIANCE_RACES = {1, 3, 4, 7, 11}

# Base WotLK classes; CoA custom classes come from acore_world.ascension_custom_class.
BASE_CLASSES = {
    1: "Warrior", 2: "Paladin", 3: "Hunter", 4: "Rogue", 5: "Priest", 6: "Death Knight",
    7: "Shaman", 8: "Mage", 9: "Warlock", 11: "Druid",
}

SQL = (
    "SELECT c.name, c.class, c.level, c.xp, c.online, c.race, c.money, c.health, c.zone, c.totaltime, "
    "IFNULL(q.n, 0) AS quests, TRIM(IFNULL(s.data, '0')) AS spec, IFNULL(k.counter, 0) AS kills "
    "FROM acore_characters.characters c JOIN acore_auth.account a ON a.id = c.account "
    "LEFT JOIN acore_characters.character_settings s ON s.guid = c.guid AND s.source = 'core.ascension_active_spec' "
    "LEFT JOIN acore_characters.character_achievement_progress k ON k.guid = c.guid AND k.criteria = 5529 "
    "LEFT JOIN (SELECT guid, COUNT(*) n FROM acore_characters.character_queststatus_rewarded GROUP BY guid) q "
    "ON q.guid = c.guid WHERE a.username LIKE 'RNDBOT%' AND c.class > 11"
)


def zone_names(dbc_dirs):
    """Zone names from AreaTable.dbc: characters.zone holds an area id. Empty when the file is not found."""
    for folder in dbc_dirs:
        path = os.path.join(folder, "AreaTable.dbc")
        if not os.path.exists(path):
            continue
        raw = open(path, "rb").read()
        magic, records, fields, size, _ = struct.unpack("<4siiii", raw[:20])
        if magic != b"WDBC" or fields < 12:
            continue
        body, block = raw[20:20 + records * size], raw[20 + records * size:]
        names = {}
        for i in range(records):
            row = struct.unpack_from("<%dI" % fields, body, i * size)
            name = block[row[11]:block.index(b"\0", row[11])].decode("utf-8", "replace")
            if name:
                names[row[0]] = name
        return names
    return {}


class BotStats:
    def __init__(self, query, dbc_dirs=(), server_running=None):
        self.query = query
        # A crash leaves characters.online = 1 behind: with the worldserver down nobody is online.
        self.server_running = server_running or (lambda: True)
        self.dbc_dirs = list(dbc_dirs)
        self.lock = threading.Lock()
        self.cached_at = 0.0
        self.data = None
        self.classes = None
        self.zones = None
        self.history = json.load(open(HISTORY_FILE, encoding="utf-8")) if os.path.exists(HISTORY_FILE) else []
        self.xp_history = json.load(open(XP_FILE, encoding="utf-8")) if os.path.exists(XP_FILE) else []
        self.xp_levels = {}

    def get(self):
        with self.lock:
            if self.data is None or time.time() - self.cached_at > CACHE_SECONDS:
                try:
                    self.data = self.collect()
                except Exception as error:  # keep the last good data, report the problem
                    self.data = dict(self.data or {}, error=str(error))
                self.cached_at = time.time()
            return self.data

    def collect(self):
        if self.classes is None:
            self.classes = dict(BASE_CLASSES)
            for row in self.query("acore_world", "SELECT class, client_name FROM ascension_custom_class"):
                self.classes[int(row["class"])] = row["client_name"]
        if self.zones is None:
            self.zones = zone_names(self.dbc_dirs)
        if not self.xp_levels:
            # Experience needed to reach each level, so levels and experience compare as one number.
            total = 0
            for row in self.query("acore_world", "SELECT Level, Experience FROM player_xp_for_level ORDER BY Level"):
                self.xp_levels[int(row["Level"])] = total
                total += int(row["Experience"])
            self.xp_levels[max(self.xp_levels) + 1] = total

        world_up = self.server_running()
        bots = []
        for r in self.query("acore_characters", SQL):
            level = int(r["level"])
            spec = int(r["spec"] or 0)
            bots.append({
                "totalXp": self.xp_levels.get(level, 0) + int(r["xp"]),
                "role": "none" if not spec else "heal" if spec in HEAL else "tank" if spec in TANK else "dps",
                "kills": int(r["kills"]),
                "name": r["name"], "cls": self.classes.get(int(r["class"]), "Class %s" % r["class"]),
                "level": level, "xp": int(r["xp"]), "online": world_up and r["online"] == "1",
                "faction": "alliance" if int(r["race"]) in ALLIANCE_RACES else "horde",
                "gold": int(r["money"]) / 10000.0, "dead": int(r["health"]) == 0,
                "zone": int(r["zone"]), "hours": int(r["totaltime"]) / 3600.0, "quests": int(r["quests"]),
            })
        online = [b for b in bots if b["online"]]

        def avg_level(group):
            return round(sum(b["level"] for b in group) / len(group), 1) if group else 0

        zone_counts = {}
        for b in online:
            zone_counts[b["zone"]] = zone_counts.get(b["zone"], 0) + 1
        levels = {}
        for b in online:
            levels[b["level"]] = levels.get(b["level"], 0) + 1
        by_class = {}
        for b in bots:
            by_class.setdefault(b["cls"], []).append(b)

        now = time.time()
        totals = {
            "bots": len(bots), "online": len(online), "avgLevelOnline": avg_level(online),
            "maxLevel": max((b["level"] for b in bots), default=0),
            "kills": sum(b["kills"] for b in bots), "quests": sum(b["quests"] for b in bots),
            "hours": round(sum(b["hours"] for b in bots)), "deadNow": sum(1 for b in online if b["dead"]),
        }
        if not self.history or now - self.history[-1]["ts"] >= HISTORY_EVERY:
            self.history.append({"ts": round(now), "kills": totals["kills"], "quests": totals["quests"],
                                 "online": totals["online"], "avg": totals["avgLevelOnline"],
                                 "dead": totals["deadNow"]})
            self.history = [p for p in self.history if now - p["ts"] <= HISTORY_KEEP]
            json.dump(self.history, open(HISTORY_FILE, "w", encoding="utf-8"))

        # Experience of every bot once an hour: the gain since the oldest reading is what the ranking uses.
        if not self.xp_history or now - self.xp_history[-1]["ts"] >= XP_EVERY:
            self.xp_history.append({"ts": round(now), "xp": {b["name"]: b["totalXp"] for b in bots}})
            self.xp_history = [p for p in self.xp_history if now - p["ts"] <= XP_KEEP]
            json.dump(self.xp_history, open(XP_FILE, "w", encoding="utf-8"))
        gains, oldest = [], self.xp_history[0]
        span = (now - oldest["ts"]) / 3600.0
        if span >= 10 / 60.0:          # under ten minutes the rate means nothing yet
            for b in bots:
                before = oldest["xp"].get(b["name"])
                if before is None or b["totalXp"] <= before:
                    continue
                gains.append({"name": b["name"], "cls": b["cls"], "role": b["role"], "level": b["level"],
                              "online": b["online"], "faction": b["faction"],
                              "gain": b["totalXp"] - before, "perHour": round((b["totalXp"] - before) / span)})
            gains.sort(key=lambda g: g["perHour"], reverse=True)

        def board(key):
            return [{k: b[k] for k in ("name", "cls", "level", "kills", "quests", "online", "faction", "role")}
                    for b in sorted(bots, key=key, reverse=True)[:10]]

        zone_alliance = {}
        for b in online:
            if b["faction"] == "alliance":
                zone_alliance[b["zone"]] = zone_alliance.get(b["zone"], 0) + 1
        buckets = [("1-9", 1, 9), ("10-19", 10, 19), ("20-29", 20, 29), ("30-39", 30, 39), ("40-49", 40, 49), ("50-60", 50, 60)]

        return {
            "generatedAt": time.strftime("%H:%M:%S"),
            "totals": totals,
            "history": self.history,
            "xpRate": {"hours": round(span, 1), "top": gains[:10]},
            "boards": {"xp": board(lambda b: (b["level"], b["xp"])), "kills": board(lambda b: b["kills"]),
                       "quests": board(lambda b: b["quests"])},
            "roles": {r: sum(1 for b in online if b["role"] == r) for r in ("tank", "heal", "dps", "none")},
            "factions": {f: {"online": sum(1 for b in online if b["faction"] == f),
                             "all": sum(1 for b in bots if b["faction"] == f),
                             "avgLevel": avg_level([b for b in online if b["faction"] == f])}
                         for f in ("alliance", "horde")},
            "zones": [{"name": self.zones.get(z, "Zone %d" % z), "count": n, "alliance": zone_alliance.get(z, 0)}
                      for z, n in sorted(zone_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]],
            "spread": [{"label": label, "count": sum(1 for b in online if lo <= b["level"] <= hi)}
                       for label, lo, hi in buckets],
            "classes": sorted(({"name": name, "bots": len(g), "online": sum(1 for b in g if b["online"]),
                                "avgLevel": avg_level(g), "kills": sum(b["kills"] for b in g),
                                "podium": [{"name": m["name"], "level": m["level"], "online": m["online"]}
                                           for m in sorted(g, key=lambda b: (b["level"], b["xp"]), reverse=True)[:3]],
                                "top": [{k: m[k] for k in ("name", "level", "kills", "quests", "online", "faction", "role")}
                                        for m in sorted(g, key=lambda b: (b["level"], b["xp"]), reverse=True)[:15]],
                                "best": max(g, key=lambda b: (b["level"], b["xp"]))["name"],
                                "bestLevel": max(b["level"] for b in g)} for name, g in by_class.items()),
                               key=lambda c: c["avgLevel"], reverse=True),
            "top": [{k: b[k] for k in ("name", "cls", "level", "quests", "kills", "online", "faction", "role")}
                    for b in sorted(bots, key=lambda b: (b["level"], b["xp"]), reverse=True)[:10]],
            "bots": [{"n": b["name"], "c": b["cls"], "l": b["level"], "q": b["quests"], "k": b["kills"],
                      "g": round(b["gold"], 1), "o": b["online"], "f": b["faction"], "d": b["dead"], "r": b["role"],
                      "z": self.zones.get(b["zone"], "Zone %d" % b["zone"]), "h": round(b["hours"], 1)}
                     for b in bots],
        }
