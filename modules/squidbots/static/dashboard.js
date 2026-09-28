const API = "/api/stats";
const PUBLIC = false;

/* ---------------- words ---------------- */
const WORDS = {
  en: {
    locale: "en-GB",
    tagline: "Conquest of Azeroth · bots, live",
    searchBot: "Search a bot", otherLang: "FR",
    navWorld: "World", navBots: "Bots", navGear: "Armory", navStats: "Stats",
    navChat: "Chat & Loot", navSettings: "Settings",
    pageTitles: { world: "World", bots: "Bots", gear: "Armory", stats: "Stats",
      chat: "Chat & Loot", settings: "Settings" },
    gearSearch: "Bot name...", gearOffline: "This bot is offline: a mailed item won't be equipped until it's online and finds a mailbox.",
    gearEmpty: "Empty", gearChoose: item => "Choose an item for: " + item, gearMailed: (item, bot) => "Mailed " + item + " to " + bot,
    mapTitle: "Map", focusTitle: "Watching", focusNone: "Pick a bot on the map or in the Bots list to follow it here.",
    rosterTitle: "Bot roster", rosterFilter: "Filter by name, zone or class",
    showOffline: "Show offline",
    sortLevel: "Level", sortName: "Name", sortZone: "Zone",
    settingsTitle: "Bot settings", reload: "Reload", applyChanges: "Apply changes",
    online: n => n + " bots online", stopped: "server stopped", unreachable: "page unreachable",
    updated: at => "updated at " + at,
    figBots: "Bots online", figBotsFoot: n => "of " + n + " characters",
    figLevel: "Average level", figLevelFoot: n => "best: " + n,
    figKills: "Mobs killed", figKillsFoot: n => n + " per hour",
    figQuests: "Quests handed in", figQuestsFoot: since => "since " + since,
    figLevels: "Levels gained", figLevelsFoot: h => "since the server started, " + h + " h ago",
    figServer: "Server", figServerRunning: "running", figServerMemory: n => n + " MB of memory",
    paceTitle: "Hunting pace", paceSub: "mobs killed per hour",
    factionsTitle: "Factions online", factionsSub: "right now", levelWord: n => "level " + n,
    rolesTitle: "Roles", rolesSub: "bots online now",
    tanks: "Tanks", healers: "Healers", damage: "Damage",
    zonesTitle: "Where the bots are", zonesSub: "busiest zones, online",
    compareTitle: "Today and yesterday", compareSub: "24 hours against the 24 before",
    compareDay: "24 h", compareBefore: "Before", compareChange: "Change",
    compareWait: "One full day of readings is needed.",
    deadTitle: "Bots on the floor", deadSub: "read every ten minutes",
    watchTitle: "Watch post", watchSub: "what deserves a look",
    watchDead: "Dead right now", watchStuck: "Stuck bots", watchCrashes: "Crashes 24 h",
    watchNoJournal: "Watch journal not configured.", watchQuiet: "No incident: no crash, no freeze.",
    stuckLine: (h, names) => "Not a single point of experience in " + h + " h: " + names,
    levelsTitle: "Level spread", levelsSub: "bots online now",
    xpTitle: "Best experience gains", xpSpan: h => "over the last " + h + " hours", xpMeasuring: "measuring",
    xpWait: "First reading under way: the ranking starts after an hour of play.",
    xpUnit: "xp/h", levelShort: n => "level " + n,
    chatTitle: "Most talkative", chatNone: "The chat journal starts at the next server restart.",
    chatSub: (m, t) => m + " messages · " + t + " talkers",
    chatChannel: n => n + " in a channel", chatOther: "conversations and emotes", chatUnit: "msg",
    feedTitle: "Live chat", feedSub: n => n + " lines, newest first, refreshed every 5 s",
    feedAll: "All", feedSay: "Say", feedWhisper: "Whisper", feedChannels: "Channels",
    feedSearch: "Search a speaker or words", feedNone: "No chat in the journal yet.",
    feedQuiet: "Nothing matches these filters.", feedTo: name => "to " + name,
    chatKinds: { say: "say", yell: "yell", whisper: "whisper", party: "party", guild: "guild",
      channel: "channel", offscreen: "off-screen", other: "other" },
    botChat: "Recent chat", botChatNone: "Nothing said lately.", botChatLoading: "Reading the chat…",
    classesTitle: "Class ranking", classesSub: "average level, and each class's podium",
    colClass: "Class", colAvgLevel: "Average level", colBots: "Bots", colKills: "Mobs", colPodium: "Podium",
    showAll: n => "Show all " + n + " classes", showFew: "Show only the first eight",
    progressTitle: "Progress", progressSub: "levels gained per hour",
    topTitle: "Leaderboard", topSub: "the first ten bots",
    tabXp: "Experience", tabKills: "Mobs", tabQuests: "Quests",
    unitLevel: "lvl", unitKills: "killed", unitQuests: "quests", offline: "offline",
    spellsTitle: "Spells cast", spellsSub: h => "over " + h + " h · cast / tried",
    spellsNone: "No spell journal.",
    colAction: "Action", colSuccess: "Success", colCast: "Cast", colTried: "Tried",
    lootTitle: "Notable finds", lootSub: n => n + " in the last two days",
    lootNone: "No loot journal yet: it starts at the next server restart.",
    lootQuiet: "Nothing notable in the last two days.",
    sheetLevel: "Level", sheetKills: "Mobs killed", sheetQuests: "Quests", sheetPlayed: "Time played",
    sheetXp: "Experience", sheetZone: "Zone", close: "Close",
    tank: "tank", heal: "healer", dps: "damage",
    footer: "Private Conquest of Azeroth server · this page refreshes itself · ",
    footerLink: "the bot module",
    chartWait: "The curve starts about 30 minutes after the server: bots are saved every quarter of an hour.",
    noData: "No data.", measuring: "Measuring…",
    spellNames: {
      attack: "Attack", aoe: "Area spells", heal: "Heal", "group heal": "Group heal", hot: "Heal over time",
      taunt: "Taunt", defensive: "Defensive", dispel: "Dispel", interrupt: "Interrupt", buff: "Buff",
    },
  },
  fr: {
    locale: "fr-FR",
    tagline: "Conquest of Azeroth · bots en direct",
    searchBot: "Chercher un bot", otherLang: "EN",
    navWorld: "Monde", navBots: "Bots", navGear: "Arsenal", navStats: "Statistiques",
    navChat: "Chat et butin", navSettings: "Réglages",
    pageTitles: { world: "Monde", bots: "Bots", gear: "Arsenal", stats: "Statistiques",
      chat: "Chat et butin", settings: "Réglages" },
    gearSearch: "Nom du bot...", gearOffline: "Ce bot est hors ligne : un objet envoyé par courrier ne sera équipé qu'une fois le bot en ligne et près d'une boîte aux lettres.",
    gearEmpty: "Vide", gearChoose: item => "Choisir un objet pour : " + item, gearMailed: (item, bot) => item + " envoyé à " + bot,
    mapTitle: "Carte", focusTitle: "Suivi", focusNone: "Choisissez un bot sur la carte ou dans la liste des bots pour le suivre ici.",
    rosterTitle: "Liste des bots", rosterFilter: "Filtrer par nom, zone ou classe",
    showOffline: "Afficher hors ligne",
    sortLevel: "Niveau", sortName: "Nom", sortZone: "Zone",
    settingsTitle: "Réglages des bots", reload: "Recharger", applyChanges: "Appliquer",
    online: n => n + " bots en ligne", stopped: "serveur arrêté", unreachable: "page injoignable",
    updated: at => "mis à jour à " + at,
    figBots: "Bots en ligne", figBotsFoot: n => "sur " + n + " personnages",
    figLevel: "Niveau moyen", figLevelFoot: n => "meilleur : " + n,
    figKills: "Monstres tués", figKillsFoot: n => n + " par heure",
    figQuests: "Quêtes rendues", figQuestsFoot: since => "depuis le " + since,
    figLevels: "Niveaux gagnés", figLevelsFoot: h => "depuis le démarrage, il y a " + h + " h",
    figServer: "Serveur", figServerRunning: "en fonctionnement", figServerMemory: n => n + " Mo de mémoire",
    paceTitle: "Rythme de chasse", paceSub: "monstres tués par heure",
    factionsTitle: "Factions en ligne", factionsSub: "à cet instant", levelWord: n => "niveau " + n,
    rolesTitle: "Rôles", rolesSub: "bots connectés",
    tanks: "Tanks", healers: "Soigneurs", damage: "Dégâts",
    zonesTitle: "Où sont les bots", zonesSub: "zones les plus peuplées, en ligne",
    compareTitle: "Hier et aujourd'hui", compareSub: "24 heures contre les 24 précédentes",
    compareDay: "24 h", compareBefore: "Veille", compareChange: "Écart",
    compareWait: "Il faut une journée de relevés.",
    deadTitle: "Bots au sol", deadSub: "relevé toutes les dix minutes",
    watchTitle: "Poste de garde", watchSub: "ce qui mérite un coup d'œil",
    watchDead: "Morts à cet instant", watchStuck: "Bots bloqués", watchCrashes: "Plantages 24 h",
    watchNoJournal: "Journal de surveillance non configuré.",
    watchQuiet: "Aucun incident : ni plantage, ni blocage.",
    stuckLine: (h, names) => "Pas un point d'expérience depuis " + h + " h : " + names,
    levelsTitle: "Répartition des niveaux", levelsSub: "bots connectés",
    xpTitle: "Meilleurs gains d'expérience", xpSpan: h => "sur les " + h + " dernières heures",
    xpMeasuring: "mesure en cours",
    xpWait: "Première mesure en cours : le classement démarre après une heure de jeu.",
    xpUnit: "xp/h", levelShort: n => "niveau " + n,
    chatTitle: "Les plus bavards", chatNone: "Le journal du chat commence au prochain démarrage du serveur.",
    chatSub: (m, t) => m + " messages · " + t + " bavards",
    chatChannel: n => n + " dans un canal", chatOther: "conversations et émotes", chatUnit: "msg",
    feedTitle: "Chat en direct", feedSub: n => n + " lignes, les plus récentes en haut, mises à jour toutes les 5 s",
    feedAll: "Tout", feedSay: "Dire", feedWhisper: "Chuchoter", feedChannels: "Canaux",
    feedSearch: "Chercher un nom ou des mots", feedNone: "Pas encore de chat dans le journal.",
    feedQuiet: "Rien ne correspond à ces filtres.", feedTo: name => "à " + name,
    chatKinds: { say: "dire", yell: "crier", whisper: "chuchoter", party: "groupe", guild: "guilde",
      channel: "canal", offscreen: "hors écran", other: "autre" },
    botChat: "Chat récent", botChatNone: "Rien dit dernièrement.", botChatLoading: "Lecture du chat…",
    classesTitle: "Classement par classe", classesSub: "niveau moyen, et le podium de chaque classe",
    colClass: "Classe", colAvgLevel: "Niveau moyen", colBots: "Bots", colKills: "Monstres", colPodium: "Podium",
    showAll: n => "Voir les " + n + " classes", showFew: "Ne montrer que les huit premières",
    progressTitle: "Progression", progressSub: "niveaux gagnés par heure",
    topTitle: "Palmarès", topSub: "les dix premiers bots",
    tabXp: "Expérience", tabKills: "Monstres", tabQuests: "Quêtes",
    unitLevel: "niv.", unitKills: "tués", unitQuests: "quêtes", offline: "hors ligne",
    spellsTitle: "Sorts lancés", spellsSub: h => "sur " + h + " h · lancés / tentés",
    spellsNone: "Pas de journal des sorts.",
    colAction: "Action", colSuccess: "Réussite", colCast: "Lancés", colTried: "Tentés",
    lootTitle: "Butin remarquable", lootSub: n => n + " sur les deux derniers jours",
    lootNone: "Pas encore de journal du butin : il commence au prochain démarrage du serveur.",
    lootQuiet: "Rien de remarquable sur les deux derniers jours.",
    sheetLevel: "Niveau", sheetKills: "Monstres tués", sheetQuests: "Quêtes", sheetPlayed: "Temps de jeu",
    sheetXp: "Expérience", sheetZone: "Zone", close: "Fermer",
    tank: "tank", heal: "soigneur", dps: "dégâts",
    footer: "Serveur privé Conquest of Azeroth · page mise à jour toute seule · ",
    footerLink: "module des bots",
    chartWait: "La courbe démarre environ 30 minutes après le serveur : les bots sont sauvegardés tous les quarts d’heure.",
    noData: "Pas de données.", measuring: "En cours de mesure…",
    spellNames: {
      attack: "Attaque", aoe: "Sorts de zone", heal: "Soin", "group heal": "Soin de groupe",
      hot: "Soin sur la durée", taunt: "Provocation", defensive: "Défensif", dispel: "Dissipation",
      interrupt: "Interruption", buff: "Amélioration",
    },
  },
};

