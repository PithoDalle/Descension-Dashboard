/* Local-mirror fixes (not part of the original site).
   1) The talent board scales via `zoom: min(1, 100cqw / (var(--bw) * 1px))`, which needs CSS
      length-division support. Browsers without it fall back to zoom:1 and clip the tree, so
      compute the same zoom in JS and set it inline. */
(function () {
  var TREE_SCALE = 0.9; // talent trees (builder + builds) drawn 10% smaller
  // Centre the node cluster (not the wider board box) horizontally in its panel. Measured, not computed, so it
  // is independent of the zoom units in play: probe how far 1px of margin moves the nodes, then apply the delta.
  function nodeCenter(b) {
    var l = Infinity, r = -Infinity;
    b.querySelectorAll(".bnode").forEach(function (n) {
      var q = n.getBoundingClientRect();
      if (q.width) { l = Math.min(l, q.left); r = Math.max(r, q.right); }
    });
    return r > l ? (l + r) / 2 : null;
  }
  function centerNodes(f, b) {
    b.style.marginLeft = "0px";
    var c0 = nodeCenter(b);
    if (c0 === null) return;
    b.style.marginLeft = "100px";
    var c1 = nodeCenter(b), per = (c1 - c0) / 100;
    if (!per) { b.style.marginLeft = "0px"; return; }
    var fr = f.getBoundingClientRect(), target = (fr.left + fr.right) / 2;
    b.style.marginLeft = ((target - c0) / per) + "px";
  }
  function fit() {
    document.querySelectorAll(".bld-fit").forEach(function (f) {
      var b = f.querySelector(".bld-board");
      var bw = parseFloat(getComputedStyle(f).getPropertyValue("--bw"));
      if (!b || !bw) return;
      var z = Math.min(1, f.clientWidth / bw) * TREE_SCALE;
      if (z > 0 && b.style.zoom !== String(z)) b.style.zoom = z;
      centerNodes(f, b);
    });
  }
  var raf = 0;
  function soon() { cancelAnimationFrame(raf); raf = requestAnimationFrame(fit); }
  new MutationObserver(soon).observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("resize", soon);
  soon();
})();

/* 2) Dashboard embed: render the whole site ~15% smaller so more fits in the tab. */
document.documentElement.style.zoom = "0.85";

/* 3) Hide Discord + feedback promotion (footer buttons, community banner, What's-new popup).
      The Discord invite is dead and feedback needs the original server.
      NB: `a.foot-disc` only -- the footer disclaimer <span> also has class foot-disc. */
(function () {
  var st = document.createElement("style");
  st.textContent = "a.foot-disc,.disc-cta,.whatsnew,.foot-cta,[data-feedback]{display:none!important}";
  document.head.appendChild(st);
})();
