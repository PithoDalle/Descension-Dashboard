'use strict';
/* Pure gating + cap engine for the on-site COA talent builder.
 *
 * No DOM access, no window.ASC (only reads window.ASC_TREE, set by app/tree.js).
 * Loaded via <script> before app.js in the browser (defines top-level globals:
 * BEspent, BEcanAdd, BEadd, BEremove, BEstatus) and module.exports-ed for Node tests.
 *
 * sel shape: { <nodeId>: pointsSpent }
 * node shape (window.ASC_TREE.nodes[id]): { ae, te, rAE, rTE, req, cls, tab, lvl, max, ... }
 *
 * Gating rule for "can this node accept +1 point?" (mirrors
 * the build validator's gates_ok() for the tab AE/TE portion, plus the
 * cap/req/level checks specified for the on-site builder):
 *   1. points < max
 *   2. total.ae + node.ae <= CAP.ae  AND  total.te + node.te <= CAP.te
 *   3. spent[tab].ae >= node.rAE  AND  spent[tab].te >= node.rTE
 *   4. every id in node.req is present in sel at its own max (fully maxed)
 *   5. LEVEL-UNLOCK PASSIVES (0-cost right-column talents, lvl 15/20/30/40/50) unlock on points
 *      spent IN THEIR OWN tree: (lvl-8)/2 points — 6→20, 11→30, 16→40, 21→50. Per-tree (not the
 *      combined total, not the other tree) and chain-free, so investing a single tree (up to 26
 *      points) unlocks every one of that tree's level passives. Normal essence talents (all
 *      lvl<=10) are unaffected by this gate.
 *   6. connectivity (mirrors validate_builds.py rule 1, is_starting()/"no connected
 *      prereq taken"): the node must be a starting node, OR at least one id in
 *      node.conn (connectedNodeIds) must already be selected (points > 0).
 *      EXCEPTION: level-unlock passives (isLevelUnlock — 0-cost, no-prereq, level-gated
 *      right-column talents) skip this; they unlock by character level alone (rule 5), so
 *      you never have to click up their same-tree chain.
 * spent/total are computed from the CURRENT sel (before adding the new point), so a
 * node's own point never counts toward unlocking itself -- self-exclusion is automatic.
 */
