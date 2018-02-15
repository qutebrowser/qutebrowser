/**
 * Copyright 2016-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

    /*
     * Blur page on load, and timeout seconds after fully completed load.
     */
    funcs.load = (blur_on_load, timeout) => {
        if (blur_on_load && document.activeElement) {
            document.activeElement.blur();
            if (timeout >= 0) {
                window.addEventListener("load",
                    () => setTimeout(
                        () => document.activeElement.blur(), timeout));
            }
        }
    };

    return funcs;
})();