let lang = "en";
try {
  const stored = localStorage.getItem("squidbots-lang");
  if (stored === "fr" || stored === "en") lang = stored;
} catch (error) { /* private window: English it is */ }
let W = WORDS[lang];

const NS = "http://www.w3.org/2000/svg";
let nf = new Intl.NumberFormat(W.locale);
const num = n => nf.format(Math.round(n || 0));
const one = n => nf.format(Math.round((n || 0) * 10) / 10);
const esc = s => String(s === null || s === undefined ? "" : s)
  .replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const el = (tag, attrs, html) => {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, v);
  if (html) node.innerHTML = html;
  return node;
};
const factionDot = f => '<span class="faction-dot" style="background:var(--' +
  (f === "alliance" ? "alliance" : "horde") + ')"></span>';
const medals = ["🥇", "🥈", "🥉"];
const clock = ts => new Date(ts * 1000).toLocaleTimeString(W.locale, { hour: "2-digit", minute: "2-digit" });
const when = ts => new Date(ts * 1000).toLocaleString(W.locale, { weekday: "short", hour: "2-digit", minute: "2-digit" });

function applyWords() {
  document.documentElement.lang = lang;
  W = WORDS[lang];
  nf = new Intl.NumberFormat(W.locale);
  for (const node of document.querySelectorAll("[data-i18n]")) node.textContent = W[node.dataset.i18n];
  for (const node of document.querySelectorAll("[data-i18n-placeholder]")) {
    node.placeholder = W[node.dataset.i18nPlaceholder];
  }
  for (const node of document.querySelectorAll("[data-i18n-aria]")) {
    node.setAttribute("aria-label", W[node.dataset.i18nAria]);
  }
  document.getElementById("langButton").textContent = W.otherLang;
  renderFooter();
}

// The page's own line, unless dashboard.json gives one of its own; "" there means no footer.
let FOOTER = null;
function renderFooter() {
  document.getElementById("footer").innerHTML = typeof FOOTER === "string"
    ? esc(FOOTER)
    : esc(W.footer) + '<a href="https://github.com/Zyth45/mod-playerbots/tree/coa">' + esc(W.footerLink) + "</a>";
}

/* ---------------- pages ---------------- */
// The public copy is read-only: no settings.
const PAGES = ["world", "bots", "gear", "stats", "chat", "settings"]
  .filter(page => !PUBLIC || page !== "settings");
if (PUBLIC) {
  for (const node of document.querySelectorAll('.nav-link[href="#settings"]')) node.remove();
}
let PAGE = "world";
function showPage() {
  const wanted = location.hash.replace("#", "");
  PAGE = PAGES.includes(wanted) ? wanted : "world";
  for (const page of document.querySelectorAll(".page")) page.hidden = page.dataset.page !== PAGE;
  for (const link of document.querySelectorAll(".nav-link")) {
    if (link.getAttribute("href") === "#" + PAGE) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  document.getElementById("pageTitle").textContent = W.pageTitles[PAGE];
  /* private:start */if (PAGE === "chat") loadFeed();/* private:end */
}
window.addEventListener("hashchange", showPage);

/* ---------------- language ---------------- */
document.getElementById("langButton").addEventListener("click", () => {
  lang = lang === "en" ? "fr" : "en";
  try { localStorage.setItem("squidbots-lang", lang); } catch (error) { /* ignore */ }
  applyWords();
  showPage();
  if (LAST) render(LAST);
  renderFeed();
});

/* ---------------- line chart ---------------- */
function lineChart(host, points, options) {
  const settings = Object.assign({ unit: "", color: "var(--gold)" }, options);
  const value = settings.value, color = settings.color, unit = settings.unit;
  host.innerHTML = "";
  if (!points || points.length < 2) { host.append(el("p", { class: "empty" }, W.chartWait)); return; }
  const width = 720, height = 240, left = 56, right = 12, top = 14, bottom = 28;
  const xs = points.map(p => p.ts), ys = points.map(value);
  const x0 = Math.min.apply(null, xs), x1 = Math.max.apply(null, xs);
  // Round the top of the scale: readers compare against 40 000, not against 43 972.
  const rough = Math.max(Math.max.apply(null, ys), 1) * 1.12 / 4;
  const power = Math.pow(10, Math.floor(Math.log10(rough)));
  const step = power * [1, 1.5, 2, 2.5, 3, 4, 5, 10].find(m => power * m >= rough);
  const yMax = step * 4;
  const px = t => left + (width - left - right) * (x1 === x0 ? 0.5 : (t - x0) / (x1 - x0));
  const py = v => height - bottom - (height - top - bottom) * (v / yMax);

  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "0 0 " + width + " " + height);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", settings.label);
  const add = (tag, attrs) => {
    const node = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    svg.append(node);
    return node;
  };
  const text = (x, y, anchor, content) => {
    add("text", { x: x, y: y, "text-anchor": anchor, fill: "var(--text-muted)", "font-size": 11 }).textContent = content;
  };

  for (let i = 0; i <= 4; i++) {
    const v = yMax * i / 4, y = py(v);
    add("line", { x1: left, x2: width - right, y1: y, y2: y, stroke: "var(--grid)", "stroke-width": 1 });
    text(left - 10, y + 4, "end", num(v));
  }
  text(left, height - 8, "start", clock(x0));
  text(width - right, height - 8, "end", clock(x1));

  const path = points.map((p, i) => (i ? "L" : "M") + px(p.ts).toFixed(1) + "," + py(value(p)).toFixed(1)).join(" ");
  const id = "fill" + Math.random().toString(36).slice(2);
  const defs = document.createElementNS(NS, "defs");
  defs.innerHTML = '<linearGradient id="' + id + '" x1="0" y1="0" x2="0" y2="1">' +
    '<stop offset="0" stop-color="' + color + '" stop-opacity=".26"/>' +
    '<stop offset="1" stop-color="' + color + '" stop-opacity="0"/></linearGradient>';
  svg.append(defs);
  add("path", { d: path + " L" + px(x1).toFixed(1) + "," + py(0) + " L" + px(x0).toFixed(1) + "," + py(0) + " Z",
    fill: "url(#" + id + ")" });
  add("path", { d: path, fill: "none", stroke: color, "stroke-width": 2,
    "stroke-linejoin": "round", "stroke-linecap": "round" });

  const cross = add("line", { x1: 0, x2: 0, y1: top, y2: height - bottom,
    stroke: "var(--axis)", "stroke-width": 1, opacity: 0 });
  const dot = add("circle", { r: 4.5, fill: color, stroke: "var(--surface)", "stroke-width": 2, opacity: 0 });
  host.append(svg);
  const tip = el("div", { class: "tip" });
  host.append(tip);

  svg.addEventListener("pointerleave", () => {
    tip.style.opacity = 0; cross.setAttribute("opacity", 0); dot.setAttribute("opacity", 0);
  });
  svg.addEventListener("pointermove", event => {
    const box = svg.getBoundingClientRect();
    const wanted = (event.clientX - box.left) / box.width * width;
    let best = points[0], bestGap = Infinity;
    for (const p of points) {
      const gap = Math.abs(px(p.ts) - wanted);
      if (gap < bestGap) { best = p; bestGap = gap; }
    }
    const bx = px(best.ts), by = py(value(best));
    cross.setAttribute("x1", bx); cross.setAttribute("x2", bx); cross.setAttribute("opacity", .55);
    dot.setAttribute("cx", bx); dot.setAttribute("cy", by); dot.setAttribute("opacity", 1);
    tip.innerHTML = "<b>" + num(value(best)) + " " + esc(unit) + "</b>" + when(best.ts);
    tip.style.opacity = 1;
    tip.style.left = Math.min(Math.max(bx / width * box.width - tip.offsetWidth / 2, 0),
      box.width - tip.offsetWidth) + "px";
    tip.style.top = Math.max(0, by / height * box.height - tip.offsetHeight - 12) + "px";
  });
}

/* Gain per hour, measured over at least `window` hours.
   The server saves its characters every quarter of an hour, so two close points read as a spike
   followed by a flat line; a wider window gives the rate the bots actually hold. */
function rates(history, key, window) {
  const span = window || 0.5;
  const points = (history || []).filter(p => p[key] !== undefined), out = [];
  let start = 0;
  for (let i = 1; i < points.length; i++) {
    while (start < i - 1 && (points[i].ts - points[start + 1].ts) / 3600 >= span) start++;
    const hours = (points[i].ts - points[start].ts) / 3600;
    const gain = points[i][key] - points[start][key];
    if (hours >= span * 0.6 && gain >= 0) out.push({ ts: points[i].ts, rate: gain / hours });
  }
  return out;
}

/* ---------------- sections ---------------- */
/* What this particular server is running. Only a test realm ships a build.json; on every other
   install `data.build` is absent and this band never appears. */
function renderBuild(data) {
  const band = document.getElementById("build");
  const build = data.build;
  if (!build) { band.hidden = true; return; }
  const pulls = (build.pullRequests || []).map(pr =>
    '<a class="pr" href="' + esc(pr.url || ("https://github.com/jealous-sound/azerothcore-wotlk-coa/pull/" + pr.number)) +
    '" target="_blank" rel="noopener">#' + esc(String(pr.number)) +
    (pr.merged ? "" : " <em>open</em>") + "<span>" + esc(pr.title || "") + "</span></a>").join("");
  band.innerHTML =
    '<div class="buildband">' +
      '<div class="buildhead"><strong>' + esc(build.label || "Server") + "</strong>" +
        '<span class="buildmeta">core ' + esc(build.core || "?") + " &middot; bots " + esc(build.bots || "?") + "</span>" +
      "</div>" +
      (pulls ? '<div class="prs">' + pulls + "</div>" : "") +
    "</div>";
  band.hidden = false;
}

