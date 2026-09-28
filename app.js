const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

const PAGES = ["dashboard", "bots", "map", "configs", "sidekick", "exilesdb", "ascensiondb","accounts", "additem", "bans", "tickets", "realmlist", "settings"];
const SERVICE_ICONS = { mysql: "🐬", auth: "🔐", world: "🌍", world2: "🧪" };

// Auth/World icons come straight from authserver.exe/worldserver.exe (via
// /api/icon); MySQL uses the cropped dolphin from mysql_logo.png (.svc-mysql in index.html).
function svcIcon(key) {
  if (key === "mysql") return `<span class="svc-mysql"></span>`;
  return `<img class="svc-icon" src="/api/icon?service=${key}" alt="" onerror="this.style.display='none';this.nextElementSibling.style.display='inline'"><span class="svc-icon-fallback" style="display:none">${SERVICE_ICONS[key]}</span>`;
}

function fmtBytes(b) {
  if (b == null) return "-";
  const gb = b / 1073741824;
  if (gb >= 1) return gb.toFixed(1) + " GB";
  return Math.round(b / 1048576) + " MB";
}

function healthRow(label, percent, valueText) {
  const dim = percent == null;
  const pct = dim ? 0 : Math.min(100, Math.max(0, percent));
  return `
    <div class="health-row ${dim ? "dim" : ""}">
      <span class="h-label">${label}</span>
      <span class="h-bar"><span style="width:${pct}%"></span></span>
      <span class="h-value">${valueText}</span>
    </div>`;
}

function healthPanel(svc) {
  if (!svc.running) return "";
  const cpuText = svc.cpu_percent == null ? "…" : svc.cpu_percent.toFixed(1) + "%";
  const ramPct = svc.ram_total_bytes ? (svc.ram_bytes / svc.ram_total_bytes) * 100 : null;
  const ramText = `${fmtBytes(svc.ram_bytes)} / ${fmtBytes(svc.ram_total_bytes)}`;
  return `
    <div class="health">
      ${healthRow("CPU", svc.cpu_percent, cpuText)}
      ${healthRow("RAM", ramPct, ramText)}
    </div>`;
}

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 2200);
}

// ---------- collapsible sidebar (remembered in the browser) ----------
function setSidebarHidden(hidden) {
  document.body.classList.toggle("sb-hidden", hidden);
  try { localStorage.setItem("sbHidden", hidden ? "1" : "0"); } catch (e) { /* not critical */ }
}
$("#sb-hide").addEventListener("click", () => setSidebarHidden(true));
$("#sb-show").addEventListener("click", () => setSidebarHidden(false));
try { if (localStorage.getItem("sbHidden") === "1") document.body.classList.add("sb-hidden"); } catch (e) { /* default: visible */ }

// ---------- navigation ----------
$$("#sidebar nav button[data-page]").forEach((btn) => {
  btn.addEventListener("click", () => {
    $$("#sidebar nav button[data-page]").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const page = btn.dataset.page;
    PAGES.forEach((p) => {
      $("#page-" + p).style.display = p === page ? "" : "none";
    });
    if (page === "bots") openBots();
    if (page === "map") loadMap();
    if (page === "configs") loadConfigList();
    if (page === "settings") loadSettings();
    if (page === "dashboard") { refreshConsole(); requestAnimationFrame(fitConsole); }
    if (page === "accounts") loadAccounts();
    if (page === "additem") { loadKits(); loadItems(); loadItemCharacters(); }
    if (page === "bans") loadBans();
    if (page === "tickets") loadTickets();
    if (page === "realmlist") loadRealms();
    if (page === "sidekick") { const f = $("#sidekick-frame"); if (!f.getAttribute("src")) f.src = "/sidekick/?t=" + Date.now(); }
    if (page === "exilesdb") openExilesDb();
    if (page === "ascensiondb") {
      const f = $("#ascensiondb-frame");
      if (!f.getAttribute("src")) f.src = "/ascensiondb/#t=" + Date.now();
    }
  });
});

// ---------- optional modules (only shown when the server reports them as installed) ----------
// Bots page: the vendored SquidBots dashboard (modules/squidbots), own port, own iframe --
// same start-on-first-open pattern as ExilesDB below.
async function openBots() {
  const msg = $("#bots-msg"), frame = $("#bots-frame");
  const show = (html) => { frame.style.display = "none"; msg.style.display = ""; msg.innerHTML = html; };
  const loaded = !!frame.getAttribute("src");
  if (loaded) { frame.style.display = "block"; msg.style.display = "none"; }
  else show("<h1>Bots</h1><div class='page-sub'>Starting the bots dashboard…</div>");
  try {
    const res = await fetch("/api/modules/squidbots/start", { method: "POST" });
    const st = await res.json();
    if (st.error) return show("<h1>Bots</h1><div class='page-sub'>Error: " + esc(st.error) + "</div>");
    if (loaded) return;
    for (let i = 0; i < 40 && !(await (await fetch("/api/modules")).json()).squidbots?.running; i++)
      await new Promise((r) => setTimeout(r, 500));
    frame.src = "http://127.0.0.1:" + st.port + "/";
    frame.style.display = "block"; msg.style.display = "none";
  } catch (e) {
    show("<h1>Bots</h1><div class='page-sub'>Could not start: " + esc(String(e)) + "</div>");
  }
}

async function openExilesDb() {
  const msg = $("#exilesdb-msg"), frame = $("#exilesdb-frame");
  const show = (html) => { frame.style.display = "none"; msg.style.display = ""; msg.innerHTML = html; };
  // Always re-check: the data folder may have been changed or removed since the iframe was loaded.
  const loaded = !!frame.getAttribute("src");
  if (loaded) { frame.style.display = "block"; msg.style.display = "none"; }
  else show("<h1>Database</h1><div class='page-sub'>Starting the offline archive…</div>");
  try {
    const res = await fetch("/api/modules/exilesdb/start", { method: "POST" });
    const st = await res.json();
    if (st.error) return show("<h1>Database</h1><div class='page-sub'>Error: " + esc(st.error) + "</div>");
    if (st.problem) frame.removeAttribute("src");
    if (loaded && !st.problem) return;
    if (st.problem) return show(
      "<h1>Database</h1><div class='page-sub'>Offline copy of the Ascension database (items, spells, quests, NPCs).</div>" +
      "<div style='max-width:640px;line-height:1.6'>" +
      "<p>The database is not set up yet. To use it:</p>" +
      "<ol style='padding-left:20px'>" +
      "<li>Download it from <a href='https://github.com/Duff-SPP/AcensionOfflineDatabase/releases' target='_blank' rel='noopener'>github.com/Duff-SPP/AcensionOfflineDatabase/releases</a> and unpack it somewhere.</li>" +
      "<li>Go to <b>Settings</b> and set <b>ExilesDB data folder</b> to the folder that contains <code>data</code> and <code>mirror</code>.</li>" +
      "<li>Save, then open this tab again.</li></ol>" +
      "<p style='opacity:.75'><b>Why isn't it included in the dashboard?</b> It is a copy of roughly 500,000 web pages and takes about 13 GB. " +
      "Most people don't need that, so it is an optional download instead of making everyone's dashboard that big.</p>" +
      "<p style='opacity:.6;font-size:12px'>" + esc(st.problem) + "</p></div>");
    for (let i = 0; i < 40 && !(await (await fetch("/api/modules")).json()).exilesdb.running; i++)
      await new Promise((r) => setTimeout(r, 500));
    frame.src = "http://127.0.0.1:" + st.port + "/";
    frame.style.display = "block"; msg.style.display = "none";
  } catch (e) {
    show("<h1>Database</h1><div class='page-sub'>Could not start: " + esc(String(e)) + "</div>");
  }
}

async function loadModules() {
  try {
    const mods = await (await fetch("/api/modules")).json();
    const on = !!mods.exilesdb;
    $("#nav-exilesdb").style.display = on ? "" : "none";
    $("#set-exilesdb-group").style.display = on ? "" : "none";
  } catch (e) { /* modules are optional; ignore */ }
}
loadModules();

// ---------- dashboard: console height fills the window so the input bar is always visible ----------
const DASH_ZOOM = 0.88; // keep in sync with the #page-dashboard zoom in index.html
function fitConsole() {
  const box = $("#console-box"), page = $("#page-dashboard");
  if (!box || !page || page.style.display === "none") return;
  const rowH = $("#console-input-row").getBoundingClientRect().height;
  const hintH = $("#console-hint").getBoundingClientRect().height + 8 * DASH_ZOOM;
  const avail = window.innerHeight - box.getBoundingClientRect().top - rowH - hintH - 24;
  box.style.height = Math.max(140, Math.min(600, avail / DASH_ZOOM)) + "px";
}
window.addEventListener("resize", fitConsole);
new ResizeObserver(fitConsole).observe($("#main"));
new ResizeObserver(fitConsole).observe($("#status-cards"));
requestAnimationFrame(fitConsole);

// ---------- dashboard: status cards ----------
async function refreshStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    const wrap = $("#status-cards");
    const keys = ["mysql", "auth", "world", "world2"].filter((k) => data[k]);
    const up = keys.filter((k) => data[k].running).length;
    $("#hdr-services").textContent = `${up} of ${keys.length} services running`;
    $("#hdr-dot").className = up === keys.length ? "" : "off";
    const world2Tab = $("#console-tab-world2");
    if (world2Tab) world2Tab.style.display = data.world2 ? "" : "none";
    wrap.innerHTML = "";
    for (const key of keys) {
      const svc = data[key];
      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML = `
        <div class="top">
          <span class="label">${svcIcon(key)}&nbsp; ${key === "mysql" && svc.label === "MySQL" ? '<span class="my-my">My</span><span class="my-sql">SQL</span>' : svc.label}</span>
        </div>
        <div class="status-text">
          <span class="dot ${svc.running ? "on" : "off"}"></span>${svc.running ? "Running" : "Stopped"}
        </div>
        <div class="actions">
          <button class="btn btn-primary" data-action="start" data-service="${key}" ${svc.running ? "disabled" : ""}>Start</button>
          <button class="btn btn-outline" data-action="restart" data-service="${key}" ${svc.running ? "" : "disabled"}>↻&nbsp; Restart</button>
          <button class="btn btn-danger" data-action="stop" data-service="${key}" ${svc.running ? "" : "disabled"}>Stop</button>
        </div>
        ${key === "world" || key === "world2" ? `
        <div class="actions" style="margin-top:8px">
          <button class="btn btn-outline" data-action="saveall" data-service="${key}" ${svc.running ? "" : "disabled"} style="width:100%">💾&nbsp; Save all</button>
        </div>` : ""}
        ${healthPanel(svc)}
      `;
      wrap.appendChild(card);
    }
    wrap.querySelectorAll("button[data-action]").forEach((b) => {
      b.addEventListener("click", async () => {
        const action = b.dataset.action;
        const service = b.dataset.service;
        b.disabled = true;
        try {
          let res;
          if (action === "saveall") {
            res = await fetch(`/api/input?service=${service}`, {
              method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ input: ".saveall" }),
            });
          } else {
            if (action === "restart") toast(`Restarting ${service}...`);
            res = await fetch(`/api/${action}?service=${service}`, { method: "POST" });
          }
          const data = await res.json();
          if (data.error) {
            toast("Error: " + data.error);
          } else if (action === "saveall") {
            toast(`Sent .saveall to ${service === "world2" ? "Worldserver (Realm 2)" : "Worldserver"}`);
            if (activeConsoleService === service) refreshConsole();
          } else {
            const verb = { start: "started", stop: "stopped", restart: "restarted" }[action];
            toast(`${service}: ${verb}`);
            setTimeout(refreshStatus, 1500);
          }
        } catch (e) {
          toast("Request failed");
        }
      });
    });
  } catch (e) {
    console.error(e);
  }
}