(function (root) {
  var CAP = { ae: 26, te: 25 };
  var LEVEL_CAP = 60;

  // nodesOf() reads window.ASC_TREE FRESH on every call (never cached at module load).
  // tree.js is lazy-loaded AFTER builder-engine.js in the browser, so window.ASC_TREE is
  // undefined at IIFE-load time; caching it into a module-scope var would permanently
  // freeze the engine on an empty tree.
  function nodesOf() {
    var g = (typeof window !== 'undefined' ? window : (root.window || root || {}));
    var tree = g.ASC_TREE;
    return (tree && tree.nodes) || {};
  }

  // BEspent(sel) -> { tab: { <tabId>: {ae,te} }, total: {ae,te} }
  // Sums ae/te per (node's own tab) over sel ONLY -- never mixes in nodes outside sel,
  // since tab ids (e.g. 87, the class tree) are reused across classes.
  function BEspent(sel) {
    var out = { tab: {}, total: { ae: 0, te: 0 } };
    var nodes = nodesOf();
    if (!sel) return out;
    for (var id in sel) {
      var pts = sel[id];
      if (!pts) continue;
      var n = nodes[id];
      if (!n) continue;
      var tab = n.tab;
      if (!out.tab[tab]) out.tab[tab] = { ae: 0, te: 0 };
      var ae = n.ae * pts;
      var te = n.te * pts;
      out.tab[tab].ae += ae;
      out.tab[tab].te += te;
      out.total.ae += ae;
      out.total.te += te;
    }
    return out;
  }

  // --- either/or "choice" groups: two co-located nodes share one nonzero `group` and are mutually
  // exclusive (retail-style choice node). At most ONE of the pair may hold a point; picking one
  // clears the other. groupIndex() is built once per ASC_TREE object (cheap, then cached). ---
  var _grpIdx = null, _grpForNodes = null;
  function groupIndex() {
    var nodes = nodesOf();
    if (_grpForNodes === nodes) return _grpIdx;   // same tree object -> reuse
    var idx = {};
    for (var id in nodes) { var g = nodes[id].group; if (g) (idx[g] = idx[g] || []).push(+id); }
    _grpIdx = idx; _grpForNodes = nodes;
    return idx;
  }
  // The OTHER node id in this node's choice group (null if it's not a choice node).
  function groupSiblingId(id) {
    var nodes = nodesOf(), n = nodes[id];
    if (!n || !n.group) return null;
    var arr = groupIndex()[n.group] || [];
    for (var i = 0; i < arr.length; i++) if (arr[i] !== +id) return arr[i];
    return null;
  }
  // sel with a node's choice sibling removed (used to gate a "swap" — picking one option auto-clears
  // the other, so the add is evaluated as if the sibling's point were already gone).
  function selWithoutSibling(id, sel) {
    var sib = groupSiblingId(id);
    if (sib == null || !sel[sib]) return sel;
    var out = {}; for (var k in sel) if (k !== String(sib)) out[k] = sel[k];
    return out;
  }

  // isLevelUnlock(n) -> bool. The right-column "level unlock" passives: 0-cost, no prerequisite,
  // gated on a level (node.lvl 15/20/30/40/50). They unlock on points spent in THEIR OWN tree —
  // NOT a same-tree chain and NOT the other tree — so a single tree unlocks all of its own level
  // passives (levelTreeReq below). They bypass connectivity; the per-tree points gate holds them.
  function isLevelUnlock(n) {
    return (n.ae || 0) === 0 && (n.te || 0) === 0 && (n.lvl || 0) > 10 && !(n.req && n.req.length);
  }

  // Points required IN A SINGLE TREE to unlock a level-N passive: (N - 8) / 2, i.e. 6→lvl20,
  // 11→lvl30, 16→lvl40, 21→lvl50 (and 4→lvl15). A tree holds up to 26 points, which covers every
  // level passive. Rounded up so an odd level (15) needs a whole point.
  function levelTreeReq(lvl) { return Math.max(0, Math.ceil(((lvl || 0) - 8) / 2)); }

  // isStarting(n) -> bool. Mirrors the build validator's is_starting():
  // isStartingNode == 1 (exact match -- one node in the data has a garbage 127 value,
  // which must NOT count as starting) OR connectedNodeIds is empty (the 208 true tab
  // roots, which the extractor consistently leaves with an empty conn list).
  function isStarting(n) {
    return n.st === 1 || !(n.conn && n.conn.length);
  }

  // connectivityOk(n, sel) -> bool. A node is reachable iff it's a starting node, or a
  // connected neighbor is satisfied. OUT-OF-ORDER building: the two trees are independent,
  // so a connector that is AUTO-granted (always present) or lives in a DIFFERENT tab counts
  // as satisfied — you can fill the whole spec tree without touching the class tree (or vice
  // versa) instead of being forced to alternate. Same-tab connectors still need a point.
  function connectivityOk(n, sel) {
    if (isStarting(n)) return true;
    var nodes = nodesOf();
    var conn = n.conn || [];
    for (var i = 0; i < conn.length; i++) {
      var cid = conn[i], cn = nodes[cid];
      if (cn && (cn.auto || cn.tab !== n.tab)) return true; // auto / cross-tree -> satisfied
      if ((sel[cid] || 0) > 0) return true;
    }
    return false;
  }

  // reqsMaxed(n, sel): explicit requiredIds must be at max. AUTO-granted prereqs are always
  // present, and CROSS-TAB prereqs are satisfied independently (out-of-order building), so
  // both are skipped — only same-tab, non-auto prereqs actually gate a click.
  function reqsMaxed(n, sel) {
    var nodes = nodesOf();
    var req = n.req || [];
    for (var i = 0; i < req.length; i++) {
      var rid = req[i];
      var rn = nodes[rid];
      if (!rn) return false; // unresolvable req id -- fail closed
      if (rn.auto || rn.tab !== n.tab) continue; // auto / cross-tree -> treated satisfied
      var have = (sel && sel[rid]) || 0;
      if (have < rn.max) return false;
    }
    return true;
  }

  // BEcanAdd(id, sel) -> bool
  function BEcanAdd(id, sel) {
    var nodes = nodesOf();
    var n = nodes[id];
    if (!n) return false;
    sel = sel || {};

    var pts = sel[id] || 0;
    if (pts >= n.max) return false;
    if ((n.lvl || 0) > LEVEL_CAP) return false;

    // either/or: adding this option auto-clears its group sibling, so gate against a sel with the
    // sibling removed — a swap costs only the net essence difference and re-uses the same cell.
    var gs = selWithoutSibling(id, sel);
    var spent = BEspent(gs);
    var tabSpent = spent.tab[n.tab] || { ae: 0, te: 0 };
    if (tabSpent.ae < n.rAE || tabSpent.te < n.rTE) return false;

    // level-unlock passive: needs (lvl-8)/2 points spent IN ITS OWN tree (6→20 … 21→50). Per-tree
    // and chain-free, so investing a single tree unlocks all of that tree's level passives.
    if (isLevelUnlock(n) && (tabSpent.ae + tabSpent.te) < levelTreeReq(n.lvl)) return false;

    if (spent.total.ae + n.ae > CAP.ae) return false;
    if (spent.total.te + n.te > CAP.te) return false;

    if (!reqsMaxed(n, gs)) return false;

    // Level-unlock passives bypass the connectivity chain — level alone unlocks them.
    if (!isLevelUnlock(n) && !connectivityOk(n, gs)) return false;

    return true;
  }

  // BEadd(id, sel) -> new sel (or the same sel, unchanged, if illegal). For a choice node, selecting
  // one option first clears its group sibling (one point per either/or pair).
  function BEadd(id, sel) {
    sel = sel || {};
    if (!BEcanAdd(id, sel)) return sel;
    var out = {};
    for (var k in sel) out[k] = sel[k];
    var sib = groupSiblingId(id);
    if (sib != null && out[sib]) { delete out[sib]; }
    out[id] = (out[id] || 0) + 1;
    // clearing the sibling may have orphaned nodes that depended on it — cascade to a fixpoint.
    if (sib != null) {
      var changed = true;
      while (changed) {
        changed = false;
        for (var nid in out) { if (out[nid] && nid !== String(id) && !nodeStillLegal(nid, out)) { delete out[nid]; changed = true; } }
      }
    }
    return out;
  }

  // Is a currently-placed node (with its own points already counted in sel) still
  // legally unlocked? Checks the tab-essence gate and req-maxed condition using sel
  // WITHOUT this node's own contribution (self-exclusion), mirroring BEcanAdd.
  function nodeStillLegal(id, sel) {
    var nodes = nodesOf();
    var n = nodes[id];
    if (!n) return false;
    var pts = sel[id] || 0;
    if (pts <= 0) return true;
    if (pts > n.max) return false;
    if ((n.lvl || 0) > LEVEL_CAP) return false;

    var selWithout = {};
    for (var k in sel) { if (k !== String(id)) selWithout[k] = sel[k]; }

    var spent = BEspent(selWithout);
    var tabSpent = spent.tab[n.tab] || { ae: 0, te: 0 };
    if (tabSpent.ae < n.rAE || tabSpent.te < n.rTE) return false;

    // per-tree level gate (see BEcanAdd): if removing points from THIS tree dropped it below the
    // passive's (lvl-8)/2 requirement, it's no longer legal and the cascade drops it. The passive
    // is 0-cost so its own point never counts toward the requirement.
    if (isLevelUnlock(n) && (tabSpent.ae + tabSpent.te) < levelTreeReq(n.lvl)) return false;

    if (!reqsMaxed(n, sel)) return false;

    if (!isLevelUnlock(n) && !connectivityOk(n, selWithout)) return false;

    return true;
  }

  // BEremove(id, sel) -> new sel with one point removed from `id` (decrement, not a full
  // clear -- right-click/shift-click == -1 per spec; multi-rank nodes step down one rank
  // at a time), cascading: drop any still-selected node whose gating no longer holds,
  // iterated to a fixpoint.
  function BEremove(id, sel) {
    sel = sel || {};
    var out = {};
    for (var k in sel) out[k] = sel[k];
    out[id] = (out[id] || 0) - 1;
    if (out[id] <= 0) delete out[id];

    var changed = true;
    while (changed) {
      changed = false;
      for (var nid in out) {
        if (!out[nid]) continue;
        if (!nodeStillLegal(nid, out)) {
          delete out[nid];
          changed = true;
        }
      }
    }
    return out;
  }

  // BEstatus(id, sel) -> "maxed" | "available" | "locked"
  function BEstatus(id, sel) {
    var nodes = nodesOf();
    var n = nodes[id];
    if (!n) return 'locked';
    sel = sel || {};
    var pts = sel[id] || 0;
    if (pts >= n.max) return 'maxed';
    if (BEcanAdd(id, sel)) return 'available';
    return 'locked';
  }

  // BEencode(sel) -> Promise<string> base64 Ascension build code.
  // Format (byte-identical to a real Ascension export): per selected node
  // ":"+id+"t"+points, concatenated in sel-key order, trailing ":", raw-DEFLATE
  // ('deflate-raw', native CompressionStream -- no external libs, CSP forbids them),
  // then base64.
  async function BEencode(sel) {
    // Omit auto-granted (eN "Unavailable") nodes — the real builder can't allocate them,
    // so a code containing one is rejected outright. tree.js flags them `auto`.
    var nodes = nodesOf();
    var s = Object.keys(sel).filter(function (id) {
      return sel[id] > 0 && !(nodes[id] && nodes[id].auto);
    }).map(function (id) { return ":" + id + "t" + sel[id]; }).join("") + ":";
    var cs = new CompressionStream("deflate-raw");
    var w = cs.writable.getWriter(); w.write(new TextEncoder().encode(s)); w.close();
    var buf = new Uint8Array(await new Response(cs.readable).arrayBuffer());
    var bin = ""; buf.forEach(function (b) { bin += String.fromCharCode(b); }); return btoa(bin);
  }

  // BErawcode(sel) -> string: the RAW in-game "game string" ( ':id t pts:...:' ) — BEencode's
  // pre-compression form. This is what you paste into COA's IN-GAME build import (the ?build=
  // base64 URL is browser-only; the game reads the 'voljin' slug from it and can't decode it).
  // Omits auto-granted (eN) nodes, same as BEencode. Returns "" when nothing is selected.
  function BErawcode(sel) {
    var nodes = nodesOf();
    var parts = Object.keys(sel || {}).filter(function (id) {
      return sel[id] > 0 && !(nodes[id] && nodes[id].auto);
    }).map(function (id) { return ":" + id + "t" + sel[id]; });
    return parts.length ? (parts.join("") + ":") : "";
  }

  // BEdecode(codeOrUrl) -> Promise<{sel, unknown}>. Accepts a bare code OR a full
  // ".../overview/<code>" URL (the prefix is stripped). unknown lists ids present in
  // the decoded code that are not in window.ASC_TREE.nodes.
  async function BEdecode(codeOrUrl) {
    var code = String(codeOrUrl).trim();
    // Accept: a bare base64 code, a "?build=<code>" URL (the real Ascension share format),
    // or a legacy ".../overview/<code>" path.
    var m = code.match(/[?&]build=([^&#\s]+)/);
    if (m) code = m[1];
    else code = code.replace(/^https?:\/\/[^]*?\/(?:overview|voljin)\//, "");
    // URL-decode (codes pasted from a link are percent-encoded: %2F, %2B). Harmless on a raw
    // base64 code (it has no % sequences). decodeURIComponent leaves '+' intact (not a space).
    try { code = decodeURIComponent(code); } catch (e) {}
    code = code.replace(/\s+/g, "");
    var nodes = nodesOf();
    // A raw 'game string' (":id t pts:...:") is the already-decompressed form (Ascension's
    // in-game import value) — it has colons, which base64 never does, so parse it directly.
    if (code.indexOf(":") !== -1 && /^[:\dt]+$/.test(code)) {
      var rsel = {}, runk = [], rre = /:(\d+)t(\d+)/g, rm;
      while ((rm = rre.exec(code))) { var rid = +rm[1], rp = +rm[2]; if (!nodes[rid]) runk.push(rid); rsel[rid] = rp; }
      return { sel: rsel, unknown: runk };
    }
    var bin = atob(code), bytes = new Uint8Array(bin.length); for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    var ds = new DecompressionStream("deflate-raw"); var w = ds.writable.getWriter(); w.write(bytes); w.close();
    var out = new TextDecoder().decode(await new Response(ds.readable).arrayBuffer());
    var sel = {}, unknown = []; var re = /:(\d+)t(\d+)/g, m;
    while ((m = re.exec(out))) { var id = +m[1], p = +m[2]; if (!nodes[id]) unknown.push(id); sel[id] = p; }
    return { sel: sel, unknown: unknown };
  }

  root.BEspent = BEspent;
  root.BEcanAdd = BEcanAdd;
  root.BEadd = BEadd;
  root.BEremove = BEremove;
  root.BEstatus = BEstatus;
  root.BEencode = BEencode;
  root.BErawcode = BErawcode;
  root.BEdecode = BEdecode;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { BEspent: BEspent, BEcanAdd: BEcanAdd, BEadd: BEadd, BEremove: BEremove, BEstatus: BEstatus, BEencode: BEencode, BErawcode: BErawcode, BEdecode: BEdecode };
  }
})(typeof window !== 'undefined' ? window : (typeof global !== 'undefined' ? global : this));
