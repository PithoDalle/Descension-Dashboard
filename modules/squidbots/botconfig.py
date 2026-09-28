"""Read and write the curated bot settings in the server's .conf files.

The dashboard was read-only until now. This module is the only thing here that
writes, and it is deliberately narrow: it edits the value of settings it already
knows about, in place, and never adds, removes or reorders a line.

Every write takes a timestamped backup of the whole file first.

Editing a .conf while the server is stopped needs no reload at all, because the
files are read at startup. That is the intended way to use this.
"""
import collections
import datetime
import os
import re
import shutil

PLAYERBOTS = "playerbots.conf"
DYNAMICXP = "dynamicxp.conf"
BOTMINDS = "mod_bot_minds.conf"

# The curated set. `when` says when a change is actually seen, in the page's terms:
#
#   "restart"   read when the server starts; a running server keeps the old value
#   "new bots"  read when a bot is first created, so existing bots keep their state
#   "reload"    read at startup and again on ".reload config"
#   "live"      used as soon as the file changes
#
# Where upstream does not document a reload path, "restart" is the promise made,
# because it is the one this panel can keep without a console.
Setting = collections.namedtuple(
    "Setting", "key file group label kind choices when help")

SETTINGS = [Setting(*row) for row in (
    ("AiPlayerbot.Enabled", PLAYERBOTS, "Population", "Bots enabled", "bool", None, "restart",
     "Master switch for the bot system. Off means no bots at all, random or otherwise."),
    ("AiPlayerbot.RandomBotAutologin", PLAYERBOTS, "Population", "Random bots log in by themselves", "bool", None, "restart",
     "Random bots log in on their own and live in the world. Off leaves only bots a player adds by hand."),
    ("AiPlayerbot.MinRandomBots", PLAYERBOTS, "Population", "Fewest random bots online", "int", None, "restart",
     "The server keeps at least this many random bots in the world."),
    ("AiPlayerbot.MaxRandomBots", PLAYERBOTS, "Population", "Most random bots online", "int", None, "restart",
     "The server never runs more random bots than this. More bots means more server load."),
    ("AiPlayerbot.BotActiveAlone", PLAYERBOTS, "Population", "Bots awake with no player near (%)", "int", None, "restart",
     "Share of bots that keep playing when no real player is around. 100 keeps them all active, at the cost of server load. 60 is what a 1000-bot realm was measured to need."),

    ("AiPlayerbot.RandomBotMinLevel", PLAYERBOTS, "Levels", "Lowest level a bot is given", "int", None, "new bots",
     "The bottom of the range new bots are rolled into."),
    ("AiPlayerbot.RandomBotMaxLevel", PLAYERBOTS, "Levels", "Highest level a bot is given", "int", None, "new bots",
     "The top of the range new bots are rolled into."),
    ("AiPlayerbot.DisableRandomLevels", PLAYERBOTS, "Levels", "Same starting level for every bot", "bool", None, "new bots",
     "On: every new bot starts at the starting level below instead of a random one. Bots still level up by playing."),
    ("AiPlayerbot.RandombotStartingLevel", PLAYERBOTS, "Levels", "Starting level", "int", None, "new bots",
     "The level every new bot starts at, when the same starting level is on."),
    ("AiPlayerbot.RandomBotMinLevelChance", PLAYERBOTS, "Levels", "Odds a new bot starts at the lowest level", "float", None, "new bots",
     "0 to 1. With random levels, this share of new bots start at the lowest level (1 means all of them). Bots that already exist are not touched."),
    ("AiPlayerbot.RandomBotMaxLevelChance", PLAYERBOTS, "Levels", "Odds a new bot starts at the highest level", "float", None, "new bots",
     "0 to 1. With random levels, this share of new bots start at the highest level. Checked before the lowest-level odds."),
    ("AiPlayerbot.RandomBotFixedLevel", PLAYERBOTS, "Levels", "Bots never level up", "bool", None, "restart",
     "On: bots stay at the level they have. Off: they gain levels by questing and killing like players."),
    ("AiPlayerbot.LevelBrackets.Enabled", PLAYERBOTS, "Levels", "Level Brackets (keep bots spread across levels)", "bool", None, "reload",
     "Every 5 minutes, moves bots between nine level ranges to keep every range populated, re-rolling a moved bot at its new level. While on, it overrides any starting level you set here."),
    ("AiPlayerbot.LevelBrackets.Dynamic.UseDynamicDistribution", PLAYERBOTS, "Levels", "Brackets follow real players", "bool", None, "reload",
     "With Level Brackets on, put more bots in the level ranges where real players are, instead of an even spread."),

    ("AiPlayerbot.RandomBotTalk", PLAYERBOTS, "Behaviour", "Canned bot chatter", "bool", None, "restart",
     "Playerbots' own built-in lines in say, yell, General and LFG. Kept off so the LLM chat below is not talked over."),
    ("AiPlayerbot.InviteChat", PLAYERBOTS, "Behaviour", "Bots announce group invites", "bool", None, "restart",
     "Bots say something in say or guild chat when they invite another bot to a group, raid or guild."),
    ("AiPlayerbot.AutoPickTalents", PLAYERBOTS, "Behaviour", "Bots spend talent points", "bool", None, "restart",
     "Bots spend their talent points themselves when they level up."),
    ("AiPlayerbot.LimitTalentsExpansion", PLAYERBOTS, "Behaviour", "Hold talents to their expansion", "bool", None, "restart",
     "Bots below 61 only use the talent rows Classic had, and below 71 the rows The Burning Crusade had."),

    # CoA Bots (mod-playerbots, branch coa). Harmless on another realm: absent keys are not shown.
    ("AiPlayerbot.CoaSpecRotations", PLAYERBOTS, "CoA Bots", "Written rotations for CoA specializations", "bool", None, "restart",
     "Bots play each Conquest of Azeroth specialization with its own written rotation. Off: they fall back to generic behaviour and none of the CoA rotation work reaches them."),
    ("AiPlayerbot.CoaClassesOnly", PLAYERBOTS, "CoA Bots", "Random bots use CoA classes only", "bool", None, "new bots",
     "New random bots are created in the Conquest of Azeroth classes only."),
    ("AiPlayerbot.CoaSmartHeal", PLAYERBOTS, "CoA Bots", "Smarter healers", "bool", None, "restart",
     "CoA healers keep their mana for healing and pick who to heal by need."),
    ("AiPlayerbot.CoaSmartTank", PLAYERBOTS, "CoA Bots", "Damage dealers let the tank open", "bool", None, "restart",
     "In a group with a tank, CoA damage dealers wait for the tank to take the target first."),
    ("AiPlayerbot.CoaTankOpenerSeconds", PLAYERBOTS, "CoA Bots", "Longest wait for the tank (seconds)", "int", None, "reload",
     "With the setting above: how long a damage dealer waits on a target no tank has touched, then goes all out. 0: no wait."),
    ("AiPlayerbot.CoaExcludedSpecializations", PLAYERBOTS, "CoA Bots", "Specializations bots never use", "ids", None, "restart",
     "Specialization numbers separated by commas. 99 (Bloodmage Eternal) is left out by default: it cannot taunt until the core grants its form."),
    ("AiPlayerbot.CoaGroupTelemetry", PLAYERBOTS, "CoA Bots", "Group fight report in CoaBots.log", "bool", None, "restart",
     "Writes a report at the end of every fight of a group with a real player in it (health, deaths, healing, mana). For measuring; off on a normal realm."),
    ("AiPlayerbot.CoaLfgBots", PLAYERBOTS, "CoA Bots", "Bots answer \"lfg bot\" in chat", "bool", None, "reload",
     "A player who says \"lfg bot heal\", \"lfg bot tank\" or \"lfg bot\" in a listened channel is whispered by free bots able to play those roles."),

    # The live view of this dashboard: mod-playerbots (branch coa) writes a snapshot of every bot.
    ("AiPlayerbot.CoaStatusFile", PLAYERBOTS, "Dashboard live view", "Live status file", "quoted", None, "reload",
     "Where the server writes each bot's health, power and current action for this dashboard's map and cards. "
     "Put it next to CoaBots.log (logs\\bot-status.json) and the dashboard finds it by itself. Empty: not written."),
    ("AiPlayerbot.CoaStatusIntervalSeconds", PLAYERBOTS, "Dashboard live view", "Refresh every (seconds)", "int", None, "reload",
     "How often the live status file is rewritten. Under a millisecond of server time per snapshot with 1000 bots."),

    # Channels and bot chat. Conquest of Azeroth numbers and names its channels differently from a
    # stock client: with the stock values bot broadcasts are dropped or land in the wrong channel.
    ("AiPlayerbot.ZoneChannelId", PLAYERBOTS, "Channels and chat", "Zone channel number", "int", None, "restart",
     "The number of the Zone channel. Conquest of Azeroth uses 3, not the stock 1."),
    ("AiPlayerbot.BroadcastWorldChannelName", PLAYERBOTS, "Channels and chat", "Realm-wide channel name", "quoted", None, "restart",
     "Conquest of Azeroth calls it Ascension. Until this matches, every broadcast meant for it is dropped."),
    ("AiPlayerbot.BroadcastToWorldGlobalChance", PLAYERBOTS, "Channels and chat", "Bot chatter in the realm-wide channel", "int", None, "restart",
     "0 to 30000; 0 keeps bots out of the realm-wide channel, which everybody reads. Their chatter belongs in Zone."),
    ("AiPlayerbot.BotsWhisperPublic", PLAYERBOTS, "Channels and chat", "Bots whisper unasked", "bool", None, "restart",
     "On: bots whisper a player who writes in a channel, and tell their master every potion and buff. Off: a word in a channel no longer brings a wall of whispers."),
    ("AiPlayerbot.PublicReplyChance", PLAYERBOTS, "Channels and chat", "Bots answering a channel message (%)", "int", None, "restart",
     "How many of the bots that read a player's channel message may answer. High values bury the player; a bot called by name always answers."),

    ("Dynamic.XP.Preset", DYNAMICXP, "Experience", "Realm XP rate", "choice", ["0", "1", "3", "5", "7"], "reload",
     "XP multiplier for every character that has not picked its own: 1 is normal, 3, 5 or 7 times as fast, or 0 for the per-level curve."),
    ("Dynamic.XP.Preset.PlayerChoice", DYNAMICXP, "Experience", "Players may pick their own rate", "bool", None, "reload",
     "Lets any player change their own rate with .xp 1, 3, 5, 7 or dynamic. Off: game masters only."),
    ("Dynamic.XP.Rate", DYNAMICXP, "Experience", "Per-level XP curve available", "bool", None, "reload",
     "Turns on the per-level XP curve (faster at higher levels) that rate 0 and .xp dynamic use."),

    # Bot LLM chat, from mod-bot-minds. `.botminds reload` re-reads the file, but
    # "restart" is the promise this panel can keep without a console.
    ("BotMinds.Enable", BOTMINDS, "Bot chat (LLM)", "LLM chat on", "bool", None, "restart",
     "Bots write their own lines with the local language model. Off: they stay quiet (canned chatter is also off)."),
    ("BotMinds.Model", BOTMINDS, "Bot chat (LLM)", "Language model", "text", None, "restart",
     "The Ollama model that writes bot lines. It must support tool calls."),
    ("BotMinds.Url", BOTMINDS, "Bot chat (LLM)", "Ollama address", "text", None, "restart",
     "Where Ollama is listening. The default is this machine."),
    ("BotMinds.SayDistance", BOTMINDS, "Bot chat (LLM)", "Earshot in yards", "float", None, "restart",
     "How far away a bot hears say and yell, and how far it looks for something to remark on."),
    ("BotMinds.Route.HandleChannel", BOTMINDS, "Bot chat (LLM)", "Answer in General, Trade and LFG", "bool", None, "restart",
     "Bots answer in the numbered channels as well as in say and party."),
    ("BotMinds.ReplyChance.Say", BOTMINDS, "Bot chat (LLM)", "Chance to answer you nearby (%)", "int", None, "restart",
     "Out of 100: how often a bot answers something said near it."),
    ("BotMinds.ReplyChance.Channel", BOTMINDS, "Bot chat (LLM)", "Chance to answer in channels (%)", "int", None, "restart",
     "Out of 100: how often a channel message gets an answer from a bot."),
    ("BotMinds.ReplyChance.BotToBot", BOTMINDS, "Bot chat (LLM)", "Chance bots answer each other (%)", "int", None, "restart",
     "Out of 100: how often a bot picks up another bot's line. Only happens where a real player can see it."),
    ("BotMinds.Ambient.Chance", BOTMINDS, "Bot chat (LLM)", "Idle chatter (%)", "int", None, "restart",
     "Out of 100: how often a bot near a real player says something unprompted."),
    ("BotMinds.Ambient.Channel.General", BOTMINDS, "Bot chat (LLM)", "Idle chatter in General", "bool", None, "restart",
     "Unprompted bot lines may go to General."),
    ("BotMinds.Ambient.Channel.Trade", BOTMINDS, "Bot chat (LLM)", "Idle chatter in Trade", "bool", None, "restart",
     "Unprompted bot lines may go to Trade, in cities."),
    ("BotMinds.WorkerThreads", BOTMINDS, "Bot chat (LLM)", "Lines written at once", "int", None, "restart",
     "How many bot lines the model writes at the same time. Higher answers faster but loads the machine."),
    ("BotMinds.Limits.MaxCallsPerMinute", BOTMINDS, "Bot chat (LLM)", "Lines per minute, whole realm", "int", None, "restart",
     "A ceiling on model calls per minute across every bot. 0 removes the ceiling."),
)]