$("#btn-refresh").addEventListener("click", refreshStatus);

$("#btn-start-all").addEventListener("click", async () => {
  toast("Starting MySQL...");
  await fetch("/api/start?service=mysql", { method: "POST" });
  setTimeout(async () => {
    toast("Starting Authserver...");
    await fetch("/api/start?service=auth", { method: "POST" });
    setTimeout(async () => {
      toast("Starting Worldserver...");
      await fetch("/api/start?service=world", { method: "POST" });
      setTimeout(refreshStatus, 1500);
    }, 2000);
  }, 8000);
});

$("#btn-open-client").addEventListener("click", async () => {
  await fetch("/api/launch-client", { method: "POST" });
  toast("Client launched");
});

// ---------- consoles ----------
let activeConsoleService = "world";
$$("#console-tabs .tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    $$("#console-tabs .tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    activeConsoleService = tab.dataset.service;
    refreshConsole();
  });
});

async function refreshConsole() {
  const box = $("#console-box");
  const input = $("#console-input");
  const hint = $("#console-hint");
  try {
    const res = await fetch(`/api/log?service=${activeConsoleService}`);
    const data = await res.json();
    const wasAtBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 40;
    box.textContent = data.log;
    if (wasAtBottom) box.scrollTop = box.scrollHeight;

    input.disabled = !data.writable;
    if (activeConsoleService === "mysql") {
      input.placeholder = "Run a SQL query...";
      hint.textContent = "Runs directly against the database via the mysql client (uses the login from Settings).";
    } else if ((activeConsoleService === "world" || activeConsoleService === "world2") && data.writable) {
      input.placeholder = "Type a GM command (e.g. .additem 123)...";
      hint.textContent = "";
    } else if (activeConsoleService === "auth") {
      input.placeholder = "Authserver's console is read-only";
      hint.textContent = "Authserver doesn't accept typed commands in this build -- use Worldserver's console or the Accounts page instead.";
    } else {
      input.placeholder = "Console isn't writable";
      hint.textContent = "Start Worldserver from the Dashboard to be able to type commands here.";
    }
  } catch (e) {
    box.textContent = "(could not load log)";
  }
}

async function sendConsoleInput() {
  const input = $("#console-input");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  try {
    const res = await fetch(`/api/input?service=${activeConsoleService}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input: text }),
    });
    const data = await res.json();
    if (data.error) toast("Error: " + data.error);
    refreshConsole();
  } catch (e) {
    toast("Could not send command");
  }
}

$("#btn-console-send").addEventListener("click", sendConsoleInput);
$("#console-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendConsoleInput();
});

setInterval(() => {
  if ($("#page-dashboard").style.display !== "none") refreshConsole();
}, 3000);

// ---------- configs: file list + built-in code editor ----------
// A transparent <textarea> sits on top of a syntax-highlighted layer; both use the same font and line height and
// are kept in sync on scroll. No external libraries.
let activeConfigKey = null;
let cfgFiles = [];
let cfgOriginal = "";     // content as last loaded / saved (LF-normalised)
let cfgEol = "\n";        // line ending of the file on disk, restored when saving
let cfgMatches = [];      // [{line, col, len}]
let cfgCur = -1;
let cfgCurLine = 0;
const CFG_LH = 19;
const cfgEditor = $("#config-editor");

function cfgTokens(line) {
  const t = line.trim();
  if (!t) return [];
  if (t[0] === "#") return [{ s: 0, e: line.length, c: "cm" }];
  if (/^\[.*\]$/.test(t)) return [{ s: 0, e: line.length, c: "cs" }];
  const m = /^(\s*)([^=\s#][^=]*?)(\s*)=(\s*)(.*)$/.exec(line);
  if (!m) return [];
  const keyS = m[1].length, keyE = keyS + m[2].length, eq = keyE + m[3].length, vs = eq + 1 + m[4].length;
  const out = [{ s: keyS, e: keyE, c: "ck" }, { s: eq, e: eq + 1, c: "cp" }];
  const re = /"(?:[^"\\]|\\.)*"?|-?\b\d+(?:\.\d+)?\b|\b(?:true|false|yes|no|on|off)\b/gi;
  let r;
  while ((r = re.exec(m[5]))) {
    const c = r[0][0] === '"' ? "cstr" : /^[-\d]/.test(r[0]) ? "cnum" : "cbool";
    out.push({ s: vs + r.index, e: vs + r.index + r[0].length, c });
  }
  return out;
}

function cfgLineHtml(line, marks) {
  const toks = cfgTokens(line);
  const cuts = new Set([0, line.length]);
  toks.forEach((t) => { cuts.add(t.s); cuts.add(t.e); });
  (marks || []).forEach((mk) => { cuts.add(mk.col); cuts.add(mk.col + mk.len); });
  const pts = [...cuts].filter((x) => x >= 0 && x <= line.length).sort((x, y) => x - y);
  let html = "";
  for (let i = 0; i < pts.length - 1; i++) {
    const a = pts[i], b = pts[i + 1];
    const tk = toks.find((t) => t.s <= a && t.e >= b);
    const mk = marks && marks.find((m) => m.col <= a && m.col + m.len >= b);
    const cls = [tk ? tk.c : "", mk ? (mk.cur ? "mk cur" : "mk") : ""].join(" ").trim();
    const txt = esc(line.slice(a, b));
    html += cls ? `<span class="${cls}">${txt}</span>` : txt;
  }
  return html || "&#8203;";
}

let cfgRaf = 0;
function cfgRenderSoon() { cancelAnimationFrame(cfgRaf); cfgRaf = requestAnimationFrame(cfgRender); }

function cfgRender() {
  const lines = cfgEditor.value.split("\n");
  const byLine = {};
  cfgMatches.forEach((m, i) => { (byLine[m.line] = byLine[m.line] || []).push({ col: m.col, len: m.len, cur: i === cfgCur }); });
  $("#cfg-hl-inner").innerHTML = lines.map((l, i) => `<div class="cl${i === cfgCurLine ? " on" : ""}">${cfgLineHtml(l, byLine[i])}</div>`).join("");
  $("#cfg-gutter-inner").textContent = lines.map((_, i) => i + 1).join("\n");
  cfgSyncScroll();
  cfgUpdateInfo(lines.length);
}

function cfgSyncScroll() {
  $("#cfg-hl-inner").style.transform = `translate(${-cfgEditor.scrollLeft}px, ${-cfgEditor.scrollTop}px)`;
  $("#cfg-gutter-inner").style.transform = `translateY(${-cfgEditor.scrollTop}px)`;
}

function cfgUpdateInfo(lineCount) {
  const n = lineCount || cfgEditor.value.split("\n").length;
  const kb = (new Blob([cfgEditor.value]).size / 1024).toFixed(1);
  $("#cfg-info").textContent = activeConfigKey ? `${n} lines · ${kb} KB · ${cfgEol === "\r\n" ? "CRLF" : "LF"} · UTF-8` : "";
}

function cfgUpdatePos() {
  const pos = cfgEditor.selectionStart, text = cfgEditor.value;
  const line = text.slice(0, pos).split("\n").length - 1;
  const col = pos - (text.lastIndexOf("\n", pos - 1) + 1);
  $("#cfg-pos").textContent = `Ln ${line + 1}, Col ${col + 1}`;
  if (line !== cfgCurLine) {
    const rows = $("#cfg-hl-inner").children;
    if (rows[cfgCurLine]) rows[cfgCurLine].classList.remove("on");
    if (rows[line]) rows[line].classList.add("on");
    cfgCurLine = line;
  }
}

function cfgDirty() { return !!activeConfigKey && cfgEditor.value !== cfgOriginal; }

function cfgUpdateDirty() {
  const d = cfgDirty();
  $("#cfg-dirty").hidden = !d;
  $("#btn-save-config").disabled = !d;
}

function cfgFind(fromCaret, reveal) {
  const term = $("#cfg-find-input").value.toLowerCase();
  cfgMatches = [];
  cfgCur = -1;
  if (term) {
    const lines = cfgEditor.value.toLowerCase().split("\n");
    outer: for (let i = 0; i < lines.length; i++) {
      let at = lines[i].indexOf(term);
      while (at !== -1) {
        cfgMatches.push({ line: i, col: at, len: term.length });
        if (cfgMatches.length >= 5000) break outer;
        at = lines[i].indexOf(term, at + term.length);
      }
    }
    if (cfgMatches.length) {
      const caretLine = cfgCurLine;
      const first = cfgMatches.findIndex((m) => m.line >= caretLine);
      cfgCur = fromCaret && first >= 0 ? first : 0;
    }
  }
  $("#cfg-find-count").textContent = term ? (cfgMatches.length ? `${cfgCur + 1}/${cfgMatches.length}${cfgMatches.length >= 5000 ? "+" : ""}` : "0") : "";
  $("#cfg-prev").disabled = $("#cfg-next").disabled = cfgMatches.length < 2;
  cfgRender();
  if (reveal && cfgCur >= 0) cfgReveal(cfgMatches[cfgCur]);
}

// Offset of a line/column in the textarea's value.
function cfgOffset(line, col) {
  let off = 0;
  for (let i = 0; i < line; i++) off = cfgEditor.value.indexOf("\n", off) + 1;
  return off + col;
}

function cfgReveal(m) {
  const charW = cfgCharWidth();
  const top = m.line * CFG_LH;
  if (top < cfgEditor.scrollTop || top > cfgEditor.scrollTop + cfgEditor.clientHeight - 2 * CFG_LH)
    cfgEditor.scrollTop = Math.max(0, top - cfgEditor.clientHeight / 2);
  const x = m.col * charW;
  if (x < cfgEditor.scrollLeft || x + m.len * charW > cfgEditor.scrollLeft + cfgEditor.clientWidth - 40)
    cfgEditor.scrollLeft = Math.max(0, x - 80);
  cfgSyncScroll();
  // Put the (unfocused) caret on the match, so focusing the editor afterwards lands there instead of jumping.
  const at = cfgOffset(m.line, m.col);
  cfgEditor.setSelectionRange(at, at + m.len);
}

let cfgCharW = 0;
function cfgCharWidth() {
  if (cfgCharW) return cfgCharW;
  const probe = document.createElement("span");
  probe.style.cssText = 'position:absolute;visibility:hidden;white-space:pre;font:12.5px "Cascadia Code", Consolas, monospace';
  probe.textContent = "M".repeat(40);
  document.body.appendChild(probe);
  cfgCharW = probe.getBoundingClientRect().width / 40 || 7.5;
  probe.remove();
  return cfgCharW;
}

function cfgStep(dir) {
  if (!cfgMatches.length) return;
  cfgCur = (cfgCur + dir + cfgMatches.length) % cfgMatches.length;
  $("#cfg-find-count").textContent = `${cfgCur + 1}/${cfgMatches.length}`;
  cfgRender();
  cfgReveal(cfgMatches[cfgCur]);
}

// The file list is one compact column. It is shown at 93% and scales down a little more when the files do not fit the
// height (never below 70%, then the list scrolls). The card is as wide as its longest file name (CSS).
const CFG_BASE = 0.93, CFG_MINZ = 0.7;
const CFG_CORE = {
  world: { icon: '<img src="/api/icon?service=world" alt="">', sub: "Game server" },
  auth: { icon: '<img src="/api/icon?service=auth" alt="">', sub: "Login server" },
  mysql: { icon: '<span class="svc-mysql"></span>', sub: "Database" },
};

function cfgLayoutList() {
  const card = document.querySelector(".cfg-card"), list = $("#config-list");
  if (!card || !list.offsetParent) return;
  let z = CFG_BASE;
  card.style.setProperty("--cfg-zoom", z);
  const need = Math.max(0, ...[...list.querySelectorAll(".cfg-col")].map((c) => c.offsetHeight)), avail = list.clientHeight;
  if (need > avail) card.style.setProperty("--cfg-zoom", Math.max(CFG_MINZ, Math.floor(CFG_BASE * avail / need * 100) / 100));
}

function cfgRenderList() {
  const q = $("#cfg-filter").value.trim().toLowerCase();
  const shown = cfgFiles.filter((c) => !q || c.label.toLowerCase().includes(q));
  const row = (c) => {
    const core = CFG_CORE[c.key];
    const plain = c.label.replace(/\.conf$/i, "");
    // MySQL gets the logo colours ("My" blue-grey, "SQL" orange), like on the Dashboard page.
    const name = c.key === "mysql" && plain.startsWith("MySQL")
      ? `<span class="my-my">My</span><span class="my-sql">SQL</span>${esc(plain.slice(5))}` : esc(plain);
    return `<button class="cfg-item${c.key === activeConfigKey ? " active" : ""}" data-key="${esc(c.key)}" title="${esc(c.label)} - ${core ? core.sub : "Module"}${c.exists ? "" : " (file not found)"}">
      <span class="cfg-ico">${core ? core.icon : "&#129513;"}</span>
      <span class="cfg-txt"><div class="cfg-name">${name}</div></span>
      <span class="cfg-dot ${c.exists ? "ok" : "missing"}"></span></button>`;
  };
  // Core first, then modules, each group under its own heading.
  const ordered = [...shown.filter((c) => CFG_CORE[c.key]), ...shown.filter((c) => !CFG_CORE[c.key])];
  let group = null, col = "";
  ordered.forEach((c) => {
    const g = CFG_CORE[c.key] ? "Core" : "Modules";
    if (g !== group) { col += `<div class="cfg-group">${g}</div>`; group = g; }
    col += row(c);
  });
  const html = col ? `<div class="cfg-col">${col}</div>` : "";
  $("#cfg-count").textContent = q ? `${shown.length} of ${cfgFiles.length}` : `${cfgFiles.length}`;
  $("#config-list").innerHTML = html || `<div class="cfg-group">No files match</div>`;
  cfgLayoutList();
  $$("#config-list .cfg-item").forEach((b) => b.addEventListener("click", () => loadConfig(b.dataset.key)));
}

async function loadConfigList() {
  try {
    cfgFiles = await (await fetch("/api/configs")).json();
  } catch (e) { toast("Could not load the config list"); return; }
  cfgRenderList();
}

function cfgSetLoaded(on) {
  cfgEditor.disabled = !on;
  $("#cfg-find-input").disabled = !on;
  $("#btn-reload-config").disabled = !on;
  $("#cfg-code").classList.toggle("empty", !on);
}

async function loadConfig(key, force) {
  if (!force && cfgDirty() && key !== undefined && !confirm("Discard your unsaved changes?")) return;
  activeConfigKey = key;
  cfgRenderList();
  const res = await fetch(`/api/config?name=${encodeURIComponent(key)}`);
  const data = await res.json();
  if (data.error) {
    $("#config-path").textContent = "Error: " + data.error;
    cfgEditor.value = ""; cfgOriginal = "";
    activeConfigKey = null;
    cfgSetLoaded(false); cfgRender(); cfgUpdateDirty();
    return;
  }
  cfgEol = data.content.includes("\r\n") ? "\r\n" : "\n";
  cfgOriginal = data.content.replace(/\r\n/g, "\n");
  cfgEditor.value = cfgOriginal;
  cfgEditor.scrollTop = cfgEditor.scrollLeft = 0;
  cfgEditor.setSelectionRange(0, 0);
  $("#config-path").textContent = data.path;
  cfgCurLine = 0;
  cfgSetLoaded(true);
  cfgFind(false, false);
  cfgUpdateDirty();
  cfgUpdatePos();
}

async function saveConfig() {
  if (!activeConfigKey || !cfgDirty()) return;
  const text = cfgEditor.value;
  const content = cfgEol === "\r\n" ? text.replace(/\n/g, "\r\n") : text;
  try {
    const res = await fetch(`/api/config?name=${encodeURIComponent(activeConfigKey)}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content }),
    });
    const data = await res.json();
    if (data.ok) { cfgOriginal = text; cfgUpdateDirty(); toast("Saved"); } else toast("Error: " + data.error);
  } catch (e) { toast("Saving failed"); }
}

