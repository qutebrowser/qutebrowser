/**
 * Copyright 2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"use strict";

window._qutebrowser.webelem = (function() {
    var funcs = {};
    var elements = [];

    function serialize_elem(elem) {
        if (!elem) {
            return null;
        }

        var id = elements.length;
        elements[id] = elem;

        var out = {
            "id": id,
            "text": elem.text,
            "value": elem.value,
            "tag_name": elem.tagName,
            "outer_xml": elem.outerHTML,
            "class_name": elem.className,
            "rects": [],  // Gets filled up later
        };

        var attributes = {};
        for (var i = 0; i < elem.attributes.length; ++i) {
            var attr = elem.attributes[i];
            attributes[attr.name] = attr.value;
        }
        out.attributes = attributes;

        var client_rects = elem.getClientRects();
        for (var k = 0; k < client_rects.length; ++k) {
            var rect = client_rects[k];
            out.rects.push({
                "top": rect.top,
                "right": rect.right,
                "bottom": rect.bottom,
                "left": rect.left,
                "height": rect.height,
                "width": rect.width,
            });
        }

        // console.log(JSON.stringify(out));

        return out;
    }

    function is_visible(elem) {
        // FIXME:qtwebengine Handle frames and iframes

        // Adopted from vimperator:
        // https://github.com/vimperator/vimperator-labs/blob/vimperator-3.14.0/common/content/hints.js#L259-L285
        // FIXME:qtwebengine we might need something more sophisticated like
        // the cVim implementation here?
        // https://github.com/1995eaton/chromium-vim/blob/1.2.85/content_scripts/dom.js#L74-L134

        var win = elem.ownerDocument.defaultView;
        var rect = elem.getBoundingClientRect();

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

        var style = win.getComputedStyle(elem, null);
        // FIXME:qtwebengine do we need this <area> handling?
        // visibility and display style are misleading for area tags and they
        // get "display: none" by default.
        // See https://github.com/vimperator/vimperator-labs/issues/236
        if (elem.nodeName.toLowerCase() !== "area" && (
                style.getPropertyValue("visibility") !== "visible" ||
                style.getPropertyValue("display") === "none")) {
            return false;
        }

        return true;
    }

    funcs.find_all = function(selector, only_visible) {
        var elems = document.querySelectorAll(selector);
        var out = [];

        for (var i = 0; i < elems.length; ++i) {
            if (!only_visible || is_visible(elems[i])) {
                out.push(serialize_elem(elems[i]));
            }
        }

        return out;
    };

    funcs.focus_element = function() {
        var elem = document.activeElement;

        if (!elem || elem === document.body) {
            // "When there is no selection, the active element is the page's
            // <body> or null."
            return null;
        }

        return serialize_elem(elem);
    };

    funcs.set_value = function(id, value) {
        elements[id].value = value;
    };

    funcs.insert_text = function(id, text) {
        var elem = elements[id];
        var event = document.createEvent("TextEvent");
        event.initTextEvent("textInput", true, true, null, text);
        elem.dispatchEvent(event);
    };

    funcs.element_at_pos = function(x, y) {
        // FIXME:qtwebengine
        // If the element at the specified point belongs to another document
        // (for example, an iframe's subdocument), the subdocument's parent
        // element is returned (the iframe itself).

        var elem = document.elementFromPoint(x, y);
        return serialize_elem(elem);
    };

    funcs.element_by_id = function(id) {
        var elem = document.getElementById(id);
        return serialize_elem(elem);
    };

    funcs.set_attribute = function(id, name, value) {
        elements[id].setAttribute(name, value);
    };

    funcs.remove_blank_target = function(id) {
        var elem = elements[id];
        while (elem !== null) {
            var tag = elem.tagName.toLowerCase();
            if (tag === "a" || tag === "area") {
                if (elem.getAttribute("target") === "_blank") {
                    elem.setAttribute("target", "_top");
                }
                break;
            }
            elem = elem.parentElement;
        }
    };

    return funcs;
})();