function renderFigures(data) {
  const host = document.getElementById("figures");
  host.innerHTML = "";
  const totals = data.totals || {}, session = data.session || {};
  const figures = [
    [W.figBots, num(totals.online), W.figBotsFoot(num(totals.bots))],
    [W.figLevel, one(totals.avgLevelOnline), W.figLevelFoot(num(totals.maxLevel))],
    [W.figKills, num(totals.kills),
      session.hours ? W.figKillsFoot(num(session.kills / Math.max(session.hours, 0.01))) : ""],
    [W.figQuests, num(totals.quests), session.since ? W.figQuestsFoot(session.since) : ""],
    [W.figLevels, num(session.levels), session.levelHours ? W.figLevelsFoot(one(session.levelHours)) : ""],
    [W.figServer, one((data.uptime || {}).hours) + " h",
      PUBLIC ? W.figServerRunning : W.figServerMemory(num((data.server || {}).ramMo))],
  ];
  for (const figure of figures) {
    host.append(el("div", { class: "figure" },
      '<div class="label">' + esc(figure[0]) + '</div><div class="value num">' + esc(figure[1]) +
      '</div><div class="foot">' + esc(figure[2]) + "</div>"));
  }
}

function splitBar(host, parts) {
  host.innerHTML = "";
  const total = Math.max(1, parts.reduce((sum, p) => sum + p.count, 0));
  const bar = el("div", { class: "split" });
  for (const p of parts) bar.append(el("i", { style: "width:" + (p.count / total * 100) + "%;background:" + p.color }));
  host.append(bar);
  host.append(el("div", { class: "legend" }, parts.map(p =>
    '<span><span class="key" style="background:' + p.color + '"></span>' + esc(p.label) +
    ' <b class="num">' + num(p.count) + "</b>" +
    (p.note ? ' <span class="meta">· ' + esc(p.note) + "</span>" : "") + "</span>").join("")));
}

function renderFactions(data) {
  const host = document.getElementById("factions");
  const f = data.factions;
  if (!f) { host.innerHTML = '<p class="empty">' + esc(W.noData) + "</p>"; return; }
  splitBar(host, [
    { label: "Alliance", count: f.online.alliance || 0, color: "var(--alliance)",
      note: W.levelWord(one(f.levelOnline.alliance)) },
    { label: "Horde", count: f.online.horde || 0, color: "var(--horde)",
      note: W.levelWord(one(f.levelOnline.horde)) },
  ]);
}

function renderRoles(data) {
  const host = document.getElementById("roles");
  const roles = data.roles || {};
  const total = Math.max(1, (roles.tank || 0) + (roles.heal || 0) + (roles.dps || 0));
  const share = n => Math.round((n || 0) / total * 100) + " %";
  splitBar(host, [
    { label: W.tanks, count: roles.tank || 0, color: "var(--alliance)", note: share(roles.tank) },
    { label: W.healers, count: roles.heal || 0, color: "var(--accent)", note: share(roles.heal) },
    { label: W.damage, count: roles.dps || 0, color: "var(--horde)", note: share(roles.dps) },
  ]);
}

function rankedList(host, rows, options) {
  host.innerHTML = "";
  if (!rows || !rows.length) { host.append(el("p", { class: "empty" }, options.waiting || W.measuring)); return; }
  const bar = options.bar || options.value;
  const max = Math.max.apply(null, rows.map(bar).concat([1]));
  const body = el("tbody");
  rows.forEach((row, i) => {
    const line = el("tr", row.online === false ? { class: "offline" } : {});
    line.append(el("td", { class: "rank" }, i < 3 ? medals[i] : String(i + 1)));
    line.append(el("td", {}, '<div class="name clickable">' + (row.faction ? factionDot(row.faction) : "") +
      esc(row.name) + '</div><div class="meta">' + esc(options.line2(row)) + "</div>"));
    line.append(el("td", { style: "width:32%" },
      '<div class="bar"><i style="width:' + (bar(row) / max * 100) + '%"></i></div>'));
    line.append(el("td", { class: "r" },
      '<b class="num">' + num(options.value(row)) + '</b> <span class="meta">' + esc(options.unit) + "</span>"));
    body.append(line);
  });
  const table = el("table");
  table.append(body);
  host.append(table);
}

function renderZones(data) {
  const host = document.getElementById("zones");
  const zones = data.zones || [];
  host.innerHTML = "";
  if (!zones.length) { host.innerHTML = '<p class="empty">' + esc(W.noData) + "</p>"; return; }
  const max = Math.max.apply(null, zones.map(z => z.count).concat([1]));
  const body = el("tbody");
  for (const zone of zones) {
    const line = el("tr");
    line.append(el("td", {}, '<span class="name">' + esc(zone.name) + "</span>"));
    line.append(el("td", { style: "width:46%" },
      '<div class="split" style="height:8px"><i style="width:' + (zone.alliance / max * 100) +
      '%;background:var(--alliance)"></i><i style="width:' + ((zone.count - zone.alliance) / max * 100) +
      '%;background:var(--horde)"></i></div>'));
    line.append(el("td", { class: "r" }, '<b class="num">' + num(zone.count) + "</b>"));
    body.append(line);
  }
  const table = el("table");
  table.append(body);
  host.append(table);
  host.append(el("p", { class: "meta", style: "margin:12px 0 0" },
    '<span class="key" style="background:var(--alliance)"></span>Alliance' +
    '<span class="key" style="background:var(--horde);margin-left:14px"></span>Horde'));
}

function renderCompare(data) {
  const host = document.getElementById("compare");
  const compare = data.compare || {};
  host.innerHTML = "";
  const labels = { kills: W.figKills, quests: W.figQuests, levels: W.figLevels };
  const body = el("tbody");
  let anything = false;
  for (const key of ["kills", "quests", "levels"]) {
    const row = compare[key] || {};
    if (row.today === null || row.today === undefined) continue;
    anything = true;
    const before = row.before;
    let change = '<span class="meta">-</span>';
    if (before !== null && before !== undefined && before > 0) {
      const delta = (row.today - before) / before * 100;
      const up = delta >= 0;
      change = '<span style="color:' + (up ? "var(--good)" : "var(--bad)") + '">' +
        (up ? "▲ +" : "▼ ") + Math.round(delta) + " %</span>";
    }
    const line = el("tr");
    line.append(el("td", {}, '<span class="name">' + esc(labels[key]) + "</span>"));
    line.append(el("td", { class: "r num" }, num(row.today)));
    line.append(el("td", { class: "r meta num" }, before === null || before === undefined ? "-" : num(before)));
    line.append(el("td", { class: "r" }, change));
    body.append(line);
  }
  if (!anything) { host.innerHTML = '<p class="empty">' + esc(W.compareWait) + "</p>"; return; }
  const table = el("table");
  table.append(el("thead", {}, '<tr><th></th><th class="r">' + esc(W.compareDay) + '</th><th class="r">' +
    esc(W.compareBefore) + '</th><th class="r">' + esc(W.compareChange) + "</th></tr>"));
  table.append(body);
  host.append(table);
}

function renderWatch(data) {
  const watch = data.watch || {}, server = data.server || {};
  const host = document.getElementById("watch");
  host.innerHTML = "";
  const missing = watch.stuck === null || watch.stuck === undefined;
  const cells = [
    [W.watchDead, watch.deadNow, watch.deadNow > 30],
    [W.watchStuck, missing ? "-" : watch.stuck,
      !missing && watch.stuck > ((data.totals || {}).online || 1000) * 0.1],
    [W.watchCrashes, PUBLIC ? "-" : server.crashes24h, server.crashes24h > 0],
  ];
  for (const cell of cells) {
    host.append(el("div", {}, '<div class="k">' + esc(cell[0]) + '</div><div class="n' + (cell[2] ? " alert" : "") +
      '">' + esc(cell[1] === undefined ? "-" : cell[1]) + "</div>"));
  }

  const span = (data.xpRate || {}).hours;
  const names = document.getElementById("stuckNames");
  names.innerHTML = (watch.stuckNames && watch.stuckNames.length)
    ? '<p class="meta" style="margin:10px 0 0">' + esc(W.stuckLine(one(span),
      watch.stuckNames.join(", ") + (watch.stuck > watch.stuckNames.length ? "…" : ""))) + "</p>"
    : "";

  const events = document.getElementById("incidents");
  events.innerHTML = "";
  const rows = watch.incidents;
  if (!rows) return;   // no watch journal on this server: nothing to list, and nothing to apologise for
  if (!rows.length) { events.innerHTML = '<li><span class="meta">' + esc(W.watchQuiet) + "</span></li>"; return; }
  for (const row of rows) {
    events.append(el("li", {}, "<time>" + esc(row.at) + "</time><span>" + esc(row.what) + "</span>"));
  }
}

function renderLevels(data) {
  const host = document.getElementById("levelBars");
  host.innerHTML = "";
  const rows = data.levels || [];
  if (!rows.length) { host.innerHTML = '<p class="empty">' + esc(W.noData) + "</p>"; return; }
  // One band per ten levels, the way the count below sorts them: 1-9, then 10-19 and so on.
  const buckets = [{ label: "1-9", count: 0 }];
  for (let start = 10; start <= 50; start += 10) {
    buckets.push({ label: start + "-" + (start === 50 ? 60 : start + 9), count: 0 });
  }
  for (const row of rows) {
    buckets[Math.min(buckets.length - 1, Math.floor(row.level / 10))].count += row.count;
  }
  const max = Math.max.apply(null, buckets.map(b => b.count).concat([1]));
  for (const bucket of buckets) {
    const cell = el("div", {});
    cell.append(el("b", { class: "num" }, num(bucket.count)));
    cell.append(el("i", { style: "height:" + (bucket.count / max * 100) + "%" }));
    cell.append(el("span", {}, bucket.label));
    host.append(cell);
  }
}

let allClasses = false;
// Which classes are drilled open right now (top ten of that class, ported from the previous
// dashboard's per-class tabs) -- a Set survives the 20 s refresh so an open row stays open.
const openClasses = new Set();
function renderClasses(data) {
  const host = document.getElementById("classes");
  const classes = data.classes || [];
  host.innerHTML = "";
  if (!classes.length) { host.innerHTML = '<p class="empty">' + esc(W.noData) + "</p>"; return; }
  const max = Math.max.apply(null, classes.map(c => c.avgLevel).concat([1]));
  const shown = allClasses ? classes : classes.slice(0, 8);
  const table = el("table");
  table.append(el("thead", {}, '<tr><th class="rank">#</th><th>' + esc(W.colClass) + "</th><th>" +
    esc(W.colAvgLevel) + '</th><th class="r">' + esc(W.colBots) + '</th><th class="r">' + esc(W.colKills) +
    "</th><th>" + esc(W.colPodium) + "</th></tr>"));
  const body = el("tbody");
  shown.forEach((c, i) => {
    const podium = (c.podium || []).map((p, k) =>
      '<span class="meta" style="white-space:nowrap">' + medals[k] + " " + factionDot(p.faction) + esc(p.name) +
      ' <b class="num" style="color:var(--text-primary)">' + esc(p.level) + "</b></span>").join("<br>");
    const open = openClasses.has(c.name);
    const line = el("tr", { style: "cursor:pointer" });
    line.append(el("td", { class: "rank" }, String(i + 1)));
    line.append(el("td", {}, '<span class="name">' + (open ? "▾ " : "▸ ") + esc(c.name) + "</span>"));
    line.append(el("td", { style: "width:24%" },
      '<div class="bar"><i style="width:' + (c.avgLevel / max * 100) + '%"></i></div>' +
      '<div class="meta num">' + one(c.avgLevel) + "</div>"));
    line.append(el("td", { class: "r num" }, num(c.bots)));
    line.append(el("td", { class: "r num" }, num(c.kills)));
    line.append(el("td", {}, podium || '<span class="meta">-</span>'));
    line.addEventListener("click", () => {
      if (openClasses.has(c.name)) openClasses.delete(c.name); else openClasses.add(c.name);
      renderClasses(LAST);
    });
    body.append(line);
    if (open) {
      const cell = el("td", { colspan: "6", style: "padding:10px 8px 18px 28px" });
      const inner = el("div");
      cell.append(inner);
      const detail = el("tr");
      detail.append(cell);
      body.append(detail);
      rankedList(inner, c.top, {
        value: b => b.level, unit: W.unitLevel,
        line2: b => W.colKills + ": " + num(b.kills) + " · " + W.tabQuests + ": " + num(b.quests) +
          (b.online ? "" : " · " + W.offline),
      });
    }
  });
  table.append(body);
  host.append(table);
  if (classes.length > 8) {
    const more = el("button", { class: "ghost", style: "margin-top:14px", type: "button" },
      allClasses ? W.showFew : W.showAll(classes.length));
    more.addEventListener("click", () => { allClasses = !allClasses; renderClasses(LAST); });
    host.append(more);
  }
}