cfgEditor.addEventListener("input", () => { cfgUpdateDirty(); cfgFind(true, false); cfgUpdatePos(); });
cfgEditor.addEventListener("scroll", cfgSyncScroll);
cfgEditor.addEventListener("keydown", (e) => {
  if (e.key === "Tab" && !e.ctrlKey && !e.altKey) {
    e.preventDefault();
    if (!document.execCommand("insertText", false, "    ")) {
      const s = cfgEditor.selectionStart;
      cfgEditor.setRangeText("    ", s, cfgEditor.selectionEnd, "end");
      cfgEditor.dispatchEvent(new Event("input"));
    }
  }
});
document.addEventListener("selectionchange", () => { if (document.activeElement === cfgEditor) cfgUpdatePos(); });
$("#cfg-filter").addEventListener("input", cfgRenderList);
$("#cfg-find-input").addEventListener("input", () => cfgFind(true, true));
$("#cfg-find-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") { e.preventDefault(); cfgStep(e.shiftKey ? -1 : 1); }
  if (e.key === "Escape") cfgEditor.focus();
});
$("#cfg-next").addEventListener("click", () => cfgStep(1));
$("#cfg-prev").addEventListener("click", () => cfgStep(-1));
$("#btn-save-config").addEventListener("click", saveConfig);
$("#btn-reload-config").addEventListener("click", () => {
  if (!activeConfigKey) return;
  if (cfgDirty() && !confirm("Discard your unsaved changes and reload the file?")) return;
  loadConfig(activeConfigKey, true);
});
document.addEventListener("keydown", (e) => {
  if ($("#page-configs").style.display === "none") return;
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); saveConfig(); }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "f" && activeConfigKey) { e.preventDefault(); $("#cfg-find-input").focus(); $("#cfg-find-input").select(); }
});
window.addEventListener("beforeunload", (e) => { if (cfgDirty()) { e.preventDefault(); e.returnValue = ""; } });
new ResizeObserver(cfgSyncScroll).observe($("#cfg-code"));
new ResizeObserver(cfgLayoutList).observe($("#cfg-layout"));
cfgSetLoaded(false);
cfgRender();

// ---------- accounts / GM level ----------

$("#btn-create-account").addEventListener("click", async () => {
  const username = $("#acc-user").value.trim();
  const password = $("#acc-pass").value.trim();
  if (!username || !password) { toast("Fill in username and password"); return; }
  const res = await fetch("/api/admin/create-account", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const data = await res.json();
  toast(data.ok ? `Account "${username}" created` : "Error: " + data.error);
  if (data.ok) { $("#acc-user").value = ""; $("#acc-pass").value = ""; }
});

$("#btn-set-gmlevel").addEventListener("click", async () => {
  const username = $("#gm-user").value.trim();
  const gmlevel = $("#gm-level").value;
  const realmid = $("#gm-realm").value.trim() || "-1";
  if (!username) { toast("Fill in a username"); return; }
  const res = await fetch("/api/admin/set-gmlevel", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, gmlevel, realmid }),
  });
  const data = await res.json();
  toast(data.ok ? `GM level ${gmlevel} set for "${username}"` : "Error: " + data.error);
});

// ---------- bans & mutes ----------

function fmtUnixTime(sec) {
  if (!sec || sec === "0") return "-";
  const d = new Date(parseInt(sec, 10) * 1000);
  return d.toLocaleString();
}

function fmtDuration(banDate, unbanDate) {
  if (unbanDate === banDate) return "permanent";
  const secs = parseInt(unbanDate, 10) - Math.floor(Date.now() / 1000);
  if (secs <= 0) return "expired";
  const hours = Math.round(secs / 3600);
  return hours >= 24 ? Math.round(hours / 24) + "d" : hours + "h";
}

let banData = { account: [], ip: [], character: [], muted: [] };
let activeBanTab = "account";

$$(".admin-tabs [data-bantab]").forEach((tab) => {
  tab.addEventListener("click", () => {
    $$(".admin-tabs [data-bantab]").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    activeBanTab = tab.dataset.bantab;
    renderBanTable();
  });
});

async function loadBans() {
  const res = await fetch("/api/admin/bans");
  const data = await res.json();
  if (!data.error) banData = data;
  renderBanTable();
}

function renderBanTable() {
  const wrap = $("#ban-table-wrap");
  const rows = banData[activeBanTab] || [];
  if (activeBanTab === "muted") {
    wrap.innerHTML = rows.length ? `
      <table class="admin-table">
        <tr><th>Account</th><th>Muted</th><th>Duration</th><th>By</th><th>Reason</th><th></th></tr>
        ${rows.map(r => `
          <tr>
            <td>${r.username || r.guid}</td>
            <td>${fmtUnixTime(r.mutedate)}</td>
            <td>${Math.round(r.mutetime / 3600)}h</td>
            <td>${r.mutedby}</td>
            <td>${r.mutereason}</td>
            <td><button class="btn btn-outline btn-sm" data-unmute="${r.guid}">Unmute</button></td>
          </tr>`).join("")}
      </table>` : `<div class="hint">No active mutes.</div>`;
    wrap.querySelectorAll("[data-unmute]").forEach(b => b.addEventListener("click", async () => {
      await fetch("/api/admin/unmute", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ guid: b.dataset.unmute }) });
      toast("Unmuted"); loadBans();
    }));
    return;
  }
  const nameField = activeBanTab === "account" ? "username" : activeBanTab === "ip" ? "ip" : "name";
  const keyField = activeBanTab === "account" ? "id" : activeBanTab === "ip" ? "ip" : "guid";
  wrap.innerHTML = rows.length ? `
    <table class="admin-table">
      <tr><th>${activeBanTab === "ip" ? "IP" : "Name"}</th><th>Banned</th><th>Duration</th><th>By</th><th>Reason</th><th></th></tr>
      ${rows.map(r => `
        <tr>
          <td>${r[nameField] || r[keyField]}</td>
          <td>${fmtUnixTime(r.bandate)}</td>
          <td>${fmtDuration(r.bandate, r.unbandate)}</td>
          <td>${r.bannedby}</td>
          <td>${r.banreason}</td>
          <td><button class="btn btn-outline btn-sm" data-unban="${r[keyField]}">Unban</button></td>
        </tr>`).join("")}
    </table>` : `<div class="hint">No active bans.</div>`;
  wrap.querySelectorAll("[data-unban]").forEach(b => b.addEventListener("click", async () => {
    await fetch("/api/admin/unban", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ type: activeBanTab, key: b.dataset.unban }) });
    toast("Unbanned"); loadBans();
  }));
}

