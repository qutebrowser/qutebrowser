/**
* Copyright 2015 Artur Shaik <ashaihullin@gmail.com>
* Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

/* eslint-disable max-len */

/**
 * Snippet to position caret at top of the page when caret mode is enabled.
 * Some code was borrowed from:
 *
 * https://github.com/1995eaton/chromium-vim/blob/master/content_scripts/dom.js
 * https://github.com/1995eaton/chromium-vim/blob/master/content_scripts/visual.js
 */

/* eslint-enable max-len */

"use strict";

(function() {
    // FIXME:qtwebengine integrate this with other window._qutebrowser code?
    function isElementInViewport(node) {  // eslint-disable-line complexity
        var i;
        var boundingRect = (node.getClientRects()[0] ||
                            node.getBoundingClientRect());

        if (boundingRect.width <= 1 && boundingRect.height <= 1) {
            var rects = node.getClientRects();
            for (i = 0; i < rects.length; i++) {
                if (rects[i].width > rects[0].height &&
                        rects[i].height > rects[0].height) {
                    boundingRect = rects[i];
                }
            }
        }
        if (boundingRect === undefined) {
            return null;
        }
        if (boundingRect.top > innerHeight || boundingRect.left > innerWidth) {
            return null;
        }
        if (boundingRect.width <= 1 || boundingRect.height <= 1) {
            var children = node.children;
            var visibleChildNode = false;
            for (i = 0; i < children.length; ++i) {
                boundingRect = (children[i].getClientRects()[0] ||
                                children[i].getBoundingClientRect());
                if (boundingRect.width > 1 && boundingRect.height > 1) {
                    visibleChildNode = true;
                    break;
                }
            }
            if (visibleChildNode === false) {
                return null;
            }
        }
        if (boundingRect.top + boundingRect.height < 10 ||
                boundingRect.left + boundingRect.width < -10) {
            return null;
        }
        var computedStyle = window.getComputedStyle(node, null);
        if (computedStyle.visibility !== "visible" ||
                computedStyle.display === "none" ||
                node.hasAttribute("disabled") ||
                parseInt(computedStyle.width, 10) === 0 ||
                parseInt(computedStyle.height, 10) === 0) {
            return null;
        }
        return boundingRect.top >= -20;
    }

    function positionCaret() {
        var walker = document.createTreeWalker(document.body, 4, null);
        var node;
        var textNodes = [];
        var el;
        while ((node = walker.nextNode())) {
            if (node.nodeType === 3 && node.data.trim() !== "") {
                textNodes.push(node);
            }
        }
        for (var i = 0; i < textNodes.length; i++) {
            var element = textNodes[i].parentElement;
            if (isElementInViewport(element.parentElement)) {
                el = element;
                break;
            }
        }
        if (el !== undefined) {
            var range = document.createRange();
            range.setStart(el, 0);
            range.setEnd(el, 0);
            var sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(range);
        }
    }

    positionCaret();
})();