let topKey = "xp";
function renderTop(data) {
  const rows = (data.top || {})[topKey] || [];
  rankedList(document.getElementById("top"), rows, {
    value: topKey === "xp" ? (b => b.level) : (b => b[topKey]),
    // Ten bots at the level cap would all draw a full bar: inside a level, the experience separates them.
    bar: topKey === "xp" ? (b => b.xp) : null,
    unit: topKey === "xp" ? W.unitLevel : topKey === "kills" ? W.unitKills : W.unitQuests,
    line2: b => b.cls + (b.spec ? " · " + b.spec : "") + (b.online ? "" : " · " + W.offline),
  });
}

function renderXpRate(data) {
  const rate = data.xpRate || {};
  document.getElementById("xpSub").textContent = rate.hours >= 1 ? W.xpSpan(one(rate.hours)) : W.xpMeasuring;
  rankedList(document.getElementById("xpRate"), rate.top, {
    value: b => b.xpPerHour, unit: W.xpUnit, waiting: W.xpWait,
    line2: b => b.cls + (b.spec ? " · " + b.spec : "") + " · " + W.levelShort(b.level) +
      (b.online ? "" : " · " + W.offline),
  });
}

function renderChat(data) {
  const host = document.getElementById("chat");
  const chat = data.chat;
  const sub = document.getElementById("chatSub");
  if (!chat) { sub.textContent = ""; host.innerHTML = '<p class="empty">' + esc(W.chatNone) + "</p>"; return; }
  sub.textContent = W.chatSub(num(chat.messages), num(chat.talkers));
  rankedList(host, chat.top, {
    value: t => t.messages, unit: W.chatUnit,
    line2: t => t.channel ? W.chatChannel(num(t.channel)) : W.chatOther,
  });
}

/* private:start */
/* ---------------- live chat feed ---------------- */
// Read from GET /api/chat every 5 s while the Chat page is open. The public copy has no
// API behind it, so the feed is left out there.
let FEED_KIND = "";
let FEED_LINES = null;     // the last answer, redrawn on a language switch
let FEED_KEY = "";         // skip the redraw when nothing changed, so a hover or a scroll survives
let FEED_ASKED = 0;        // drop answers that arrive after a newer request
let feedTimer = null;

// One chat line in the log's own words: "HH:MM:SS", the kind (or the channel's name) and "to X".
const chatTime = at => (at ? at.slice(11, 19) : "");
const chatKindLabel = line => line.channel || W.chatKinds[line.kind] || line.kind;

function renderFeed() {
  const host = document.getElementById("feed");
  const sub = document.getElementById("feedSub");
  if (!FEED_LINES) return;
  sub.textContent = W.feedSub(num(FEED_LINES.length));
  if (!FEED_LINES.length) {
    const filtered = FEED_KIND || document.getElementById("feedSearch").value.trim();
    host.innerHTML = '<p class="empty">' + esc(filtered ? W.feedQuiet : W.feedNone) + "</p>";
    return;
  }
  host.innerHTML = "<table><tbody>" + FEED_LINES.map(line =>
    '<tr class="chat-' + esc(line.kind) + '">'
    + '<td class="meta num feed-time" title="' + esc(line.at || "") + '">' + esc(chatTime(line.at)) + "</td>"
    + '<td class="feed-who"><span class="name">' + esc(line.speaker) + "</span></td>"
    + '<td class="feed-kind">' + esc(chatKindLabel(line)) + "</td>"
    + '<td class="feed-text">' + (line.target ? '<span class="meta">' + esc(W.feedTo(line.target)) + "</span> " : "")
    + esc(line.text) + "</td></tr>").join("") + "</tbody></table>";
}

async function loadFeed() {
  if (PUBLIC) return;
  const asked = ++FEED_ASKED;
  const params = new URLSearchParams({ limit: "100" });
  if (FEED_KIND) params.set("kind", FEED_KIND);
  const wanted = document.getElementById("feedSearch").value.trim();
  if (wanted) params.set("q", wanted);
  let answer;
  try { answer = await (await fetch("/api/chat?" + params, { cache: "no-store" })).json(); } catch (error) { return; }
  if (asked !== FEED_ASKED || !answer || !Array.isArray(answer.lines)) return;
  const key = JSON.stringify(answer.lines);
  if (key === FEED_KEY && FEED_LINES) return;
  FEED_KEY = key;
  FEED_LINES = answer.lines;
  renderFeed();
}

if (PUBLIC) document.getElementById("feedCard").remove();
else {
  document.getElementById("feedKinds").addEventListener("click", event => {
    const button = event.target.closest("button[data-kind]");
    if (!button) return;
    FEED_KIND = button.dataset.kind;
    for (const other of document.querySelectorAll("#feedKinds button")) {
      other.setAttribute("aria-selected", String(other === button));
    }
    loadFeed();
  });
  document.getElementById("feedSearch").addEventListener("input", () => {
    clearTimeout(feedTimer);
    feedTimer = setTimeout(loadFeed, 300);
  });
}

/* ---------------- one bot's recent chat ---------------- */
// Fetched when a bot's card opens (clicked on the map, in the roster or from the search),
// then drawn from this cache while the card stays open.
const BOT_CHAT = {};       // name -> {lines} once read, {loading: true} before

function botChatHtml(name) {
  const entry = BOT_CHAT[name];
  if (!entry && !PUBLIC) loadBotChat(name);
  let body;
  if (!entry || entry.loading) body = '<p class="meta">' + esc(W.botChatLoading) + "</p>";
  else if (!entry.lines.length) body = '<p class="meta">' + esc(W.botChatNone) + "</p>";
  else {
    body = "<ul>" + entry.lines.map(line => {
      const said = line.speaker.toLowerCase() === name.toLowerCase();
      return '<li class="chat-' + esc(line.kind) + '"><time title="' + esc(line.at || "") + '">'
        + esc(chatTime(line.at).slice(0, 5)) + "</time> "
        + (said ? (line.target ? '<span class="meta">' + esc(W.feedTo(line.target)) + ":</span> " : "")
          : "<b>" + esc(line.speaker) + ":</b> ")
        + esc(line.text) + "</li>";
    }).join("") + "</ul>";
  }
  return '<div class="bc-chat" data-bot-chat="' + esc(name) + '"><span>' + esc(W.botChat) + "</span>" + body + "</div>";
}

async function loadBotChat(name) {
  if (PUBLIC) return;
  if (!BOT_CHAT[name]) BOT_CHAT[name] = { loading: true };
  let answer;
  try {
    answer = await (await fetch("/api/chat?" + new URLSearchParams({ bot: name, limit: "10" }),
      { cache: "no-store" })).json();
  } catch (error) { answer = null; }
  BOT_CHAT[name] = { lines: (answer && Array.isArray(answer.lines)) ? answer.lines : [] };
  for (const node of document.querySelectorAll(".bc-chat[data-bot-chat]")) {
    if (node.dataset.botChat === name) node.outerHTML = botChatHtml(name);
  }
}

/* private:end */

function renderLoot(data) {
  const host = document.getElementById("loot");
  const loot = data.loot;
  const sub = document.getElementById("lootSub");
  host.innerHTML = "";
  if (!loot) { sub.textContent = ""; host.innerHTML = '<p class="empty">' + esc(W.lootNone) + "</p>"; return; }
  sub.textContent = W.lootSub(num(loot.total));
  if (!loot.rows.length) { host.innerHTML = '<p class="empty">' + esc(W.lootQuiet) + "</p>"; return; }
  const names = data.classNames || {};
  const body = el("tbody");
  for (const row of loot.rows) {
    const line = el("tr");
    line.append(el("td", { class: "meta num", style: "white-space:nowrap" }, clock(row.ts)));
    line.append(el("td", {}, '<div class="q' + (row.quality > 5 ? 5 : row.quality) + '">' +
      esc(row.item) + (row.count > 1 ? " ×" + row.count : "") +
      '</div><div class="meta">' + esc(names[row.cls] || "") + " · " + esc(W.levelShort(row.level)) + "</div>"));
    line.append(el("td", { class: "r" }, '<div class="name clickable">' + esc(row.bot) +
      '</div><div class="meta">ilvl ' + esc(row.ilvl) + "</div>"));
    body.append(line);
  }
  const table = el("table");
  table.append(body);
  host.append(table);
}

function renderActions(data) {
  const host = document.getElementById("actions");
  const actions = data.actions;
  host.innerHTML = "";
  if (!actions || !actions.rows || !actions.rows.length) {
    host.innerHTML = '<p class="empty">' + esc(W.spellsNone) + "</p>";
    return;
  }
  document.getElementById("actionsSub").textContent = W.spellsSub(one(actions.hours));
  const rows = actions.rows.filter(r => r.tried > 0).sort((a, b) => b.cast - a.cast);
  const table = el("table");
  table.append(el("thead", {}, "<tr><th>" + esc(W.colAction) + "</th><th>" + esc(W.colSuccess) +
    '</th><th class="r">' + esc(W.colCast) + '</th><th class="r">' + esc(W.colTried) + "</th></tr>"));
  const body = el("tbody");
  for (const row of rows) {
    const share = row.cast / row.tried;
    const line = el("tr");
    line.append(el("td", {}, '<span class="name">' + esc(W.spellNames[row.key] || row.key) + "</span>"));
    line.append(el("td", { style: "width:36%" }, '<div class="bar"><i style="width:' + Math.round(share * 100) +
      "%;background:" + (share > 0.5 ? "var(--accent)" : "var(--gold)") + '"></i></div>'));
    line.append(el("td", { class: "r num" }, num(row.cast)));
    line.append(el("td", { class: "r num" },
      num(row.tried) + ' <span class="meta">' + Math.round(share * 100) + " %</span>"));
    body.append(line);
  }
  table.append(body);
  host.append(table);
}

