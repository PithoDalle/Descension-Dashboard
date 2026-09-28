/* Local-only "Armory" tab: an Armory-style view of a bot's equipped items, with a picker to mail a
 * replacement into any slot. Not part of upstream squidbots-dashboard -- kept in its own file so
 * dashboard.js/dashboard.css stay a clean diff against Zyth45/squidbots-dashboard. See
 * dashboard_squidbots_module memory for why this calls the *parent* dashboard's API (127.0.0.1:8877)
 * instead of squidbots' own (this iframe's own server has no console/mail access -- only the parent
 * dashboard does), and why "give" is mail, not an instant equip (no headless equip path exists).
 */
const PARENT_API = "http://127.0.0.1:8877";

let gearBot = null;
let gearPickerSlot = null;
let gearPickerPage = 1;

const gearSearchInput = document.getElementById("gearSearch");
const gearSearchResults = document.getElementById("gearSearchResults");

gearSearchInput.placeholder = "";
function gearApplyWords() { gearSearchInput.placeholder = W.gearSearch; }
gearApplyWords();

// Debounced (200ms) so a fast typist doesn't fire a request per keystroke; a stale in-flight
// request that resolves after a newer one is dropped via the sequence counter.
let gearSearchTimer = null;
let gearSearchSeq = 0;
function gearSearchBots() {
  clearTimeout(gearSearchTimer);
  gearSearchTimer = setTimeout(gearSearchRun, 200);
}
async function gearSearchRun() {
  const q = gearSearchInput.value.trim();
  if (!q) { gearSearchResults.hidden = true; return; }
  const seq = ++gearSearchSeq;
  try {
    const rows = await (await fetch(PARENT_API + "/api/admin/char-search?q=" + encodeURIComponent(q))).json();
    if (seq !== gearSearchSeq) return;
    if (!Array.isArray(rows) || !rows.length) {
      gearSearchResults.innerHTML = `<div class="results-empty">${esc(W.noData)}</div>`;
      gearSearchResults.hidden = false;
      return;
    }
    gearSearchResults.innerHTML = rows.map((r, i) =>
      `<button type="button" data-bot="${esc(r.name)}" data-idx="${i}">${r.online ? "\u{1F7E2}" : "⚪"}&nbsp; ${esc(r.name)}
        <span class="tag ${r.bot ? "tag-bot" : "tag-player"}">${r.bot ? "Bot" : "Player"}</span>
        <span class="meta">lvl ${r.level} ${esc(r.class)}</span></button>`).join("");
    gearSearchResults.hidden = false;
    gearSearchActiveIdx = -1;
    gearSearchResults.querySelectorAll("[data-bot]").forEach((b) => b.addEventListener("click", () => gearSearchPick(b.dataset.bot)));
  } catch (error) { gearSearchResults.hidden = true; }
}
function gearSearchPick(name) {
  gearSearchInput.value = name;
  gearSearchResults.hidden = true;
  gearLoad(name);
}
gearSearchInput.addEventListener("input", gearSearchBots);
document.addEventListener("click", (e) => {
  if (!e.target.closest("#gearSearchResults") && e.target !== gearSearchInput) gearSearchResults.hidden = true;
});

