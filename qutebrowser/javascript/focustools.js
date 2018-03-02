/**
 * Copyright 2017-2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
 *
 * This file is part of qutebrowser.
 *
 * qutebrowser is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * qutebrowser is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.
 */

/**
 * Functions for interacting with focus from the js side.
 */

"use strict";

window._qutebrowser.focustools = (function() {
    const funcs = {};
    let lastFocusedElement = null;
    let handlerInstalled = false;

    /*
     * Basic function for blurring the page.
     */
    funcs.blur = () => {
        if (document && document.activeElement) {
            document.activeElement.blur();
        }
    };

    /*
     * Blur page on load, and timeout seconds after fully completed load.
     */
    funcs.load = (blur_on_load, timeout) => {
        if (blur_on_load) {
            // add a DOM event listener if we haven't loaded that yet
            if (document.readyState === "complete") {
                funcs.blur();
            } else {
                window.addEventListener("DOMContentLoaded", () => {
                    funcs.blur();
                });
            }

            if (timeout >= 0) {
                window.addEventListener("load",
                    () => setTimeout(
                        () => funcs.blur(), timeout));
            }
        }
    };

    funcs.installFocusHandler = () => {
        if (document && document.body && !handlerInstalled) {
            document.body.addEventListener("blur", (event) => {
                lastFocusedElement = event.srcElement;
            }, true);
            handlerInstalled = true;
        }
    };

    funcs.focusLastElement = () => {
        if (document && document.body
            // No element focused currently
            && document.activeElement == document.body
            && lastFocusedElement
            // Check if the element is still in the DO
            && document.body.contains(lastFocusedElement)) {
            lastFocusedElement.focus();
        }
    }

    funcs.installFocusHandler();

    return funcs;
})();