/* ---------------- one bot's sheet ---------------- */
function openSheet(name) {
  const bot = ((LAST && LAST.bots) || []).find(b => b.n === name);
  if (!bot) return;
  const rate = ((LAST.xpRate || {}).top || []).find(g => g.name === name);
  const rows = [
    [W.sheetLevel, bot.l], [W.sheetKills, num(bot.k)], [W.sheetQuests, num(bot.q)],
    [W.sheetZone, bot.z || "-"], [W.sheetPlayed, one(bot.h) + " h"],
    [W.sheetXp, rate ? num(rate.xpPerHour) + " " + W.xpUnit : "-"],
  ];
  document.getElementById("sheetBody").innerHTML =
    "<h3>" + (bot.f ? factionDot(bot.f) : "") + esc(bot.n) + "</h3>" +
    '<p class="who">' + esc(bot.c) + (bot.s ? " · " + esc(bot.s) : "") + " · " + esc(W[bot.r] || bot.r) +
    (bot.o ? "" : " · " + esc(W.offline)) + "</p><dl>" +
    rows.map(r => "<dt>" + esc(r[0]) + "</dt><dd>" + esc(r[1]) + "</dd>").join("") +
    '</dl><button class="ghost close" type="button" id="sheetClose">' + esc(W.close) + "</button>";
  const sheet = document.getElementById("sheet");
  document.getElementById("sheetClose").addEventListener("click", () => sheet.close());
  sheet.showModal();
}

document.addEventListener("click", event => {
  const target = event.target.closest(".name");
  if (target && LAST && (LAST.bots || []).some(b => b.n === target.textContent.trim())) {
    openSheet(target.textContent.trim());
  }
});

const search = document.getElementById("search");
const results = document.getElementById("results");
search.addEventListener("input", () => {
  const wanted = search.value.trim().toLowerCase();
  results.innerHTML = "";
  if (wanted.length < 2 || !LAST) { results.hidden = true; return; }
  const found = (LAST.bots || []).filter(b => b.n.toLowerCase().includes(wanted)).slice(0, 12);
  if (!found.length) { results.hidden = true; return; }
  for (const bot of found) {
    const button = el("button", { type: "button" },
      (bot.f ? factionDot(bot.f) : "") + "<b>" + esc(bot.n) + "</b> " +
      '<span class="meta">' + esc(bot.c) + " · " + esc(W.levelShort(bot.l)) + "</span>");
    button.addEventListener("click", () => { results.hidden = true; search.value = ""; setFocus(bot.n); openSheet(bot.n); });
    results.append(button);
  }
  results.hidden = false;
});
document.addEventListener("click", event => {
  if (!event.target.closest(".search")) results.hidden = true;
});

/* ---------------- page ---------------- */
let LAST = null;
function render(data) {
  LAST = data;
  if (typeof data.footer === "string" || data.footer === null) {
    FOOTER = typeof data.footer === "string" ? data.footer : null;
    renderFooter();
  }
  const running = (data.server || {}).running;
  document.getElementById("stateDot").className = "dot live" + (running ? "" : " off");
  document.getElementById("stateText").textContent =
    running ? W.online(num((data.totals || {}).online)) : W.stopped;
  document.getElementById("updatedPill").textContent = W.updated(data.generatedAt || "-");

  renderBuild(data);
  renderFigures(data);
  renderFactions(data);
  renderRoles(data);
  renderZones(data);
  renderCompare(data);
  renderWatch(data);
  renderLevels(data);
  renderXpRate(data);
  renderChat(data);
  renderClasses(data);
  renderTop(data);
  renderLoot(data);
  renderActions(data);
  renderRoster();
  renderFocus();

  const pace = rates(data.history, "kills");
  lineChart(document.getElementById("paceChart"), pace,
    { value: p => p.rate, label: W.paceTitle, unit: W.paceSub });
  document.getElementById("paceSub").textContent = pace.length ? W.paceSub : "";
  const levels = rates(data.history, "levelUps");
  lineChart(document.getElementById("levelsChart"), levels,
    { value: p => p.rate, label: W.progressTitle, unit: W.progressSub, color: "var(--accent)" });
  document.getElementById("progressSub").textContent = levels.length ? W.progressSub : "";
  const dead = (data.history || []).filter(p => p.dead !== undefined).map(p => ({ ts: p.ts, dead: p.dead }));
  lineChart(document.getElementById("deadChart"), dead,
    { value: p => p.dead, label: W.deadTitle, unit: W.figBots, color: "var(--horde)" });
}

document.getElementById("topTabs").addEventListener("click", event => {
  const button = event.target.closest("button[data-key]");
  if (!button) return;
  topKey = button.dataset.key;
  for (const other of document.querySelectorAll("#topTabs button")) {
    other.setAttribute("aria-selected", String(other === button));
  }
  if (LAST) renderTop(LAST);
});

/* ---------------------------------------------------------------- map ---- */

let WORLD = null;
let MAP_ID = "0";
let ZOOM_ZONE = null;
// Live snapshot (bot-status.json, written by mod-playerbots when AiPlayerbot.CoaStatusFile is set,
// read by the local server): current position, health and what each bot is doing. Keyed by name.
// Empty when the server is down or nothing writes bot-status.json, and the map falls back to the
// characters table.
let LIVE = { byName: {}, age: null, missing: null };
// Bumped when the extracted art changes shape. An early build served the maps with
// a one day max-age, so a stale 1024x768 copy would otherwise sit in the browser
// cache and be squashed into the new 1002x668 box, padding and all. The server now
// sends no-cache, so this only has to get past that one old entry.
const MAP_ART_VERSION = 3;
// Changed after an extraction, so the new maps replace whatever the browser holds.
let ART_STAMP = "";

async function loadWorld() {
  if (WORLD) return WORLD;
  try {
    // Relative: the public copy carries its own worldmap.json next to stats.json.
    const answer = await fetch("worldmap.json", { cache: "no-cache" });
    if (!answer.ok) return null;
    WORLD = await answer.json();
  } catch (error) { WORLD = null; }
  return WORLD;
}

// The public page reads live.json, which the dashboard copies beside it every 12 s; the local one
// asks its server. live.json is revalidated rather than fetched again: unchanged, it costs nothing.
const LIVE_EVERY = PUBLIC ? 12000 : 5000;
const LIVE_STALE = 90;  // seconds: older than this, the server or the dashboard has stopped

async function refreshLive() {
  let url = "live.json";
  /* private:start */url = "/api/live";/* private:end */
  try {
    const answer = await fetch(url, { cache: PUBLIC ? "no-cache" : "no-store" });
    const data = await answer.json();
    let age = data.age === undefined ? null : data.age;
    if (PUBLIC && data.at) {
      // How old the file is, by the web server's own clock (the visitor's may be off), plus how old
      // the snapshot already was when it was copied.
      const written = Date.parse(answer.headers.get("last-modified") || "");
      const now = Date.parse(answer.headers.get("date") || "");
      age = (age || 0) + (written && now ? Math.max(0, Math.round((now - written) / 1000)) : 0);
    }
    const byName = {};
    let missing = data.missing || null;
    if (PUBLIC && data.at && age > LIVE_STALE) missing = "the server is not sending live positions";
    else for (const bot of data.bots || []) byName[bot.n] = bot;
    LIVE = { byName: byName, age: data.absent ? null : age, missing: missing };
  } catch (error) {
    LIVE = { byName: {}, age: null, missing: PUBLIC ? null : "live status unavailable" };
  }
}

// World coordinates are rotated relative to the map: LocLeft and LocRight bound
// world Y, LocTop and LocBottom bound world X.
function worldToPct(bounds, worldX, worldY) {
  const spanX = bounds.left - bounds.right;
  const spanY = bounds.top - bounds.bottom;
  if (!spanX || !spanY) return null;
  return [(bounds.left - worldY) / spanX, (bounds.top - worldX) / spanY];
}

function inBox(spot, slack) {
  const s = slack || 0;
  return spot && spot[0] >= -s && spot[0] <= 1 + s && spot[1] >= -s && spot[1] <= 1 + s;
}

// The union of a continent's zone rectangles: the part of the texture that is
// actually land. Eastern Kingdoms content is only about a quarter of the texture
// width, the rest being open sea, so the view is cropped to this.
function contentBounds(continent) {
  const zs = continent.zones || [];
  if (!zs.length) return { x: 0, y: 0, w: 1, h: 1 };
  const pad = 0.015;
  const x1 = Math.max(0, Math.min.apply(null, zs.map(z => z.x)) - pad);
  const y1 = Math.max(0, Math.min.apply(null, zs.map(z => z.y)) - pad);
  const x2 = Math.min(1, Math.max.apply(null, zs.map(z => z.x + z.w)) + pad);
  const y2 = Math.min(1, Math.max.apply(null, zs.map(z => z.y + z.h)) + pad);
  return { x: x1, y: y1, w: x2 - x1, h: y2 - y1 };
}

// Every zone the current tab can open: the continent's own, plus the offworld ones
// (the blood elf and draenei starts) that share its map id but sit outside its art.
function tabZones(continent) {
  const offworld = (WORLD.offworld || []).filter(z => String(z.mapId) === MAP_ID && z.bounds);
  return continent.zones.concat(offworld.map(z => Object.assign({ offworld: true }, z)));
}

function zoneTitle(z) { return z.title || z.name; }

// A bot's position: the live snapshot when there is one, else the last save.
function whereIs(b) {
  const live = LIVE.byName[b.n];
  return live ? { m: live.m, x: live.x, y: live.y, live: true } : { m: b.m, x: b.x, y: b.y, live: false };
}