BY_KEY = {entry.key: entry for entry in SETTINGS}

_CHANCES = ["AiPlayerbot.RandomBotMinLevelChance", "AiPlayerbot.RandomBotMaxLevelChance"]
_LLM = [s.key for s in SETTINGS if s.file == BOTMINDS and s.key != "BotMinds.Enable"]

# When every "if" setting has the given value, each "warn" setting shows the text.
# The page evaluates this same table as values are edited, so the rules live once.
OVERRIDES = [
    {"if": {"AiPlayerbot.LevelBrackets.Enabled": "1"},
     "warn": _CHANCES + ["AiPlayerbot.DisableRandomLevels", "AiPlayerbot.RandombotStartingLevel"],
     "text": "Level Brackets is on: every 5 minutes it moves bots between level ranges, so "
             "starting levels do not last. Turn Level Brackets off for this to stick."},
    {"if": {"AiPlayerbot.DisableRandomLevels": "0"},
     "warn": ["AiPlayerbot.RandombotStartingLevel"],
     "text": "Only used while \"Same starting level for every bot\" is on."},
    {"if": {"AiPlayerbot.DisableRandomLevels": "1"},
     "warn": _CHANCES,
     "text": "Ignored while \"Same starting level for every bot\" is on."},
    {"if": {"AiPlayerbot.LevelBrackets.Enabled": "0"},
     "warn": ["AiPlayerbot.LevelBrackets.Dynamic.UseDynamicDistribution"],
     "text": "Only used while Level Brackets is on."},
    {"if": {"Dynamic.XP.Preset": "0", "Dynamic.XP.Rate": "0"},
     "warn": ["Dynamic.XP.Preset"],
     "text": "Rate 0 means the per-level curve, which is switched off below, so this gives normal XP."},
    {"if": {"BotMinds.Route.HandleChannel": "0"},
     "warn": ["BotMinds.ReplyChance.Channel"],
     "text": "Bots do not answer in channels at all while \"Answer in General, Trade and LFG\" is off."},
    {"if": {"BotMinds.Enable": "0"},
     "warn": _LLM,
     "text": "LLM chat is off, so this has no effect."},
]

