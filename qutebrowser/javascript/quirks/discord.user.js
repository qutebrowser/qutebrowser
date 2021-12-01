// ==UserScript==
// @include https://discord.com/*
// ==/UserScript==

// Workaround for Discord's silly bot detection (or whatever it is logging
// people out with vertical tabs).

"use strict";

Object.defineProperty(window, "outerWidth", {
    get() {
        return window.innerWidth;
    },
});