$("#ban-type").addEventListener("change", () => {
  $("#btn-add-ban").textContent = $("#ban-type").value === "mute" ? "Mute" : "Ban";
});

$("#btn-add-ban").addEventListener("click", async () => {
  const type = $("#ban-type").value;
  const name = $("#ban-name").value.trim();
  const reason = $("#ban-reason").value.trim() || "no reason";
  const hours = parseFloat($("#ban-duration").value.trim() || "0");
  if (!name) { toast("Fill in a name/IP"); return; }
  const endpoint = type === "mute" ? "/api/admin/mute" : "/api/admin/ban";
  const payload = type === "mute" ? { name, reason, duration: Math.round(hours * 3600) } : { type, name, reason, duration: Math.round(hours * 3600) };
  const res = await fetch(endpoint, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  toast(data.ok ? (type === "mute" ? "Muted" : "Banned") : "Error: " + data.error);
  if (data.ok) { $("#ban-name").value = ""; loadBans(); if (type === "mute") { $$(".admin-tabs [data-bantab]").forEach(t => t.classList.remove("active")); $(`[data-bantab="muted"]`).classList.add("active"); activeBanTab = "muted"; renderBanTable(); } }
});

// ---------- tickets ----------

async function loadTickets() {
  const res = await fetch("/api/admin/tickets");
  const rows = await res.json();
  const wrap = $("#ticket-table-wrap");
  if (rows.error) { wrap.innerHTML = `<div class="hint">Error: ${rows.error}</div>`; return; }
  wrap.innerHTML = rows.length ? `
    <table class="admin-table">
      <tr><th>#</th><th>Player</th><th>Message</th><th>Created</th><th></th></tr>
      ${rows.map(r => `
        <tr>
          <td>${r.id}</td>
          <td>${r.name}</td>
          <td style="max-width:400px">${(r.description || "").slice(0, 200)}</td>
          <td>${fmtUnixTime(r.createTime)}</td>
          <td><button class="btn btn-outline btn-sm" data-close-ticket="${r.id}">Close</button></td>
        </tr>`).join("")}
    </table>` : `<div class="hint">No open tickets.</div>`;
  wrap.querySelectorAll("[data-close-ticket]").forEach(b => b.addEventListener("click", async () => {
    await fetch("/api/admin/close-ticket", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: b.dataset.closeTicket }) });
    toast("Ticket closed"); loadTickets();
  }));
}

// ---------- realmlist ----------

async function loadRealms() {
  const res = await fetch("/api/admin/realms");
  const rows = await res.json();
  const wrap = $("#realm-table-wrap");
  if (rows.error) { wrap.innerHTML = `<div class="hint">Error: ${rows.error}</div>`; return; }
  wrap.innerHTML = `
    <table class="admin-table">
      <tr><th>Name</th><th>Address</th><th>Port</th><th>Flag</th><th>Pop.</th><th></th></tr>
      ${rows.map(r => `
        <tr>
          <td><input class="realm-name" data-id="${r.id}" value="${r.name}" style="width:120px;background:var(--panel-2);border:1px solid var(--border);border-radius:6px;color:var(--text);padding:4px 6px;font-size:12px"></td>
          <td><input class="realm-address" data-id="${r.id}" value="${r.address}" style="width:130px;background:var(--panel-2);border:1px solid var(--border);border-radius:6px;color:var(--text);padding:4px 6px;font-size:12px"></td>
          <td><input class="realm-port" data-id="${r.id}" value="${r.port}" style="width:60px;background:var(--panel-2);border:1px solid var(--border);border-radius:6px;color:var(--text);padding:4px 6px;font-size:12px"></td>
          <td><input class="realm-flag" data-id="${r.id}" value="${r.flag}" style="width:40px;background:var(--panel-2);border:1px solid var(--border);border-radius:6px;color:var(--text);padding:4px 6px;font-size:12px"></td>
          <td>${r.population}</td>
          <td><button class="btn btn-primary btn-sm" data-save-realm="${r.id}">Save</button></td>
        </tr>`).join("")}
    </table>`;
  wrap.querySelectorAll("[data-save-realm]").forEach(b => b.addEventListener("click", async () => {
    const id = b.dataset.saveRealm;
    const name = wrap.querySelector(`.realm-name[data-id="${id}"]`).value.trim();
    const address = wrap.querySelector(`.realm-address[data-id="${id}"]`).value.trim();
    const port = wrap.querySelector(`.realm-port[data-id="${id}"]`).value.trim();
    const flag = wrap.querySelector(`.realm-flag[data-id="${id}"]`).value.trim();
    const res = await fetch("/api/admin/update-realm", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, name, address, port, flag }),
    });
    const data = await res.json();
    toast(data.ok ? "Realm saved" : "Error: " + data.error);
  }));
}

// ---------- settings ----------
async function loadSettings() {
  const res = await fetch("/api/settings");
  const s = await res.json();
  $("#set-install_dir").value = s.install_dir || "";
  $("#set-configs_dir").value = s.configs_dir || "";
  $("#set-mysql_dir").value = s.mysql_dir || "";
  $("#set-mysql_data_dir").value = s.mysql_data_dir || "";
  $("#set-client_exe").value = s.client_exe || "";
  $("#set-authserver_exe").value = s.authserver_exe || "";
  $("#set-worldserver_exe").value = s.worldserver_exe || "";
  $("#set-worldserver2_exe").value = s.worldserver2_exe || "";
  $("#set-mysql_host").value = s.mysql_host || "";
  $("#set-mysql_port").value = s.mysql_port || "";
  $("#set-mysql_user").value = s.mysql_user || "";
  $("#set-mysql_password").value = s.mysql_password || "";
  $("#set-exilesdb_path").value = s.exilesdb_path || "";
  $("#set-exilesdb_port").value = s.exilesdb_port || "8081";
}

$("#btn-save-settings").addEventListener("click", async () => {
  const payload = {
    install_dir: $("#set-install_dir").value.trim(),
    configs_dir: $("#set-configs_dir").value.trim(),
    mysql_dir: $("#set-mysql_dir").value.trim(),
    mysql_data_dir: $("#set-mysql_data_dir").value.trim(),
    client_exe: $("#set-client_exe").value.trim(),
    authserver_exe: $("#set-authserver_exe").value.trim(),
    worldserver_exe: $("#set-worldserver_exe").value.trim(),
    worldserver2_exe: $("#set-worldserver2_exe").value.trim(),
    mysql_host: $("#set-mysql_host").value.trim(),
    mysql_port: $("#set-mysql_port").value.trim(),
    mysql_user: $("#set-mysql_user").value.trim(),
    mysql_password: $("#set-mysql_password").value,
    exilesdb_path: $("#set-exilesdb_path").value.trim(),
    exilesdb_port: $("#set-exilesdb_port").value.trim() || "8081",
  };
  const res = await fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  toast(data.ok ? "Settings saved" : "Error: " + data.error);
  refreshStatus();
});

// Browse buttons on the Settings page (kind=folder|file, target = the input's id).
async function browseInto(inputId, kind, title, filter) {
  const input = $("#" + inputId);
  const res = await fetch("/api/setup/browse", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind, title: title || "Choose a folder", start: input.value.trim(), filter }),
  });
  const data = await res.json();
  if (data.error) { toast("Error: " + data.error); return; }
  if (data.path) input.value = data.path;
}
$$("[data-browse-folder]").forEach((b) => b.addEventListener("click", () => browseInto(b.dataset.browseFolder, "folder")));
$$("[data-browse-file]").forEach((b) => b.addEventListener("click", () => browseInto(b.dataset.browseFile, "file")));

// ---------- setup wizard ----------
const WIZ_STEPS = 6;
let wizStep = 1;

function wizRenderDots() {
  const host = $("#wiz-dots");
  host.innerHTML = "";
  for (let i = 1; i <= WIZ_STEPS; i++) {
    const dot = document.createElement("span");
    if (i === wizStep) dot.className = "active";
    else if (i < wizStep) dot.className = "done";
    host.appendChild(dot);
  }
}

function wizShowStep(n) {
  wizStep = n;
  $$(".wizard-panel").forEach((p) => { p.style.display = Number(p.dataset.panel) === n ? "" : "none"; });
  wizRenderDots();
  $("#wiz-error").textContent = "";
  $("#wiz-back").style.visibility = n === 1 ? "hidden" : "visible";
  $("#wiz-next").textContent = n === WIZ_STEPS ? "Save & finish" : (n === 5 ? "Skip / Next" : "Next");
  if (n === 6) wizFillSummary();
}

function wizFillSummary() {
  const rows = [
    ["Install directory", $("#wiz-install_dir").value || "(not set)"],
    ["Configs directory", $("#wiz-configs_dir").value || "(not set)"],
    ["MySQL directory", $("#wiz-mysql_dir").value || "(not set)"],
    ["MySQL login", `${$("#wiz-mysql_user").value}@${$("#wiz-mysql_host").value}:${$("#wiz-mysql_port").value}`],
    ["Game client", $("#wiz-client_exe").value || "(not set, Open client button will be disabled)"],
    ["Second realm's worldserver.exe", $("#wiz-worldserver2_exe").value || "(not set, hidden)"],
    ["ExilesDB", $("#wiz-exilesdb_path").value || "(not set, tab stays hidden)"],
  ];
  $("#wiz-summary").innerHTML = rows.map(([k, v]) => `<div><b>${esc(k)}:</b> ${esc(v)}</div>`).join("");
}

async function wizValidateStep(n) {
  const err = (msg) => { $("#wiz-error").textContent = msg; return false; };
  if (n === 2) {
    if (!$("#wiz-install_dir").value.trim()) return err("Pick the install directory first.");
  }
  if (n === 3) {
    if (!$("#wiz-mysql_dir").value.trim()) return err("Pick the MySQL directory first.");
  }
  return true;
}

async function wizCheckPath(path) {
  try {
    const res = await fetch("/api/setup/check-path?path=" + encodeURIComponent(path));
    return (await res.json()).exists === true;
  } catch (e) { return false; }
}

async function wizCheckServerFolder() {
  const dir = $("#wiz-install_dir").value.trim();
  const el = $("#wiz-server-check");
  if (!dir) { el.textContent = ""; el.className = "wizard-check"; return; }
  el.textContent = "Checking…"; el.className = "wizard-check";
  const ok = await wizCheckPath(dir + "\\worldserver.exe") && await wizCheckPath(dir + "\\authserver.exe");
  el.textContent = ok ? "✓ Found authserver.exe and worldserver.exe" : "authserver.exe / worldserver.exe not found in this folder.";
  el.className = "wizard-check " + (ok ? "ok" : "bad");
}
$("#wiz-install_dir").addEventListener("change", wizCheckServerFolder);