# A recipe is a named set of changes, shown as a before and after list first.
RECIPES = [
    {"id": "fresh-level-1",
     "title": "Fresh world: every bot starts at level 1",
     "summary": "New bots start at level 1 in their starting zones and level up by playing. "
                "Level Brackets is turned off so nothing moves them afterwards.",
     "changes": {"AiPlayerbot.DisableRandomLevels": "1",
                 "AiPlayerbot.RandombotStartingLevel": "1",
                 "AiPlayerbot.LevelBrackets.Enabled": "0"},
     "after": "Takes effect for new bots after a restart. Bots that already exist keep their "
              "level until they are re-created."},
    {"id": "spread-levels",
     "title": "Mixed levels: bots spread from 1 to max",
     "summary": "The repack's own setup: random starting levels, and Level Brackets keeping "
                "every level range populated, weighted towards where real players are.",
     "changes": {"AiPlayerbot.DisableRandomLevels": "0",
                 "AiPlayerbot.LevelBrackets.Enabled": "1",
                 "AiPlayerbot.LevelBrackets.Dynamic.UseDynamicDistribution": "1"},
     "after": "Level Brackets starts moving bots within 5 minutes of a restart."},
]
RECIPES.insert(0, {
    "id": "coa-v14",
    "title": "CoA Bots v1.4: the recommended settings",
    "summary": "What the v1.4 release ships: 200 bots, 60% awake, Conquest of Azeroth's channel number "
               "and name, no whisper flood, the written rotations on and Bloodmage Eternal left out.",
    "changes": {"AiPlayerbot.MinRandomBots": "200", "AiPlayerbot.MaxRandomBots": "200",
                "AiPlayerbot.BotActiveAlone": "60",
                "AiPlayerbot.ZoneChannelId": "3", "AiPlayerbot.BroadcastWorldChannelName": "Ascension",
                "AiPlayerbot.BroadcastToWorldGlobalChance": "0",
                "AiPlayerbot.BotsWhisperPublic": "0", "AiPlayerbot.PublicReplyChance": "5",
                "AiPlayerbot.CoaSpecRotations": "1", "AiPlayerbot.CoaExcludedSpecializations": "99",
                "AiPlayerbot.CoaGroupTelemetry": "0", "AiPlayerbot.CoaLfgBots": "1"},
    "after": "Takes effect at the next server start."})
