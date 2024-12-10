/* eslint-disable strict */
/* (this file gets used as a snippet) */

/*
SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
})();
