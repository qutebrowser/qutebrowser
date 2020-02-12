/**
 * Copyright 2016-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

window._qutebrowser.webelem = (function() {
    const funcs = {};
    const elements = [];

    function get_frame_offset(frame) {
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
    }

    // Add an offset rect to a base rect, for use with frames
    function add_offset_rect(base, offset) {
        return {
            "top": base.top + offset.top,
            "left": base.left + offset.left,
            "bottom": base.bottom + offset.top,
            "right": base.right + offset.left,
            "height": base.height,
            "width": base.width,
        };
    }

    function get_caret_position(elem, frame) {
        // With older Chromium versions (and QtWebKit), InvalidStateError will
        // be thrown if elem doesn't have selectionStart.
        // With newer Chromium versions (>= Qt 5.10), we get null.
        try {
            return elem.selectionStart;
        } catch (err) {
            if ((err instanceof DOMException ||
                 (frame && err instanceof frame.DOMException)) &&
                err.name === "InvalidStateError") {
                // nothing to do, caret_position is already null
            } else {
                // not the droid we're looking for
                throw err;
            }
        }
        return null;
    }

    function serialize_elem(elem, frame = null) {
        if (!elem) {
            return null;
        }

        const id = elements.length;
        elements[id] = elem;

        const caret_position = get_caret_position(elem, frame);

        const out = {
            "id": id,
            "rects": [],  // Gets filled up later
            "caret_position": caret_position,
        };

        // Deal with various fun things which can happen in form elements
        // https://github.com/qutebrowser/qutebrowser/issues/2569
        // https://github.com/qutebrowser/qutebrowser/issues/2877
        // https://stackoverflow.com/q/22942689/2085149
        if (typeof elem.tagName === "string") {
            out.tag_name = elem.tagName;
        } else if (typeof elem.nodeName === "string") {
            out.tag_name = elem.nodeName;
        } else {
            out.tag_name = "";
        }

        if (typeof elem.className === "string") {
            out.class_name = elem.className;
        } else {
            // e.g. SVG elements
            out.class_name = "";
        }

        if (typeof elem.value === "string" || typeof elem.value === "number") {
            out.value = elem.value;
        } else {
            out.value = "";
        }

        if (typeof elem.outerHTML === "string") {
            out.outer_xml = elem.outerHTML;
        } else {
            out.outer_xml = "";
        }

        if (typeof elem.textContent === "string") {
            out.text = elem.textContent;
        } else if (typeof elem.text === "string") {
            out.text = elem.text;
        }  // else: don't add the text at all

        const attributes = {};
        for (let i = 0; i < elem.attributes.length; ++i) {
            const attr = elem.attributes[i];
            attributes[attr.name] = attr.value;
        }
        out.attributes = attributes;

        const client_rects = elem.getClientRects();
        const frame_offset_rect = get_frame_offset(frame);

        for (let k = 0; k < client_rects.length; ++k) {
            const rect = client_rects[k];
            out.rects.push(
                add_offset_rect(rect, frame_offset_rect)
            );
        }

        // console.log(JSON.stringify(out));

        return out;
    }

    function is_visible(elem, frame = null) {
        // Adopted from vimperator:
        // https://github.com/vimperator/vimperator-labs/blob/vimperator-3.14.0/common/content/hints.js#L259-L285
        // FIXME:qtwebengine we might need something more sophisticated like
        // the cVim implementation here?
        // https://github.com/1995eaton/chromium-vim/blob/1.2.85/content_scripts/dom.js#L74-L134

        const win = elem.ownerDocument.defaultView;
        const offset_rect = get_frame_offset(frame);
        let rect = add_offset_rect(elem.getBoundingClientRect(), offset_rect);

        if (!rect ||
                rect.top > window.innerHeight ||
                rect.bottom < 0 ||
                rect.left > window.innerWidth ||
                rect.right < 0) {
            return false;
        }

        rect = elem.getClientRects()[0];
        if (!rect) {
            return false;
        }

        const style = win.getComputedStyle(elem, null);
        if (style.getPropertyValue("visibility") !== "visible" ||
                style.getPropertyValue("display") === "none" ||
                style.getPropertyValue("opacity") === "0") {
            // FIXME:qtwebengine do we need this <area> handling?
            // visibility and display style are misleading for area tags and
            // they get "display: none" by default.
            // See https://github.com/vimperator/vimperator-labs/issues/236
            if (elem.nodeName.toLowerCase() !== "area" &&
                    !elem.classList.contains("ace_text-input")) {
                return false;
            }
        }

        return true;
    }

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

    funcs.find_css = (selector, only_visible) => {
        let elems;

        try {
            elems = document.querySelectorAll(selector);
        } catch (ex) {
            return {"success": false, "error": ex.toString()};
        }

        const subelem_frames = window.frames;
        const out = [];

        for (let i = 0; i < elems.length; ++i) {
            if (!only_visible || is_visible(elems[i])) {
                out.push(serialize_elem(elems[i]));
            }
        }

        // Recurse into frames and add them
        for (let i = 0; i < subelem_frames.length; i++) {
            if (iframe_same_domain(subelem_frames[i])) {
                const frame = subelem_frames[i];
                const subelems = frame.document.
                    querySelectorAll(selector);
                for (let elem_num = 0; elem_num < subelems.length; ++elem_num) {
                    if (!only_visible ||
                        is_visible(subelems[elem_num], frame)) {
                        out.push(serialize_elem(subelems[elem_num], frame));
                    }
                }
            }
        }

        return {"success": true, "result": out};
    };

    // Runs a function in a frame until the result is not null, then return
    // If no frame succeeds, return null
    function run_frames(func) {
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
    }

    funcs.find_id = (id) => {
        const elem = document.getElementById(id);
        if (elem) {
            return serialize_elem(elem);
        }

        const serialized_elem = run_frames((frame) => {
            const element = frame.window.document.getElementById(id);
            return serialize_elem(element, frame);
        });

        if (serialized_elem) {
            return serialized_elem;
        }

        return null;
    };

    // Check if elem is an iframe, and if so, return the result of func on it.
    // If no iframes match, return null
    function call_if_frame(elem, func) {
        // Check if elem is a frame, and if so, call func on the window
        if ("contentWindow" in elem) {
            const frame = elem.contentWindow;
            if (iframe_same_domain(frame) &&
                "frameElement" in elem.contentWindow) {
                return func(frame);
            }
        }
        return null;
    }

    funcs.find_focused = () => {
        const elem = document.activeElement;

        if (!elem || elem === document.body) {
            // "When there is no selection, the active element is the page's
            // <body> or null."
            return null;
        }

        // Check if we got an iframe, and if so, recurse inside of it
        const frame_elem = call_if_frame(elem,
            (frame) => serialize_elem(frame.document.activeElement, frame));

        if (frame_elem !== null) {
            return frame_elem;
        }
        return serialize_elem(elem);
    };

    funcs.find_at_pos = (x, y) => {
        const elem = document.elementFromPoint(x, y);


        // Check if we got an iframe, and if so, recurse inside of it
        const frame_elem = call_if_frame(elem,
            (frame) => {
                // Subtract offsets due to being in an iframe
                const frame_offset_rect =
                      frame.frameElement.getBoundingClientRect();
                return serialize_elem(frame.document.
                    elementFromPoint(x - frame_offset_rect.left,
                        y - frame_offset_rect.top), frame);
            });

        if (frame_elem !== null) {
            return frame_elem;
        }
        return serialize_elem(elem);
    };

    // Function for returning a selection or focus to python (so we can click
    // it). If nothing is selected but there is something focused, returns
    // "focused"
    funcs.find_selected_focused_link = () => {
        const elem = window.getSelection().anchorNode;
        if (elem) {
            return serialize_elem(elem.parentNode);
        }

        const serialized_frame_elem = run_frames((frame) => {
            const node = frame.window.getSelection().anchorNode;
            if (node) {
                return serialize_elem(node.parentNode, frame);
            }
            return null;
        });

        if (serialized_frame_elem) {
            return serialized_frame_elem;
        }
        return funcs.find_focused() && "focused";
    };

    funcs.set_value = (id, value) => {
        elements[id].value = value;
    };

    funcs.insert_text = (id, text) => {
        const elem = elements[id];
        elem.focus();
        document.execCommand("insertText", false, text);
    };

    funcs.dispatch_event = (id, event, bubbles = false,
        cancelable = false, composed = false) => {
        const elem = elements[id];
        elem.dispatchEvent(
            new Event(event, {"bubbles": bubbles,
                "cancelable": cancelable,
                "composed": composed}));
    };

    funcs.set_attribute = (id, name, value) => {
        elements[id].setAttribute(name, value);
    };

    funcs.remove_blank_target = (id) => {
        let elem = elements[id];
        while (elem !== null) {
            const tag = elem.tagName.toLowerCase();
            if (tag === "a" || tag === "area") {
                if (elem.getAttribute("target") === "_blank") {
                    elem.setAttribute("target", "_top");
                }
                break;
            }
            elem = elem.parentElement;
        }
    };

    funcs.click = (id) => {
        const elem = elements[id];
        elem.click();
    };

    funcs.focus = (id) => {
        const elem = elements[id];
        elem.focus();
    };

    funcs.move_cursor_to_end = (id) => {
        const elem = elements[id];
        elem.selectionStart = elem.value.length;
        elem.selectionEnd = elem.value.length;
    };

    funcs.delete = (id) => {
        const elem = elements[id];
        elem.remove();
    };

    return funcs;
})();