_RECIPES = {recipe["id"]: recipe for recipe in RECIPES}


def override_warnings(settings):
    """{key: [warning, ...]} for the given settings (read_settings rows)."""
    current = {row["key"]: row["value"] for row in settings}
    out = {}
    for rule in OVERRIDES:
        if all(current.get(key) == value for key, value in rule["if"].items()):
            for key in rule["warn"]:
                out.setdefault(key, []).append(rule["text"])
    return out


def recipe_diff(settings, recipe_id):
    """The rows a recipe would change: [{key, label, from, to}]. KeyError if unknown."""
    recipe = _RECIPES[recipe_id]
    current = {row["key"]: row["value"] for row in settings}
    return [{"key": key, "label": BY_KEY[key].label, "from": current.get(key), "to": value}
            for key, value in recipe["changes"].items() if current.get(key) != value]

# A setting line looks like "Key.Name = value", optionally indented.
def _line_re(key):
    # Spaces and tabs only: \s would reach across the line end and eat the blank line after it.
    return re.compile(r"^([ \t]*%s[ \t]*=[ \t]*)([^\r\n]*?)([ \t]*)(?=\r?$)" % re.escape(key), re.M)


def config_dir(repack_root, bots=True):
    """Where the module .conf files live. The bots server has its own set."""
    if bots:
        return os.path.join(repack_root, "CoA-Bots", "Core", "configs", "modules")
    return os.path.join(repack_root, "Core", "configs", "modules")


