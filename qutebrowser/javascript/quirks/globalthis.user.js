// ==UserScript==
// @include https://www.reddit.com/*
// @include https://open.spotify.com/*
// ==/UserScript==

// Polyfill for a failing globalThis with older Qt versions.

"use strict";
window.globalThis = window;
