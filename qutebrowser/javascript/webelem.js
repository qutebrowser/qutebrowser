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


document._qutebrowser_elements = [];


function _qutebrowser_serialize_elem(elem, id) {
    var out = {};

    var attributes = {};
    for (var i = 0; i < elem.attributes.length; ++i) {
        attr = elem.attributes[i];
        attributes[attr.name] = attr.value;
    }
    out["attributes"] = attributes;

    out["text"] = elem.text;
    out["tag_name"] = elem.tagName;
    out["outer_xml"] = elem.outerHTML;
    out["id"] = id;

    // console.log(JSON.stringify(out));

    return out;
}


function _qutebrowser_find_all_elements(selector) {
    var elems = document.querySelectorAll(selector);
    var out = [];
    var id = document._qutebrowser_elements.length;

    for (var i = 0; i < elems.length; ++i) {
        var elem = elems[i];
        out.push(_qutebrowser_serialize_elem(elem, id));
        document._qutebrowser_elements[id] = elem;
        id++;
    }

    return out;
}


function _qutebrowser_get_element(id) {
    return document._qutebrowser_elements[id];
}
