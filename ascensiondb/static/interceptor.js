// This is an offline mirror of db.ascension.gg pulled from the Wayback Machine -- there is no live
// backend behind it, so the site's own SPA click handlers (global.js's delegated 'a' click routing,
// incl. the top nav which locale_enus.js builds client-side with relative hrefs like "?item=123")
// will AJAX-fail silently and fall back to re-rendering the home content, which looks like "the link
// just goes to the front page". Intercept in the capture phase (before their handlers run): for
// internal links, do a real navigation to our own /ascensiondb/ route (which serves the matching
// mirrored page if we have one, or a "not archived" fallback otherwise); for genuinely external
// links (discord, wiki, ...) do nothing and let the browser handle it natively.
(function () {
    function resolveLocal(raw) {
        var qp = raw;
        var m = /^https?:\/\/[^/]*ascension\.gg(\/.*)?$/i.exec(raw);
        if (m) qp = m[1] || '/';
        if (qp.charAt(0) !== '/' && qp.charAt(0) !== '?') qp = '/' + qp;
        if (qp.charAt(0) === '/') qp = qp.slice(1);
        return '/ascensiondb/' + qp;
    }
    function isInternal(raw) {
        if (!raw || raw === '#' || raw.indexOf('javascript:') === 0) return false;
        if (/^https?:\/\//i.test(raw) && !/ascension\.gg/i.test(raw)) return false; // external (discord, wiki, ...)
        if (raw.indexOf('/ascensiondb/static/') !== -1) return false; // our own mirrored assets
        if (raw.indexOf('/ascensiondb/pages/') !== -1) return false; // direct page link, already local
        return true;
    }
    document.addEventListener('click', function (e) {
        var a = e.target.closest && e.target.closest('a[href]');
        if (!a) return;
        var raw = a.getAttribute('href') || '';
        if (!isInternal(raw)) return;
        e.preventDefault();
        e.stopImmediatePropagation();
        window.location.href = resolveLocal(raw);
    }, true);
    document.addEventListener('mouseup', function (e) {
        var a = e.target.closest && e.target.closest('a[href]');
        if (!a) return;
        var raw = a.getAttribute('href') || '';
        if (!isInternal(raw)) return;
        e.preventDefault();
        e.stopImmediatePropagation();
    }, true);
})();
