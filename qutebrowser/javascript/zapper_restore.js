// SPDX-License-Identifier: GPL-3.0-or-later
//
// Clears saved zapper settings for the current URL and unhides elements
"use strict";
(function() {
    const HIDDEN_CLASS = "__qute_zapper_hidden";

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

    // Remove the injected style
    const loadStyle = document.getElementById("__qute_zapper_load_style");
    if (loadStyle) {
        loadStyle.remove();
    }

    // Un-hide elements 
    try {
        const hiddenElems = document.querySelectorAll(`.${HIDDEN_CLASS}`);
        for (let i = 0; i < hiddenElems.length; i++) {
            hiddenElems[i].classList.remove(HIDDEN_CLASS);
            hiddenElems[i].style.removeProperty("display");
        }
    } catch (err) {
        /* ignore */
    }
})();