function renderMap(data) {
  const holder = document.getElementById("mapHolder");
  const tabs = document.getElementById("mapTabs");
  const elsewhere = document.getElementById("mapElsewhere");
  const sub = document.getElementById("mapSub");
  hideBotCard();

  if (!WORLD) {
    tabs.innerHTML = "";
    elsewhere.textContent = "";
    holder.innerHTML = '<div class="map-empty">Map geometry is not available. '
      + 'Run <code>python tools/gen_worldmap.py</code> to create worldmap.json.</div>';
    sub.textContent = "";
    return;
  }

  if (!tabs.childElementCount) {
    tabs.setAttribute("role", "tablist");
    tabs.innerHTML = Object.keys(WORLD.continents).map(id =>
      '<button type="button" data-map="' + id + '" role="tab" aria-selected="'
      + (id === MAP_ID) + '">' + esc(WORLD.continents[id].name) + "</button>").join("");
  }

  const continent = WORLD.continents[MAP_ID];
  const zones = tabZones(continent);
  const online = (data.bots || []).filter(b => b.o && (LIVE.byName[b.n] || b.x !== undefined));
  const here = online.map(b => ({ b: b, at: whereIs(b) })).filter(p => String(p.at.m) === MAP_ID);
  const known = new Set(Object.keys(WORLD.continents));
  const away = online.filter(b => !known.has(String(whereIs(b).m)));

  // A bot counts in the zone the server says it is in (live zone id, else the saved
  // zone name). Zone rectangles overlap at the edges, so the rectangle test is only
  // the fallback for a bot whose zone is not one of this tab's.
  const zoneOfBot = p => {
    const live = LIVE.byName[p.b.n];
    return zones.find(z => (live && live.zone === z.areaId) || (!live && p.b.z && p.b.z === zoneTitle(z)));
  };
  const counts = {};
  for (const z of zones) counts[z.name] = 0;
  for (const p of here) {
    const home = zoneOfBot(p);
    if (home) { counts[home.name] += 1; continue; }
    const box = zones.find(z => z.bounds && inBox(worldToPct(z.bounds, p.at.x, p.at.y)));
    if (box) counts[box.name] += 1;
  }

  const zoom = ZOOM_ZONE ? zones.find(z => z.name === ZOOM_ZONE) || null : null;
  if (ZOOM_ZONE && !zoom) ZOOM_ZONE = null;

  // The continent and zone maps extracted from the player's own client (tools/gen_art.py), served
  // by the local server and copied beside the public page (publish_maps in squidbots.py).
  const W = 1002, H = 668;
  let view, image = null, dots, hits = "";

  if (zoom) {
    view = { x: 0, y: 0, w: 1, h: 1 };
    image = "maps/zones/" + encodeURIComponent(zoom.name) + ".png?v=" + MAP_ART_VERSION + ART_STAMP;
    dots = here.map(p => ({ b: p.b, live: p.at.live, spot: worldToPct(zoom.bounds, p.at.x, p.at.y) }))
      .filter(p => inBox(p.spot, 0.01));
  } else {
    view = contentBounds(continent);
    image = "maps/" + encodeURIComponent(MAP_ID) + ".png?v=" + MAP_ART_VERSION + ART_STAMP;
    dots = here.map(p => ({ b: p.b, live: p.at.live, spot: worldToPct(continent.bounds, p.at.x, p.at.y) }))
      .filter(p => inBox(p.spot, 0.02));
    hits = continent.zones.map(z => {
      const n = counts[z.name] || 0;
      return '<rect class="map-hit" data-zone="' + esc(z.name) + '" x="' + (z.x * W) + '" y="'
        + (z.y * H) + '" width="' + (z.w * W) + '" height="' + (z.h * H) + '"><title>'
        + esc(zoneTitle(z)) + (n ? " – " + n + " bot" + (n === 1 ? "" : "s") : " – no bots")
        + "</title></rect>";
    }).join("");
  }

  sub.textContent = zoom
    ? zoneTitle(zoom) + ": " + (counts[zoom.name] || 0) + " bot(s)"
    : here.length + " of " + online.length + " online bots";

  // Dots stay the same size on screen whether the view is a continent or a zone.
  const radius = zoom ? 6.5 : (view.w * W) / 190;
  const dotMarks = dots.map(p =>
    '<circle class="map-bot ' + (p.b.f === "alliance" ? "alliance" : "horde")
    + (p.live ? "" : " stale") + (p.b.n === FOCUS ? " focused" : "") + '" data-name="' + esc(p.b.n) + '" tabindex="0" role="button" aria-label="'
    + esc(p.b.n) + '" cx="' + (p.spot[0] * W).toFixed(1) + '" cy="' + (p.spot[1] * H).toFixed(1)
    + '" r="' + radius.toFixed(2) + '" stroke-width="' + (radius / 3).toFixed(2) + '"></circle>').join("");

  const vbW = view.w * W, vbH = view.h * H;
  holder.innerHTML = '<svg class="map-svg' + (image ? "" : " no-art") + '" style="aspect-ratio:' + vbW.toFixed(2) + "/"
    + vbH.toFixed(2) + '" viewBox="' + (view.x * W) + " " + (view.y * H)
    + " " + vbW + " " + vbH + '" preserveAspectRatio="xMidYMid meet" '
    + 'role="img" aria-label="Bot positions on ' + esc(zoom ? zoneTitle(zoom) : continent.name) + '">'
    + (image ? '<image href="' + image + '" x="0" y="0" width="' + W
      + '" height="' + H + '" preserveAspectRatio="none"></image>' : "")
    + hits + dotMarks + "</svg>"
    + '<div class="bot-card" id="botCard" hidden></div>'
    + (zoom ? '<div class="map-crumb"><button class="ghost" type="button" id="mapBack">'
        + "← " + esc(continent.name) + "</button><span>" + esc(zoneTitle(zoom)) + "</span></div>"
      : '<div class="map-crumb"><span>Click a zone to open its map. Hover a bot for its status.</span></div>');

  const most = Math.max(1, Math.max.apply(null, zones.map(z => counts[z.name] || 0)));
  document.getElementById("mapZones").innerHTML = zones
    .slice()
    .sort((a, b) => (counts[b.name] || 0) - (counts[a.name] || 0) || zoneTitle(a).localeCompare(zoneTitle(b)))
    .map(z => {
      const n = counts[z.name] || 0;
      return '<div class="zone-row' + (n ? " has" : "") + (ZOOM_ZONE === z.name ? " active" : "")
        + '" data-zone="' + esc(z.name) + '"><span class="zn">' + esc(zoneTitle(z)) + "</span>"
        + '<span class="bar"><i style="width:' + Math.round((n / most) * 100) + '%"></i></span>'
        + '<span class="zc">' + n + "</span></div>";
    }).join("");

  const bits = [];
  if (away.length) bits.push(away.length + " bot(s) in instances or on maps with no world outline");
  if (LIVE.missing) bits.push("Positions are from the last save, not live: " + LIVE.missing);
  else if (LIVE.age !== null) bits.push("Live positions, " + LIVE.age + " s old");
  else bits.push("Positions are from the last character save");
  elsewhere.textContent = bits.join(". ");
}

/* --------------------------------------------------------- bot card ---- */

// withChat: the card of a clicked bot (pinned on the map, or the focus panel) lists its recent chat;
// the hover card stays short and reads nothing.
function botCardHtml(bot, withChat) {
  const live = LIVE.byName[bot.n];
  const bar = (label, pct, kind) =>
    '<div class="bc-meter"><span>' + esc(label) + '</span><span class="bc-track"><i class="' + kind
    + '" style="width:' + Math.max(0, Math.min(100, pct)) + '%"></i></span><b>' + pct + "%</b></div>";
  const power = live ? ({ 0: "Mana", 1: "Rage", 2: "Focus", 3: "Energy", 6: "Runic" }[live.pt] || "Power") : "";
  let task;
  // Without a live snapshot (no module writes one on a stock repack), say what the last save knows.
  if (live) task = live.task || "Idle";
  else if (LIVE.missing) task = "No live status: " + LIVE.missing;
  else task = bot.d ? "Dead" : bot.o ? "Online" : "Offline";
  const rows = [];
  rows.push('<div class="bc-head">' + (bot.f ? factionDot(bot.f) : "") + "<b>" + esc(bot.n) + "</b>"
    + '<span class="bc-lvl">' + esc(String(live ? live.l : bot.l)) + "</span></div>");
  rows.push('<div class="bc-who">' + esc(bot.c) + (bot.s ? " · " + esc(bot.s) : "")
    + (bot.r ? " · " + esc(W[bot.r] || bot.r) : "") + "</div>");
  rows.push('<div class="bc-task' + (live && live.combat ? " combat" : "") + ((live ? live.dead : bot.d) ? " dead" : "")
    + '">' + esc(task) + "</div>");
  if (live) {
    rows.push(bar("Health", live.hp, "hp"));
    if (live.pt !== undefined && live.pt !== 1 && live.pt !== 6) rows.push(bar(power, live.pw, "pw"));
    if (live.grp) {
      rows.push('<div class="bc-line">Group of ' + live.grp + (live.lead ? ", led by " + esc(live.lead) : "")
        + "</div>");
    }
    if ((live.quests || []).length) {
      rows.push('<div class="bc-quests"><span>Quests</span><ul>'
        + live.quests.map(q => "<li>" + esc(q) + "</li>").join("") + "</ul></div>");
    }
  }
  /* private:start */if (withChat && !PUBLIC) rows.push(botChatHtml(bot.n));/* private:end */
  const zoneName = zoneNameOf(bot);
  rows.push('<div class="bc-foot">' + esc(zoneName) + (zoneName ? " · " : "")
    + num(bot.k) + " kills · " + num(bot.q) + " quests · " + one(bot.g) + "g</div>");
  return rows.join("");
}

function showBotCard(dot, pinned) {
  const card = document.getElementById("botCard");
  const holder = document.getElementById("mapHolder");
  if (!card || !LAST) return;
  const bot = (LAST.bots || []).find(b => b.n === dot.dataset.name);
  if (!bot) return;
  card.innerHTML = botCardHtml(bot, pinned);
  card.hidden = false;
  card.classList.toggle("pinned", !!pinned);
  card.dataset.name = bot.n;
  // Beside the dot, flipped to the other side when it would leave the map.
  const box = holder.getBoundingClientRect();
  const spot = dot.getBoundingClientRect();
  const gap = 12;
  let left = spot.right - box.left + gap;
  let top = spot.top - box.top - 8;
  if (left + card.offsetWidth > box.width) left = spot.left - box.left - card.offsetWidth - gap;
  if (left < 0) left = Math.max(0, (box.width - card.offsetWidth) / 2);
  top = Math.max(0, Math.min(top, box.height - card.offsetHeight));
  card.style.left = left + "px";
  card.style.top = top + "px";
}

function hideBotCard(force) {
  const card = document.getElementById("botCard");
  if (card && (force || !card.classList.contains("pinned"))) card.hidden = true;
}

const mapHolder = document.getElementById("mapHolder");
mapHolder.addEventListener("mouseover", event => {
  const dot = event.target.closest(".map-bot");
  if (dot) showBotCard(dot, false);
});
mapHolder.addEventListener("mouseout", event => {
  if (event.target.closest(".map-bot")) hideBotCard(false);
});
mapHolder.addEventListener("focusin", event => {
  const dot = event.target.closest(".map-bot");
  if (dot) showBotCard(dot, false);
});
mapHolder.addEventListener("focusout", () => hideBotCard(false));

document.getElementById("mapZones").addEventListener("click", event => {
  const row = event.target.closest(".zone-row");
  if (!row) return;
  ZOOM_ZONE = (ZOOM_ZONE === row.dataset.zone) ? null : row.dataset.zone;
  if (LAST) renderMap(LAST);
});

mapHolder.addEventListener("click", event => {
  if (event.target.closest("#mapBack")) {
    ZOOM_ZONE = null;
    if (LAST) renderMap(LAST);
    return;
  }
  // A tap on a bot pins its card (there is no hover on a phone); a second tap on
  // the same bot, or a tap anywhere else, lets it go.
  const dot = event.target.closest(".map-bot");
  if (dot) {
    setFocus(dot.dataset.name);
    const card = document.getElementById("botCard");
    if (card && card.classList.contains("pinned") && card.dataset.name === dot.dataset.name) hideBotCard(true);
    else showBotCard(dot, true);
    return;
  }
  if (event.target.closest("#botCard")) return;
  hideBotCard(true);
  const hit = event.target.closest(".map-hit");
  if (!hit) return;
  const zone = hit.dataset.zone;
  ZOOM_ZONE = (ZOOM_ZONE === zone) ? null : zone;
  if (LAST) renderMap(LAST);
});

document.getElementById("mapTabs").addEventListener("click", event => {
  const button = event.target.closest("button[data-map]");
  if (!button) return;
  MAP_ID = button.dataset.map;
  ZOOM_ZONE = null;
  for (const other of document.querySelectorAll("#mapTabs button")) {
    other.setAttribute("aria-selected", String(other === button));
  }
  if (LAST) renderMap(LAST);
});

// Live positions and tasks move faster than the 20 s stats refresh. Skip a redraw
// while a card is pinned so it does not vanish under the reader.
// Only the World and Bots pages show live data: elsewhere, or in a hidden tab, nothing is fetched,
// and coming back fetches at once.
async function refreshLiveMap() {
  if (document.hidden || (PAGE !== "world" && PAGE !== "bots")) return;
  await refreshLive();
  const card = document.getElementById("botCard");
  if (LAST && !(card && !card.hidden)) renderMap(LAST);
  renderFocus();
  if (PAGE === "bots") renderRoster();
}