$("#wiz-test-mysql").addEventListener("click", async () => {
  const el = $("#wiz-mysql-result");
  el.textContent = "Testing…"; el.className = "wizard-check";
  const res = await fetch("/api/setup/test-mysql", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mysql_dir: $("#wiz-mysql_dir").value.trim(), mysql_host: $("#wiz-mysql_host").value.trim(),
      mysql_port: $("#wiz-mysql_port").value.trim(), mysql_user: $("#wiz-mysql_user").value.trim(),
      mysql_password: $("#wiz-mysql_password").value,
    }),
  });
  const data = await res.json();
  el.textContent = data.ok ? "✓ Connected" : "Failed: " + (data.error || "unknown error");
  el.className = "wizard-check " + (data.ok ? "ok" : "bad");
});

$$("[data-wiz-browse-folder]").forEach((b) => b.addEventListener("click", async () => {
  const id = b.dataset.wizBrowseFolder;
  const res = await fetch("/api/setup/browse", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind: "folder", title: b.dataset.wizTitle, start: $("#" + id).value.trim() }),
  });
  const data = await res.json();
  if (data.path) { $("#" + id).value = data.path; $("#" + id).dispatchEvent(new Event("change")); }
}));
$$("[data-wiz-browse-file]").forEach((b) => b.addEventListener("click", async () => {
  const id = b.dataset.wizBrowseFile;
  const res = await fetch("/api/setup/browse", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind: "file", title: b.dataset.wizTitle, filter: b.dataset.wizFilter, start: $("#" + id).value.trim() }),
  });
  const data = await res.json();
  if (data.path) $("#" + id).value = data.path;
}));

$("#wiz-back").addEventListener("click", () => { if (wizStep > 1) wizShowStep(wizStep - 1); });
$("#wiz-next").addEventListener("click", async () => {
  if (!(await wizValidateStep(wizStep))) return;
  if (wizStep < WIZ_STEPS) { wizShowStep(wizStep + 1); return; }
  // Last step: save for real, via the same endpoint the Settings page uses.
  const payload = {
    install_dir: $("#wiz-install_dir").value.trim(),
    configs_dir: $("#wiz-configs_dir").value.trim(),
    mysql_dir: $("#wiz-mysql_dir").value.trim(),
    mysql_data_dir: $("#wiz-mysql_data_dir").value.trim(),
    client_exe: $("#wiz-client_exe").value.trim(),
    authserver_exe: $("#wiz-authserver_exe").value.trim(),
    worldserver_exe: $("#wiz-worldserver_exe").value.trim(),
    worldserver2_exe: $("#wiz-worldserver2_exe").value.trim(),
    mysql_host: $("#wiz-mysql_host").value.trim(),
    mysql_port: $("#wiz-mysql_port").value.trim(),
    mysql_user: $("#wiz-mysql_user").value.trim(),
    mysql_password: $("#wiz-mysql_password").value,
    exilesdb_path: $("#wiz-exilesdb_path").value.trim(),
    exilesdb_port: "8081",
  };
  const res = await fetch("/api/settings", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (data.error) { $("#wiz-error").textContent = "Error: " + data.error; return; }
  $("#setup-wizard").style.display = "none";
  toast("Setup saved");
  loadSettings();
  refreshStatus();
});

async function wizOpen() {
  // Prefill from whatever's already saved, then layer best-effort auto-detected guesses on top
  // of any still-empty fields -- never overwrites something the user already chose.
  const s = await (await fetch("/api/settings")).json();
  const d = await (await fetch("/api/setup/detect")).json();
  const val = (key) => s[key] || d[key] || "";
  $("#wiz-install_dir").value = val("install_dir");
  $("#wiz-configs_dir").value = val("configs_dir");
  $("#wiz-mysql_dir").value = val("mysql_dir");
  $("#wiz-mysql_data_dir").value = val("mysql_data_dir");
  $("#wiz-mysql_host").value = s.mysql_host || "127.0.0.1";
  $("#wiz-mysql_port").value = s.mysql_port || "3306";
  $("#wiz-mysql_user").value = s.mysql_user || "acore";
  $("#wiz-mysql_password").value = s.mysql_password || "acore";
  $("#wiz-client_exe").value = s.client_exe || "";
  $("#wiz-authserver_exe").value = s.authserver_exe || "";
  $("#wiz-worldserver_exe").value = s.worldserver_exe || "";
  $("#wiz-worldserver2_exe").value = s.worldserver2_exe || "";
  $("#wiz-exilesdb_path").value = s.exilesdb_path || "";
  $("#wiz-mysql-result").textContent = "";
  $("#setup-wizard").style.display = "flex";
  wizShowStep(1);
  wizCheckServerFolder();
}
$("#btn-run-wizard").addEventListener("click", wizOpen);

// Auto-open on first load if the saved paths don't actually resolve to real files.
(async () => {
  try {
    const status = await (await fetch("/api/setup/status")).json();
    if (!status.ok) wizOpen();
  } catch (e) { /* if this fails, let the normal dashboard load and surface errors as usual */ }
})();

// ---------- init ----------
refreshStatus();
refreshConsole();
setInterval(refreshStatus, 5000);


const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// ---------- live map ----------
let mapZoom = { z: 1, tx: 0, ty: 0 }, mapDrag = null;
let mapTimer = null, mapData = null, mapDots = [], mapWfDots = [], mapWf = null;
const MAP_QUALITY_COLORS = { 0: "#9d9d9d", 1: "#ffffff", 2: "#1eff00", 3: "#0070dd", 4: "#a335ee", 5: "#ff8000", 6: "#e6cc80", 7: "#e6cc80" };
const MAP_QUALITY_NAMES = ["Poor", "Common", "Uncommon", "Rare", "Epic", "Legendary", "Artifact", "Heirloom"];
const MAP_NAMES = { 0: "Eastern Kingdoms", 1: "Kalimdor", 530: "Outland", 571: "Northrend" };
// Ascension RAID_CLASS_COLORS by class name. Felsworn, Knight of Xoroth, Templar, Bloodmage, Venomancer,
// Primalist and Runemaster are matched to the client's internal names by guess.
const MAP_CLASS_COLORS = {
  warrior: "#C79C6E", paladin: "#F58CBA", hunter: "#ABD473", rogue: "#FFF569", priest: "#FFFFFF", deathknight: "#C41F3B",
  shaman: "#0070DE", mage: "#69CCF0", warlock: "#9482C9", druid: "#FF7D0A",
  barbarian: "#8A3303", witchdoctor: "#F500FF", felsworn: "#75FA00", witchhunter: "#5433CF", stormbringer: "#007DED",
  knightofxoroth: "#FC0005", guardian: "#9C9482", templar: "#FFD624", bloodmage: "#A30000", ranger: "#BFF06B",
  chronomancer: "#FFED4A", necromancer: "#45DB9C", pyromancer: "#FF6112", cultist: "#9C45F2", starcaller: "#8FFFFF",
  suncleric: "#FFB340", tinker: "#D9D9D9", venomancer: "#6BA600", reaper: "#0A876B", primalist: "#E38C59", runemaster: "#40C7EB",
};
const mapClassColor = (name) => MAP_CLASS_COLORS[String(name).toLowerCase().replace(/[^a-z]/g, "")] || "#bbbbbb";
// The World picture is drawn by hand, so continent-map pixels are fitted onto it: world = offset + scale * pixel.
const MAP_WORLD_FIT = {
  c1: { sx: 0.69, sy: 0.67, ox: -131.7, oy: 149.8 },   // Kalimdor
  c0: { sx: 0.846, sy: 0.818, ox: 393, oy: 88.6 },      // Eastern Kingdoms
};
const MAP_NAME_FIX = {
  Darnassis: "Darnassus", Palehorn: "Druk'Thar", Scadeald: "Pale Reach", ShadewellSpring: "Pale Reach Shadewell", Uldamanin: "Uldaman Entrance",
};
const mapScale = () => +$("#map-size").value || 1;
try { const s = localStorage.getItem("mapIconSize"); if (s) $("#map-size").value = s; } catch (e) { /* default size */ }
$("#map-size").addEventListener("input", () => {
  try { localStorage.setItem("mapIconSize", $("#map-size").value); } catch (e) { /* not saved */ }
  if (mapData) drawMap();
});
function mapViews() {
  const views = {}, ID = { sx: 1, sy: 1, ox: 0, oy: 0 };
  views.world = { label: "Azeroth", rank: 0, dot: 0.5, panels: [{ img: "world", conts: [["c1", MAP_WORLD_FIT.c1], ["c0", MAP_WORLD_FIT.c0]] }] };
  Object.entries(mapData.zones).forEach(([key, z]) => {
    const cont = key[0] === "c", name = key === "c0" ? "Eastern Kingdoms" : (MAP_NAME_FIX[z.name] || z.name);
    views[key] = { label: (cont ? "Continent: " : "Zone: ") + name, rank: cont ? (key === "c1" ? 1 : 2) : 3, dot: cont ? 0.65 : 1.2, zone: cont ? null : key, panels: [{ img: key, conts: [[key, ID]] }] };
  });
  return views;
}
function drawMap() {
  const cv = $("#map-canvas"), ctx = cv.getContext("2d"), sel = $("#map-view").value, view = mapViews()[sel];
  const imgs = [$("#map-img"), $("#map-img2")], W = 1002, H = 668;
  mapDots = []; mapWfDots = [];
  if (!view) { imgs.forEach((i) => { i.style.display = "none"; }); ctx.clearRect(0, 0, cv.width, cv.height); return; }
  const n = view.panels.length;
  if (cv.width !== W * n) cv.width = W * n;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, cv.width, cv.height);
  mapClampZoom(W * n, H);
  ctx.setTransform(mapZoom.z, 0, 0, mapZoom.z, mapZoom.tx, mapZoom.ty);
  $("#map-layers").style.transform = `translate(${mapZoom.tx}px, ${mapZoom.ty}px) scale(${mapZoom.z})`;
  $("#map-wrap").style.aspectRatio = (W * n) + "/" + H;
  $("#map-wrap").style.maxWidth = (W * n) + "px";
  const showBots = $("#map-bots").checked, showPl = $("#map-players").checked, showWf = $("#map-wf").checked;
  imgs.forEach((img, k) => {
    if (k >= n) { img.style.display = "none"; return; }
    const src = "/worldmaps/" + view.panels[k].img + ".jpg?v=" + mapData.ver;
    if (!img.src.endsWith(src)) img.src = src;
    img.style.display = "";
    img.style.width = (100 / n) + "%"; img.style.left = (k * 100 / n) + "%";
  });
  view.panels.forEach((panel, k) => {
    const ox0 = k * W;
    panel.conts.forEach(([key, t]) => {
      const z = mapData.zones[key];
      if (!z) return;
      if (showWf && mapWf) mapWf.markers.forEach((m) => {
        if (m[1] !== z.map) return;
        const u = (z.left - m[3]) / (z.left - z.right), v = (z.top - m[2]) / (z.top - z.bottom);
        if (u < 0 || v < 0 || u > 1 || v > 1) return;
        const px = ox0 + t.ox + t.sx * u * W, py = t.oy + t.sy * v * H, r = 7 * view.dot * mapScale() / Math.pow(mapZoom.z, 0.6), item = mapWf.items[m[0]];
        ctx.beginPath();
        for (let i = 0; i < 10; i++) { const rr = i % 2 ? r * 0.45 : r * 1.25, ang = -Math.PI / 2 + i * Math.PI / 5; ctx.lineTo(px + rr * Math.cos(ang), py + rr * Math.sin(ang)); }
        ctx.closePath();
        ctx.fillStyle = MAP_QUALITY_COLORS[item[1]] || "#ffffff"; ctx.globalAlpha = m[4] === "FADING" ? 0.75 : 1; ctx.fill(); ctx.globalAlpha = 1;
        ctx.lineWidth = 1 / mapZoom.z; ctx.strokeStyle = "#000000c0"; ctx.stroke();
        mapWfDots.push({ px, py, m, item });
      });
      mapData.players.forEach((p) => {
        if (+p.map !== z.map || !(+p.bot ? showBots : showPl)) return;
        const u = (z.left - +p.y) / (z.left - z.right), v = (z.top - +p.x) / (z.top - z.bottom);
        if (u < 0 || v < 0 || u > 1 || v > 1) return;
        const px = ox0 + t.ox + t.sx * u * W, py = t.oy + t.sy * v * H;
        const ally = [1, 3, 4, 7, 11].includes(+p.race), r = (+p.bot ? 5 : 8) * view.dot * mapScale() / Math.pow(mapZoom.z, 0.6);
        ctx.beginPath();
        if (ally) ctx.arc(px, py, r, 0, 7);                 // Alliance = circle, Horde = diamond
        else { ctx.moveTo(px, py - r * 1.3); ctx.lineTo(px + r * 1.3, py); ctx.lineTo(px, py + r * 1.3); ctx.lineTo(px - r * 1.3, py); ctx.closePath(); }
        ctx.fillStyle = mapClassColor(p.cls); ctx.fill();
        ctx.lineWidth = (+p.bot ? 1 : 1.5) * Math.min(1, view.dot + 0.2) / mapZoom.z; ctx.strokeStyle = "#000000b0"; ctx.stroke();
        mapDots.push({ px, py, p });
      });
    });
  });
}
async function loadMap() {
  clearTimeout(mapTimer);
  if ($("#page-map").style.display === "none") return;
  try {
    const d = await (await fetch("/api/map")).json();
    if (d.error) throw new Error(d.error);
    mapData = d;
    if ($("#map-info").textContent.startsWith("Could not load")) $("#map-info").textContent = "";
    const sel = $("#map-view"), keep = sel.value, views = mapViews();
    sel.innerHTML = Object.entries(views).sort((x, y) => (x[1].rank - y[1].rank) || x[1].label.localeCompare(y[1].label)).map(([k, v]) => `<option value="${k}">${v.label}</option>`).join("");
    sel.value = views[keep] ? keep : "world";
    mapRenderZoneList(views);
    const tp = $("#map-tp"), tpKeep = tp.value || (() => { try { return localStorage.getItem("mapTpChar") || ""; } catch (e) { return ""; } })();
    tp.innerHTML = (d.real || []).map((n) => `<option>${esc(n)}</option>`).join("");
    if ((d.real || []).includes(tpKeep)) tp.value = tpKeep;
    drawMap();
  } catch (e) {
    $("#map-info").textContent = "Could not load: " + e.message;
  }
  mapTimer = setTimeout(loadMap, 3000);
}
// Zoom (mouse wheel, around the cursor) and pan (drag); double-click resets. Dots are drawn with the same transform
// so they stay sharp; the pictures are moved with CSS.
function mapClampZoom(w, h) {
  mapZoom.z = Math.min(8, Math.max(1, mapZoom.z));
  mapZoom.tx = Math.min(0, Math.max(w * (1 - mapZoom.z), mapZoom.tx));
  mapZoom.ty = Math.min(0, Math.max(h * (1 - mapZoom.z), mapZoom.ty));
}
function mapPointer(e) {
  const cv = $("#map-canvas"), r = cv.getBoundingClientRect(), cx = (e.clientX - r.left) * cv.width / r.width, cy = (e.clientY - r.top) * cv.height / r.height;
  return { cx, cy, mx: (cx - mapZoom.tx) / mapZoom.z, my: (cy - mapZoom.ty) / mapZoom.z };
}
$("#map-canvas").addEventListener("wheel", (e) => {
  if (!mapData) return;
  e.preventDefault();
  const p = mapPointer(e), z = Math.min(8, Math.max(1, mapZoom.z * (e.deltaY < 0 ? 1.25 : 0.8)));
  mapZoom = { z, tx: p.cx - p.mx * z, ty: p.cy - p.my * z };
  $("#map-tip").style.display = "none";
  drawMap();
}, { passive: false });
$("#map-canvas").addEventListener("mousedown", (e) => { if (e.button === 0 && mapZoom.z > 1) mapDrag = { x: e.clientX, y: e.clientY, tx: mapZoom.tx, ty: mapZoom.ty, moved: false }; });
window.addEventListener("mouseup", () => { if (mapDrag) setTimeout(() => { mapDrag = null; }, 0); });
window.addEventListener("mousemove", (e) => {
  if (!mapDrag) return;
  const cv = $("#map-canvas"), k = cv.width / cv.getBoundingClientRect().width;
  mapDrag.moved = true;
  mapZoom.tx = mapDrag.tx + (e.clientX - mapDrag.x) * k; mapZoom.ty = mapDrag.ty + (e.clientY - mapDrag.y) * k;
  $("#map-tip").style.display = "none";
  drawMap();
});
$("#map-canvas").addEventListener("dblclick", () => { mapZoom = { z: 1, tx: 0, ty: 0 }; drawMap(); });
$("#map-view").addEventListener("change", () => { mapZoom = { z: 1, tx: 0, ty: 0 }; });

