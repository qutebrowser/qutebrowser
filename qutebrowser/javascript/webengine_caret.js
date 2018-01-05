/* eslint-disable max-lines, max-len, max-statements, complexity, max-params, default-case */
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
 * Create and control div caret, which listen commands from qutebrowser,
 * change document selection model and div caret position.
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
                        (color.alpha *= style.opacity),
                        color.alpha !== 0 &&
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

    // eslint-disable-next-line func-style
    const Cursor = function(node, index, text) {
        this.node = node;
        this.index = index;
        this.text = text;
    };

    Cursor.prototype.clone = function() {
        return new Cursor(this.node, this.index, this.text);
    };

    Cursor.prototype.copyFrom = function(otherCursor) {
        this.node = otherCursor.node;
        this.index = otherCursor.index;
        this.text = otherCursor.text;
    };

    const TraverseUtil = {};

    TraverseUtil.getNodeText = function(node) {
        if (node.constructor === Text) {
            return node.data;
        }
        return "";
    };

    TraverseUtil.treatAsLeafNode = function(node) {
        return node.childNodes.length === 0 ||
            node.nodeName === "SELECT" ||
            node.nodeName === "OBJECT";
    };

    TraverseUtil.isWhitespace = function(ch) {
        return (ch === " " || ch === "\n" || ch === "\r" || ch === "\t");
    };

    TraverseUtil.isVisible = function(node) {
        if (!node.style) {
            return true;
        }
        const style = window.getComputedStyle(node, null);
        return (Boolean(style) &&
            style.display !== "none" &&
            style.visibility !== "hidden");
    };

    TraverseUtil.isSkipped = function(_node) {
        let node = _node;
        if (node.constructor === Text) {
            node = node.parentElement;
        }
        if (node.className === "CaretBrowsing_Caret" ||
            node.className === "CaretBrowsing_AnimateCaret") {
            return true;
        }
        return false;
    };

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
                if (cursor.index < cursor.text.length) {
                    return cursor.text[cursor.index++];
                }

                while (cursor.node !== null) {
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

    TraverseUtil.getNextChar = function(
        startCursor, endCursor, nodesCrossed, skipWhitespace) {
        startCursor.copyFrom(endCursor);
        let fChar = TraverseUtil.forwardsChar(endCursor, nodesCrossed);
        if (fChar === null) {
            return null;
        }

        const initialWhitespace = TraverseUtil.isWhitespace(fChar);

        while ((TraverseUtil.isWhitespace(fChar)) ||
            (TraverseUtil.isSkipped(endCursor.node))) {
            fChar = TraverseUtil.forwardsChar(endCursor, nodesCrossed);
            if (fChar === null) {
                return null;
            }
        }
        if (skipWhitespace || !initialWhitespace) {
            startCursor.copyFrom(endCursor);
            startCursor.index--;
            return fChar;
        }

        for (let i = 0; i < nodesCrossed.length; i++) {
            if (TraverseUtil.isSkipped(nodesCrossed[i])) {
                endCursor.index--;
                startCursor.copyFrom(endCursor);
                startCursor.index--;
                return " ";
            }
        }
        endCursor.index--;
        return " ";
    };

    const CaretBrowsing = {};

    CaretBrowsing.isEnabled = false;

    CaretBrowsing.forceEnabled = false;

    CaretBrowsing.onEnable = undefined;

    CaretBrowsing.onJump = undefined;

    CaretBrowsing.isWindowFocused = false;

    CaretBrowsing.isCaretVisible = false;

    CaretBrowsing.caretElement = undefined;

    CaretBrowsing.caretX = 0;

    CaretBrowsing.caretY = 0;

    CaretBrowsing.caretWidth = 0;

    CaretBrowsing.caretHeight = 0;

    CaretBrowsing.caretForeground = "#000";

    CaretBrowsing.caretBackground = "#fff";

    CaretBrowsing.isSelectionCollapsed = false;

    CaretBrowsing.blinkFunctionId = null;

    CaretBrowsing.targetX = null;

    CaretBrowsing.blinkFlag = true;

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
                return true;
            case "datetime":
            case "datetime-local":
            case "date":
            case "month":
            case "radio":
            case "range":
            case "week":
                return true;
            }
        }

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
        const style = ".CaretBrowsing_Caret {" +
            "  position: absolute;" +
            "  z-index: 2147483647;" +
            "  min-height: 10px;" +
            "  background-color: #000;" +
            "}" +
            ".CaretBrowsing_AnimateCaret {" +
            "  position: absolute;" +
            "  z-index: 2147483647;" +
            "  min-height: 10px;" +
            "}" +
            ".CaretBrowsing_FlashVert {" +
            "  position: absolute;" +
            "  z-index: 2147483647;" +
            "  background: linear-gradient(" +
            "      270deg," +
            "      rgba(128, 128, 255, 0) 0%," +
            "      rgba(128, 128, 255, 0.3) 45%," +
            "      rgba(128, 128, 255, 0.8) 50%," +
            "      rgba(128, 128, 255, 0.3) 65%," +
            "      rgba(128, 128, 255, 0) 100%);" +
            "}";
        const node = document.createElement("style");
        node.innerHTML = style;
        document.body.appendChild(node);
    };

    CaretBrowsing.setInitialCursor = function(platform) {
        CaretBrowsing.isWindows = platform === "Windows";
        if (window.getSelection().rangeCount > 0) {
            return;
        }

        positionCaret();
        CaretBrowsing.injectCaretStyles();
        CaretBrowsing.toggle();
        CaretBrowsing.initiated = true;
        CaretBrowsing.selectionEnabled = false;
    };

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

    CaretBrowsing.animateCaretElement = function() {
        const element = CaretBrowsing.caretElement;
        element.style.left = `${CaretBrowsing.caretX - 50}px`;
        element.style.top = `${CaretBrowsing.caretY - 100}px`;
        element.style.width = `${CaretBrowsing.caretWidth + 100}px`;
        element.style.height = `${CaretBrowsing.caretHeight + 200}px`;
        element.className = "CaretBrowsing_AnimateCaret";

        window.setTimeout(() => {
            if (!CaretBrowsing.caretElement) {
                return;
            }
            CaretBrowsing.setCaretElementNormalStyle();
            element.style.transition = "all 0.8s ease-in";
            function listener() {
                element.removeEventListener(
                    "transitionend", listener, false);
                element.style.transition = "none";
            }
            element.addEventListener(
                "transitionend", listener, false);
        }, 0);
    };

    CaretBrowsing.flashCaretElement = function() {
        const x = CaretBrowsing.caretX;
        const y = CaretBrowsing.caretY;

        const vert = document.createElement("div");
        vert.className = "CaretBrowsing_FlashVert";
        vert.style.left = `${x - 6}px`;
        vert.style.top = `${y - 100}px`;
        vert.style.width = "11px";
        vert.style.height = `${200}px`;
        document.body.appendChild(vert);

        window.setTimeout(() => {
            document.body.removeChild(vert);
            if (CaretBrowsing.caretElement) {
                CaretBrowsing.setCaretElementNormalStyle();
            }
        }, 250);
    };

    CaretBrowsing.createCaretElement = function() {
        const element = document.createElement("div");
        element.className = "CaretBrowsing_Caret";
        document.body.appendChild(element);
        CaretBrowsing.caretElement = element;

        if (CaretBrowsing.onEnable === "anim") {
            CaretBrowsing.animateCaretElement();
        } else if (CaretBrowsing.onEnable === "flash") {
            CaretBrowsing.flashCaretElement();
        } else {
            CaretBrowsing.setCaretElementNormalStyle();
        }
    };

    CaretBrowsing.recreateCaretElement = function() {
        if (CaretBrowsing.caretElement) {
            window.clearInterval(CaretBrowsing.blinkFunctionId);
            CaretBrowsing.caretElement.parentElement.removeChild(
                CaretBrowsing.caretElement);
            CaretBrowsing.caretElement = null;
            CaretBrowsing.updateIsCaretVisible();
        }
    };

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

    CaretBrowsing.updateCaretOrSelection =
        function(scrollToSelection) {
            const previousX = CaretBrowsing.caretX;
            const previousY = CaretBrowsing.caretY;

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

            if (Math.abs(previousX - CaretBrowsing.caretX) > 500 ||
                Math.abs(previousY - CaretBrowsing.caretY) > 100) {
                if (CaretBrowsing.onJump === "anim") {
                    CaretBrowsing.animateCaretElement();
                } else if (CaretBrowsing.onJump === "flash") {
                    CaretBrowsing.flashCaretElement();
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
    };

    CaretBrowsing.toggle = function() {
        if (CaretBrowsing.forceEnabled) {
            CaretBrowsing.recreateCaretElement();
            return;
        }

        CaretBrowsing.isEnabled = !CaretBrowsing.isEnabled;
        const obj = {};
        obj.enabled = CaretBrowsing.isEnabled;
        CaretBrowsing.updateIsCaretVisible();
    };

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

    CaretBrowsing.caretBlinkFunction = function() {
        if (CaretBrowsing.caretElement) {
            if (CaretBrowsing.blinkFlag) {
                CaretBrowsing.caretElement.style.backgroundColor =
                    CaretBrowsing.caretForeground;
                CaretBrowsing.blinkFlag = false;
            } else {
                CaretBrowsing.caretElement.style.backgroundColor =
                    CaretBrowsing.caretBackground;
                CaretBrowsing.blinkFlag = true;
            }
        }
    };

    CaretBrowsing.updateIsCaretVisible = function() {
        CaretBrowsing.isCaretVisible =
            (CaretBrowsing.isEnabled && CaretBrowsing.isWindowFocused);
        if (CaretBrowsing.isCaretVisible && !CaretBrowsing.caretElement) {
            CaretBrowsing.setInitialCursor(CaretBrowsing.isWindows);
            CaretBrowsing.updateCaretOrSelection(true);
            if (CaretBrowsing.caretElement) {
                CaretBrowsing.blinkFunctionId = window.setInterval(
                    CaretBrowsing.caretBlinkFunction, 500);
            }
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

    funcs.setInitialCursor = (platform) => {
        if (!CaretBrowsing.initiated) {
            CaretBrowsing.setInitialCursor(platform);
            return;
        }

        if (!window.getSelection().toString()) {
            positionCaret();
        }
        CaretBrowsing.toggle();
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
    };

    return funcs;
})();
