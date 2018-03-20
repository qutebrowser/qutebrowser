/**
 * Copyright 2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
    // Lets us know if the user did something on the page, if so, stop blurring.
    let userInteracted = false;

    /*
     * Basic function for blurring the page.
     */
    funcs.blur = () => {
        if (document && document.activeElement) {
            // If we have something focused, store it (in case js is disabled)
            if (document.activeElement !== document.body) {
                lastFocusedElement = document.activeElement;
            }
            document.activeElement.blur();
        }
    };

    /*
     * Blur page on load, and timeout seconds after fully completed load.
     */
    funcs.load = (blur_on_load) => {
        if (blur_on_load) {
            // add a DOM event listener if we haven't loaded that yet
            if (document.readyState === "complete" ||
                document.readyState === "interactive") {
                funcs.blur();
            } else {
                window.addEventListener("DOMContentLoaded", funcs.blur);
            }
            funcs.installHandlers();
        }
    };

    funcs.installHandlers = () => {
        if (document.readyState !== "complete" &&
            document.readyState !== "interactive") {
            window.addEventListener("DOMContentLoaded", funcs.installHandlers);
        } else if (document && document.body && !handlerInstalled) {
            // Listen for future blur events; store the last focused element.
            document.body.addEventListener("blur", (event) => {
                lastFocusedElement = event.srcElement;
            }, true);

            // Blur right now in case anything managed to beat us.
            funcs.blur();

            // Blur any future focus events unless userInteracted is set
            // https://github.com/philc/vimium/pull/1480/files for inspiration.
            document.body.addEventListener("focus", (event) => {
                if (!userInteracted) {
                    event.target.blur();
                }
            }, true);

            // Set userInteracted if we get any mouse/keypresses
            document.body.addEventListener("mousedown", () => {
                userInteracted = true;
            }, true);
            document.body.addEventListener("keydown", () => {
                userInteracted = true;
            }, true);

            handlerInstalled = true;
        }
    };

    funcs.focusLastElement = () => {
        userInteracted = true;
        if (document && document.body &&
            // No element focused currently
            document.activeElement === document.body &&
            lastFocusedElement &&
            // Check if the element is still in the DOM
            document.body.contains(lastFocusedElement)) {
            lastFocusedElement.focus();
        }
    };

    // Expose userInteracted so we can receive qb's js click/focus events
    funcs.setUserInteracted = () => {
        userInteracted = true;
    };

    return funcs;
})();
