// SPDX-License-Identifier: GPL-3.0-or-later
//
// Restores previously saved zapper settings for a certain url.
// Used on website reload, to create hiding persistence.
"use strict";
(function() {
    // Generate the same unique storage key based on the current URL
    function getStorageKey() {
        const url = window.location.origin + window.location.pathname;
        const encoded = btoa(url)
            .replace(/[^a-zA-Z0-9_-]/g, "_")
            .slice(0, 50);
        return `__qute_zapper_persist_${ encoded}`;
    }

    // data: some URLs disable web storage
    if (window.location.origin === "null") {
        return;
    }

    let stored;
    try {
        stored = localStorage.getItem(getStorageKey());
    } catch (err) {
        return;
    }
    if (!stored) {return;}

    let selectors;
    try {
        selectors = JSON.parse(stored);
    } catch (err) {
        return;
    }
    if (!Array.isArray(selectors) || selectors.length === 0) {return;}

    // Wrap selectors in hide element rule
    const css = selectors
        .map(selector => `${selector} { display: none !important; }`)
        .join("\n");

    function injectStyle(doc) {
        try {
            const style = doc.createElement("style");
            style.id = "__qute_zapper_load_style";
            style.textContent = css;
            (doc.head || doc.documentElement).appendChild(style);
        } catch (err) {
            /* cross-origin, skip */
        }
    }

    // Apply to main document
    injectStyle(document);
})();