/* ----------------------------------------------- followed bot and roster ---- */

// The bot being followed: picked on the map, in the Bots list or from the search.
// The World page's card follows it. Kept for the tab's session.
let FOCUS = null;
try { FOCUS = sessionStorage.getItem("squidbots-focus"); } catch (error) { /* private window */ }

function classIdOf(name) {
  for (const [id, className] of Object.entries((LAST && LAST.classNames) || {})) {
    if (className === name) return id;
  }
  return null;
}

function setFocus(name) {
  FOCUS = name;
  loadBotChat(name);
  try { sessionStorage.setItem("squidbots-focus", name); } catch (error) { /* ignore */ }
  // Show the continent the bot is on, if the map has a tab for it.
  const bot = LAST ? (LAST.bots || []).find(b => b.n === name) : null;
  const live = LIVE.byName[name];
  const mapId = String(live ? live.m : bot ? bot.m : "");
  const tab = document.querySelector('#mapTabs button[data-map="' + mapId + '"]');
  if (tab && mapId !== MAP_ID) {
    MAP_ID = mapId;
    ZOOM_ZONE = null;
    for (const other of document.querySelectorAll("#mapTabs button")) other.setAttribute("aria-selected", String(other === tab));
    if (LAST) renderMap(LAST);
  }
  renderFocus();
  renderRoster();
  for (const dot of document.querySelectorAll(".map-bot")) dot.classList.toggle("focused", dot.dataset.name === name);
}

// Where a bot is now: the live zone when the server reports one, else the last save
// (the characters table is only written every quarter of an hour).
let ZONE_TITLES = null;
function zoneNameOf(bot) {
  const live = LIVE.byName[bot.n];
  if (live && WORLD) {
    if (!ZONE_TITLES) {
      ZONE_TITLES = {};
      const zones = Object.values(WORLD.continents || {}).flatMap(c => c.zones || []).concat(WORLD.offworld || []);
      for (const zone of zones) ZONE_TITLES[zone.areaId] = zoneTitle(zone);
    }
    if (ZONE_TITLES[live.zone]) return ZONE_TITLES[live.zone];
  }
  return bot.z || "";
}

// The followed bot's card, on the World page and beside the Bots page roster.
function renderFocus() {
  const bot = FOCUS && LAST ? (LAST.bots || []).find(b => b.n === FOCUS) : null;
  for (const sub of document.querySelectorAll("[data-focus-name]")) sub.textContent = bot ? bot.n : "";
  for (const card of document.querySelectorAll("[data-focus-card]")) {
    if (!bot) {
      card.innerHTML = '<p class="empty">' + esc(W.focusNone) + "</p>";
      continue;
    }
    card.innerHTML = '<div class="bot-card">' + botCardHtml(bot, true) + "</div>";
    const head = card.querySelector(".bc-head");
  }
}

let ROSTER_SORT = "level";
let ROSTER_SHOW_OFFLINE = false;
try { ROSTER_SHOW_OFFLINE = localStorage.getItem("squidbots-roster-offline") === "1"; } catch (error) { /* private window etc. */ }
function rosterRows() {
  const wanted = document.getElementById("rosterFilter").value.trim().toLowerCase();
  const rows = ((LAST && LAST.bots) || []).filter(b => ROSTER_SHOW_OFFLINE || b.o).map(b => {
    const live = LIVE.byName[b.n];
    const task = live ? (live.task || "Idle") : (b.o ? "" : W.offline);
    return { bot: b, live: live, level: live ? live.l : b.l, zone: zoneNameOf(b), task: task };
  }).filter(r => !wanted || (r.bot.n + " " + r.zone + " " + r.bot.c).toLowerCase().includes(wanted));
  const byName = (a, b) => a.bot.n.localeCompare(b.bot.n);
  if (ROSTER_SORT === "name") rows.sort(byName);
  else if (ROSTER_SORT === "zone") rows.sort((a, b) => a.zone.localeCompare(b.zone) || byName(a, b));
  else rows.sort((a, b) => b.level - a.level || byName(a, b));
  return rows;
}

function renderRoster() {
  const host = document.getElementById("roster");
  if (!LAST) return;
  const rows = rosterRows();
  document.getElementById("rosterSub").textContent = rows.length + " shown";
  if (!rows.length) { host.innerHTML = '<p class="empty">' + esc(W.noData) + "</p>"; return; }
  const health = r => r.live
    ? '<div class="bar" title="' + r.live.hp + '%"><i style="width:' + Math.max(0, Math.min(100, r.live.hp))
      + "%;background:linear-gradient(180deg,#4ee06f,#13891f)\"></i></div>"
    : '<span class="meta">-</span>';
  // Capped so a filter-less list of hundreds stays quick to draw.
  const shown = rows.slice(0, 300);
  host.innerHTML = "<table><thead><tr><th>" + esc(W.sortName) + "</th><th>" + esc(W.colClass) + '</th><th class="r">'
    + esc(W.sortLevel) + "</th><th>" + esc(W.sortZone) + "</th><th>Doing</th><th>Health</th></tr></thead><tbody>"
    + shown.map(r => '<tr data-bot="' + esc(r.bot.n) + '"'
      + (r.bot.n === FOCUS ? ' class="focused"' : (r.bot.o ? "" : ' class="offline"')) + ">"
      + "<td>" + factionDot(r.bot.f) + "<b>" + esc(r.bot.n) + "</b></td>"
      + '<td class="meta">' + esc(r.bot.c) + (r.bot.s ? " · " + esc(r.bot.s) : "") + "</td>"
      + '<td class="r">' + esc(r.level) + "</td>"
      + "<td>" + esc(r.zone) + "</td>"
      + '<td class="' + (r.live && r.live.combat ? "fighting" : "meta") + '">' + esc(r.task) + "</td>"
      + '<td class="hp-cell">' + health(r) + "</td></tr>").join("")
    + "</tbody></table>"
    + (rows.length > shown.length ? '<p class="empty">' + (rows.length - shown.length) + " more: narrow the filter.</p>" : "");
}

document.getElementById("roster").addEventListener("click", event => {
  const row = event.target.closest("tr[data-bot]");
  if (!row) return;
  setFocus(row.dataset.bot);
});
document.getElementById("rosterFilter").addEventListener("input", renderRoster);
const rosterOfflineBox = document.getElementById("rosterOffline");
rosterOfflineBox.checked = ROSTER_SHOW_OFFLINE;
rosterOfflineBox.addEventListener("change", () => {
  ROSTER_SHOW_OFFLINE = rosterOfflineBox.checked;
  try { localStorage.setItem("squidbots-roster-offline", ROSTER_SHOW_OFFLINE ? "1" : "0"); } catch (error) { /* private window etc. */ }
  renderRoster();
});
document.getElementById("rosterSort").addEventListener("click", event => {
  const button = event.target.closest("button[data-key]");
  if (!button) return;
  ROSTER_SORT = button.dataset.key;
  for (const other of document.querySelectorAll("#rosterSort button")) {
    other.setAttribute("aria-selected", String(other === button));
  }
  renderRoster();
});

/* private:start */
/* --------------------------------------------------------------- maps ---- */
// The Maps section of Settings, and the same controls above the map while it has no
// art. POST /api/art starts tools/gen_art.py on the server; GET /api/art reports progress.
let ART_STATE = null;
let artTimer = null;
let artWasRunning = false;

function artHosts() {
  return [document.getElementById("artPanel"), document.getElementById("artPrompt")];
}

// Built once per host, so a redraw never wipes a folder being typed.
function artSkeleton(host) {
  if (host.dataset.built) return;
  host.dataset.built = "1";
  host.innerHTML = '<p class="set-help" data-art-text></p>'
    + '<div class="art-row"><input data-art-client autocomplete="off" spellcheck="false" '
    + 'placeholder="C:\\Games\\World of Warcraft" aria-label="Game client folder">'
    + '<button class="btn primary" type="button" data-art-go>Extract maps</button></div>'
    + '<div class="art-progress" data-art-progress hidden><div class="bar"><i></i></div><span data-art-label></span></div>'
    + '<p class="meta" data-art-note></p>';
  let saved = "";
  try { saved = localStorage.getItem("squidbots-client") || ""; } catch (error) { /* ignore */ }
  host.querySelector("[data-art-client]").value = saved;
}

function renderArt() {
  if (PUBLIC || !ART_STATE) return;
  const state = ART_STATE;
  const job = state.job || {};
  const have = state.maps > 0;
  const prompt = document.getElementById("artPrompt");
  prompt.hidden = state.maps > 0 && !job.running;
  document.getElementById("artSub").textContent = have
    ? state.maps + " maps on this machine"
    : "not extracted yet";
  for (const host of artHosts()) {
    if (host.hidden) continue;
    artSkeleton(host);
    host.querySelector("[data-art-text]").textContent = host === prompt
      ? "This map has no background yet. The dashboard can take the continent and zone maps from your own "
        + "game client. It takes about two minutes and needs nothing installed."
      : "Takes the continent and zone maps from your own game client. About two minutes, nothing to install. "
        + "About 70 MB, copied to the public page too when one is set up. Run it again after a client patch.";
    const field = host.querySelector("[data-art-client]");
    if (!field.value && (job.client || state.suggestedClient)) field.value = job.client || state.suggestedClient;
    field.disabled = !!job.running;
    const button = host.querySelector("[data-art-go]");
    button.disabled = !!job.running;
    button.textContent = job.running ? "Extracting…" : have ? "Extract again" : "Extract maps";
    const progress = host.querySelector("[data-art-progress]");
    progress.hidden = !job.running;
    if (job.running) {
      const share = job.total ? Math.round((job.step / job.total) * 100) : 0;
      progress.querySelector("i").style.width = share + "%";
      host.querySelector("[data-art-label]").textContent = job.total
        ? job.label + " (" + job.step + " of " + job.total + ")" : job.label || "Starting";
    }
    const note = host.querySelector("[data-art-note]");
    note.className = job.error ? "meta bad-text" : "meta";
    note.textContent = job.error ? "Could not finish: " + job.error
      : job.finished && !job.running ? ((job.log || []).filter(l => l.startsWith("DONE")).pop() || "DONE").replace(/^DONE/, "Finished") + "."
      : "";
  }
}

async function loadArt() {
  if (PUBLIC) return;
  try { ART_STATE = await (await fetch("/api/art", { cache: "no-store" })).json(); } catch (error) { return; }
  const running = !!(ART_STATE.job && ART_STATE.job.running);
  if (artWasRunning && !running) {
    // A run just ended: show the new art without a reload.
    ART_STAMP = "-" + Date.now();
    if (LAST) renderMap(LAST);
  }
  artWasRunning = running;
  renderArt();
  clearTimeout(artTimer);
  if (running) artTimer = setTimeout(loadArt, 1500);
}

