"use strict";

window._qutebrowser.caret = (function() {

    var axs = {};

    axs.dom = {};

    axs.color = {};

    axs.utils = {};

    axs.dom.parentElement = function(a) {
        if (!a) {
            return null;
        }
        a = axs.dom.composedParentNode(a);
        if (!a) {
            return null;
        }
        switch(a.nodeType) {
            case Node.ELEMENT_NODE:
                return a;
            default:
                return axs.dom.parentElement(a);
        }
    };

    axs.dom.shadowHost = function(a) {
        return "host" in a ? a.host : null;
    };

    axs.dom.composedParentNode = function(a) {
        if (!a) {
            return null;
        }
        if (a.nodeType === Node.DOCUMENT_FRAGMENT_NODE) {
            return axs.dom.shadowHost(a);
        }
        var b = a.parentNode;
        if (!b) {
            return null;
        }
        if (b.nodeType === Node.DOCUMENT_FRAGMENT_NODE) {
            return axs.dom.shadowHost(b);
        }
        if (!b.shadowRoot) {
            return b;
        }
        a = a.getDestinationInsertionPoints();
        return 0 < a.length ? axs.dom.composedParentNode(a[a.length - 1]) : null;
    };

    axs.color.Color = function(a, b, c, d) {
        this.red = a;
        this.green = b;
        this.blue = c;
        this.alpha = d;
    };

    axs.color.parseColor = function(a) {
        if ("transparent" === a) {
            return new axs.color.Color(0, 0, 0, 0);
        }
        var b = a.match(/^rgb\((\d+), (\d+), (\d+)\)$/);
        if (b) {
            a = parseInt(b[1], 10);
            var c = parseInt(b[2], 10), d = parseInt(b[3], 10);
            return new axs.color.Color(a, c, d, 1);
        }
        return (b = a.match(/^rgba\((\d+), (\d+), (\d+), (\d*(\.\d+)?)\)/)) ? (a = parseInt(b[1], 10), c = parseInt(b[2], 10), d = parseInt(b[3], 10), b = parseFloat(b[4]), new axs.color.Color(a, c, d, b)) : null;
    };

    axs.color.flattenColors = function(a, b) {
        var c = a.alpha;
        return new axs.color.Color((1 - c) * b.red + c * a.red, (1 - c) * b.green + c * a.green, (1 - c) * b.blue + c * a.blue, a.alpha + b.alpha * (1 - a.alpha));
    };

    axs.utils.getParentBgColor = function(a) {
        var b = a;
        a = [];
        for (var c = null;b = axs.dom.parentElement(b);) {
            var d = window.getComputedStyle(b, null);
            if (d) {
                var e = axs.color.parseColor(d.backgroundColor);
                if (e && (1 > d.opacity && (e.alpha *= d.opacity), 0 != e.alpha && (a.push(e), 1 == e.alpha))) {
                    c = !0;
                    break;
                }
            }
        }
        c || a.push(new axs.color.Color(255, 255, 255, 1));
        for (b = a.pop();a.length;) {
            c = a.pop(), b = axs.color.flattenColors(c, b);
        }
        return b;
    };

    axs.utils.getFgColor = function(a, b, c) {
        var d = axs.color.parseColor(a.color);
        if (!d) {
            return null;
        }
        1 > d.alpha && (d = axs.color.flattenColors(d, c));
        1 > a.opacity && (b = axs.utils.getParentBgColor(b), d.alpha *= a.opacity, d = axs.color.flattenColors(d, b));
        return d;
    };

    axs.utils.getBgColor = function(a, b) {
        var c = axs.color.parseColor(a.backgroundColor);
        if (!c) {
            return null;
        }
        1 > a.opacity && (c.alpha *= a.opacity);
        if (1 > c.alpha) {
            var d = axs.utils.getParentBgColor(b);
            if (null == d) {
                return null;
            }
            c = axs.color.flattenColors(c, d);
        }
        return c;
    };

    axs.color.colorChannelToString = function(a) {
        a = Math.round(a);
        return 15 >= a ? "0" + a.toString(16) : a.toString(16);
    };

    axs.color.colorToString = function(a) {
        return 1 == a.alpha ? "#" + axs.color.colorChannelToString(a.red) + axs.color.colorChannelToString(a.green) + axs.color.colorChannelToString(a.blue) : "rgba(" + [a.red, a.green, a.blue, a.alpha].join() + ")";
    };

    var Cursor = function(node, index, text) {
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

    var TraverseUtil = function() {};

    TraverseUtil.getNodeText = function(node) {
        if (node.constructor == Text) {
            return node.data;
        } else {
            return '';
        }
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
        return node.childNodes.length == 0 ||
            node.nodeName == 'SELECT' ||
            node.nodeName == 'OBJECT';
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
    TraverseUtil.isWhitespace = function(c) {
        return (c == ' ' || c == '\n' || c == '\r' || c == '\t');
    };

    /**
     * Use the computed CSS style to figure out if this DOM node is currently
     * visible.
     * @param {Node} node A HTML DOM node.
     * @return {boolean} Whether or not the html node is visible.
     */
    TraverseUtil.isVisible = function(node) {
        if (!node.style)
            return true;
        var style = window.getComputedStyle(/** @type {Element} */(node), null);
        return (!!style && style.display != 'none' && style.visibility != 'hidden');
    };

    /**
     * Use the class name to figure out if this DOM node should be traversed.
     * @param {Node} node A HTML DOM node.
     * @return {boolean} Whether or not the html node should be traversed.
     */
    TraverseUtil.isSkipped = function(node) {
        if (node.constructor == Text)
            node = node.parentElement;
        if (node.className == 'CaretBrowsing_Caret' ||
            node.className == 'CaretBrowsing_AnimateCaret') {
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
        while (true) {
            // Move down until we get to a leaf node.
            var childNode = null;
            if (!TraverseUtil.treatAsLeafNode(cursor.node)) {
                for (var i = cursor.index; i < cursor.node.childNodes.length; i++) {
                    var node = cursor.node.childNodes[i];
                    if (TraverseUtil.isSkipped(node)) {
                        nodesCrossed.push(node);
                        continue;
                    }
                    if (TraverseUtil.isVisible(node)) {
                        childNode = node;
                        break;
                    }
                }
            }
            if (childNode) {
                cursor.node = childNode;
                cursor.index = 0;
                cursor.text = TraverseUtil.getNodeText(cursor.node);
                if (cursor.node.constructor != Text) {
                    nodesCrossed.push(cursor.node);
                }
                continue;
            }

            // Return the next character from this leaf node.
            if (cursor.index < cursor.text.length)
                return cursor.text[cursor.index++];

            // Move to the next sibling, going up the tree as necessary.
            while (cursor.node != null) {
                // Try to move to the next sibling.
                var siblingNode = null;
                for (var node = cursor.node.nextSibling;
                    node != null;
                    node = node.nextSibling) {
                    if (TraverseUtil.isSkipped(node)) {
                        nodesCrossed.push(node);
                        continue;
                    }
                    if (TraverseUtil.isVisible(node)) {
                        siblingNode = node;
                        break;
                    }
                }
                if (siblingNode) {
                    cursor.node = siblingNode;
                    cursor.text = TraverseUtil.getNodeText(siblingNode);
                    cursor.index = 0;

                    if (cursor.node.constructor != Text) {
                        nodesCrossed.push(cursor.node);
                    }

                    break;
                }

                // Otherwise, move to the parent.
                if (cursor.node.parentNode &&
                    cursor.node.parentNode.constructor != HTMLBodyElement) {
                    cursor.node = cursor.node.parentNode;
                    cursor.text = null;
                    cursor.index = 0;
                } else {
                    return null;
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
        var c = TraverseUtil.forwardsChar(endCursor, nodesCrossed);
        if (c == null)
        return null;

        // Keep track of whether the first character was whitespace.
        var initialWhitespace = TraverseUtil.isWhitespace(c);

        // Keep scanning until we find a non-whitespace or non-skipped character.
        while ((TraverseUtil.isWhitespace(c)) ||
            (TraverseUtil.isSkipped(endCursor.node))) {
            c = TraverseUtil.forwardsChar(endCursor, nodesCrossed);
            if (c == null)
            return null;
        }
        if (skipWhitespace || !initialWhitespace) {
            // If skipWhitepace is true, or if the first character we encountered
            // was not whitespace, return that non-whitespace character.
            startCursor.copyFrom(endCursor);
            startCursor.index--;
            return c;
        }
        else {
            for (var i = 0; i < nodesCrossed.length; i++) {
                if (TraverseUtil.isSkipped(nodesCrossed[i])) {
                    // We need to make sure that startCursor and endCursor aren't
                    // surrounding a skippable node.
                    endCursor.index--;
                    startCursor.copyFrom(endCursor);
                    startCursor.index--;
                    return ' ';
                }
            }
            // Otherwise, return all of the whitespace before that last character.
            endCursor.index--;
            return ' ';
        }
    };

    var CaretBrowsing = function() {};

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
    CaretBrowsing.onEnable;

    /**
     * What to do when the caret jumps?
     * @type {string}
     */
    CaretBrowsing.onJump;

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
    CaretBrowsing.caretElement;

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
    CaretBrowsing.caretForeground = '#000';

    /**
     * The backgroundc color.
     * @type {string}
     */
    CaretBrowsing.caretBackground = '#fff';

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

        if (node == document.body || node != document.activeElement) {
            return false;
        }

        if (node.constructor == HTMLSelectElement) {
            return true;
        }

        if (node.constructor == HTMLInputElement) {
            switch (node.type) {
                case 'email':
                case 'number':
                case 'password':
                case 'search':
                case 'text':
                case 'tel':
                case 'url':
                case '':
                    return true;  // All of these are text boxes.
                case 'datetime':
                case 'datetime-local':
                case 'date':
                case 'month':
                case 'radio':
                case 'range':
                case 'week':
                    return true;  // These are other input elements that use arrows.
            }
        }

        // Handle focusable ARIA controls.
        if (node.getAttribute && isFocusable(node)) {
            var role = node.getAttribute('role');
            switch (role) {
                case 'combobox':
                case 'grid':
                case 'gridcell':
                case 'listbox':
                case 'menu':
                case 'menubar':
                case 'menuitem':
                case 'menuitemcheckbox':
                case 'menuitemradio':
                case 'option':
                case 'radiogroup':
                case 'scrollbar':
                case 'slider':
                case 'spinbutton':
                case 'tab':
                case 'tablist':
                case 'textbox':
                case 'tree':
                case 'treegrid':
                case 'treeitem':
                    return true;
            }
        }

        return false;
    };

    CaretBrowsing.injectCaretStyles = function() {
        var style = '.CaretBrowsing_Caret {' +
            '  position: absolute;' +
            '  z-index: 2147483647;' +
            '  min-height: 10px;' +
            '  background-color: #000;' +
            '}' +
            '.CaretBrowsing_AnimateCaret {' +
            '  position: absolute;' +
            '  z-index: 2147483647;' +
            '  min-height: 10px;' +
            '}' +
            '.CaretBrowsing_FlashVert {' +
            '  position: absolute;' +
            '  z-index: 2147483647;' +
            '  background: linear-gradient(' +
            '      270deg,' +
            '      rgba(128, 128, 255, 0) 0%,' +
            '      rgba(128, 128, 255, 0.3) 45%,' +
            '      rgba(128, 128, 255, 0.8) 50%,' +
            '      rgba(128, 128, 255, 0.3) 65%,' +
            '      rgba(128, 128, 255, 0) 100%);' +
            '}';
        var node = document.createElement('style');
        node.innerHTML = style;
        document.body.appendChild(node);
    }

    CaretBrowsing.setInitialCursor = function() {
        var sel = window.getSelection();
        if (sel.rangeCount > 0) {
            return;
        }

        positionCaret();
        CaretBrowsing.injectCaretStyles();
        CaretBrowsing.toggle();
        CaretBrowsing.initiated = true;
        CaretBrowsing.selectionEnabled = false;
    };

    /**
     * Try to set the window's selection to be between the given start and end
     * cursors, and return whether or not it was successful.
     * @param {Cursor} start The start position.
     * @param {Cursor} end The end position.
     * @return {boolean} True if the selection was successfully set.
     */
    CaretBrowsing.setAndValidateSelection = function(start, end) {
        var sel = window.getSelection();
        sel.setBaseAndExtent(start.node, start.index, end.node, end.index);

        if (sel.rangeCount != 1) {
            return false;
        }

        return (sel.anchorNode == start.node &&
            sel.anchorOffset == start.index &&
            sel.focusNode == end.node &&
            sel.focusOffset == end.index);
    };


    CaretBrowsing.setFocusToNode = function(node) {
        while (node && node != document.body) {
            if (isFocusable(node) && node.constructor != HTMLIFrameElement) {
                node.focus();
                if (node.constructor == HTMLInputElement && node.select) {
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
        var element = CaretBrowsing.caretElement;
        element.className = 'CaretBrowsing_Caret';
        element.style.opacity = CaretBrowsing.isSelectionCollapsed ? '1.0' : '0.0';
        element.style.left = CaretBrowsing.caretX + 'px';
        element.style.top = CaretBrowsing.caretY + 'px';
        element.style.width = CaretBrowsing.caretWidth + 'px';
        element.style.height = CaretBrowsing.caretHeight + 'px';
        element.style.color = CaretBrowsing.caretForeground;
    };

    /**
     * Animate the caret element into the normal style.
     */
    CaretBrowsing.animateCaretElement = function() {
        var element = CaretBrowsing.caretElement;
        element.style.left = (CaretBrowsing.caretX - 50) + 'px';
        element.style.top = (CaretBrowsing.caretY - 100) + 'px';
        element.style.width = (CaretBrowsing.caretWidth + 100) + 'px';
        element.style.height = (CaretBrowsing.caretHeight + 200) + 'px';
        element.className = 'CaretBrowsing_AnimateCaret';

        // Start the animation. The setTimeout is so that the old values will get
        // applied first, so we can animate to the new values.
        window.setTimeout(function() {
            if (!CaretBrowsing.caretElement) {
                return;
            }
            CaretBrowsing.setCaretElementNormalStyle();
            element.style['transition'] = 'all 0.8s ease-in';
            function listener() {
                element.removeEventListener(
                    'transitionend', listener, false);
                element.style['transition'] = 'none';
            }
            element.addEventListener(
                'transitionend', listener, false);
        }, 0);
    };

    /**
     * Quick flash and then show the normal caret style.
     */
    CaretBrowsing.flashCaretElement = function() {
        var x = CaretBrowsing.caretX;
        var y = CaretBrowsing.caretY;
        var height = CaretBrowsing.caretHeight;

        var vert = document.createElement('div');
        vert.className = 'CaretBrowsing_FlashVert';
        vert.style.left = (x - 6) + 'px';
        vert.style.top = (y - 100) + 'px';
        vert.style.width = '11px';
        vert.style.height = (200) + 'px';
        document.body.appendChild(vert);

        window.setTimeout(function() {
            document.body.removeChild(vert);
            if (CaretBrowsing.caretElement) {
                CaretBrowsing.setCaretElementNormalStyle();
            }
        }, 250);
    };

    /**
     * Create the caret element. This assumes that caretX, caretY,
     * caretWidth, and caretHeight have all been set. The caret is
     * animated in so the user can find it when it first appears.
     */
    CaretBrowsing.createCaretElement = function() {
        var element = document.createElement('div');
        element.className = 'CaretBrowsing_Caret';
        document.body.appendChild(element);
        CaretBrowsing.caretElement = element;

        if (CaretBrowsing.onEnable == 'anim') {
            CaretBrowsing.animateCaretElement();
        } else if (CaretBrowsing.onEnable == 'flash') {
            CaretBrowsing.flashCaretElement();
        } else {
            CaretBrowsing.setCaretElementNormalStyle();
        }
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
        var node = cursor.node;
        var index = cursor.index;
        var rect = {
            left: 0,
            top: 0,
            width: 1,
            height: 0
        };
        if (node.constructor == Text) {
            var left = index;
            var right = index;
            var max = node.data.length;
            var newRange = document.createRange();
            while (left > 0 || right < max) {
                if (left > 0) {
                    left--;
                    newRange.setStart(node, left);
                    newRange.setEnd(node, index);
                    var rangeRect = newRange.getBoundingClientRect();
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
                    var rangeRect = newRange.getBoundingClientRect();
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
    CaretBrowsing.updateCaretOrSelection = function(scrollToSelection) {
        var previousX = CaretBrowsing.caretX;
        var previousY = CaretBrowsing.caretY;

        var sel = window.getSelection();
        if (sel.rangeCount == 0) {
            if (CaretBrowsing.caretElement) {
                CaretBrowsing.isSelectionCollapsed = false;
                CaretBrowsing.caretElement.style.opacity = '0.0';
            }
            return;
        }

        var range = sel.getRangeAt(0);
        if (!range) {
            if (CaretBrowsing.caretElement) {
                CaretBrowsing.isSelectionCollapsed = false;
                CaretBrowsing.caretElement.style.opacity = '0.0';
            }
            return;
        }

        if (CaretBrowsing.isControlThatNeedsArrowKeys(document.activeElement)) {
            var node = document.activeElement;
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
        } else if (range.startOffset != range.endOffset ||
            range.startContainer != range.endContainer) {
            var rect = range.getBoundingClientRect();
            if (!rect) {
                return;
            }
            CaretBrowsing.caretX = rect.left + window.pageXOffset;
            CaretBrowsing.caretY = rect.top + window.pageYOffset;
            CaretBrowsing.caretWidth = rect.width;
            CaretBrowsing.caretHeight = rect.height;
            CaretBrowsing.isSelectionCollapsed = false;
        } else {
            var rect = CaretBrowsing.getCursorRect(
                new Cursor(range.startContainer,
                    range.startOffset,
                    TraverseUtil.getNodeText(range.startContainer)));
            CaretBrowsing.caretX = rect.left;
            CaretBrowsing.caretY = rect.top;
            CaretBrowsing.caretWidth = rect.width;
            CaretBrowsing.caretHeight = rect.height;
            CaretBrowsing.isSelectionCollapsed = true;
        }

        if (!CaretBrowsing.caretElement) {
            CaretBrowsing.createCaretElement();
        } else {
            var element = CaretBrowsing.caretElement;
            if (CaretBrowsing.isSelectionCollapsed) {
                element.style.opacity = '1.0';
                element.style.left = CaretBrowsing.caretX + 'px';
                element.style.top = CaretBrowsing.caretY + 'px';
                element.style.width = CaretBrowsing.caretWidth + 'px';
                element.style.height = CaretBrowsing.caretHeight + 'px';
            } else {
                element.style.opacity = '0.0';
            }
        }

        var elem = range.startContainer;
        if (elem.constructor == Text)
            elem = elem.parentElement;
        var style = window.getComputedStyle(elem);
        var bg = axs.utils.getBgColor(style, elem);
        var fg = axs.utils.getFgColor(style, elem, bg);
        CaretBrowsing.caretBackground = axs.color.colorToString(bg);
        CaretBrowsing.caretForeground = axs.color.colorToString(fg);

        if (scrollToSelection) {
            // Scroll just to the "focus" position of the selection,
            // the part the user is manipulating.
            var rect = CaretBrowsing.getCursorRect(
                new Cursor(sel.focusNode, sel.focusOffset,
                    TraverseUtil.getNodeText(sel.focusNode)));

            var yscroll = window.pageYOffset;
            var pageHeight = window.innerHeight;
            var caretY = rect.top;
            var caretHeight = Math.min(rect.height, 30);
            if (yscroll + pageHeight < caretY + caretHeight) {
                window.scroll(0, (caretY + caretHeight - pageHeight + 100));
            } else if (caretY < yscroll) {
                window.scroll(0, (caretY - 100));
            }
        }

        if (Math.abs(previousX - CaretBrowsing.caretX) > 500 ||
            Math.abs(previousY - CaretBrowsing.caretY) > 100) {
            if (CaretBrowsing.onJump == 'anim') {
                CaretBrowsing.animateCaretElement();
            } else if (CaretBrowsing.onJump == 'flash') {
                CaretBrowsing.flashCaretElement();
            }
        }
    };

    CaretBrowsing.move = function(direction, granularity) {
        window
            .getSelection()
            .modify(
                CaretBrowsing.selectionEnabled ? 'extend' : 'move', 
                direction,
                granularity);

        window.setTimeout(function() {
            CaretBrowsing.updateCaretOrSelection(true);
        }, 0);
    }

    CaretBrowsing.moveToBlock = function(paragraph, boundary) {
        window
            .getSelection()
            .modify(
                CaretBrowsing.selectionEnabled ? 'extend' : 'move', 
                paragraph, 
                'paragraph');

        window
            .getSelection()
            .modify(
                CaretBrowsing.selectionEnabled ? 'extend' : 'move', 
                boundary, 
                'paragraphboundary');

        window.setTimeout(function() {
            CaretBrowsing.updateCaretOrSelection(true);
        }, 0);

    }

    /**
     * Toggle whether caret browsing is enabled or not.
     */
    CaretBrowsing.toggle = function() {
        if (CaretBrowsing.forceEnabled) {
            CaretBrowsing.recreateCaretElement();
            return;
        }

        CaretBrowsing.isEnabled = !CaretBrowsing.isEnabled;
        var obj = {};
        obj['enabled'] = CaretBrowsing.isEnabled;
        CaretBrowsing.updateIsCaretVisible();
    };

    /**
     * Event handler, called when the mouse is clicked. Chrome already
     * sets the selection when the mouse is clicked, all we need to do is
     * update our cursor.
     * @param {Event} evt The DOM event.
     * @return {boolean} True if the default action should be performed.
     */
    CaretBrowsing.onClick = function(evt) {
        if (!CaretBrowsing.isEnabled) {
            return true;
        }
        window.setTimeout(function() {
            CaretBrowsing.targetX = null;
            CaretBrowsing.updateCaretOrSelection(false);
        }, 0);
        return true;
    };

    /**
     * Called at a regular interval. Blink the cursor by changing its visibility.
     */
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

    /**
     * Called when the prefs get updated.
     */
    /**
     * Called when this window / iframe gains focus.
     */
    CaretBrowsing.onWindowFocus = function() {
        CaretBrowsing.isWindowFocused = true;
        CaretBrowsing.updateIsCaretVisible();
    };

    /**
     * Called when this window / iframe loses focus.
     */
    CaretBrowsing.onWindowBlur = function() {
        CaretBrowsing.isWindowFocused = false;
        CaretBrowsing.updateIsCaretVisible();
    };

    /**
     * Initializes caret browsing by adding event listeners and extension
     * message listeners.
     */
    CaretBrowsing.init = function() {
        CaretBrowsing.isWindowFocused = document.hasFocus();

        document.addEventListener('click', CaretBrowsing.onClick, false);
        window.addEventListener('focus', CaretBrowsing.onWindowFocus, false);
        window.addEventListener('blur', CaretBrowsing.onWindowBlur, false);
    };

    window.setTimeout(function() {

        // Make sure the script only loads once.
        if (!window['caretBrowsingLoaded']) {
            window['caretBrowsingLoaded'] = true;
            CaretBrowsing.init();

            if (document.body.getAttribute('caretbrowsing') == 'on') {
                CaretBrowsing.forceEnabled = true;
                CaretBrowsing.isEnabled = true;
                CaretBrowsing.updateIsCaretVisible();
            }

        }

    }, 0);

    function isElementInViewport(node) {  // eslint-disable-line complexity
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
            var start = new Cursor(el, 0, '');
            var end = new Cursor(el, 0, '');
            var nodesCrossed = [];
            var result = TraverseUtil.getNextChar(start, end, nodesCrossed, true);
            if (result == null) {
                return;
            }
            CaretBrowsing.setAndValidateSelection(start, start);
        }
    }

    function isFocusable(targetNode) {
        if (!targetNode || typeof(targetNode.tabIndex) != 'number') {
            return false;
        }

        if (targetNode.tabIndex >= 0) {
            return true;
        }

        if (targetNode.hasAttribute &&
            targetNode.hasAttribute('tabindex') &&
            targetNode.getAttribute('tabindex') == '-1') {
            return true;
        }

        return false;
    }

    const funcs = {};

    funcs.setInitialCursor = () => {
        if (!CaretBrowsing.initiated) {
            CaretBrowsing.setInitialCursor();
        } else {
            if (!window.getSelection().toString()) {
                positionCaret();
            }
            CaretBrowsing.toggle();
        }
    }

    funcs.toggle = () => {
        CaretBrowsing.toggle();
    }

    funcs.moveRight = () => {
        CaretBrowsing.move('right', 'character');
    }

    funcs.moveLeft = () => {
        CaretBrowsing.move('left', 'character');
    }

    funcs.moveDown = () => {
        CaretBrowsing.move('forward', 'line');
    }

    funcs.moveUp = () => {
        CaretBrowsing.move('backward', 'line');
    }

    funcs.moveToEndOfWord = () => {
        funcs.moveToNextWord();
        funcs.moveLeft();
    }

    funcs.moveToNextWord = () => {
        CaretBrowsing.move('forward', 'word');
        funcs.moveRight();
    }

    funcs.moveToPreviousWord = () => {
        CaretBrowsing.move('backward', 'word');
    }

    funcs.moveToStartOfLine = () => {
        CaretBrowsing.move('left', 'lineboundary');
    }

    funcs.moveToEndOfLine = () => {
        CaretBrowsing.move('right', 'lineboundary');
    }

    funcs.moveToStartOfNextBlock = () => {
        CaretBrowsing.moveToBlock('forward', 'backward');
    }

    funcs.moveToStartOfPrevBlock = () => {
        CaretBrowsing.moveToBlock('backward', 'backward');
    }

    funcs.moveToEndOfNextBlock = () => {
        CaretBrowsing.moveToBlock('forward', 'forward');
    }

    funcs.moveToEndOfPrevBlock = () => {
        CaretBrowsing.moveToBlock('backward', 'forward');
    }

    funcs.moveToStartOfDocument = () => {
        CaretBrowsing.move('backward', 'documentboundary');
    }

    funcs.moveToEndOfDocument = () => {
        CaretBrowsing.move('forward', 'documentboundary');
    }

    funcs.dropSelection = () => {
        window.getSelection().removeAllRanges();
    }

    funcs.getSelection = () => {
        return window.getSelection().toString();
    }

    funcs.toggleSelection = () => {
        CaretBrowsing.selectionEnabled = !CaretBrowsing.selectionEnabled;
    }

    return funcs;
})();