// Right-click on the map -> "TP here": the click is turned back into world x/y and the chosen character is teleported.
let mapClick = null;
$("#map-tp").addEventListener("change", () => { try { localStorage.setItem("mapTpChar", $("#map-tp").value); } catch (e) { /* not saved */ } });
function mapWorldAt(e) {
  const cv = $("#map-canvas"), r = cv.getBoundingClientRect(), view = mapViews()[$("#map-view").value];
  if (!view) return null;
  const W = 1002, H = 668, ptr = mapPointer(e), cx = ptr.mx, cy = ptr.my;
  const k = Math.min(view.panels.length - 1, Math.floor(cx / W)), px = cx - k * W;
  let best = null;
  view.panels[k].conts.forEach(([key, t]) => {
    const z = mapData.zones[key];
    if (!z) return;
    const u = (px - t.ox) / (t.sx * W), v = (cy - t.oy) / (t.sy * H);
    if (u < 0 || u > 1 || v < 0 || v > 1) return;
    const dist = Math.abs(u - 0.5) + Math.abs(v - 0.5);
    if (!best || dist < best.dist) best = { dist, map: z.map, x: z.top - v * (z.top - z.bottom), y: z.left - u * (z.left - z.right) };
  });
  return best;
}
$("#map-canvas").addEventListener("contextmenu", (e) => {
  e.preventDefault();
  const w = $("#map-wrap").getBoundingClientRect(), menu = $("#map-menu"), who = $("#map-tp").value;
  mapClick = mapWorldAt(e);
  if (!mapClick) { menu.style.display = "none"; return; }
  $("#map-menu-tp").textContent = who ? `📍 TP ${who} here` : "📍 TP here (no character online)";
  $("#map-menu-tp").style.opacity = who ? "1" : ".5";
  menu.style.left = (e.clientX - w.left) + "px"; menu.style.top = (e.clientY - w.top) + "px"; menu.style.display = "";
});
$("#map-menu-tp").addEventListener("mouseenter", (e) => { e.target.style.background = "#ffffff18"; });
$("#map-menu-tp").addEventListener("mouseleave", (e) => { e.target.style.background = ""; });
$("#map-menu-tp").addEventListener("click", async () => {
  $("#map-menu").style.display = "none";
  const who = $("#map-tp").value, info = $("#map-info");
  if (!who || !mapClick) return;
  info.textContent = `Teleporting ${who}…`;
  try {
    const r = await fetch("/api/map/teleport", { method: "POST", body: JSON.stringify({ character: who, map: mapClick.map, x: mapClick.x, y: mapClick.y }) });
    const d = await r.json();
    info.textContent = d.error ? "Teleport failed: " + d.error : `${who} teleported (${Math.round(mapClick.x)}, ${Math.round(mapClick.y)}).`;
  } catch (err) { info.textContent = "Teleport failed: " + err.message; }
  setTimeout(() => { info.textContent = ""; }, 5000);
});
document.addEventListener("click", (e) => { if (!e.target.closest("#map-menu")) $("#map-menu").style.display = "none"; });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") $("#map-menu").style.display = "none"; });
$("#map-view").addEventListener("change", drawMap);

// ---------- live map: zone picker box (right of the map) ----------
const MAP_ZONE_GROUPS = { 0: "Continents", 1: "Continents", 2: "Continents", 3: "Zones" };
let mapZoneViews = null;
function mapRenderZoneList(views) {
  mapZoneViews = views;
  mapFilterZoneList();
}
function mapFilterZoneList() {
  if (!mapZoneViews) return;
  const q = ($("#map-zone-filter").value || "").trim().toLowerCase(), sel = $("#map-view").value;
  const entries = Object.entries(mapZoneViews)
    .filter(([k, v]) => !q || v.label.toLowerCase().includes(q))
    .sort((x, y) => (x[1].rank - y[1].rank) || x[1].label.localeCompare(y[1].label));
  let lastGroup = null, html = "";
  entries.forEach(([k, v]) => {
    const group = MAP_ZONE_GROUPS[v.rank] || "Zones";
    if (group !== lastGroup) { html += `<div class="map-zone-group">${group}</div>`; lastGroup = group; }
    const label = v.label.replace(/^(Continent|Zone): /, "");
    html += `<button type="button" class="map-zone-item${k === sel ? " active" : ""}" data-key="${k}">${esc(label)}</button>`;
  });
  $("#map-zone-list").innerHTML = html || `<div class="map-zone-group">No matches</div>`;
}
$("#map-zone-filter").addEventListener("input", mapFilterZoneList);
$("#map-zone-list").addEventListener("click", (e) => {
  const btn = e.target.closest(".map-zone-item");
  if (!btn) return;
  $("#map-view").value = btn.dataset.key;
  $("#map-view").dispatchEvent(new Event("change"));
  mapFilterZoneList();
});
$("#map-bots").addEventListener("change", drawMap);
$("#map-players").addEventListener("change", drawMap);
$("#map-wf").addEventListener("change", async () => {
  if ($("#map-wf").checked && !mapWf) {
    try { mapWf = await (await fetch("/api/map/worldforge")).json(); if (mapWf.error) throw new Error(mapWf.error); }
    catch (e) { mapWf = null; $("#map-wf").checked = false; $("#map-info").textContent = "Could not load Worldforge locations: " + e.message; return; }
  }
  if (mapData) drawMap();
});
$("#map-canvas").addEventListener("mousemove", (e) => {
  if (mapDrag && mapDrag.moved) return;
  const cv = e.target, r = cv.getBoundingClientRect(), { mx, my } = mapPointer(e);
  const hit = mapDots.find((d) => Math.hypot(d.px - mx, d.py - my) * mapZoom.z < 8), tip = $("#map-tip");
  if (!hit) {
    const wf = mapWfDots.find((d) => Math.hypot(d.px - mx, d.py - my) * mapZoom.z < 9);
    if (!wf) { tip.style.display = "none"; return; }
    const [name, q, icon, slot, sub] = wf.item;
    tip.innerHTML = `<div style="display:flex;gap:8px;align-items:center"><img src="/item_icons/${encodeURIComponent(icon)}.png" width="28" height="28" alt="" onerror="this.style.display='none'"><div><b style="color:${MAP_QUALITY_COLORS[q] || "#fff"}">${esc(name)}</b><br><span style="opacity:.75">${MAP_QUALITY_NAMES[q] || ""} ${esc(sub)} ${esc(slot)} · ${esc(wf.m[4].toLowerCase())}</span></div></div>`;
    tip.style.display = ""; tip.style.left = (e.clientX - r.left + 12) + "px"; tip.style.top = (e.clientY - r.top + 12) + "px";
    return;
  }
  tip.textContent = `${hit.p.name} · lvl ${hit.p.level} ${hit.p.cls} · ${[1, 3, 4, 7, 11].includes(+hit.p.race) ? "Alliance" : "Horde"}${+hit.p.bot ? " · bot" : ""}`;
  tip.style.display = ""; tip.style.left = (e.clientX - r.left + 12) + "px"; tip.style.top = (e.clientY - r.top + 12) + "px";
});



