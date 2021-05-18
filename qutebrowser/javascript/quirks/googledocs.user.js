// ==UserScript==
// @include https://docs.google.com/*
// ==/UserScript==

// Workaround for typing dead keys on Google Docs
// See https://bugreports.qt.io/browse/QTBUG-69652

"use strict";

Object.defineProperty(navigator, "userAgent", {
    get() {
        return "Mozilla/5.0 (X11; Linux x86_64; rv:88.0) Gecko/20100101 Firefox/88.0";
    },
});
