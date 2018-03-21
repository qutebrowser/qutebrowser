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
 * General utilities used by multiple qutebrowser js files.
 */

"use strict";

window._qutebrowser.utils = (function() {
    const funcs = {};

    // Returns true if the iframe is accessible without
    // cross domain errors, else false.
    function iframe_same_domain(frame) {
        try {
            frame.document; // eslint-disable-line no-unused-expressions
            return true;
        } catch (err) {
            return false;
        }
    }
    funcs.iframe_same_domain = iframe_same_domain;

    // Check if elem is an iframe, and if so, return the result of func on it.
    // If no iframes match, return null
    funcs.call_if_frame = (elem, func) => {
        // Check if elem is a frame, and if so, call func on the window
        if ("contentWindow" in elem) {
            const frame = elem.contentWindow;
            if (iframe_same_domain(frame) &&
                "frameElement" in frame) {
                return func(frame);
            }
        }
        return null;
    };

    return funcs;
})();
