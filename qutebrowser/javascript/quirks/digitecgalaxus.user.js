// ==UserScript==
// @include https://id.digitecgalaxus.ch/*
// @include https://id.galaxus.eu/*
// ==/UserScript==

// Needed because their /api/v1/login/_actions/find-user endpoint claims
// that the user does not exist (!?) with the default UA

"use strict";

const originalUserAgent = navigator.userAgent;

Object.defineProperty(navigator, "userAgent", {
    get() {
        return originalUserAgent.replace(/QtWebEngine\/[\d.]+ /, "");
    },
});
