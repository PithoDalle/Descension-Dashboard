"""Item tooltip data for the dashboard's "Add item" page.

Builds a WoW-style tooltip (stats, weapon damage, sockets, Use/Equip effects ...) from the world DB's item_template
plus the server's own Spell.dbc, so custom (CoA) spells are described too. Pure stdlib.
"""
import math
import mmap
import os
import re
import struct
import threading

QUALITY_NAMES = ["Poor", "Common", "Uncommon", "Rare", "Epic", "Legendary", "Artifact", "Heirloom"]
BONDING = {1: "Binds when picked up", 2: "Binds when equipped", 3: "Binds when used", 4: "Quest Item", 5: "Quest Item"}
SLOTS = {1: "Head", 2: "Neck", 3: "Shoulder", 4: "Shirt", 5: "Chest", 6: "Waist", 7: "Legs", 8: "Feet", 9: "Wrist", 10: "Hands",
         11: "Finger", 12: "Trinket", 13: "One-Hand", 14: "Shield", 15: "Ranged", 16: "Back", 17: "Two-Hand", 18: "Bag", 19: "Tabard",
         20: "Chest", 21: "Main Hand", 22: "Off Hand", 23: "Held In Off-hand", 24: "Ammo", 25: "Thrown", 26: "Ranged", 28: "Relic"}
WEAPON_SUB = {0: "Axe", 1: "Two-Handed Axe", 2: "Bow", 3: "Gun", 4: "Mace", 5: "Two-Handed Mace", 6: "Polearm", 7: "Sword",
              8: "Two-Handed Sword", 10: "Staff", 13: "Fist Weapon", 14: "Miscellaneous", 15: "Dagger", 16: "Thrown", 17: "Spear",
              18: "Crossbow", 19: "Wand", 20: "Fishing Pole"}
ARMOR_SUB = {1: "Cloth", 2: "Leather", 3: "Mail", 4: "Plate", 6: "Shield", 7: "Libram", 8: "Idol", 9: "Totem", 10: "Sigil"}
STAT_NAMES = {0: "Mana", 1: "Health", 3: "Agility", 4: "Strength", 5: "Intellect", 6: "Spirit", 7: "Stamina"}
# rating stats: shown as "Equip: Increases your X rating by N."
STAT_RATINGS = {12: "defense rating", 13: "dodge rating", 14: "parry rating", 15: "shield block rating", 16: "melee hit rating",
                17: "ranged hit rating", 18: "spell hit rating", 19: "melee critical strike rating", 20: "ranged critical strike rating",
                21: "spell critical strike rating", 22: "melee hit avoidance rating", 23: "ranged hit avoidance rating",
                24: "spell hit avoidance rating", 25: "melee critical avoidance rating", 26: "ranged critical avoidance rating",
                27: "spell critical avoidance rating", 28: "melee haste rating", 29: "ranged haste rating", 30: "spell haste rating",
                31: "hit rating", 32: "critical strike rating", 33: "hit avoidance rating", 34: "critical avoidance rating",
                35: "resilience rating", 36: "haste rating", 37: "expertise rating"}
STAT_SPECIAL = {38: "Increases attack power by {}.", 39: "Increases ranged attack power by {}.", 40: "Increases feral attack power by {}.",
                41: "Increases healing done by spells and effects by up to {}.", 42: "Increases damage done by magical spells and effects by up to {}.",
                43: "Restores {} mana per 5 sec.", 44: "Your attacks ignore {} of your opponent's armor.",
                45: "Increases spell power by {}.", 46: "Restores {} health per 5 sec.", 47: "Increases your spell penetration by {}.",
                48: "Increases the block value of your shield by {}."}
RESISTS = (("holy_res", "Holy"), ("fire_res", "Fire"), ("nature_res", "Nature"), ("frost_res", "Frost"),
           ("shadow_res", "Shadow"), ("arcane_res", "Arcane"))
DMG_TYPES = {0: "", 1: "Holy ", 2: "Fire ", 3: "Nature ", 4: "Frost ", 5: "Shadow ", 6: "Arcane "}
SOCKETS = {1: "Meta Socket", 2: "Red Socket", 4: "Yellow Socket", 8: "Blue Socket"}
TRIGGERS = {0: "Use", 1: "Equip", 2: "Chance on hit", 4: "Soulstone", 5: "Use", 6: "Use"}
SPELL_FIELDS = 234
F_DURATION, F_PROCCHANCE, F_PROCCHARGES, F_DIESIDES, F_BASEPOINTS, F_RADIUS = 40, 35, 36, 74, 80, 92
F_AURA_PERIOD, F_CHAIN, F_MISC, F_NAME, F_DESC = 98, 104, 110, 136, 170


