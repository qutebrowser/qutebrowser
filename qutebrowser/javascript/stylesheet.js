/**
 * Copyright 2017 Ulrik de Muelenaere <ulrikdem@gmail.com>
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

window._qutebrowser.stylesheet = (function() {
    if (window._qutebrowser.stylesheet) {
        return window._qutebrowser.stylesheet;
    }

    var funcs = {};

    var xhtml_ns = "http://www.w3.org/1999/xhtml";
    var svg_ns = "http://www.w3.org/2000/svg";

    var root_elem;
    var style_elem;
    var css_content = "";

    var root_observer;
    var style_observer;
    var initialized = false;

    // Watch for rewrites of the root element and changes to its children,
    // then move the stylesheet to the end. Partially inspired by Stylus:
    // https://github.com/openstyles/stylus/blob/1.1.4.2/content/apply.js#L235-L355
    function watch_root() {
        if (root_elem !== document.documentElement) {
            root_elem = document.documentElement;
            root_observer.disconnect();
            root_observer.observe(document, {"childList": true});
            root_observer.observe(root_elem, {"childList": true});
        }
        if (style_elem !== root_elem.lastChild) {
            root_elem.appendChild(style_elem);
        }
    }

    function create_style() {
        var ns = xhtml_ns;
        if (document.documentElement.namespaceURI === svg_ns) {
            ns = svg_ns;
        }
        style_elem = document.createElementNS(ns, "style");
        style_elem.textContent = css_content;
        root_observer = new MutationObserver(watch_root);
        watch_root();
    }

    // We should only inject the stylesheet if the document already has style
    // information associated with it. Otherwise we wait until the browser
    // rewrites it to an XHTML document showing the document tree. As a
    // starting point for exploring the relevant code in Chromium, see
    // https://github.com/qt/qtwebengine-chromium/blob/cfe8c60/chromium/third_party/WebKit/Source/core/xml/parser/XMLDocumentParser.cpp#L1539-L1540
    function check_style(node) {
        var stylesheet = node.nodeType === Node.PROCESSING_INSTRUCTION_NODE &&
                         node.target === "xml-stylesheet" &&
                         node.parentNode === document;
        var known_ns = node.nodeType === Node.ELEMENT_NODE &&
                       (node.namespaceURI === xhtml_ns ||
                        node.namespaceURI === svg_ns);
        if (stylesheet || known_ns) {
            create_style();
            return true;
        }
        return false;
    }

    function check_added_style(mutations) {
        for (var mi = 0; mi < mutations.length; ++mi) {
            var nodes = mutations[mi].addedNodes;
            for (var ni = 0; ni < nodes.length; ++ni) {
                if (check_style(nodes[ni])) {
                    style_observer.disconnect();
                    return;
                }
            }
        }
    }

    function init() {
        initialized = true;
        // Chromium will not rewrite a document inside a frame, so add the
        // stylesheet even if the document is unstyled.
        if (window !== window.top) {
            create_style();
            return;
        }
        var iter = document.createNodeIterator(document);
        var node;
        while ((node = iter.nextNode())) {
            if (check_style(node)) {
                return;
            }
        }
        style_observer = new MutationObserver(check_added_style);
        style_observer.observe(document, {"childList": true, "subtree": true});
    }

    funcs.set_css = function(css) {
        if (!initialized) {
            init();
        }
        if (style_elem) {
            style_elem.textContent = css;
            // The browser seems to rewrite the document in same-origin frames
            // without notifying the mutation observer. Ensure that the
            // stylesheet is in the current document.
            watch_root();
        } else {
            css_content = css;
        }
        // Propagate the new CSS to all child frames.
        // FIXME:qtwebengine This does not work for cross-origin frames.
        for (var i = 0; i < window.frames.length; ++i) {
            var frame = window.frames[i];
            if (frame._qutebrowser && frame._qutebrowser.stylesheet) {
                frame._qutebrowser.stylesheet.set_css(css);
            }
        }
    };

    return funcs;
})();