// Keyboard navigation: Down/Up move a highlighted row, Enter picks it, Escape closes the list.
let gearSearchActiveIdx = -1;
gearSearchInput.addEventListener("keydown", (e) => {
  if (gearSearchResults.hidden) return;
  const buttons = gearSearchResults.querySelectorAll("[data-bot]");
  if (!buttons.length) return;
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    gearSearchActiveIdx = (gearSearchActiveIdx + (e.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length;
    buttons.forEach((b, i) => b.classList.toggle("active", i === gearSearchActiveIdx));
    buttons[gearSearchActiveIdx].scrollIntoView({ block: "nearest" });
  } else if (e.key === "Enter" && gearSearchActiveIdx >= 0) {
    e.preventDefault();
    gearSearchPick(buttons[gearSearchActiveIdx].dataset.bot);
  } else if (e.key === "Escape") {
    gearSearchResults.hidden = true;
  }
});

// "All characters" browse-all modal: the small name-search dropdown above is capped at 20 rows
// (a live-typing autocomplete, not a roster), so this is a separate, explicit way to page through
// literally every character -- 100 per page, see list_characters() in dashboard_server.py.
const gearBrowsePicker = document.getElementById("gearBrowsePicker");
let gearBrowsePage = 1;
let gearBrowseTimer = null;
document.getElementById("gearBrowseOpen").addEventListener("click", () => {
  gearBrowsePage = 1;
  document.getElementById("gearBrowseSearch").value = "";
  document.getElementById("gearBrowseMinLevel").value = "";
  document.getElementById("gearBrowseMaxLevel").value = "";
  document.getElementById("gearBrowseClass").value = "";
  document.getElementById("gearBrowseRole").value = "";
  gearBrowsePicker.hidden = false;
  gearLoadBrowse();
});
document.getElementById("gearBrowseClose").addEventListener("click", () => { gearBrowsePicker.hidden = true; });
document.getElementById("gearBrowseSearch").addEventListener("input", () => {
  clearTimeout(gearBrowseTimer);
  gearBrowseTimer = setTimeout(() => { gearBrowsePage = 1; gearLoadBrowse(); }, 200);
});
// Level range debounced like the name filter (typing "6" then "0" for level 60 shouldn't fire a
// request on the "6" alone); class/role dropdowns reset the page immediately, no debounce needed.
["gearBrowseMinLevel", "gearBrowseMaxLevel"].forEach((id) => {
  document.getElementById(id).addEventListener("input", () => {
    clearTimeout(gearBrowseTimer);
    gearBrowseTimer = setTimeout(() => { gearBrowsePage = 1; gearLoadBrowse(); }, 400);
  });
});
["gearBrowseClass", "gearBrowseRole"].forEach((id) => {
  document.getElementById(id).addEventListener("change", () => { gearBrowsePage = 1; gearLoadBrowse(); });
});
let gearBrowseClassesLoaded = false;

async function gearLoadBrowse() {
  const p = new URLSearchParams({
    q: document.getElementById("gearBrowseSearch").value.trim(), page: gearBrowsePage,
    min: document.getElementById("gearBrowseMinLevel").value.trim(),
    max: document.getElementById("gearBrowseMaxLevel").value.trim(),
    class: document.getElementById("gearBrowseClass").value,
    role: document.getElementById("gearBrowseRole").value,
  });
  const host = document.getElementById("gearBrowseResults");
  host.innerHTML = `<p class="empty">${esc(W.measuring)}</p>`;
  try {
    const d = await (await fetch(PARENT_API + "/api/admin/char-list?" + p)).json();
    if (d.error) throw new Error(d.error);
    if (!gearBrowseClassesLoaded && d.classes) {
      gearBrowseClassesLoaded = true;
      const sel = document.getElementById("gearBrowseClass");
      for (const c of d.classes) sel.append(new Option(c.name, c.id));
    }
    host.innerHTML = d.rows.length
      ? d.rows.map((r) => `<button type="button" data-bot="${esc(r.name)}">
          <span class="browse-row-top">${r.online ? "\u{1F7E2}" : "⚪"}
            ${r.race ? `<img class="race-icon" src="static/race-icons/races_${r.race}-${r.gender}.png" alt="${esc(r.race)}">` : ""}
            <b>${esc(r.name)}</b></span>
          <span class="browse-row-tags">
            <span class="tag ${r.bot ? "tag-bot" : "tag-player"}">${r.bot ? "Bot" : "Player"}</span>
            <span class="tag tag-${r.faction}">${r.faction === "alliance" ? "Alliance" : "Horde"}</span>
          </span>
          <span class="meta">lvl ${r.level} ${esc(r.class)}</span></button>`).join("")
      : `<div class="browse-results-empty">${esc(W.noData)}</div>`;
    document.getElementById("gearBrowsePager").innerHTML =
      `<span class="meta">${d.total.toLocaleString()} · ${d.page}/${d.pages}</span>
      <span style="display:flex;gap:8px"><button class="btn small" id="gearBrowsePrev" type="button" ${d.page <= 1 ? "disabled" : ""}>←</button>
      <button class="btn small" id="gearBrowseNext" type="button" ${d.page >= d.pages ? "disabled" : ""}>→</button></span>`;
    document.getElementById("gearBrowsePrev").addEventListener("click", () => { gearBrowsePage--; gearLoadBrowse(); });
    document.getElementById("gearBrowseNext").addEventListener("click", () => { gearBrowsePage++; gearLoadBrowse(); });
    host.querySelectorAll("[data-bot]").forEach((b) => b.addEventListener("click", () => {
      gearBrowsePicker.hidden = true;
      gearSearchPick(b.dataset.bot);
    }));
    // Custom Ascension races have no icon file (list_characters() sends race: "" for them) and
    // some base-race/gender combos may still be missing from static/race-icons/ -- either way,
    // drop the broken-image box rather than show it.
    host.querySelectorAll(".race-icon").forEach((img) => { img.onerror = () => { img.style.display = "none"; }; });
  } catch (error) {
    host.innerHTML = `<p class="empty">${esc(error.message)}</p>`;
  }
}

function gearSlotBox(s) {
  return `<div class="armory-slot" data-slot="${s.slot}" data-label="${esc(s.label)}">
    <span class="icon" ${s.item ? `style="background-image:url('${PARENT_API}/item_icons/${encodeURIComponent(s.item.icon)}.png')"` : ""}></span>
    <div><div class="label">${esc(s.label)}</div>
    ${s.item ? `<div class="item-name gq${s.item.quality}">${esc(s.item.name)}</div>` : `<div class="item-name empty">${esc(W.gearEmpty)}</div>`}</div>
  </div>`;
}

async function gearLoad(name) {
  gearBot = name;
  const host = document.getElementById("gearBody");
  host.innerHTML = `<p class="empty">${esc(W.measuring)}</p>`;
  try {
    const d = await (await fetch(PARENT_API + "/api/admin/char-gear?name=" + encodeURIComponent(name))).json();
    if (d.error) throw new Error(d.error);
    const left = d.gear.slice(0, 8), right = d.gear.slice(8, 16), weapons = d.gear.slice(16, 19);
    host.innerHTML = `<div class="armory-cols">
        <div class="armory-col">${left.map(gearSlotBox).join("")}</div>
        <div class="armory-center">
          <div class="armory-name">${esc(d.name)}</div>
          <div class="armory-pills">
            <span class="armory-pill">⬆ ${esc(W.levelShort(d.level))}</span>
            <span class="armory-pill">${esc(d.class)}</span>
            <span class="armory-pill">${esc(d.race)}</span>
            <span class="tag ${d.bot ? "tag-bot" : "tag-player"}">${d.bot ? "Bot" : "Player"}</span>
            <span class="dot ${d.online ? "live" : "off"}"></span>
          </div>
          <div class="armory-model" id="armoryModel">
            <img class="armory-portrait" id="armoryPortrait" alt="${esc(d.race)}">
            <div class="armory-model-fallback" id="armoryModelFallback">No portrait for this race yet</div>
          </div>
        </div>
        <div class="armory-col">${right.map(gearSlotBox).join("")}</div>
      </div>
      <div class="armory-weapons">${weapons.map(gearSlotBox).join("")}</div>
      ${!d.online ? `<p class="empty" style="margin-top:14px">${esc(W.gearOffline)}</p>` : ""}`;
    host.querySelectorAll("[data-slot]").forEach((el) => el.addEventListener("click", () => gearOpenPicker(+el.dataset.slot, el.dataset.label)));
    gearLoadPortrait(d.race, d.gender);
    requestAnimationFrame(gearSizeModel);
  } catch (error) {
    host.innerHTML = `<p class="empty">${esc(error.message)}</p>`;
  }
}

// Sets the portrait box's height so its bottom edge lands exactly on the bottom of the taller
// of the two item columns (Wrist / Trinket 2) -- measured against the real rendered layout
// instead of relying on flexbox stretch, which couldn't be made to land on that edge reliably
// once the panel's own width (and so the columns' wrapped-text height) started changing.
function gearSizeModel() {
  const cols = document.querySelectorAll(".armory-col");
  const model = document.getElementById("armoryModel");
  if (!cols.length || !model) return;
  let maxBottom = 0;
  cols.forEach((c) => { const r = c.getBoundingClientRect(); if (r.bottom > maxBottom) maxBottom = r.bottom; });
  const h = maxBottom - model.getBoundingClientRect().top;
  if (h > 100) model.style.height = h + "px";
}
let gearResizeTimer = null;
window.addEventListener("resize", () => {
  if (!gearBot) return;
  clearTimeout(gearResizeTimer);
  gearResizeTimer = setTimeout(gearSizeModel, 150);
});

// A static race+gender portrait image instead of a live 3D model -- dropped the Three.js/glTF
// viewer entirely (see dashboard_squidbots_module memory for why: the exported model had no
// composited skin/face texture, and getting one meant reverse-engineering WoW's character
// texture-layer system, a genuinely separate project). Drop portrait files in as
// modules/squidbots/static/race-portraits/<race>_<gender>.<ext> (e.g. human_female.png) in any
// of a few common formats -- tries each extension in turn (squidbots.py's static route already
// serves all of them) so the user doesn't have to convert whatever format they already have.
const GEAR_PORTRAIT_EXTS = ["png", "jpg", "jpeg", "webp"];
function gearLoadPortrait(race, gender) {
  const img = document.getElementById("armoryPortrait");
  const fallback = document.getElementById("armoryModelFallback");
  if (!img || !fallback) return;
  img.style.display = "none";
  fallback.style.display = "flex";
  let i = 0;
  const tryNext = () => {
    if (i >= GEAR_PORTRAIT_EXTS.length) { img.style.display = "none"; fallback.style.display = "flex"; return; }
    img.src = `static/race-portraits/${race}_${gender}.${GEAR_PORTRAIT_EXTS[i++]}`;
  };
  img.onload = () => { img.style.display = "block"; fallback.style.display = "none"; };
  img.onerror = tryNext;
  tryNext();
}

const gearPicker = document.getElementById("gearPicker");
document.getElementById("gearPickerClose").addEventListener("click", () => { gearPicker.hidden = true; });
document.getElementById("gearPickerSearch").addEventListener("input", () => { gearPickerPage = 1; gearLoadPicker(); });

function gearOpenPicker(slot, label) {
  gearPickerSlot = slot;
  gearPickerPage = 1;
  document.getElementById("gearPickerTitle").textContent = W.gearChoose(label);
  document.getElementById("gearPickerSearch").value = "";
  gearPicker.hidden = false;
  gearLoadPicker();
}

// InventoryType values (item_template) that fit each equipment slot -- rings/trinkets share one
// type across their two slots, weapon slots (main/off/ranged) are left unfiltered since 1H/2H/
// shield/bow/gun/wand all differ and none should be hidden.
const GEAR_SLOT_TO_INVTYPE = { 0: 1, 1: 2, 2: 3, 14: 16, 4: 5, 3: 4, 18: 19, 8: 9, 9: 10, 5: 6, 6: 7, 7: 8,
  10: 11, 11: 11, 12: 12, 13: 12, 15: "", 16: "", 17: "" };

async function gearLoadPicker() {
  const p = new URLSearchParams({
    q: document.getElementById("gearPickerSearch").value.trim(),
    page: gearPickerPage, slot: GEAR_SLOT_TO_INVTYPE[gearPickerSlot] ?? "",
  });
  const host = document.getElementById("gearPickerResults");
  try {
    const d = await (await fetch(PARENT_API + "/api/admin/items?" + p)).json();
    if (d.error) throw new Error(d.error);
    host.innerHTML = d.rows.length
      ? d.rows.map((r) => `<button type="button" class="armory-slot" style="width:100%;margin-bottom:6px" data-pick="${r.entry}" data-name="${esc(r.name)}">
          <span class="icon" ${r.icon ? `style="background-image:url('${PARENT_API}/item_icons/${encodeURIComponent(r.icon)}.png')"` : ""}></span>
          <div><div class="item-name gq${r.Quality}">${esc(r.name)}</div><div class="label">iLvl ${r.ItemLevel} · req ${r.RequiredLevel}</div></div></button>`).join("")
      : `<p class="empty">${esc(W.noData)}</p>`;
    document.getElementById("gearPickerPager").innerHTML =
      `<span class="meta">${d.total.toLocaleString()} · ${d.page}/${d.pages}</span>
      <span style="display:flex;gap:8px"><button class="btn small" id="gearPagerPrev" type="button" ${d.page <= 1 ? "disabled" : ""}>←</button>
      <button class="btn small" id="gearPagerNext" type="button" ${d.page >= d.pages ? "disabled" : ""}>→</button></span>`;
    document.getElementById("gearPagerPrev").addEventListener("click", () => { gearPickerPage--; gearLoadPicker(); });
    document.getElementById("gearPagerNext").addEventListener("click", () => { gearPickerPage++; gearLoadPicker(); });
    host.querySelectorAll("[data-pick]").forEach((b) => b.addEventListener("click", () => gearGiveItem(b.dataset.pick, b.dataset.name)));
  } catch (error) {
    host.innerHTML = `<p class="empty">${esc(error.message)}</p>`;
  }
}

async function gearGiveItem(itemId, itemName) {
  if (!gearBot) return;
  try {
    const res = await fetch(PARENT_API + "/api/admin/give-item", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ character: gearBot, item: itemId, count: "1" }),
    });
    const d = await res.json();
    if (!d.ok) { alert("Error: " + d.error); return; }
    gearPicker.hidden = true;
    gearLoad(gearBot);
  } catch (error) { alert("Request failed: " + error.message); }
}

// Opens on a random bot by default (prefers an online one, server-side) instead of an empty
// search box -- only the first time the tab is visited each page load, not on every switch back
// to it, and never once a bot has actually been picked.
async function gearLoadRandom() {
  try {
    const d = await (await fetch(PARENT_API + "/api/admin/random-bot")).json();
    if (d.name) { gearSearchInput.value = d.name; gearLoad(d.name); }
  } catch (error) { /* leave the empty search box -- not fatal */ }
}
function gearMaybeAutoLoad() {
  if (location.hash.replace("#", "") === "gear" && !gearBot) gearLoadRandom();
}
window.addEventListener("hashchange", gearMaybeAutoLoad);
window.addEventListener("load", gearMaybeAutoLoad);
