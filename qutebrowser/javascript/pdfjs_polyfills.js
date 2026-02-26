/* eslint-disable strict, no-extend-native */
/* (this file gets used as a snippet) */

/*
SPDX-FileCopyrightText: Freya Bruhin (The Compiler) <mail@qutebrowser.org>
SPDX-License-Identifier: GPL-3.0-or-later
*/

(function() {
    // Chromium 119 / QtWebEngine 6.8
    // https://caniuse.com/mdn-javascript_builtins_promise_withresolvers
    if (typeof Promise.withResolvers === "undefined") {
        Promise.withResolvers = function() {
            let resolve, reject
            const promise = new Promise((res, rej) => {
                resolve = res
                reject = rej
            })
            return { promise, resolve, reject }
        }
    }

    // Chromium 126 / QtWebEngine 6.9
    // https://caniuse.com/mdn-api_url_parse_static
    if (typeof URL.parse === "undefined") {
        URL.parse = function(url, base) {
            try { 
                return new URL(url, base);
            } catch (ex) {
                return null;
            }
        }
    }

    // Chromium 140 / QtWebEngine 6.11
    // https://caniuse.com/mdn-javascript_builtins_uint8array_tohex
    if (typeof Uint8Array.toHex === "undefined") {
        Uint8Array.prototype.toHex = function() {
            let out = "";
            for (let i = 0; i < this.length; ++i) {
              out += this[i].toString(16).padStart(2, "0");
            }
            return out;
        }
    }
})();
