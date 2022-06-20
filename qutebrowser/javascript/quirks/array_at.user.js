// ==UserScript==
// @include https://*.linkedin.com/*
// @include https://test.qutebrowser.org/*
// ==/UserScript==
//
// Based on: https://github.com/tc39/proposal-relative-indexing-method#polyfill

/* eslint-disable no-invalid-this */

"use strict";

(function() {
    function at(idx) {
        // ToInteger() abstract op
        let n = Math.trunc(idx) || 0;
        // Allow negative indexing from the end
        if (n < 0) {
            n += this.length;
        }
        // OOB access is guaranteed to return undefined
        if (n < 0 || n >= this.length) {
            return undefined;
        }
        // Otherwise, this is just normal property access
        return this[n];
    }

    const TypedArray = Reflect.getPrototypeOf(Int8Array);
    for (const type of [Array, String, TypedArray]) {
        Object.defineProperty(
            type.prototype,
            "at",
            {
                "value": at,
                "writable": true,
                "enumerable": false,
                "configurable": true,
            }
        );
    }
})();