class SpellDb:
    """Lazy, memory-mapped reader for Spell.dbc (200+ MB) -- only the requested records are decoded."""

    def __init__(self, dbc_dir):
        self.dir = dbc_dir
        self._lock = threading.Lock()
        self._ready = False
        self._index = {}
        self._mm = None
        self._durations = {}
        self._radii = {}

    def _small_dbc(self, name, fmt):
        out = {}
        try:
            raw = open(os.path.join(self.dir, name), "rb").read()
            magic, records, fields, size, _ = struct.unpack("<4siiii", raw[:20])
            for i in range(records):
                row = struct.unpack_from(fmt, raw, 20 + i * size)
                out[row[0]] = row[1]
        except (OSError, struct.error):
            pass
        return out

    def _load(self):
        with self._lock:
            if self._ready:
                return
            try:
                f = open(os.path.join(self.dir, "Spell.dbc"), "rb")
                self._mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
                magic, records, fields, size, _ = struct.unpack("<4siiii", self._mm[:20])
                if magic == b"WDBC" and fields == SPELL_FIELDS:
                    self._size, self._block = size, 20 + records * size
                    self._index = {struct.unpack_from("<I", self._mm, 20 + i * size)[0]: 20 + i * size for i in range(records)}
            except (OSError, ValueError, struct.error):
                self._index = {}
            self._durations = self._small_dbc("SpellDuration.dbc", "<Ii")
            self._radii = self._small_dbc("SpellRadius.dbc", "<If")
            self._ready = True

    def get(self, spell_id):
        self._load()
        off = self._index.get(int(spell_id))
        if off is None:
            return None
        f = struct.unpack_from("<%di" % SPELL_FIELDS, self._mm, off)

        def text(o):
            if o <= 0:
                return ""
            start = self._block + o
            return self._mm[start:self._mm.find(b"\0", start)].decode("utf-8", "replace")

        return {"id": int(spell_id), "f": f, "name": text(f[F_NAME]), "desc": text(f[F_DESC]),
                "duration": self._durations.get(f[F_DURATION], 0)}

    # -- description formatting -------------------------------------------------------------------------------
    def _num(self, sp, kind, n):
        i = n - 1
        f = sp["f"]
        if not 0 <= i <= 2:
            return None
        base, die = f[F_BASEPOINTS + i], f[F_DIESIDES + i]
        lo, hi = base + (1 if die >= 1 else 0), base + die
        if kind in "sS":
            lo_a, hi_a = abs(lo), abs(hi)
            return lo_a if lo_a == hi_a or die <= 1 else (lo_a, hi_a)
        if kind == "m":
            return abs(lo)
        if kind == "M":
            return abs(hi)
        if kind == "t":
            return f[F_AURA_PERIOD + i] / 1000.0
        if kind == "x":
            return f[F_CHAIN + i]
        if kind == "q":
            return f[F_MISC + i]
        if kind == "a":
            r = self._radii.get(f[F_RADIUS + i])
            return r
        if kind == "o":
            period = f[F_AURA_PERIOD + i]
            if period and sp["duration"] > 0:
                return abs(lo) * (sp["duration"] // period)
            return None
        return None

    def _fmt(self, v):
        if v is None:
            return "?"
        if isinstance(v, tuple):
            return "%s to %s" % (self._fmt(v[0]), self._fmt(v[1]))
        if isinstance(v, float) and v == int(v):
            v = int(v)
        return ("%g" % v) if isinstance(v, float) else str(v)

    def _duration_text(self, ms):
        if ms <= 0:
            return "until cancelled"
        s = ms / 1000
        if s % 3600 == 0:
            return "%d hour%s" % (s // 3600, "" if s == 3600 else "s")
        if s % 60 == 0:
            return "%d min" % (s // 60)
        return "%g sec" % s

    def describe(self, spell_id, depth=0):
        sp = self.get(spell_id)
        if not sp:
            return None
        text = sp["desc"].replace("\r\n", "\n").replace("\r", "\n")

        def resolve(m):
            ref, kind, idx = m.group(1), m.group(2), m.group(3)
            target = sp
            if ref:
                target = self.get(int(ref)) if depth < 2 else None
                if not target:
                    return "?"
            if kind == "d":
                return self._duration_text(target["duration"])
            if kind == "h":
                return str(target["f"][F_PROCCHANCE])
            if kind == "n":
                return str(target["f"][F_PROCCHARGES])
            if kind in "sSmMtxqao":
                return self._fmt(self._num(target, kind, int(idx or 1)))
            return "?"

        tok = re.compile(r"\$(\d+)?([a-zA-Z])(\d)?")

        def expr(m):
            body = m.group(1)
            body = tok.sub(lambda t: (lambda v: str(v) if isinstance(v, (int, float)) else "x")(
                self._num(self.get(int(t.group(1))) if t.group(1) and self.get(int(t.group(1))) else sp,
                          t.group(2), int(t.group(3) or 1))) if t.group(2) in "sSmMtxqao" else "x", body)
            if re.fullmatch(r"[0-9.+\-*/() ]+", body or ""):
                try:
                    v = eval(body, {"__builtins__": {}}, {})
                    return str(int(round(v))) if abs(v) >= 10 else ("%g" % round(v, 2))
                except Exception:
                    pass
            return "(scales with power)"

        text = re.sub(r"\$\{([^}]*)\}(?:\.\d+)?", expr, text)
        text = re.sub(r"\$l([^:;]*):([^;]*);", lambda m: m.group(2), text)  # plural form
        text = re.sub(r"\$g([^:;]*):([^;]*);", lambda m: m.group(1), text)
        text = tok.sub(resolve, text)
        return {"name": sp["name"], "text": re.sub(r"[ \t]+\n", "\n", text).strip()}


_SPELLS = None


def spells(install_dir):
    global _SPELLS
    if _SPELLS is None:
        _SPELLS = SpellDb(os.path.join(install_dir, "dbc"))
    return _SPELLS


def _money(copper):
    g, rest = divmod(int(copper), 10000)
    s, c = divmod(rest, 100)
    return " ".join(p for p in ((f"{g}g" if g else ""), (f"{s}s" if s else ""), (f"{c}c" if c else "")) if p)


def _n(v):
    v = float(v)
    return str(int(v)) if v == int(v) else ("%.1f" % v)


def item_tip(query_rows, install_dir, item_id):
    rows = query_rows("acore_world", f"SELECT * FROM item_template WHERE entry = {int(item_id)}")
    if not rows:
        raise ValueError(f"item {item_id} not found")
    r = {k: (v if v is not None else "0") for k, v in rows[0].items()}
    iv = lambda k: int(float(r.get(k) or 0))
    lines = []

    def add(left, cls="", right=""):
        lines.append({"l": left, "r": right, "c": cls})

    cls_id, sub, inv = iv("class"), iv("subclass"), iv("InventoryType")
    if iv("bonding") in BONDING:
        add(BONDING[iv("bonding")])
    if iv("maxcount") == 1:
        add("Unique")
    slot = SLOTS.get(inv, "") if cls_id in (2, 4) or inv else ""
    subname = WEAPON_SUB.get(sub, "") if cls_id == 2 else (ARMOR_SUB.get(sub, "") if cls_id == 4 else "")
    if slot or subname:
        add(slot, "", subname if subname != slot else "")
    # weapon damage
    if cls_id == 2 and iv("delay"):
        speed = iv("delay") / 1000.0
        lo1, hi1 = float(r["dmg_min1"]), float(r["dmg_max1"])
        add(f"{_n(lo1)} - {_n(hi1)} {DMG_TYPES.get(iv('dmg_type1'), '')}Damage", "", f"Speed {speed:.2f}")
        if float(r["dmg_max2"]) > 0:
            add(f"+ {_n(float(r['dmg_min2']))} - {_n(float(r['dmg_max2']))} {DMG_TYPES.get(iv('dmg_type2'), '')}Damage")
        total = (lo1 + hi1 + (float(r["dmg_min2"]) + float(r["dmg_max2"]))) / 2
        add(f"({total / speed:.1f} damage per second)")
    if iv("armor"):
        add(f"{iv('armor')} Armor")
    if iv("block"):
        add(f"{iv('block')} Block")
    ratings = []
    for i in range(1, 11):
        t, v = iv(f"stat_type{i}"), iv(f"stat_value{i}")
        if not v:
            continue
        if t in STAT_NAMES:
            add(f"{v:+d} {STAT_NAMES[t]}")
        elif t in STAT_RATINGS:
            ratings.append(f"Increases your {STAT_RATINGS[t]} by {v}.")
        elif t in STAT_SPECIAL:
            ratings.append(STAT_SPECIAL[t].format(v))
    for key, name in RESISTS:
        if iv(key):
            add(f"{iv(key):+d} {name} Resistance")
    for i in (1, 2, 3):
        color = iv(f"socketColor_{i}")
        if color:
            add(SOCKETS.get(color, "Socket"), "dim")
    if iv("MaxDurability"):
        add(f"Durability {iv('MaxDurability')} / {iv('MaxDurability')}")
    if iv("RequiredLevel"):
        add(f"Requires Level {iv('RequiredLevel')}")
    if iv("ItemLevel"):
        add(f"Item Level {iv('ItemLevel')}")
    for text in ratings:
        add("Equip: " + text, "good")
    spelldb = spells(install_dir)
    for i in range(1, 6):
        sid = iv(f"spellid_{i}")
        if not sid:
            continue
        desc = spelldb.describe(sid)
        trig = TRIGGERS.get(iv(f"spelltrigger_{i}"), "Use")
        if desc and desc["text"]:
            add(f"{trig}: {desc['text']}", "good")
        elif desc:
            add(f"{trig}: {desc['name']}", "good")
        else:
            add(f"{trig}: spell {sid}", "good")
    if r.get("description"):
        add('"' + r["description"] + '"', "flavor")
    if iv("stackable") > 1:
        add(f"Stacks to {iv('stackable')}", "dim")
    if iv("SellPrice"):
        add("Sell Price: " + _money(iv("SellPrice")), "dim")
    q = iv("Quality")
    return {"id": iv("entry"), "name": r["name"], "quality": q, "qualityName": QUALITY_NAMES[q] if q < len(QUALITY_NAMES) else "",
            "lines": lines}
