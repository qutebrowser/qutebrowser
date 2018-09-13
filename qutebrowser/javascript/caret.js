/* eslint-disable max-len, max-statements, complexity,
default-case, valid-jsdoc */

// Copyright 2014 The Chromium Authors. All rights reserved.
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are
// met:
//
//    * Redistributions of source code must retain the above copyright
// notice, this list of conditions and the following disclaimer.
//    * Redistributions in binary form must reproduce the above
// copyright notice, this list of conditions and the following disclaimer
// in the documentation and/or other materials provided with the
// distribution.
//    * Neither the name of Google Inc. nor the names of its
// contributors may be used to endorse or promote products derived from
// this software without specific prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
// "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
// LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
// A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
// OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
// SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
// LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
// DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
// THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
// (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
// OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

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
 * Ported chrome-caretbrowsing extension.
 * https://cs.chromium.org/chromium/src/ui/accessibility/extensions/caretbrowsing/
 *
 * The behavior is based on Mozilla's spec whenever possible:
 *   http://www.mozilla.org/access/keyboard/proposal
 *
 * The one exception is that Esc is used to escape out of a form control,
 * rather than their proposed key (which doesn't seem to work in the
 * latest Firefox anyway).
 *
 * Some details about how Chrome selection works, which will help in
 * understanding the code:
 *
 * The Selection object (window.getSelection()) has four components that
 * completely describe the state of the caret or selection:
 *
 * base and anchor: this is the start of the selection, the fixed point.
 * extent and focus: this is the end of the selection, the part that
 *     moves when you hold down shift and press the left or right arrows.
 *
 * When the selection is a cursor, the base, anchor, extent, and focus are
 * all the same.
 *
 * There's only one time when the base and anchor are not the same, or the
 * extent and focus are not the same, and that's when the selection is in
 * an ambiguous state - i.e. it's not clear which edge is the focus and which
 * is the anchor. As an example, if you double-click to select a word, then
 * the behavior is dependent on your next action. If you press Shift+Right,
 * the right edge becomes the focus. But if you press Shift+Left, the left
 * edge becomes the focus.
 *
 * When the selection is in an ambiguous state, the base and extent are set
 * to the position where the mouse clicked, and the anchor and focus are set
 * to the boundaries of the selection.
 *
 * The only way to set the selection and give it direction is to use
 * the non-standard Selection.setBaseAndExtent method. If you try to use
 * Selection.addRange(), the anchor will always be on the left and the focus
 * will always be on the right, making it impossible to manipulate
 * selections that move from right to left.
 *
 * Finally, Chrome will throw an exception if you try to set an invalid
 * selection - a selection where the left and right edges are not the same,
 * but it doesn't span any visible characters. A common example is that
 * there are often many whitespace characters in the DOM that are not
 * visible on the page; trying to select them will fail. Another example is
 * any node that's invisible or not displayed.
 *
 * While there are probably many possible methods to determine what is
 * selectable, this code uses the method of determining if there's a valid
 * bounding box for the range or not - keep moving the cursor forwards until
 * the range from the previous position and candidate next position has a
 * valid bounding box.
 */

"use strict";

