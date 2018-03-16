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
 * The connection for web elements between Python and Javascript works like
 * this:
 *
 * - Python calls into Javascript and invokes a function to find elements (one
 *   of the find_* functions).
 * - Javascript gets the requested element, and calls serialize_elem on it.
 * - serialize_elem saves the javascript element object in "elements", gets some
 *   attributes from the element, and assigns an ID (index into 'elements') to
 *   it.
 * - Python gets this information and constructs a Python wrapper object with
 *   the information it got right away, and the ID.
 * - When Python wants to modify an element, it calls javascript again with the
 *   element ID.
 * - Javascript gets the element from the elements array, and modifies it.
 */

"use strict";

window._qutebrowser.utils = (function() {
    const funcs = {};

    funcs.get_frame_offset = (frame) => {
        if (frame === null) {
            // Dummy object with zero offset
            return {
                "top": 0,
                "right": 0,
                "bottom": 0,
                "left": 0,
                "height": 0,
                "width": 0,
            };
        }
        return frame.frameElement.getBoundingClientRect();
    };

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

    // Runs a function in a frame until the result is not null, then return
    funcs.run_frames = (func) => {
        for (let i = 0; i < window.frames.length; ++i) {
            const frame = window.frames[i];
            if (iframe_same_domain(frame)) {
                const result = func(frame);
                if (result) {
                    return result;
                }
            }
        }
        return null;
    };

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