// ---------- accounts: list, search, edit ----------
let accPage = 1;
let accRows = [];
let accEditing = null;
let accSearchTimer = null;

async function loadAccounts() {
  const q = encodeURIComponent($("#acc-search").value.trim());
  const bots = $("#acc-bots").checked ? 1 : 0;
  try {
    const d = await (await fetch(`/api/admin/accounts?q=${q}&page=${accPage}&bots=${bots}`)).json();
    if (d.error) throw new Error(d.error);
    accPage = d.page;
    accRows = d.rows;
    const gm = ["", "moderator", "gamemaster", "admin"];
    $("#acc-table-wrap").innerHTML = d.rows.length
      ? `<table class="admin-table"><tr><th>ID</th><th>Username</th><th>GM</th><th>Email</th><th>Expansion</th><th>Characters</th><th>Last login</th><th>Online</th><th></th></tr>` +
        d.rows.map((r) => `<tr><td>${r.id}</td><td>${esc(r.username)}</td><td>${r.gmlevel}${gm[r.gmlevel] ? " " + gm[r.gmlevel] : ""}</td>
          <td>${esc(r.email || "")}</td><td>${["Classic", "TBC", "WotLK"][r.expansion] || r.expansion}</td><td>${r.characters}</td>
          <td>${esc(r.last_login || "-")}</td><td>${r.online === "1" ? "🟢" : "⚪"}</td>
          <td><button class="btn btn-outline" data-edit="${r.id}" style="padding:4px 14px">Edit</button></td></tr>`).join("") + "</table>"
      : `<div class="page-sub" style="margin:12px 0">No accounts match.</div>`;
    $("#acc-pager").innerHTML = `<span class="page-sub" style="margin:0">${d.total} accounts · page ${d.page} of ${d.pages}</span>
      <span style="display:flex;gap:8px"><button class="btn btn-outline" id="acc-prev" ${d.page <= 1 ? "disabled" : ""}>← Prev</button>
      <button class="btn btn-outline" id="acc-next" ${d.page >= d.pages ? "disabled" : ""}>Next →</button></span>`;
    $("#acc-prev").addEventListener("click", () => { accPage--; loadAccounts(); });
    $("#acc-next").addEventListener("click", () => { accPage++; loadAccounts(); });
    $$("#acc-table-wrap [data-edit]").forEach((b) => b.addEventListener("click", () => editAccount(b.dataset.edit)));
  } catch (e) {
    $("#acc-table-wrap").innerHTML = `<div class="page-sub">Could not load accounts: ${esc(e.message)}</div>`;
  }
}

function editAccount(id) {
  const r = accRows.find((x) => x.id === id);
  if (!r) return;
  accEditing = r.id;
  $("#acc-edit-title").textContent = `Edit ${r.username} (id ${r.id})`;
  $("#acc-e-email").value = r.email || "";
  $("#acc-e-gm").value = String(Math.min(3, r.gmlevel));
  $("#acc-e-exp").value = String(r.expansion);
  $("#acc-e-locked").value = r.locked === "1" ? "1" : "0";
  $("#acc-e-pass").value = "";
  $("#acc-edit").style.display = "";
  $("#acc-edit").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

$("#acc-e-cancel").addEventListener("click", () => { $("#acc-edit").style.display = "none"; accEditing = null; });
$("#acc-e-save").addEventListener("click", async () => {
  if (accEditing == null) return;
  const res = await fetch("/api/admin/update-account", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      id: accEditing, email: $("#acc-e-email").value.trim(), gmlevel: $("#acc-e-gm").value,
      expansion: $("#acc-e-exp").value, locked: $("#acc-e-locked").value, password: $("#acc-e-pass").value,
    }),
  });
  const data = await res.json();
  toast(data.ok ? "Account saved" : "Error: " + data.error);
  if (data.ok) { $("#acc-edit").style.display = "none"; accEditing = null; loadAccounts(); }
});
$("#acc-search").addEventListener("input", () => {
  clearTimeout(accSearchTimer);
  accSearchTimer = setTimeout(() => { accPage = 1; loadAccounts(); }, 300);
});
$("#acc-bots").addEventListener("change", () => { accPage = 1; loadAccounts(); });


// ---------- add item ----------
let itemPage = 1;
let itemTimer = null;
const QUALITY = [["Poor", "#9d9d9d"], ["Common", "#f6f5f2"], ["Uncommon", "#1eff00"], ["Rare", "#4a9eff"],
  ["Epic", "#a335ee"], ["Legendary", "#ff8000"], ["Artifact", "#e6cc80"], ["Heirloom", "#00ccff"]];
const SLOTS = { 1: "Head", 2: "Neck", 3: "Shoulder", 4: "Shirt", 5: "Chest", 6: "Waist", 7: "Legs", 8: "Feet", 9: "Wrist", 10: "Hands",
  11: "Finger", 12: "Trinket", 13: "One-hand", 14: "Shield", 15: "Ranged", 16: "Back", 17: "Two-hand", 18: "Bag", 19: "Tabard",
  20: "Robe", 21: "Main hand", 22: "Off hand", 23: "Held off-hand", 24: "Ammo", 25: "Thrown", 26: "Ranged", 28: "Relic" };

async function loadItemCharacters() {
  try {
    const names = await (await fetch("/api/admin/characters")).json();
    if (Array.isArray(names)) $("#item-char-list").innerHTML = names.map((n) => `<option value="${esc(n)}">`).join("");
  } catch (e) { /* the field still accepts a typed name */ }
}

async function loadItems() {
  const p = new URLSearchParams({
    q: $("#item-search").value.trim(), page: itemPage, quality: $("#item-quality").value, class: $("#item-class").value,
    slot: $("#item-slot").value, sub: $("#item-sub").value, min: $("#item-min").value.trim(), max: $("#item-max").value.trim(), hide: $("#item-hide").checked ? 1 : 0,
  });
  try {
    const d = await (await fetch("/api/admin/items?" + p)).json();
    if (d.error) throw new Error(d.error);
    itemPage = d.page;
    $("#item-table-wrap").innerHTML = d.rows.length
      ? `<table class="admin-table"><tr><th>ID</th><th>Name</th><th>Quality</th><th>Type</th><th>Slot</th><th>iLvl</th><th>Req</th><th></th></tr>` +
        d.rows.map((r) => { const q = QUALITY[r.Quality] || ["?", "#f6f5f2"]; return `<tr><td>${r.entry}</td>
          <td data-tip="${r.entry}" style="color:${q[1]};font-weight:600">${r.icon
            ? `<img class="item-icon" src="/item_icons/${encodeURIComponent(r.icon)}.png" alt="" onerror="this.className='item-icon none';this.removeAttribute('src')">`
            : `<span class="item-icon none"></span>`}${esc(r.name)}</td><td>${q[0]}</td><td>${esc(r.type)}</td><td>${SLOTS[r.InventoryType] || ""}</td>
          <td>${r.ItemLevel}</td><td>${r.RequiredLevel}</td>
          <td style="white-space:nowrap"><button class="btn btn-primary" data-give="${r.entry}" data-name="${esc(r.name)}" style="padding:4px 14px">Add</button>
            <button class="star${kitsData.favorites.includes(r.entry) ? " on" : ""}" data-fav="${r.entry}" title="Favorite">★</button>
            <button class="btn btn-outline" data-tokit="${r.entry}" style="padding:4px 10px" title="Add to the selected kit">+ Kit</button></td></tr>`; }).join("") + "</table>"
      : `<div class="page-sub" style="margin:12px 0">No items match.</div>`;
    $("#item-pager").innerHTML = `<span class="page-sub" style="margin:0">${d.total.toLocaleString()} items · page ${d.page.toLocaleString()} of ${d.pages.toLocaleString()}</span>
      <span style="display:flex;gap:8px"><button class="btn btn-outline" id="item-prev" ${d.page <= 1 ? "disabled" : ""}>← Prev</button>
      <button class="btn btn-outline" id="item-next" ${d.page >= d.pages ? "disabled" : ""}>Next →</button></span>`;
    $("#item-prev").addEventListener("click", () => { itemPage--; loadItems(); });
    $("#item-next").addEventListener("click", () => { itemPage++; loadItems(); });
    $$("#item-table-wrap [data-give]").forEach((b) => b.addEventListener("click", () => giveItem(b)));
    d.rows.forEach((r) => { itemRows[r.entry] = r; });
    $$("#item-table-wrap [data-fav]").forEach((b) => b.addEventListener("click", () => toggleFavorite(+b.dataset.fav)));
    $$("#item-table-wrap [data-tokit]").forEach((b) => b.addEventListener("click", () => addToKit(+b.dataset.tokit)));
  } catch (e) {
    $("#item-table-wrap").innerHTML = `<div class="page-sub">Could not load items: ${esc(e.message)}</div>`;
  }
}

async function giveItem(btn, itemId) {
  const character = $("#item-char").value.trim();
  if (!character) { toast("Pick a character first"); return; }
  btn.disabled = true;
  try {
    const res = await fetch("/api/admin/give-item", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ character, item: itemId || btn.dataset.give, count: $("#item-count").value.trim() || "1" }),
    });
    const d = await res.json();
    toast(d.ok ? `Mailed ${d.count}x ${d.item} to ${character}` : "Error: " + d.error);
  } catch (e) { toast("Request failed"); }
  btn.disabled = false;
}

// ---------- kits & favorites (stored server-side in kits.json) ----------
let kitsData = { kits: [], favorites: [], info: {} };
// Kits are minimized by default; this is the set of kit names the user expanded (remembered in the browser).
const kitOpen = new Set((() => { try { return JSON.parse(localStorage.getItem("kitOpen") || "[]"); } catch (e) { return []; } })());
function saveKitOpen() { try { localStorage.setItem("kitOpen", JSON.stringify([...kitOpen])); } catch (e) { /* not critical */ } }
const itemRows = {};

function itemInfo(id) { return kitsData.info[id] || { name: "Item " + id, quality: 1, icon: "", stackable: 1 }; }