document.addEventListener("click", async event => {
  const button = event.target.closest("[data-art-go]");
  if (!button) return;
  const host = button.closest("#artPanel, #artPrompt");
  const client = host.querySelector("[data-art-client]").value.trim();
  try { localStorage.setItem("squidbots-client", client); } catch (error) { /* ignore */ }
  for (const other of artHosts()) {
    const field = other.querySelector("[data-art-client]");
    if (field) field.value = client;
  }
  let answer = null;
  try {
    answer = await (await fetch("/api/art", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ client }),
    })).json();
  } catch (error) {
    answer = { error: "the dashboard did not answer" };
  }
  if (answer && answer.error) {
    host.querySelector("[data-art-note]").className = "meta bad-text";
    host.querySelector("[data-art-note]").textContent = answer.error;
    return;
  }
  ART_STATE = answer;
  artWasRunning = true;
  renderArt();
  artTimer = setTimeout(loadArt, 1000);
});

/* ----------------------------------------------------------- settings ---- */

let CONFIG = null;

const WHEN = {
  restart: "after a restart",
  "new bots": "new bots only",
  reload: "after .reload config",
  live: "at once",
};

function settingControl(setting) {
  const id = "set_" + setting.key.replace(/[^A-Za-z0-9]/g, "_");
  const value = setting.value === null ? "" : setting.value;
  if (setting.kind === "bool") {
    return '<select id="' + id + '" data-key="' + esc(setting.key) + '">'
      + '<option value="1"' + (value === "1" ? " selected" : "") + ">On</option>"
      + '<option value="0"' + (value === "0" ? " selected" : "") + ">Off</option></select>";
  }
  if (setting.kind === "choice") {
    return '<select id="' + id + '" data-key="' + esc(setting.key) + '">'
      + (setting.choices || []).map(c =>
        '<option value="' + esc(c) + '"' + (value === c ? " selected" : "") + ">"
        + esc(c === "0" ? "0 (per-level curve)" : "x" + c) + "</option>").join("")
      + "</select>";
  }
  return '<input id="' + id + '" data-key="' + esc(setting.key) + '" value="' + esc(value) + '">';
}

// The values on screen: saved ones, overlaid with anything edited but not applied.
function shownValues() {
  const values = {};
  for (const s of (CONFIG && CONFIG.settings) || []) values[s.key] = s.value;
  for (const field of document.querySelectorAll("#settings [data-key]")) values[field.dataset.key] = field.value.trim();
  return values;
}

// Same rule table the server uses (botconfig.OVERRIDES), evaluated as fields change.
function overrideWarnings(values) {
  const out = {};
  for (const rule of (CONFIG && CONFIG.overrides) || []) {
    if (Object.entries(rule.if).every(([key, value]) => values[key] === value)) {
      for (const key of rule.warn) (out[key] = out[key] || []).push(rule.text);
    }
  }
  return out;
}

function showWarnings() {
  const warnings = overrideWarnings(shownValues());
  for (const row of document.querySelectorAll("#settings .settings-row")) {
    const box = row.querySelector(".set-warn");
    const texts = warnings[row.dataset.row] || [];
    box.hidden = !texts.length;
    box.innerHTML = texts.map(esc).join("<br>");
  }
}

function recipeDiff(recipe) {
  const current = {};
  for (const s of CONFIG.settings) current[s.key] = s;
  return Object.entries(recipe.changes)
    .filter(([key, value]) => current[key] && current[key].value !== value)
    .map(([key, value]) => ({ key, label: current[key].label, from: current[key].value, to: value }));
}

function renderRecipes() {
  const holder = document.getElementById("recipes");
  const recipes = (CONFIG && CONFIG.recipes) || [];
  if (!recipes.length) { holder.innerHTML = ""; return; }
  holder.innerHTML = '<div class="settings-group"><h3>Quick setups</h3><div class="recipes">'
    + recipes.map(recipe => {
      const diff = recipeDiff(recipe);
      return '<div class="recipe" data-recipe="' + esc(recipe.id) + '">'
        + '<div class="recipe-title">' + esc(recipe.title) + "</div>"
        + '<p class="set-help">' + esc(recipe.summary) + "</p>"
        + (diff.length
          ? '<table class="diff"><tbody>' + diff.map(row =>
              "<tr><td>" + esc(row.label) + '</td><td class="r meta">' + esc(row.from) + "</td>"
              + '<td class="arrow">&#8594;</td><td class="to">' + esc(row.to) + "</td></tr>").join("")
            + "</tbody></table>"
            + '<div class="recipe-foot"><button class="btn small" type="button" data-apply-recipe="'
            + esc(recipe.id) + '">Apply ' + diff.length + " change" + (diff.length === 1 ? "" : "s") + "</button></div>"
          : '<p class="recipe-done">Already set up this way.</p>')
        + '<p class="meta">' + esc(recipe.after) + "</p>"
        + "</div>";
    }).join("")
    + "</div></div>";
}

function renderSettings(config) {
  CONFIG = config;
  const holder = document.getElementById("settings");
  const notes = document.getElementById("settingsNotes");
  const sub = document.getElementById("settingsSub");

  if (!config || config.error) {
    holder.innerHTML = '<div class="map-empty">Settings are unavailable: '
      + esc((config && config.error) || "no response") + "</div>";
    return;
  }

  sub.textContent = config.serverRunning
    ? "server running: most changes wait for a restart"
    : "server stopped: changes apply when it starts";

  notes.innerHTML = (config.notes || []).map(n => esc(n)).join("<br>");

  // Only settings found in their file get a row. A group with none (a module that is not
  // installed) is left out entirely; keys missing from a file that exists fit on one line.
  const groups = [];
  for (const setting of config.settings) {
    let group = groups.find(g => g.name === setting.group);
    if (!group) { group = { name: setting.group, rows: [], missing: [] }; groups.push(group); }
    (setting.present ? group.rows : group.missing).push(setting);
  }

  holder.innerHTML = groups.filter(group => group.rows.length).map(group =>
    '<div class="settings-group"><h3>' + esc(group.name) + "</h3>"
    + group.rows.map(s =>
      '<div class="settings-row" data-row="' + esc(s.key) + '">'
      + '<div class="set-text">'
      + '<label for="set_' + esc(s.key.replace(/[^A-Za-z0-9]/g, "_")) + '">' + esc(s.label) + "</label>"
      + '<p class="set-help">' + esc(s.help) + "</p>"
      + '<p class="set-warn" hidden></p>'
      + '<span class="key">' + esc(s.key) + "</span>"
      + "</div>"
      + '<div class="set-control">'
      + settingControl(s)
      + '<span class="when">' + esc(WHEN[s.when] || "") + "</span>"
      + "</div></div>").join("")
    + (group.missing.length
      ? '<p class="set-missing">Not in ' + esc(group.missing[0].file) + ", so not shown: "
        + group.missing.map(s => esc(s.key)).join(", ") + "</p>"
      : "")
    + "</div>").join("");

  renderRecipes();
  showWarnings();
  document.getElementById("settingsApply").disabled = true;
  document.getElementById("settingsApply").textContent = W.applyChanges;
  document.getElementById("settingsStatus").textContent = "";
}

function changedSettings() {
  const changes = {};
  if (!CONFIG) return changes;
  const current = {};
  for (const s of CONFIG.settings) current[s.key] = s.value;
  for (const field of document.querySelectorAll("#settings [data-key]")) {
    const key = field.dataset.key;
    const value = field.value.trim();
    if (current[key] !== null && value !== current[key]) changes[key] = value;
  }
  return changes;
}

function markChanges() {
  const changes = changedSettings();
  for (const row of document.querySelectorAll("#settings .settings-row")) {
    row.classList.toggle("changed", Object.prototype.hasOwnProperty.call(changes, row.dataset.row));
  }
  const count = Object.keys(changes).length;
  document.getElementById("settingsApply").disabled = count === 0;
  document.getElementById("settingsApply").textContent =
    count ? "Apply " + count + " change" + (count === 1 ? "" : "s") : W.applyChanges;
  showWarnings();
  return changes;
}

document.getElementById("settings").addEventListener("input", markChanges);
document.getElementById("settings").addEventListener("change", markChanges);

async function loadConfig() {
  if (PUBLIC) return;
  try {
    const answer = await fetch("/api/config", { cache: "no-store" });
    renderSettings(await answer.json());
  } catch (error) {
    renderSettings({ error: String(error) });
  }
}

document.getElementById("settingsReload").addEventListener("click", loadConfig);

// Every write is confirmed and lists exactly what changes: this edits the
// server's own configuration files (each one is backed up first).
async function writeSettings(changes) {
  const keys = Object.keys(changes);
  if (!keys.length) return;
  const labels = {};
  for (const s of CONFIG.settings) labels[s.key] = s;
  const lines = keys.map(k => "  " + (labels[k] ? labels[k].label : k) + ": "
    + (labels[k] ? labels[k].value : "?") + " -> " + changes[k]).join("\n");
  if (!window.confirm("Write these to the server configuration?\n\n" + lines
      + "\n\nThe current files are backed up first.")) return;

  const status = document.getElementById("settingsStatus");
  const button = document.getElementById("settingsApply");
  button.disabled = true;
  status.textContent = "Writing...";
  try {
    const answer = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    });
    const result = await answer.json();
    if (!answer.ok) {
      status.textContent = "Rejected: "
        + Object.entries(result.errors || { error: result.error })
            .map(([k, v]) => k + " (" + v + ")").join(", ");
      button.disabled = false;
      return;
    }
    await loadConfig();
    status.textContent = result.note
      + (result.backups && result.backups.length ? " Backed up " + result.backups.length + " file(s)." : "");
  } catch (error) {
    status.textContent = "Failed: " + error;
    button.disabled = false;
  }
}

document.getElementById("settingsApply").addEventListener("click", () => writeSettings(changedSettings()));

document.getElementById("recipes").addEventListener("click", event => {
  const button = event.target.closest("[data-apply-recipe]");
  if (!button || !CONFIG) return;
  const recipe = CONFIG.recipes.find(r => r.id === button.dataset.applyRecipe);
  const changes = {};
  for (const row of recipeDiff(recipe)) changes[row.key] = row.to;
  writeSettings(changes);
});

/* private:end */

/* ------------------------------------------------------------- refresh ---- */

function renderOffline(data) {
  const banner = document.getElementById("offlineBanner");
  banner.hidden = false;
  banner.innerHTML = "<strong>The game server is not reachable.</strong> Live figures are unavailable"
    + (PUBLIC ? "." : ", but bot settings can still be changed: the configuration files are "
      + "read when the server starts, so edits made now apply at the next start.");
  document.getElementById("stateText").textContent = W.stopped;
  document.getElementById("stateDot").className = "dot off";
  document.getElementById("updatedPill").textContent = W.updated("-");
  LAST = data;
  renderMap(data);
}

async function refresh() {
  await loadWorld();
  await refreshLive();
  try {
    const answer = await fetch(API + (PUBLIC ? "?t=" + Date.now() : ""), { cache: "no-store" });
    const data = await answer.json();
    if (data && data.error) { renderOffline(data); return; }
    document.getElementById("offlineBanner").hidden = true;
    render(data);
    renderMap(data);
  } catch (error) {
    renderOffline({});
  }
}
applyWords();
showPage();
/* private:start */loadConfig();
loadArt();/* private:end */
refresh();
setInterval(refresh, 20000);
setInterval(refreshLiveMap, LIVE_EVERY);
window.addEventListener("hashchange", refreshLiveMap);
document.addEventListener("visibilitychange", refreshLiveMap);
// The chat feed follows the log only while its page is open.
/* private:start */setInterval(() => { if (PAGE === "chat" && !document.hidden) loadFeed(); }, 5000);/* private:end */