window._qutebrowser.caret = (function() {
    function isElementInViewport(node) {
        let i;
        let boundingRect = (node.getClientRects()[0] ||
            node.getBoundingClientRect());

        if (boundingRect.width <= 1 && boundingRect.height <= 1) {
            const rects = node.getClientRects();
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
            const children = node.children;
            let visibleChildNode = false;
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
        const computedStyle = window.getComputedStyle(node, null);
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
        const walker = document.createTreeWalker(document.body, -1);
        let node;
        const textNodes = [];
        let el;
        while ((node = walker.nextNode())) {
            if (node.nodeType === 3 && node.nodeValue.trim() !== "") {
                textNodes.push(node);
            }
        }
        for (let i = 0; i < textNodes.length; i++) {
            const element = textNodes[i].parentElement;
            if (isElementInViewport(element)) {
                el = element;
                break;
            }
        }
        if (el !== undefined) {
            /* eslint-disable no-use-before-define */
            const start = new Cursor(el, 0, "");
            const end = new Cursor(el, 0, "");
            const nodesCrossed = [];
            const result = TraverseUtil.getNextChar(
                start, end, nodesCrossed, true);
            if (result === null) {
                return;
            }
            CaretBrowsing.setAndValidateSelection(start, start);
            /* eslint-enable no-use-before-define */
        }
    }

    /**
     * Return whether a node is focusable. This includes nodes whose tabindex
     * attribute is set to "-1" explicitly - these nodes are not in the tab
     * order, but they should still be focused if the user navigates to them
     * using linear or smart DOM navigation.
     *
     * Note that when the tabIndex property of an Element is -1, that doesn't
     * tell us whether the tabIndex attribute is missing or set to "-1" explicitly,
     * so we have to check the attribute.
     *
     * @param {Object} targetNode The node to check if it's focusable.
     * @return {boolean} True if the node is focusable.
     */
    function isFocusable(targetNode) {
        if (!targetNode || typeof (targetNode.tabIndex) !== "number") {
            return false;
        }

        if (targetNode.tabIndex >= 0) {
            return true;
        }

        if (targetNode.hasAttribute &&
            targetNode.hasAttribute("tabindex") &&
            targetNode.getAttribute("tabindex") === "-1") {
            return true;
        }

        return false;
    }

    const axs = {};

    axs.dom = {};

    axs.color = {};

    axs.utils = {};

    axs.dom.parentElement = function(node) {
        if (!node) {
            return null;
        }
        const composedNode = axs.dom.composedParentNode(node);
        if (!composedNode) {
            return null;
        }
        switch (composedNode.nodeType) {
        case Node.ELEMENT_NODE:
            return composedNode;
        default:
            return axs.dom.parentElement(composedNode);
        }
    };

    axs.dom.shadowHost = function(node) {
        if ("host" in node) {
            return node.host;
        }
        return null;
    };

    axs.dom.composedParentNode = function(node) {
        if (!node) {
            return null;
        }
        if (node.nodeType === Node.DOCUMENT_FRAGMENT_NODE) {
            return axs.dom.shadowHost(node);
        }
        const parentNode = node.parentNode;
        if (!parentNode) {
            return null;
        }
        if (parentNode.nodeType === Node.DOCUMENT_FRAGMENT_NODE) {
            return axs.dom.shadowHost(parentNode);
        }
        if (!parentNode.shadowRoot) {
            return parentNode;
        }
        const points = node.getDestinationInsertionPoints();
        if (points.length > 0) {
            return axs.dom.composedParentNode(points[points.length - 1]);
        }
        return null;
    };

    axs.color.Color = function(red, green, blue, alpha) {
        this.red = red;
        this.green = green;
        this.blue = blue;
        this.alpha = alpha;
    };

    axs.color.parseColor = function(colorText) {
        if (colorText === "transparent") {
            return new axs.color.Color(0, 0, 0, 0);
        }
        let match = colorText.match(/^rgb\((\d+), (\d+), (\d+)\)$/);
        if (match) {
            const blue = parseInt(match[3], 10);
            const green = parseInt(match[2], 10);
            const red = parseInt(match[1], 10);
            return new axs.color.Color(red, green, blue, 1);
        }
        match = colorText.match(/^rgba\((\d+), (\d+), (\d+), (\d*(\.\d+)?)\)/);
        if (match) {
            const red = parseInt(match[1], 10);
            const green = parseInt(match[2], 10);
            const blue = parseInt(match[3], 10);
            const alpha = parseFloat(match[4]);
            return new axs.color.Color(red, green, blue, alpha);
        }
        return null;
    };

    axs.color.flattenColors = function(color1, color2) {
        const colorAlpha = color1.alpha;
        return new axs.color.Color(
            ((1 - colorAlpha) * color2.red) + (colorAlpha * color1.red),
            ((1 - colorAlpha) * color2.green) + (colorAlpha * color1.green),
            ((1 - colorAlpha) * color2.blue) + (colorAlpha * color2.blue),
            color1.alpha + (color2.alpha * (1 - color1.alpha)));
    };

    axs.utils.getParentBgColor = function(_el) {
        let el = _el;
        let el2 = el;
        let iter = null;
        el = [];
        for (iter = null; (el2 = axs.dom.parentElement(el2));) {
            const style = window.getComputedStyle(el2, null);
            if (style) {
                const color = axs.color.parseColor(style.backgroundColor);
                if (color &&
                    (style.opacity < 1 &&
                     (color.alpha *= style.opacity), color.alpha !== 0 &&
                     (el.push(color), color.alpha === 1))) {
                    iter = !0;
                    break;
                }
            }
        }
        if (!iter) {
            el.push(new axs.color.Color(255, 255, 255, 1));
        }
        for (el2 = el.pop(); el.length;) {
            iter = el.pop();
            el2 = axs.color.flattenColors(iter, el2);
        }
        return el2;
    };

    axs.utils.getFgColor = function(el, el2, color) {
        let color2 = axs.color.parseColor(el.color);
        if (!color2) {
            return null;
        }
        if (color2.alpha < 1) {
            color2 = axs.color.flattenColors(color2, color);
        }
        if (el.opacity < 1) {
            const el3 = axs.utils.getParentBgColor(el2);
            color2.alpha *= el.opacity;
            color2 = axs.color.flattenColors(color2, el3);
        }
        return color2;
    };

    axs.utils.getBgColor = function(el, elParent) {
        let color = axs.color.parseColor(el.backgroundColor);
        if (!color) {
            return null;
        }
        if (el.opacity < 1) {
            color.alpha *= el.opacity;
        }
        if (color.alpha < 1) {
            const bgColor = axs.utils.getParentBgColor(elParent);
            if (bgColor === null) {
                return null;
            }
            color = axs.color.flattenColors(color, bgColor);
        }
        return color;
    };

    axs.color.colorChannelToString = function(_color) {
        const color = Math.round(_color);
        if (color < 15) {
            return `0${color.toString(16)}`;
        }
        return color.toString(16);
    };

    axs.color.colorToString = function(color) {
        if (color.alpha === 1) {
            const red = axs.color.colorChannelToString(color.red);
            const green = axs.color.colorChannelToString(color.green);
            const blue = axs.color.colorChannelToString(color.blue);
            return `#${red}${green}${blue}`;
        }
        const arr = [color.red, color.green, color.blue, color.alpha].join();
        return `rgba(${arr})`;
    };

    /**
     * A class to represent a cursor location in the document,
     * like the start position or end position of a selection range.
     *
     * Later this may be extended to support "virtual text" for an object,
     * like the ALT text for an image.
     *
     * Note: we cache the text of a particular node at the time we
     * traverse into it. Later we should add support for dynamically
     * reloading it.
     * @param {Node} node The DOM node.
     * @param {number} index The index of the character within the node.
     * @param {string} text The cached text contents of the node.
     * @constructor
     */
    // eslint-disable-next-line func-style
    const Cursor = function(node, index, text) {
        this.node = node;
        this.index = index;
        this.text = text;
    };

    /**
     * @return {Cursor} A new cursor pointing to the same location.
     */
    Cursor.prototype.clone = function() {
        return new Cursor(this.node, this.index, this.text);
    };

    /**
     * Modify this cursor to point to the location that another cursor points to.
     * @param {Cursor} otherCursor The cursor to copy from.
     */
    Cursor.prototype.copyFrom = function(otherCursor) {
        this.node = otherCursor.node;
        this.index = otherCursor.index;
        this.text = otherCursor.text;
    };

    /**
     * Utility functions for stateless DOM traversal.
     * @constructor
     */
    const TraverseUtil = {};

    /**
     * Gets the text representation of a node. This allows us to substitute
     * alt text, names, or titles for html elements that provide them.
     * @param {Node} node A DOM node.
     * @return {string} A text string representation of the node.
     */
    TraverseUtil.getNodeText = function(node) {
        if (node.constructor === Text) {
            return node.data;
        }
        return "";
    };

    /**
     * Return true if a node should be treated as a leaf node, because
     * its children are properties of the object that shouldn't be traversed.
     *
     * TODO(dmazzoni): replace this with a predicate that detects nodes with
     * ARIA roles and other objects that have their own description.
     * For now we just detect a couple of common cases.
     *
     * @param {Node} node A DOM node.
     * @return {boolean} True if the node should be treated as a leaf node.
     */
    TraverseUtil.treatAsLeafNode = function(node) {
        return node.childNodes.length === 0 ||
            node.nodeName === "SELECT" ||
            node.nodeName === "OBJECT";
    };

    /**
     * Return true only if a single character is whitespace.
     * From https://developer.mozilla.org/en/Whitespace_in_the_DOM,
     * whitespace is defined as one of the characters
     *  "\t" TAB \u0009
     *  "\n" LF  \u000A
     *  "\r" CR  \u000D
     *  " "  SPC \u0020.
     *
     * @param {string} c A string containing a single character.
     * @return {boolean} True if the character is whitespace, otherwise false.
     */
    TraverseUtil.isWhitespace = function(ch) {
        return (ch === " " || ch === "\n" || ch === "\r" || ch === "\t");
    };

    /**
     * Use the computed CSS style to figure out if this DOM node is currently
     * visible.
     * @param {Node} node A HTML DOM node.
     * @return {boolean} Whether or not the html node is visible.
     */
    TraverseUtil.isVisible = function(node) {
        if (!node.style) {
            return true;
        }
        const style = window.getComputedStyle(node, null);
        return (Boolean(style) &&
            style.display !== "none" &&
            style.visibility !== "hidden");
    };

    /**
     * Use the class name to figure out if this DOM node should be traversed.
     * @param {Node} node A HTML DOM node.
     * @return {boolean} Whether or not the html node should be traversed.
     */
    TraverseUtil.isSkipped = function(_node) {
        let node = _node;
        if (node.constructor === Text) {
            node = node.parentElement;
        }
        if (node.className === "CaretBrowsing_Caret") {
            return true;
        }
        return false;
    };

    /**
     * Moves the cursor forwards until it has crossed exactly one character.
     * @param {Cursor} cursor The cursor location where the search should start.
     *     On exit, the cursor will be immediately to the right of the
     *     character returned.
     * @param {Array<Node>} nodesCrossed Any HTML nodes crossed between the
     *     initial and final cursor position will be pushed onto this array.
     * @return {?string} The character found, or null if the bottom of the
     *     document has been reached.
     */
    TraverseUtil.forwardsChar = function(cursor, nodesCrossed) {
        for (;;) {
            let childNode = null;
            if (!TraverseUtil.treatAsLeafNode(cursor.node)) {
                for (let i = cursor.index;
                    i < cursor.node.childNodes.length;
                    i++) {
                    const node = cursor.node.childNodes[i];
                    if (TraverseUtil.isSkipped(node)) {
                        nodesCrossed.push(node);
                    } else if (TraverseUtil.isVisible(node)) {
                        childNode = node;
                        break;
                    }
                }
            }
            if (childNode) {
                cursor.node = childNode;
                cursor.index = 0;
                cursor.text = TraverseUtil.getNodeText(cursor.node);
                if (cursor.node.constructor !== Text) {
                    nodesCrossed.push(cursor.node);
                }
            } else {
                // Return the next character from this leaf node.
                if (cursor.index < cursor.text.length) {
                    return cursor.text[cursor.index++];
                }

                // Move to the next sibling, going up the tree as necessary.
                while (cursor.node !== null) {
                    // Try to move to the next sibling.
                    let siblingNode = null;
                    for (let node = cursor.node.nextSibling;
                        node !== null;
                        node = node.nextSibling) {
                        if (TraverseUtil.isSkipped(node)) {
                            nodesCrossed.push(node);
                        } else if (TraverseUtil.isVisible(node)) {
                            siblingNode = node;
                            break;
                        }
                    }
                    if (siblingNode) {
                        cursor.node = siblingNode;
                        cursor.text = TraverseUtil.getNodeText(siblingNode);
                        cursor.index = 0;

                        if (cursor.node.constructor !== Text) {
                            nodesCrossed.push(cursor.node);
                        }

                        break;
                    }

                    // Otherwise, move to the parent.
                    const parentNode = cursor.node.parentNode;
                    if (parentNode &&
                        parentNode.constructor !== HTMLBodyElement) {
                        cursor.node = cursor.node.parentNode;
                        cursor.text = null;
                        cursor.index = 0;
                    } else {
                        return null;
                    }
                }
            }
        }
    };

    /**
     * Finds the next character, starting from endCursor.  Upon exit, startCursor
     * and endCursor will surround the next character. If skipWhitespace is
     * true, will skip until a real character is found. Otherwise, it will
     * attempt to select all of the whitespace between the initial position
     * of endCursor and the next non-whitespace character.
     * @param {Cursor} startCursor On exit, points to the position before
     *     the char.
     * @param {Cursor} endCursor The position to start searching for the next
     *     char.  On exit, will point to the position past the char.
     * @param {Array<Node>} nodesCrossed Any HTML nodes crossed between the
     *     initial and final cursor position will be pushed onto this array.
     * @param {boolean} skipWhitespace If true, will keep scanning until a
     *     non-whitespace character is found.
     * @return {?string} The next char, or null if the bottom of the
     *     document has been reached.
     */
    TraverseUtil.getNextChar = function(
        startCursor, endCursor, nodesCrossed, skipWhitespace) {
        // Save the starting position and get the first character.
        startCursor.copyFrom(endCursor);
        let fChar = TraverseUtil.forwardsChar(endCursor, nodesCrossed);
        if (fChar === null) {
            return null;
        }

        // Keep track of whether the first character was whitespace.
        const initialWhitespace = TraverseUtil.isWhitespace(fChar);

        // Keep scanning until we find a non-whitespace or non-skipped character.
        while ((TraverseUtil.isWhitespace(fChar)) ||
            (TraverseUtil.isSkipped(endCursor.node))) {
            fChar = TraverseUtil.forwardsChar(endCursor, nodesCrossed);
            if (fChar === null) {
                return null;
            }
        }
        if (skipWhitespace || !initialWhitespace) {
            // If skipWhitepace is true, or if the first character we encountered
            // was not whitespace, return that non-whitespace character.
            startCursor.copyFrom(endCursor);
            startCursor.index--;
            return fChar;
        }

        for (let i = 0; i < nodesCrossed.length; i++) {
            if (TraverseUtil.isSkipped(nodesCrossed[i])) {
                // We need to make sure that startCursor and endCursor aren't
                // surrounding a skippable node.
                endCursor.index--;
                startCursor.copyFrom(endCursor);
                startCursor.index--;
                return " ";
            }
        }
        // Otherwise, return all of the whitespace before that last character.
        endCursor.index--;
        return " ";
    };

    /**
     * The class handling the Caret Browsing implementation in the page.
     * Sets up communication with the background page, and then when caret
     * browsing is enabled, response to various key events to move the caret
     * or selection within the text content of the document.
     * @constructor
     */
    const CaretBrowsing = {};

    /**
     * Is caret browsing enabled?
     * @type {boolean}
     */
    CaretBrowsing.isEnabled = false;

    /**
     * Keep it enabled even when flipped off (for the options page)?
     * @type {boolean}
     */
    CaretBrowsing.forceEnabled = false;

    /**
     * What to do when the caret appears?
     * @type {string}
     */
    CaretBrowsing.onEnable = undefined;

    /**
     * What to do when the caret jumps?
     * @type {string}
     */
    CaretBrowsing.onJump = undefined;

    /**
     * Is this window / iframe focused? We won't show the caret if not,
     * especially so that carets aren't shown in two iframes of the same
     * tab.
     * @type {boolean}
     */
    CaretBrowsing.isWindowFocused = false;

    /**
     * Is the caret actually visible? This is true only if isEnabled and
     * isWindowFocused are both true.
     * @type {boolean}
     */
    CaretBrowsing.isCaretVisible = false;

    /**
     * The actual caret element, an absolute-positioned flashing line.
     * @type {Element}
     */
    CaretBrowsing.caretElement = undefined;

    /**
     * The x-position of the caret, in absolute pixels.
     * @type {number}
     */
    CaretBrowsing.caretX = 0;

    /**
     * The y-position of the caret, in absolute pixels.
     * @type {number}
     */
    CaretBrowsing.caretY = 0;

    /**
     * The width of the caret in pixels.
     * @type {number}
     */
    CaretBrowsing.caretWidth = 0;

    /**
     * The height of the caret in pixels.
     * @type {number}
     */
    CaretBrowsing.caretHeight = 0;

    /**
     * The foregroundc color.
     * @type {string}
     */
    CaretBrowsing.caretForeground = "#000";

    /**
     * The backgroundc color.
     * @type {string}
     */
    CaretBrowsing.caretBackground = "#fff";

    /**
     * Is the selection collapsed, i.e. are the start and end locations
     * the same? If so, our blinking caret image is shown; otherwise
     * the Chrome selection is shown.
     * @type {boolean}
     */
    CaretBrowsing.isSelectionCollapsed = false;

    /**
     * The id returned by window.setInterval for our blink function, so
     * we can cancel it when caret browsing is disabled.
     * @type {number?}
     */
    CaretBrowsing.blinkFunctionId = null;

    /**
     * The desired x-coordinate to match when moving the caret up and down.
     * To match the behavior as documented in Mozilla's caret browsing spec
     * (http://www.mozilla.org/access/keyboard/proposal), we keep track of the
     * initial x position when the user starts moving the caret up and down,
     * so that the x position doesn't drift as you move throughout lines, but
     * stays as close as possible to the initial position. This is reset when
     * moving left or right or clicking.
     * @type {number?}
     */
    CaretBrowsing.targetX = null;

    /**
     * A flag that flips on or off as the caret blinks.
     * @type {boolean}
     */
    CaretBrowsing.blinkFlag = true;

    /**
     * Whether we're running on Windows.
     * @type {boolean}
     */
    CaretBrowsing.isWindows = null;

    /**
     * Whether we're running on on old Qt 5.7.1.
     * @type {boolean}
     */
    CaretBrowsing.isOldQt = null;

    /**
     * Check if a node is a control that normally allows the user to interact
     * with it using arrow keys. We won't override the arrow keys when such a
     * control has focus, the user must press Escape to do caret browsing outside
     * that control.
     * @param {Node} node A node to check.
     * @return {boolean} True if this node is a control that the user can
     *     interact with using arrow keys.
     */
    CaretBrowsing.isControlThatNeedsArrowKeys = function(node) {
        if (!node) {
            return false;
        }

        if (node === document.body || node !== document.activeElement) {
            return false;
        }

        if (node.constructor === HTMLSelectElement) {
            return true;
        }

        if (node.constructor === HTMLInputElement) {
            switch (node.type) {
            case "email":
            case "number":
            case "password":
            case "search":
            case "text":
            case "tel":
            case "url":
            case "":
                return true;  // All of these are text boxes.
            case "datetime":
            case "datetime-local":
            case "date":
            case "month":
            case "radio":
            case "range":
            case "week":
                return true;  // These are other input elements that use arrows.
            }
        }

        // Handle focusable ARIA controls.
        if (node.getAttribute && isFocusable(node)) {
            const role = node.getAttribute("role");
            switch (role) {
            case "combobox":
            case "grid":
            case "gridcell":
            case "listbox":
            case "menu":
            case "menubar":
            case "menuitem":
            case "menuitemcheckbox":
            case "menuitemradio":
            case "option":
            case "radiogroup":
            case "scrollbar":
            case "slider":
            case "spinbutton":
            case "tab":
            case "tablist":
            case "textbox":
            case "tree":
            case "treegrid":
            case "treeitem":
                return true;
            }
        }

        return false;
    };

    CaretBrowsing.injectCaretStyles = function() {
        const prefix = CaretBrowsing.isOldQt ? "-webkit-" : "";
        const style = `
            .CaretBrowsing_Caret {
              position: absolute;
              z-index: 2147483647;
              min-height: 1em;
              min-width: 0.2em;
              animation: blink 1s step-end infinite;
              --inherited-color: inherit;
              background-color: var(--inherited-color, #000);
              color: var(--inherited-color, #000);
              mix-blend-mode: difference;
              ${prefix}filter: invert(85%);
            }
            @keyframes blink {
              50% { visibility: hidden; }
            }
        `;
        const node = document.createElement("style");
        node.innerHTML = style;
        document.body.appendChild(node);
    };

    /**
     * If there's no initial selection, set the cursor just before the
     * first text character in the document.
     */
    CaretBrowsing.setInitialCursor = function() {
        const selectionRange = window.getSelection().toString().length;
        if (selectionRange === 0) {
            positionCaret();
        }

        CaretBrowsing.injectCaretStyles();
        CaretBrowsing.toggle();
        CaretBrowsing.initiated = true;
        CaretBrowsing.selectionEnabled = selectionRange > 0;
    };

    /**
     * Try to set the window's selection to be between the given start and end
     * cursors, and return whether or not it was successful.
     * @param {Cursor} start The start position.
     * @param {Cursor} end The end position.
     * @return {boolean} True if the selection was successfully set.
     */
    CaretBrowsing.setAndValidateSelection = function(start, end) {
        const sel = window.getSelection();
        sel.setBaseAndExtent(start.node, start.index, end.node, end.index);

        if (sel.rangeCount !== 1) {
            return false;
        }

        return (sel.anchorNode === start.node &&
            sel.anchorOffset === start.index &&
            sel.focusNode === end.node &&
            sel.focusOffset === end.index);
    };

    /**
     * Set focus to a node if it's focusable. If it's an input element,
     * select the text, otherwise it doesn't appear focused to the user.
     * Every other control behaves normally if you just call focus() on it.
     * @param {Node} node The node to focus.
     * @return {boolean} True if the node was focused.
     */
    CaretBrowsing.setFocusToNode = function(nodeArg) {
        let node = nodeArg;
        while (node && node !== document.body) {
            if (isFocusable(node) && node.constructor !== HTMLIFrameElement) {
                node.focus();
                if (node.constructor === HTMLInputElement && node.select) {
                    node.select();
                }
                return true;
            }
            node = node.parentNode;
        }

        return false;
    };

    /**
     * Set the caret element's normal style, i.e. not when animating.
     */
    CaretBrowsing.setCaretElementNormalStyle = function() {
        const element = CaretBrowsing.caretElement;
        element.className = "CaretBrowsing_Caret";
        if (CaretBrowsing.isSelectionCollapsed) {
            element.style.opacity = "1.0";
        } else {
            element.style.opacity = "0.0";
        }
        element.style.left = `${CaretBrowsing.caretX}px`;
        element.style.top = `${CaretBrowsing.caretY}px`;
        element.style.width = `${CaretBrowsing.caretWidth}px`;
        element.style.height = `${CaretBrowsing.caretHeight}px`;
        element.style.color = CaretBrowsing.caretForeground;
    };

    /**
     * Create the caret element. This assumes that caretX, caretY,
     * caretWidth, and caretHeight have all been set. The caret is
     * animated in so the user can find it when it first appears.
     */
    CaretBrowsing.createCaretElement = function() {
        const element = document.createElement("div");
        element.className = "CaretBrowsing_Caret";
        document.body.appendChild(element);
        CaretBrowsing.caretElement = element;
        CaretBrowsing.setCaretElementNormalStyle();
    };

    /**
     * Recreate the caret element, triggering any intro animation.
     */
    CaretBrowsing.recreateCaretElement = function() {
        if (CaretBrowsing.caretElement) {
            window.clearInterval(CaretBrowsing.blinkFunctionId);
            CaretBrowsing.caretElement.parentElement.removeChild(
                CaretBrowsing.caretElement);
            CaretBrowsing.caretElement = null;
            CaretBrowsing.updateIsCaretVisible();
        }
    };

    /**
     * Get the rectangle for a cursor position. This is tricky because
     * you can't get the bounding rectangle of an empty range, so this function
     * computes the rect by trying a range including one character earlier or
     * later than the cursor position.
     * @param {Cursor} cursor A single cursor position.
     * @return {{left: number, top: number, width: number, height: number}}
     *     The bounding rectangle of the cursor.
     */
    CaretBrowsing.getCursorRect = function(cursor) {
        let node = cursor.node;
        const index = cursor.index;
        const rect = {
            "left": 0,
            "top": 0,
            "width": 1,
            "height": 0,
        };
        if (node.constructor === Text) {
            let left = index;
            let right = index;
            const max = node.data.length;
            const newRange = document.createRange();
            while (left > 0 || right < max) {
                if (left > 0) {
                    left--;
                    newRange.setStart(node, left);
                    newRange.setEnd(node, index);
                    const rangeRect = newRange.getBoundingClientRect();
                    if (rangeRect && rangeRect.width && rangeRect.height) {
                        rect.left = rangeRect.right;
                        rect.top = rangeRect.top;
                        rect.height = rangeRect.height;
                        break;
                    }
                }
                if (right < max) {
                    right++;
                    newRange.setStart(node, index);
                    newRange.setEnd(node, right);
                    const rangeRect = newRange.getBoundingClientRect();
                    if (rangeRect && rangeRect.width && rangeRect.height) {
                        rect.left = rangeRect.left;
                        rect.top = rangeRect.top;
                        rect.height = rangeRect.height;
                        break;
                    }
                }
            }
        } else {
            rect.height = node.offsetHeight;
            while (node !== null) {
                rect.left += node.offsetLeft;
                rect.top += node.offsetTop;
                node = node.offsetParent;
            }
        }
        rect.left += window.pageXOffset;
        rect.top += window.pageYOffset;
        return rect;
    };

    /**
     * Compute the new location of the caret or selection and update
     * the element as needed.
     * @param {boolean} scrollToSelection If true, will also scroll the page
     *     to the caret / selection location.
     */
    CaretBrowsing.updateCaretOrSelection =
        function(scrollToSelection) {
            const sel = window.getSelection();
            if (sel.rangeCount === 0) {
                if (CaretBrowsing.caretElement) {
                    CaretBrowsing.isSelectionCollapsed = false;
                    CaretBrowsing.caretElement.style.opacity = "0.0";
                }
                return;
            }

            const range = sel.getRangeAt(0);
            if (!range) {
                if (CaretBrowsing.caretElement) {
                    CaretBrowsing.isSelectionCollapsed = false;
                    CaretBrowsing.caretElement.style.opacity = "0.0";
                }
                return;
            }

            if (CaretBrowsing.isControlThatNeedsArrowKeys(
                document.activeElement)) {
                let node = document.activeElement;
                CaretBrowsing.caretWidth = node.offsetWidth;
                CaretBrowsing.caretHeight = node.offsetHeight;
                CaretBrowsing.caretX = 0;
                CaretBrowsing.caretY = 0;
                while (node.offsetParent) {
                    CaretBrowsing.caretX += node.offsetLeft;
                    CaretBrowsing.caretY += node.offsetTop;
                    node = node.offsetParent;
                }
                CaretBrowsing.isSelectionCollapsed = false;
            } else if (range.startOffset !== range.endOffset ||
                range.startContainer !== range.endContainer) {
                const rect = range.getBoundingClientRect();
                if (!rect) {
                    return;
                }
                CaretBrowsing.caretX = rect.left + window.pageXOffset;
                CaretBrowsing.caretY = rect.top + window.pageYOffset;
                CaretBrowsing.caretWidth = rect.width;
                CaretBrowsing.caretHeight = rect.height;
                CaretBrowsing.isSelectionCollapsed = false;
            } else {
                const rect = CaretBrowsing.getCursorRect(
                    new Cursor(range.startContainer,
                        range.startOffset,
                        TraverseUtil.getNodeText(range.startContainer)));
                CaretBrowsing.caretX = rect.left;
                CaretBrowsing.caretY = rect.top;
                CaretBrowsing.caretWidth = rect.width;
                CaretBrowsing.caretHeight = rect.height;
                CaretBrowsing.isSelectionCollapsed = true;
            }

            if (CaretBrowsing.caretElement) {
                const element = CaretBrowsing.caretElement;
                if (CaretBrowsing.isSelectionCollapsed) {
                    element.style.opacity = "1.0";
                    element.style.left = `${CaretBrowsing.caretX}px`;
                    element.style.top = `${CaretBrowsing.caretY}px`;
                    element.style.width = `${CaretBrowsing.caretWidth}px`;
                    element.style.height = `${CaretBrowsing.caretHeight}px`;
                } else {
                    element.style.opacity = "0.0";
                }
            } else {
                CaretBrowsing.createCaretElement();
            }

            let elem = range.startContainer;
            if (elem.constructor === Text) {
                elem = elem.parentElement;
            }
            const style = window.getComputedStyle(elem);
            const bg = axs.utils.getBgColor(style, elem);
            const fg = axs.utils.getFgColor(style, elem, bg);
            CaretBrowsing.caretBackground = axs.color.colorToString(bg);
            CaretBrowsing.caretForeground = axs.color.colorToString(fg);

            if (scrollToSelection) {
                // Scroll just to the "focus" position of the selection,
                // the part the user is manipulating.
                const rect = CaretBrowsing.getCursorRect(
                    new Cursor(sel.focusNode, sel.focusOffset,
                        TraverseUtil.getNodeText(sel.focusNode)));

                const yscroll = window.pageYOffset;
                const pageHeight = window.innerHeight;
                const caretY = rect.top;
                const caretHeight = Math.min(rect.height, 30);
                if (yscroll + pageHeight < caretY + caretHeight) {
                    window.scroll(0, (caretY + caretHeight - pageHeight + 100));
                } else if (caretY < yscroll) {
                    window.scroll(0, (caretY - 100));
                }
            }
        };

    CaretBrowsing.move = function(direction, granularity) {
        let action = "move";
        if (CaretBrowsing.selectionEnabled) {
            action = "extend";
        }
        window.
            getSelection().
            modify(action, direction, granularity);

        if (CaretBrowsing.isWindows &&
                (direction === "forward" ||
                    direction === "right") &&
                granularity === "word") {
            CaretBrowsing.move("left", "character");
        } else {
            window.setTimeout(() => {
                CaretBrowsing.updateCaretOrSelection(true);
            }, 0);
        }

        CaretBrowsing.stopAnimation();
    };

    CaretBrowsing.moveToBlock = function(paragraph, boundary) {
        let action = "move";
        if (CaretBrowsing.selectionEnabled) {
            action = "extend";
        }
        window.
            getSelection().
            modify(action, paragraph, "paragraph");

        window.
            getSelection().
            modify(action, boundary, "paragraphboundary");

        window.setTimeout(() => {
            CaretBrowsing.updateCaretOrSelection(true);
        }, 0);

        CaretBrowsing.stopAnimation();
    };

    CaretBrowsing.toggle = function(value) {
        if (CaretBrowsing.forceEnabled) {
            CaretBrowsing.recreateCaretElement();
            return;
        }

        if (value === undefined) {
            CaretBrowsing.isEnabled = !CaretBrowsing.isEnabled;
        } else {
            CaretBrowsing.isEnabled = value;
        }
        CaretBrowsing.updateIsCaretVisible();
    };

    /**
     * Event handler, called when the mouse is clicked. Chrome already
     * sets the selection when the mouse is clicked, all we need to do is
     * update our cursor.
     * @param {Event} evt The DOM event.
     * @return {boolean} True if the default action should be performed.
     */
    CaretBrowsing.onClick = function() {
        if (!CaretBrowsing.isEnabled) {
            return true;
        }
        window.setTimeout(() => {
            CaretBrowsing.targetX = null;
            CaretBrowsing.updateCaretOrSelection(false);
        }, 0);
        return true;
    };

    /**
     * Update whether or not the caret is visible, based on whether caret browsing
     * is enabled and whether this window / iframe has focus.
     */
    CaretBrowsing.updateIsCaretVisible = function() {
        CaretBrowsing.isCaretVisible =
            (CaretBrowsing.isEnabled && CaretBrowsing.isWindowFocused);
        if (CaretBrowsing.isCaretVisible && !CaretBrowsing.caretElement) {
            CaretBrowsing.setInitialCursor();
            CaretBrowsing.updateCaretOrSelection(true);
        } else if (!CaretBrowsing.isCaretVisible &&
            CaretBrowsing.caretElement) {
            window.clearInterval(CaretBrowsing.blinkFunctionId);
            if (CaretBrowsing.caretElement) {
                CaretBrowsing.isSelectionCollapsed = false;
                CaretBrowsing.caretElement.parentElement.removeChild(
                    CaretBrowsing.caretElement);
                CaretBrowsing.caretElement = null;
            }
        }
    };

    CaretBrowsing.onWindowFocus = function() {
        CaretBrowsing.isWindowFocused = true;
        CaretBrowsing.updateIsCaretVisible();
    };

    CaretBrowsing.onWindowBlur = function() {
        CaretBrowsing.isWindowFocused = false;
        CaretBrowsing.updateIsCaretVisible();
    };

    CaretBrowsing.startAnimation = function() {
        CaretBrowsing.caretElement.style.animationIterationCount = "infinite";
    };

    CaretBrowsing.stopAnimation = function() {
        CaretBrowsing.caretElement.style.animationIterationCount = 0;
        window.setTimeout(() => {
            CaretBrowsing.startAnimation();
        }, 1000);
    };

    CaretBrowsing.init = function() {
        CaretBrowsing.isWindowFocused = document.hasFocus();

        document.addEventListener("click", CaretBrowsing.onClick, false);
        window.addEventListener("focus", CaretBrowsing.onWindowFocus, false);
        window.addEventListener("blur", CaretBrowsing.onWindowBlur, false);
    };

    window.setTimeout(() => {
        if (!window.caretBrowsingLoaded) {
            window.caretBrowsingLoaded = true;
            CaretBrowsing.init();

            if (document.body &&
                document.body.getAttribute("caretbrowsing") === "on") {
                CaretBrowsing.forceEnabled = true;
                CaretBrowsing.isEnabled = true;
                CaretBrowsing.updateIsCaretVisible();
            }
        }
    }, 0);

    const funcs = {};

    funcs.setInitialCursor = () => {
        if (!CaretBrowsing.initiated) {
            CaretBrowsing.setInitialCursor();
            return CaretBrowsing.selectionEnabled;
        }

        if (window.getSelection().toString().length === 0) {
            positionCaret();
        }
        CaretBrowsing.toggle();
        return CaretBrowsing.selectionEnabled;
    };

    funcs.setPlatform = (platform, qtVersion) => {
        CaretBrowsing.isWindows = platform.startsWith("win");
        CaretBrowsing.isOldQt = qtVersion === "5.7.1";
    };

    funcs.disableCaret = () => {
        CaretBrowsing.toggle(false);
    };

    funcs.toggle = () => {
        CaretBrowsing.toggle();
    };

    funcs.moveRight = () => {
        CaretBrowsing.move("right", "character");
    };

    funcs.moveLeft = () => {
        CaretBrowsing.move("left", "character");
    };

    funcs.moveDown = () => {
        CaretBrowsing.move("forward", "line");
    };

    funcs.moveUp = () => {
        CaretBrowsing.move("backward", "line");
    };

    funcs.moveToEndOfWord = () => {
        funcs.moveToNextWord();
        funcs.moveLeft();
    };

    funcs.moveToNextWord = () => {
        CaretBrowsing.move("forward", "word");
        funcs.moveRight();
    };

    funcs.moveToPreviousWord = () => {
        CaretBrowsing.move("backward", "word");
    };

    funcs.moveToStartOfLine = () => {
        CaretBrowsing.move("left", "lineboundary");
    };

    funcs.moveToEndOfLine = () => {
        CaretBrowsing.move("right", "lineboundary");
    };

    funcs.moveToStartOfNextBlock = () => {
        CaretBrowsing.moveToBlock("forward", "backward");
    };

    funcs.moveToStartOfPrevBlock = () => {
        CaretBrowsing.moveToBlock("backward", "backward");
    };

    funcs.moveToEndOfNextBlock = () => {
        CaretBrowsing.moveToBlock("forward", "forward");
    };

    funcs.moveToEndOfPrevBlock = () => {
        CaretBrowsing.moveToBlock("backward", "forward");
    };

    funcs.moveToStartOfDocument = () => {
        CaretBrowsing.move("backward", "documentboundary");
    };

    funcs.moveToEndOfDocument = () => {
        CaretBrowsing.move("forward", "documentboundary");
        funcs.moveLeft();
    };

    funcs.dropSelection = () => {
        window.getSelection().removeAllRanges();
    };

    funcs.getSelection = () => window.getSelection().toString();

    funcs.toggleSelection = () => {
        CaretBrowsing.selectionEnabled = !CaretBrowsing.selectionEnabled;
        return CaretBrowsing.selectionEnabled;
    };

    return funcs;
})();