def read_settings(conf_dir):
    """Current value of every curated setting. Missing files and keys are reported,
    not raised: the dashboard has to work on a half-configured install too."""
    cache = {}
    out = []
    for key, filename, group, label, kind, choices, when, help_text in SETTINGS:
        if filename not in cache:
            path = os.path.join(conf_dir, filename)
            try:
                cache[filename] = open(path, encoding="utf-8-sig", errors="replace").read()
            except OSError:
                cache[filename] = None
        text = cache[filename]
        value, present = None, False
        if text is not None:
            match = _line_re(key).search(text)
            if match:
                value, present = match.group(2).strip(), True
                if kind == "quoted" and len(value) >= 2 and value[0] == value[-1] == '"':
                    value = value[1:-1]
        out.append({"key": key, "file": filename, "group": group, "label": label,
                    "kind": kind, "choices": choices, "when": when, "help": help_text,
                    "value": value, "present": present})
    return out


def validate(key, value):
    """Return an error string, or None when the value is acceptable."""
    entry = BY_KEY.get(key)
    if not entry:
        return "unknown setting"
    kind, choices = entry[4], entry[5]
    text = str(value).strip()
    if text == "" and kind != "quoted":
        return "value is empty"
    if kind == "bool":
        if text not in ("0", "1"):
            return "expected 0 or 1"
    elif kind == "int":
        if not re.match(r"^-?\d+$", text):
            return "expected a whole number"
    elif kind == "float":
        if not re.match(r"^-?\d+(\.\d+)?$", text):
            return "expected a number"
    elif kind == "ids":
        if not re.match(r"^\d+(\s*,\s*\d+)*$", text):
            return "expected numbers separated by commas"
    elif kind == "quoted":
        if '"' in text or len(text) > 100:
            return "a name without quotes, at most 100 characters"
    elif kind == "text":
        if len(text) > 200:
            return "value is too long"
    elif kind == "choice":
        if text not in (choices or []):
            return "expected one of %s" % ", ".join(choices or [])
    if "\n" in text or "\r" in text:
        return "value may not span lines"
    return None