function itemIconHtml(info) {
  return info.icon
    ? `<img class="item-icon" src="/item_icons/${encodeURIComponent(info.icon)}.png" alt="" onerror="this.className='item-icon none';this.removeAttribute('src')">`
    : `<span class="item-icon none"></span>`;
}

function rememberItem(id) {
  const r = itemRows[id];
  if (r) kitsData.info[id] = { name: r.name, quality: r.Quality, icon: r.icon || "", stackable: +r.stackable || 1 };
}

async function loadKits() {
  try {
    const d = await (await fetch("/api/admin/kits")).json();
    if (d.error) throw new Error(d.error);
    kitsData = d;
  } catch (e) { toast("Could not load kits: " + e.message); }
  renderKits();
}

async function saveKits() {
  try {
    const res = await fetch("/api/admin/kits-save", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kits: kitsData.kits, favorites: kitsData.favorites }) });
    const d = await res.json();
    if (!d.ok) toast("Error: " + d.error);
  } catch (e) { toast("Saving kits failed"); }
}

function renderKits() {
  const nameOf = (id) => { const i = itemInfo(id); return `<span style="color:${(QUALITY[i.quality] || QUALITY[1])[1]}">${esc(i.name)}</span>`; };
  $("#fav-list").innerHTML = kitsData.favorites.length
    ? `<div class="kit-items">` + kitsData.favorites.map((id) => `<div class="kit-item" data-tip="${id}">${itemIconHtml(itemInfo(id))}${nameOf(id)}
        <button class="btn btn-primary" data-favgive="${id}" style="padding:2px 10px">Add</button><button class="kit-x" data-favdel="${id}" title="Remove">✕</button></div>`).join("") + `</div>`
    : `<div class="page-sub" style="margin:8px 0 0">No favorites yet. Click ★ on an item below.</div>`;
  $$("#fav-list [data-favgive]").forEach((b) => b.addEventListener("click", () => giveItem(b, +b.dataset.favgive)));
  $$("#fav-list [data-favdel]").forEach((b) => b.addEventListener("click", () => toggleFavorite(+b.dataset.favdel)));

  const sel = $("#kit-target"), keep = sel.value;
  sel.innerHTML = kitsData.kits.length ? kitsData.kits.map((k) => `<option>${esc(k.name)}</option>`).join("") : `<option value="">(create a kit first)</option>`;
  if (kitsData.kits.some((k) => k.name === keep)) sel.value = keep;

  $("#kit-list").innerHTML = kitsData.kits.length ? kitsData.kits.map((k, ki) => `<div class="kit-card">
      <div class="kit-card-h"><button class="kit-toggle" data-kittoggle="${ki}" title="${kitOpen.has(k.name) ? "Minimize" : "Expand"}">${kitOpen.has(k.name) ? "▾" : "▸"}</button>
        <span class="kit-name" data-kittoggle="${ki}">${esc(k.name)}</span><span class="kit-count-badge">${k.items.length} item${k.items.length === 1 ? "" : "s"}</span><span style="margin-right:auto"></span>
        <button class="btn btn-primary" data-kitgive="${ki}" ${k.items.length ? "" : "disabled"}>Send kit</button>
        <button class="btn btn-outline" data-kitrename="${ki}">Rename</button>
        <button class="btn btn-danger" data-kitdel="${ki}">Delete</button></div>
      <div class="kit-items" ${kitOpen.has(k.name) ? "" : "hidden"}>${k.items.length ? k.items.map((it, ii) => `<div class="kit-item" data-tip="${it.id}">${itemIconHtml(itemInfo(it.id))}${nameOf(it.id)}
        ×<input class="kit-count" type="text" value="${it.count}" data-kitcount="${ki}:${ii}"><button class="kit-x" data-kitrm="${ki}:${ii}" title="Remove">✕</button></div>`).join("")
        : `<span class="page-sub" style="margin:0">Empty. Use "+ Kit" on an item in the search results.</span>`}</div></div>`).join("")
    : `<div class="page-sub" style="margin:8px 0 0">No kits yet.</div>`;
  $$("#kit-list [data-kittoggle]").forEach((b) => b.addEventListener("click", () => {
    const name = kitsData.kits[+b.dataset.kittoggle].name;
    if (kitOpen.has(name)) kitOpen.delete(name); else kitOpen.add(name);
    saveKitOpen(); renderKits();
  }));
  $$("#kit-list [data-kitgive]").forEach((b) => b.addEventListener("click", () => giveKit(+b.dataset.kitgive, b)));
  $$("#kit-list [data-kitdel]").forEach((b) => b.addEventListener("click", () => {
    const k = kitsData.kits[+b.dataset.kitdel];
    if (confirm(`Delete kit "${k.name}"?`)) { kitsData.kits.splice(+b.dataset.kitdel, 1); saveKits(); renderKits(); }
  }));
  $$("#kit-list [data-kitrename]").forEach((b) => b.addEventListener("click", () => {
    const k = kitsData.kits[+b.dataset.kitrename];
    const n = (prompt("New name for the kit:", k.name) || "").replace(/[^A-Za-z0-9 _-]/g, "").trim().slice(0, 40);
    if (!n || n === k.name) return;
    if (kitsData.kits.some((o) => o !== k && o.name.toLowerCase() === n.toLowerCase())) { toast("A kit with that name exists"); return; }
    if (kitOpen.delete(k.name)) kitOpen.add(n);
    k.name = n; saveKitOpen(); saveKits(); renderKits();
  }));
  $$("#kit-list [data-kitrm]").forEach((b) => b.addEventListener("click", () => {
    const [ki, ii] = b.dataset.kitrm.split(":").map(Number);
    kitsData.kits[ki].items.splice(ii, 1); saveKits(); renderKits();
  }));
  $$("#kit-list [data-kitcount]").forEach((inp) => inp.addEventListener("change", () => {
    const [ki, ii] = inp.dataset.kitcount.split(":").map(Number);
    const n = Math.min(1000, Math.max(1, parseInt(inp.value, 10) || 1));
    kitsData.kits[ki].items[ii].count = n; inp.value = n; saveKits();
  }));
}

function toggleFavorite(id) {
  const i = kitsData.favorites.indexOf(id);
  if (i >= 0) kitsData.favorites.splice(i, 1); else { kitsData.favorites.push(id); rememberItem(id); }
  saveKits(); renderKits();
  $$(`#item-table-wrap [data-fav="${id}"]`).forEach((b) => b.classList.toggle("on", kitsData.favorites.includes(id)));
}

function addToKit(id) {
  const name = $("#kit-target").value;
  const kit = kitsData.kits.find((k) => k.name === name);
  if (!kit) { toast("Create or pick a kit first"); return; }
  const count = Math.min(1000, Math.max(1, parseInt($("#item-count").value, 10) || 1));
  rememberItem(id);
  const existing = kit.items.find((it) => it.id === id);
  if (existing) existing.count = Math.min(1000, existing.count + count); else kit.items.push({ id, count });
  saveKits(); renderKits();
  toast(`Added ${count}× ${itemInfo(id).name} to ${kit.name}`);
}

async function giveKit(ki, btn) {
  const character = $("#item-char").value.trim();
  if (!character) { toast("Pick a character first"); return; }
  const kit = kitsData.kits[ki];
  btn.disabled = true;
  try {
    const res = await fetch("/api/admin/give-kit", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ character, kit: kit.name }) });
    const d = await res.json();
    toast(d.ok ? `Mailed kit "${d.kit}" (${d.items} items, ${d.mails} mail${d.mails === 1 ? "" : "s"}) to ${character}` : "Error: " + d.error);
  } catch (e) { toast("Request failed"); }
  btn.disabled = false;
}

$("#kit-create").addEventListener("click", () => {
  const n = $("#kit-new-name").value.replace(/[^A-Za-z0-9 _-]/g, "").trim().slice(0, 40);
  if (!n) { toast("Give the kit a name"); return; }
  if (kitsData.kits.some((k) => k.name.toLowerCase() === n.toLowerCase())) { toast("A kit with that name exists"); return; }
  kitsData.kits.push({ name: n, items: [] });
  kitOpen.add(n); saveKitOpen();
  $("#kit-new-name").value = "";
  saveKits(); renderKits(); $("#kit-target").value = n;
});
$("#kit-new-name").addEventListener("keydown", (e) => { if (e.key === "Enter") $("#kit-create").click(); });

// ---------- item tooltips (hover any element with data-tip="<item id>") ----------
const tipCache = {};
let tipFor = null, tipTimer = null;

function renderTip(t) {
  const q = (QUALITY[t.quality] || QUALITY[1])[1];
  return `<div class="tip-name" style="color:${q}">${esc(t.name)}</div>` + t.lines.map((l) =>
    l.r ? `<div class="tip-row"><span>${esc(l.l)}</span><span>${esc(l.r)}</span></div>`
        : `<div class="${l.c || ""}" style="white-space:pre-wrap">${esc(l.l)}</div>`).join("") + `<div class="tip-id">Item ${t.id}</div>`;
}

function placeTip(x, y) {
  const el = $("#item-tip"), w = el.offsetWidth, h = el.offsetHeight;
  el.style.left = Math.max(8, Math.min(x + 16, window.innerWidth - w - 8)) + "px";
  el.style.top = Math.max(8, Math.min(y + 16, window.innerHeight - h - 8)) + "px";
}

async function showTip(id, x, y) {
  const el = $("#item-tip");
  if (!tipCache[id]) {
    try {
      const d = await (await fetch("/api/admin/item-tip?id=" + id)).json();
      if (d.error) throw new Error(d.error);
      tipCache[id] = d;
    } catch (e) { tipCache[id] = { id, name: "Item " + id, quality: 1, lines: [{ l: "No tooltip: " + e.message, c: "dim" }] }; }
  }
  if (tipFor !== id) return; // the mouse has already moved on
  el.innerHTML = renderTip(tipCache[id]);
  el.style.display = "block";
  placeTip(x, y);
}

function hideTip() { clearTimeout(tipTimer); tipFor = null; $("#item-tip").style.display = "none"; }

document.addEventListener("mouseover", (e) => {
  const t = e.target.closest ? e.target.closest("[data-tip]") : null;
  if (!t) return;
  const id = +t.dataset.tip;
  if (tipFor === id) return;
  tipFor = id;
  clearTimeout(tipTimer);
  const x = e.clientX, y = e.clientY;
  tipTimer = setTimeout(() => showTip(id, x, y), tipCache[id] ? 0 : 120);
});
document.addEventListener("mousemove", (e) => { if ($("#item-tip").style.display === "block") placeTip(e.clientX, e.clientY); });
document.addEventListener("mouseout", (e) => {
  const t = e.target.closest ? e.target.closest("[data-tip]") : null;
  if (t && !(e.relatedTarget && t.contains(e.relatedTarget))) hideTip();
});
document.addEventListener("scroll", hideTip, true);

function itemSearchSoon() { clearTimeout(itemTimer); itemTimer = setTimeout(() => { itemPage = 1; loadItems(); }, 300); }
["#item-search", "#item-min", "#item-max"].forEach((sel) => $(sel).addEventListener("input", itemSearchSoon));
["#item-quality", "#item-class", "#item-sub", "#item-slot", "#item-hide"].forEach((sel) => $(sel).addEventListener("change", itemSearchSoon));
