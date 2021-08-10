// ==UserScript==
// @include https://www.reddit.com/*
// @include https://open.spotify.com/*
// @include https://test.qutebrowser.org/*
// ==/UserScript==

// Polyfill for a failing globalThis with older Qt versions.

"use strict";
window.globalThis = window;
