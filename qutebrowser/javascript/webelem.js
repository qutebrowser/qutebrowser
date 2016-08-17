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

    function serialize_elem(elem, id) {
        var out = {
            "id": id,
            "text": elem.text,
            "tag_name": elem.tagName,
            "outer_xml": elem.outerHTML,
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

    funcs.find_all = function(selector) {
        var elems = document.querySelectorAll(selector);
        var out = [];
        var id = elements.length;

        for (var i = 0; i < elems.length; ++i) {
            var elem = elems[i];
            out.push(serialize_elem(elem, id));
            elements[id] = elem;
            id++;
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

        var id = elements.length;
        elements[id] = elem;
        return serialize_elem(elem, id);
    };

    funcs.set_text = function(id, text) {
        elements[id].value = text;
    };

    funcs.element_at_pos = function(x, y) {
        // FIXME:qtwebengine
        // If the element at the specified point belongs to another document
        // (for example, an iframe's subdocument), the subdocument's parent
        // element is returned (the iframe itself).

        var elem = document.elementFromPoint(x, y);
        if (!elem) {
            return null;
        }

        var id = elements.length;
        elements[id] = elem;
        return serialize_elem(elem, id);
    };

    return funcs;
})();