def apply_settings(conf_dir, changes, backup_dir):
    """Write `changes` ({key: value}) into the .conf files.

    Backs up each file it touches first. Returns (written, backups, errors).
    Nothing is written if any value fails validation, so a bad field cannot leave
    the configuration half applied.
    """
    errors = {}
    for key, value in changes.items():
        problem = validate(key, value)
        if problem:
            errors[key] = problem
    if errors:
        return {}, [], errors

    by_file = {}
    for key, value in changes.items():
        text = str(value).strip()
        if BY_KEY[key].kind == "quoted":
            text = '"%s"' % text
        by_file.setdefault(BY_KEY[key].file, {})[key] = text

    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    written, backups = {}, []

    for filename, pairs in by_file.items():
        path = os.path.join(conf_dir, filename)
        if not os.path.exists(path):
            errors[filename] = "file not found: %s" % path
            continue
        # newline="" keeps CRLF as it is, and plain utf-8 keeps a BOM as a character: the file
        # comes back byte for byte apart from the values changed.
        with open(path, encoding="utf-8", errors="replace", newline="") as handle:
            text = handle.read()

        updated = text
        missing = []
        for key, value in pairs.items():
            pattern = _line_re(key)
            if not pattern.search(updated):
                missing.append(key)
                continue
            updated = pattern.sub(lambda m: m.group(1) + value + m.group(3), updated, count=1)
        for key in missing:
            errors[key] = "setting not found in %s" % filename
        if missing or updated == text:
            if not missing:
                written[filename] = 0
            continue

        os.makedirs(backup_dir, exist_ok=True)
        backup = os.path.join(backup_dir, "%s.%s.bak" % (filename, stamp))
        shutil.copy2(path, backup)
        backups.append(backup)

        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(updated)
        written[filename] = len(pairs)

    return written, backups, errors
