// SPDX-License-Identifier: GPL-3.0-or-later
//
// Deletes zapper settings for the current URL
"use strict";
(function() {
    // Generate the same unique storage key based on the current URL
    function getStorageKey() {
        const url = window.location.origin + window.location.pathname;
        return `__qute_zapper_persist_${ btoa(url)
            .replace(/[^a-zA-Z0-9_-]/g, "_")
            .slice(0, 50)}`;
    }
    try {
        localStorage.removeItem(getStorageKey());
    } catch (err) {
        /* ignore */
    }
})();

