"use strict";

window._qutebrowser.caret = (function() {
    const funcs = {};

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
     * Set the selection to the range between the given start and end cursors.
     * @param {Cursor} start The desired start of the selection.
     * @param {Cursor} end The desired end of the selection.
     * @return {Selection} the selection object.
     */
    TraverseUtil.setSelection = function(start, end) {
        var sel = window.getSelection();
        sel.removeAllRanges();
        var range = document.createRange();
        range.setStart(start.node, start.index);
        range.setEnd(end.node, end.index);
        sel.addRange(range);

        return sel;
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
     * Moves the cursor backwards until it has crossed exactly one character.
     * @param {Cursor} cursor The cursor location where the search should start.
     *     On exit, the cursor will be immediately to the left of the
     *     character returned.
     * @param {Array<Node>} nodesCrossed Any HTML nodes crossed between the
     *     initial and final cursor position will be pushed onto this array.
     * @return {?string} The previous character, or null if the top of the
     *     document has been reached.
     */
    TraverseUtil.backwardsChar = function(cursor, nodesCrossed) {
        while (true) {
            // Move down until we get to a leaf node.
            var childNode = null;
            if (!TraverseUtil.treatAsLeafNode(cursor.node)) {
                for (var i = cursor.index - 1; i >= 0; i--) {
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
                cursor.text = TraverseUtil.getNodeText(cursor.node);
                if (cursor.text.length)
                    cursor.index = cursor.text.length;
                else
                    cursor.index = cursor.node.childNodes.length;
                if (cursor.node.constructor != Text)
                    nodesCrossed.push(cursor.node);
                continue;
            }

            // Return the previous character from this leaf node.
            if (cursor.text.length > 0 && cursor.index > 0) {
                return cursor.text[--cursor.index];
            }

            // Move to the previous sibling, going up the tree as necessary.
            while (true) {
                // Try to move to the previous sibling.
                var siblingNode = null;
                for (var node = cursor.node.previousSibling;
                    node != null;
                    node = node.previousSibling) {
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
                    if (cursor.text.length)
                        cursor.index = cursor.text.length;
                    else
                        cursor.index = cursor.node.childNodes.length;
                    if (cursor.node.constructor != Text)
                        nodesCrossed.push(cursor.node);
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

    /**
     * Finds the previous character, starting from startCursor.  Upon exit,
     * startCursor and endCursor will surround the previous character.
     * If skipWhitespace is true, will skip until a real character is found.
     * Otherwise, it will attempt to select all of the whitespace between
     * the initial position of endCursor and the next non-whitespace character.
     * @param {Cursor} startCursor The position to start searching for the
     *     char. On exit, will point to the position before the char.
     * @param {Cursor} endCursor The position to start searching for the next
     *     char. On exit, will point to the position past the char.
     * @param {Array<Node>} nodesCrossed Any HTML nodes crossed between the
     *     initial and final cursor position will be pushed onto this array.
     * @param {boolean} skipWhitespace If true, will keep scanning until a
     *     non-whitespace character is found.
     * @return {?string} The previous char, or null if the top of the
     *     document has been reached.
     */
    TraverseUtil.getPreviousChar = function(
        startCursor, endCursor, nodesCrossed, skipWhitespace) {

        // Save the starting position and get the first character.
        endCursor.copyFrom(startCursor);
        var c = TraverseUtil.backwardsChar(startCursor, nodesCrossed);
        if (c == null)
        return null;

        // Keep track of whether the first character was whitespace.
        var initialWhitespace = TraverseUtil.isWhitespace(c);

        // Keep scanning until we find a non-whitespace or non-skipped character.
        while ((TraverseUtil.isWhitespace(c)) ||
            (TraverseUtil.isSkipped(startCursor.node))) {
            c = TraverseUtil.backwardsChar(startCursor, nodesCrossed);
            if (c == null)
            return null;
        }
        if (skipWhitespace || !initialWhitespace) {
            // If skipWhitepace is true, or if the first character we encountered
            // was not whitespace, return that non-whitespace character.
            endCursor.copyFrom(startCursor);
            endCursor.index++;
            return c;
        } else {
            for (var i = 0; i < nodesCrossed.length; i++) {
                if (TraverseUtil.isSkipped(nodesCrossed[i])) {
                    startCursor.index++;
                    endCursor.copyFrom(startCursor);
                    endCursor.index++;
                    return ' ';
                }
            }
            // Otherwise, return all of the whitespace before that last character.
            startCursor.index++;
            return ' ';
        }
    };

    /**
     * Finds the next word, starting from endCursor.  Upon exit, startCursor
     * and endCursor will surround the next word.  A word is defined to be
     * a string of 1 or more non-whitespace characters in the same DOM node.
     * @param {Cursor} startCursor On exit, will point to the beginning of the
     *     word returned.
     * @param {Cursor} endCursor The position to start searching for the next
     *     word.  On exit, will point to the end of the word returned.
     * @param {Array<Node>} nodesCrossed Any HTML nodes crossed between the
     *     initial and final cursor position will be pushed onto this array.
     * @return {?string} The next word, or null if the bottom of the
     *     document has been reached.
     */
    TraverseUtil.getNextWord = function(startCursor, endCursor,
        nodesCrossed) {

        // Find the first non-whitespace or non-skipped character.
        var cursor = endCursor.clone();
        var c = TraverseUtil.forwardsChar(cursor, nodesCrossed);
        if (c == null)
        return null;
        while ((TraverseUtil.isWhitespace(c)) ||
            (TraverseUtil.isSkipped(cursor.node))) {
            c = TraverseUtil.forwardsChar(cursor, nodesCrossed);
            if (c == null)
            return null;
        }

        // Set startCursor to the position immediately before the first
        // character in our word. It's safe to decrement |index| because
        // forwardsChar guarantees that the cursor will be immediately to the
        // right of the returned character on exit.
        startCursor.copyFrom(cursor);
        startCursor.index--;

        // Keep building up our word until we reach a whitespace character or
        // would cross a tag.  Don't actually return any tags crossed, because this
        // word goes up until the tag boundary but not past it.
        endCursor.copyFrom(cursor);
        var word = c;
        var newNodesCrossed = [];
        c = TraverseUtil.forwardsChar(cursor, newNodesCrossed);
        if (c == null) {
            return word;
        }
        while (!TraverseUtil.isWhitespace(c) &&
            newNodesCrossed.length == 0) {
            word += c;
            endCursor.copyFrom(cursor);
            c = TraverseUtil.forwardsChar(cursor, newNodesCrossed);
            if (c == null) {
                return word;
            }
        }
        return word;
    };

    /**
     * Finds the previous word, starting from startCursor.  Upon exit, startCursor
     * and endCursor will surround the previous word.  A word is defined to be
     * a string of 1 or more non-whitespace characters in the same DOM node.
     * @param {Cursor} startCursor The position to start searching for the
     *     previous word.  On exit, will point to the beginning of the
     *     word returned.
     * @param {Cursor} endCursor On exit, will point to the end of the
     *     word returned.
     * @param {Array<Node>} nodesCrossed Any HTML nodes crossed between the
     *     initial and final cursor position will be pushed onto this array.
     * @return {?string} The previous word, or null if the bottom of the
     *     document has been reached.
     */
    TraverseUtil.getPreviousWord = function(startCursor, endCursor,
        nodesCrossed) {
        // Find the first non-whitespace or non-skipped character.
        var cursor = startCursor.clone();
        var c = TraverseUtil.backwardsChar(cursor, nodesCrossed);
        if (c == null)
        return null;
        while ((TraverseUtil.isWhitespace(c) ||
            (TraverseUtil.isSkipped(cursor.node)))) {
            c = TraverseUtil.backwardsChar(cursor, nodesCrossed);
            if (c == null)
            return null;
        }

        // Set endCursor to the position immediately after the first
        // character we've found (the last character of the word, since we're
        // searching backwards).
        endCursor.copyFrom(cursor);
        endCursor.index++;

        // Keep building up our word until we reach a whitespace character or
        // would cross a tag.  Don't actually return any tags crossed, because this
        // word goes up until the tag boundary but not past it.
        startCursor.copyFrom(cursor);
        var word = c;
        var newNodesCrossed = [];
        c = TraverseUtil.backwardsChar(cursor, newNodesCrossed);
        if (c == null)
        return word;
        while (!TraverseUtil.isWhitespace(c) &&
            newNodesCrossed.length == 0) {
            word = c + word;
            startCursor.copyFrom(cursor);
            c = TraverseUtil.backwardsChar(cursor, newNodesCrossed);
            if (c == null)
            return word;
        }

        return word;
    };

    /**
     * Finds the next sentence, starting from endCursor.  Upon exit,
     * startCursor and endCursor will surround the next sentence.
     *
     * @param {Cursor} startCursor On exit, marks the beginning of the sentence.
     * @param {Cursor} endCursor The position to start searching for the next
     *     sentence.  On exit, will point to the end of the returned string.
     * @param {Array<Node>} nodesCrossed Any HTML nodes crossed between the
     *     initial and final cursor position will be pushed onto this array.
     * @param {Object} breakTags Associative array of tags that should break
     *     the sentence.
     * @return {?string} The next sentence, or null if the bottom of the
     *     document has been reached.
     */
    TraverseUtil.getNextSentence = function(
        startCursor, endCursor, nodesCrossed, breakTags) {
        return TraverseUtil.getNextString(
            startCursor, endCursor, nodesCrossed,
            function(str, word, nodes) {
                if (str.substr(-1) == '.')
                    return true;
                for (var i = 0; i < nodes.length; i++) {
                    if (TraverseUtil.isSkipped(nodes[i])) {
                        return true;
                    }
                    var style = window.getComputedStyle(nodes[i], null);
                    if (style && (style.display != 'inline' ||
                        breakTags[nodes[i].tagName])) {
                        return true;
                    }
                }
                return false;
            });
    };

    /**
     * Finds the previous sentence, starting from startCursor.  Upon exit,
     * startCursor and endCursor will surround the previous sentence.
     *
     * @param {Cursor} startCursor The position to start searching for the next
     *     sentence.  On exit, will point to the start of the returned string.
     * @param {Cursor} endCursor On exit, the end of the returned string.
     * @param {Array<Node>} nodesCrossed Any HTML nodes crossed between the
     *     initial and final cursor position will be pushed onto this array.
     * @param {Object} breakTags Associative array of tags that should break
     *     the sentence.
     * @return {?string} The previous sentence, or null if the bottom of the
     *     document has been reached.
     */
    TraverseUtil.getPreviousSentence = function(
        startCursor, endCursor, nodesCrossed, breakTags) {
        return TraverseUtil.getPreviousString(
            startCursor, endCursor, nodesCrossed,
            function(str, word, nodes) {
                if (word.substr(-1) == '.')
                    return true;
                for (var i = 0; i < nodes.length; i++) {
                    if (TraverseUtil.isSkipped(nodes[i])) {
                        return true;
                    }
                    var style = window.getComputedStyle(nodes[i], null);
                    if (style && (style.display != 'inline' ||
                        breakTags[nodes[i].tagName])) {
                        return true;
                    }
                }
                return false;
            });
    };

    /**
     * Finds the next line, starting from endCursor.  Upon exit,
     * startCursor and endCursor will surround the next line.
     *
     * @param {Cursor} startCursor On exit, marks the beginning of the line.
     * @param {Cursor} endCursor The position to start searching for the next
     *     line.  On exit, will point to the end of the returned string.
     * @param {Array<Node>} nodesCrossed Any HTML nodes crossed between the
     *     initial and final cursor position will be pushed onto this array.
     * @param {number} lineLength The maximum number of characters in a line.
     * @param {Object} breakTags Associative array of tags that should break
     *     the line.
     * @return {?string} The next line, or null if the bottom of the
     *     document has been reached.
     */
    TraverseUtil.getNextLine = function(
        startCursor, endCursor, nodesCrossed, lineLength, breakTags) {
        return TraverseUtil.getNextString(
            startCursor, endCursor, nodesCrossed,
            function(str, word, nodes) {
                if (str.length + word.length + 1 > lineLength)
                    return true;
                for (var i = 0; i < nodes.length; i++) {
                    if (TraverseUtil.isSkipped(nodes[i])) {
                        return true;
                    }
                    var style = window.getComputedStyle(nodes[i], null);
                    if (style && (style.display != 'inline' ||
                        breakTags[nodes[i].tagName])) {
                        return true;
                    }
                }
                return false;
            });
    };

    /**
     * Finds the previous line, starting from startCursor.  Upon exit,
     * startCursor and endCursor will surround the previous line.
     *
     * @param {Cursor} startCursor The position to start searching for the next
     *     line.  On exit, will point to the start of the returned string.
     * @param {Cursor} endCursor On exit, the end of the returned string.
     * @param {Array<Node>} nodesCrossed Any HTML nodes crossed between the
     *     initial and final cursor position will be pushed onto this array.
     * @param {number} lineLength The maximum number of characters in a line.
     * @param {Object} breakTags Associative array of tags that should break
     *     the sentence.
     *  @return {?string} The previous line, or null if the bottom of the
     *     document has been reached.
     */
    TraverseUtil.getPreviousLine = function(
        startCursor, endCursor, nodesCrossed, lineLength, breakTags) {
        return TraverseUtil.getPreviousString(
            startCursor, endCursor, nodesCrossed,
            function(str, word, nodes) {
                if (str.length + word.length + 1 > lineLength)
                    return true;
                for (var i = 0; i < nodes.length; i++) {
                    if (TraverseUtil.isSkipped(nodes[i])) {
                        return true;
                    }
                    var style = window.getComputedStyle(nodes[i], null);
                    if (style && (style.display != 'inline' ||
                        breakTags[nodes[i].tagName])) {
                        return true;
                    }
                }
                return false;
            });
    };

    /**
     * Finds the next paragraph, starting from endCursor.  Upon exit,
     * startCursor and endCursor will surround the next paragraph.
     *
     * @param {Cursor} startCursor On exit, marks the beginning of the paragraph.
     * @param {Cursor} endCursor The position to start searching for the next
     *     paragraph.  On exit, will point to the end of the returned string.
     * @param {Array<Node>} nodesCrossed Any HTML nodes crossed between the
     *     initial and final cursor position will be pushed onto this array.
     * @return {?string} The next paragraph, or null if the bottom of the
     *     document has been reached.
     */
    TraverseUtil.getNextParagraph = function(startCursor, endCursor,
        nodesCrossed) {
        return TraverseUtil.getNextString(
            startCursor, endCursor, nodesCrossed,
            function(str, word, nodes) {
                for (var i = 0; i < nodes.length; i++) {
                    if (TraverseUtil.isSkipped(nodes[i])) {
                        return true;
                    }
                    var style = window.getComputedStyle(nodes[i], null);
                    if (style && style.display != 'inline') {
                        return true;
                    }
                }
                return false;
            });
    };

    /**
     * Finds the previous paragraph, starting from startCursor.  Upon exit,
     * startCursor and endCursor will surround the previous paragraph.
     *
     * @param {Cursor} startCursor The position to start searching for the next
     *     paragraph.  On exit, will point to the start of the returned string.
     * @param {Cursor} endCursor On exit, the end of the returned string.
     * @param {Array<Node>} nodesCrossed Any HTML nodes crossed between the
     *     initial and final cursor position will be pushed onto this array.
     * @return {?string} The previous paragraph, or null if the bottom of the
     *     document has been reached.
     */
    TraverseUtil.getPreviousParagraph = function(
        startCursor, endCursor, nodesCrossed) {
        return TraverseUtil.getPreviousString(
            startCursor, endCursor, nodesCrossed,
            function(str, word, nodes) {
                for (var i = 0; i < nodes.length; i++) {
                    if (TraverseUtil.isSkipped(nodes[i])) {
                        return true;
                    }
                    var style = window.getComputedStyle(nodes[i], null);
                    if (style && style.display != 'inline') {
                        return true;
                    }
                }
                return false;
            });
    };

    /**
     * Customizable function to return the next string of words in the DOM, based
     * on provided functions to decide when to break one string and start
     * the next. This can be used to get the next sentence, line, paragraph,
     * or potentially other granularities.
     *
     * Finds the next contiguous string, starting from endCursor.  Upon exit,
     * startCursor and endCursor will surround the next string.
     *
     * The breakBefore function takes three parameters, and
     * should return true if the string should be broken before the proposed
     * next word:
     *   str The string so far.
     *   word The next word to be added.
     *   nodesCrossed The nodes crossed in reaching this next word.
     *
     * @param {Cursor} startCursor On exit, will point to the beginning of the
     *     next string.
     * @param {Cursor} endCursor The position to start searching for the next
     *     string.  On exit, will point to the end of the returned string.
     * @param {Array<Node>} nodesCrossed Any HTML nodes crossed between the
     *     initial and final cursor position will be pushed onto this array.
     * @param {function(string, string, Array<string>)} breakBefore
     *     Function that takes the string so far, next word to be added, and
     *     nodes crossed, and returns true if the string should be ended before
     *     adding this word.
     * @return {?string} The next string, or null if the bottom of the
     *     document has been reached.
     */
    TraverseUtil.getNextString = function(
        startCursor, endCursor, nodesCrossed, breakBefore) {
        // Get the first word and set the start cursor to the start of the
        // first word.
        var wordStartCursor = endCursor.clone();
        var wordEndCursor = endCursor.clone();
        var newNodesCrossed = [];
        var str = '';
        var word = TraverseUtil.getNextWord(
            wordStartCursor, wordEndCursor, newNodesCrossed);
        if (word == null)
        return null;
        startCursor.copyFrom(wordStartCursor);

        // Always add the first word when the string is empty, and then keep
        // adding more words as long as breakBefore returns false
        while (!str || !breakBefore(str, word, newNodesCrossed)) {
            // Append this word, set the end cursor to the end of this word, and
            // update the returned list of nodes crossed to include ones we crossed
            // in reaching this word.
            if (str)
                str += ' ';
            str += word;
            nodesCrossed = nodesCrossed.concat(newNodesCrossed);
            endCursor.copyFrom(wordEndCursor);

            // Get the next word and go back to the top of the loop.
            newNodesCrossed = [];
            word = TraverseUtil.getNextWord(
                wordStartCursor, wordEndCursor, newNodesCrossed);
            if (word == null)
                return str;
        }

        return str;
    };

    /**
     * Customizable function to return the previous string of words in the DOM,
     * based on provided functions to decide when to break one string and start
     * the next. See getNextString, above, for more details.
     *
     * Finds the previous contiguous string, starting from startCursor.  Upon exit,
     * startCursor and endCursor will surround the next string.
     *
     * @param {Cursor} startCursor The position to start searching for the
     *     previous string.  On exit, will point to the beginning of the
     *     string returned.
     * @param {Cursor} endCursor On exit, will point to the end of the
     *     string returned.
     * @param {Array<Node>} nodesCrossed Any HTML nodes crossed between the
     *     initial and final cursor position will be pushed onto this array.
     * @param {function(string, string, Array<string>)} breakBefore
     *     Function that takes the string so far, the word to be added, and
     *     nodes crossed, and returns true if the string should be ended before
     *     adding this word.
     * @return {?string} The next string, or null if the top of the
     *     document has been reached.
     */
    TraverseUtil.getPreviousString = function(
        startCursor, endCursor, nodesCrossed, breakBefore) {
        // Get the first word and set the end cursor to the end of the
        // first word.
        var wordStartCursor = startCursor.clone();
        var wordEndCursor = startCursor.clone();
        var newNodesCrossed = [];
        var str = '';
        var word = TraverseUtil.getPreviousWord(
            wordStartCursor, wordEndCursor, newNodesCrossed);
        if (word == null)
        return null;
        endCursor.copyFrom(wordEndCursor);

        // Always add the first word when the string is empty, and then keep
        // adding more words as long as breakBefore returns false
        while (!str || !breakBefore(str, word, newNodesCrossed)) {
            // Prepend this word, set the start cursor to the start of this word, and
            // update the returned list of nodes crossed to include ones we crossed
            // in reaching this word.
            if (str)
                str = ' ' + str;
            str = word + str;
            nodesCrossed = nodesCrossed.concat(newNodesCrossed);
            startCursor.copyFrom(wordStartCursor);
            v
            // Get the previous word and go back to the top of the loop.
            newNodesCrossed = [];
            word = TraverseUtil.getPreviousWord(
                wordStartCursor, wordEndCursor, newNodesCrossed);
            if (word == null)
                return str;
        }

        return str;
    };


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

    /**
     * Determines whether or not a node is or is the descendant of another node.
     *
     * @param {Object} node The node to be checked.
     * @param {Object} ancestor The node to see if it's a descendant of.
     * @return {boolean} True if the node is ancestor or is a descendant of it.
     */
    function isDescendantOfNode(node, ancestor) {
        while (node && ancestor) {
            if (node.isSameNode(ancestor)) {
                return true;
            }
            node = node.parentNode;
        }
        return false;
    }


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
     * Whether or not we're on a Mac - affects modifier keys.
     * @type {boolean}
     */
    CaretBrowsing.isMac = (navigator.appVersion.indexOf("Mac") != -1);

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

    /**
     * If there's no initial selection, set the cursor just before the
     * first text character in the document.
     */
    funcs.setInitialCursor = () => {
        CaretBrowsing.setInitialCursor();
    }

    CaretBrowsing.setInitialCursor = function() {
        var sel = window.getSelection();
        if (sel.rangeCount > 0) {
            return;
        }

        var start = new Cursor(document.body, 0, '');
        var end = new Cursor(document.body, 0, '');
        var nodesCrossed = [];
        var result = TraverseUtil.getNextChar(start, end, nodesCrossed, true);
        if (result == null) {
            return;
        }
        CaretBrowsing.setAndValidateSelection(start, start);
        CaretBrowsing.toggle();
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
     * Set focus to the first focusable node in the given list.
     * select the text, otherwise it doesn't appear focused to the user.
     * Every other control behaves normally if you just call focus() on it.
     * @param {Array<Node>} nodeList An array of nodes to focus.
     * @return {boolean} True if the node was focused.
     */
    CaretBrowsing.setFocusToFirstFocusable = function(nodeList) {
        for (var i = 0; i < nodeList.length; i++) {
            if (CaretBrowsing.setFocusToNode(nodeList[i])) {
                return true;
            }
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

    /**
     * Return true if the selection directionality is ambiguous, which happens
     * if, for example, the user double-clicks in the middle of a word to select
     * it. In that case, the selection should extend by the right edge if the
     * user presses right, and by the left edge if the user presses left.
     * @param {Selection} sel The selection.
     * @return {boolean} True if the selection directionality is ambiguous.
     */
    CaretBrowsing.isAmbiguous = function(sel) {
        return (sel.anchorNode != sel.baseNode ||
            sel.anchorOffset != sel.baseOffset ||
            sel.focusNode != sel.extentNode ||
            sel.focusOffset != sel.extentOffset);
    };

    /**
     * Create a Cursor from the anchor position of the selection, the
     * part that doesn't normally move.
     * @param {Selection} sel The selection.
     * @return {Cursor} A cursor pointing to the selection's anchor location.
     */
    CaretBrowsing.makeAnchorCursor = function(sel) {
        return new Cursor(sel.anchorNode, sel.anchorOffset,
            TraverseUtil.getNodeText(sel.anchorNode));
    };

    /**
     * Create a Cursor from the focus position of the selection.
     * @param {Selection} sel The selection.
     * @return {Cursor} A cursor pointing to the selection's focus location.
     */
    CaretBrowsing.makeFocusCursor = function(sel) {
        return new Cursor(sel.focusNode, sel.focusOffset,
            TraverseUtil.getNodeText(sel.focusNode));
    };

    /**
     * Create a Cursor from the left boundary of the selection - the boundary
     * closer to the start of the document.
     * @param {Selection} sel The selection.
     * @return {Cursor} A cursor pointing to the selection's left boundary.
     */
    CaretBrowsing.makeLeftCursor = function(sel) {
        var range = sel.rangeCount == 1 ? sel.getRangeAt(0) : null;
        if (range &&
            range.endContainer == sel.anchorNode &&
            range.endOffset == sel.anchorOffset) {
            return CaretBrowsing.makeFocusCursor(sel);
        } else {
            return CaretBrowsing.makeAnchorCursor(sel);
        }
    };

    /**
     * Create a Cursor from the right boundary of the selection - the boundary
     * closer to the end of the document.
     * @param {Selection} sel The selection.
     * @return {Cursor} A cursor pointing to the selection's right boundary.
     */
    CaretBrowsing.makeRightCursor = function(sel) {
        var range = sel.rangeCount == 1 ? sel.getRangeAt(0) : null;
        if (range &&
            range.endContainer == sel.anchorNode &&
            range.endOffset == sel.anchorOffset) {
            return CaretBrowsing.makeAnchorCursor(sel);
        } else {
            return CaretBrowsing.makeFocusCursor(sel);
        }
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

    /**
     * Note: the built-in function by the same name is unreliable.
     * @param {Selection} sel The selection.
     * @return {boolean} True if the start and end positions are the same.
     */
    CaretBrowsing.isCollapsed = function(sel) {
        return (sel.anchorOffset == sel.focusOffset &&
            sel.anchorNode == sel.focusNode);
    };

    /**
     * Determines if the modifier key is held down that should cause
     * the cursor to move by word rather than by character.
     * @param {Event} evt A keyboard event.
     * @return {boolean} True if the cursor should move by word.
     */
    CaretBrowsing.isMoveByWordEvent = function(evt) {
        if (CaretBrowsing.isMac) {
            return evt.altKey;
        } else {
            return evt.ctrlKey;
        }
    };

    /**
     * Moves the cursor forwards to the next valid position.
     * @param {Cursor} cursor The current cursor location.
     *     On exit, the cursor will be at the next position.
     * @param {Array<Node>} nodesCrossed Any HTML nodes crossed between the
     *     initial and final cursor position will be pushed onto this array.
     * @return {?string} The character reached, or null if the bottom of the
     *     document has been reached.
     */
    CaretBrowsing.forwards = function(cursor, nodesCrossed) {
        var previousCursor = cursor.clone();
        var result = TraverseUtil.forwardsChar(cursor, nodesCrossed);

        // Work around the fact that TraverseUtil.forwardsChar returns once per
        // char in a block of text, rather than once per possible selection
        // position in a block of text.
        if (result && cursor.node != previousCursor.node && cursor.index > 0) {
            cursor.index = 0;
        }

        return result;
    };

    /**
     * Moves the cursor backwards to the previous valid position.
     * @param {Cursor} cursor The current cursor location.
     *     On exit, the cursor will be at the previous position.
     * @param {Array<Node>} nodesCrossed Any HTML nodes crossed between the
     *     initial and final cursor position will be pushed onto this array.
     * @return {?string} The character reached, or null if the top of the
     *     document has been reached.
     */
    CaretBrowsing.backwards = function(cursor, nodesCrossed) {
        var previousCursor = cursor.clone();
        var result = TraverseUtil.backwardsChar(cursor, nodesCrossed);

        // Work around the fact that TraverseUtil.backwardsChar returns once per
        // char in a block of text, rather than once per possible selection
        // position in a block of text.
        if (result &&
            cursor.node != previousCursor.node &&
            cursor.index < cursor.text.length) {
            cursor.index = cursor.text.length;
        }

        return result;
    };

    /**
     * Called when the user presses the right arrow. If there's a selection,
     * moves the cursor to the end of the selection range. If it's a cursor,
     * moves past one character.
     * @param {Event} evt The DOM event.
     * @return {boolean} True if the default action should be performed.
     */
    CaretBrowsing.moveRight = function(evt) {
        CaretBrowsing.targetX = null;

        var sel = window.getSelection();
        if (!evt.shiftKey && !CaretBrowsing.isCollapsed(sel)) {
            var right = CaretBrowsing.makeRightCursor(sel);
            CaretBrowsing.setAndValidateSelection(right, right);
            return false;
        }

        var start = CaretBrowsing.isAmbiguous(sel) ?
            CaretBrowsing.makeLeftCursor(sel) :
            CaretBrowsing.makeAnchorCursor(sel);
        var end = CaretBrowsing.isAmbiguous(sel) ?
            CaretBrowsing.makeRightCursor(sel) :
            CaretBrowsing.makeFocusCursor(sel);
        var previousEnd = end.clone();
        var nodesCrossed = [];
        while (true) {
            var result;
            if (CaretBrowsing.isMoveByWordEvent(evt)) {
                result = TraverseUtil.getNextWord(previousEnd, end, nodesCrossed);
            } else {
                previousEnd = end.clone();
                result = CaretBrowsing.forwards(end, nodesCrossed);
            }

            if (result === null) {
                return CaretBrowsing.moveLeft(evt);
            }

            if (CaretBrowsing.setAndValidateSelection(
                evt.shiftKey ? start : end, end)) {
                break;
            }
        }

        if (!evt.shiftKey) {
            nodesCrossed.push(end.node);
            CaretBrowsing.setFocusToFirstFocusable(nodesCrossed);
        }

        return false;
    };

    /**
     * Called when the user presses the left arrow. If there's a selection,
     * moves the cursor to the start of the selection range. If it's a cursor,
     * moves backwards past one character.
     * @param {Event} evt The DOM event.
     * @return {boolean} True if the default action should be performed.
     */
    CaretBrowsing.moveLeft = function(evt) {
        CaretBrowsing.targetX = null;

        var sel = window.getSelection();
        if (!evt.shiftKey && !CaretBrowsing.isCollapsed(sel)) {
            var left = CaretBrowsing.makeLeftCursor(sel);
            CaretBrowsing.setAndValidateSelection(left, left);
            return false;
        }

        var start = CaretBrowsing.isAmbiguous(sel) ?
            CaretBrowsing.makeLeftCursor(sel) :
            CaretBrowsing.makeFocusCursor(sel);
        var end = CaretBrowsing.isAmbiguous(sel) ?
            CaretBrowsing.makeRightCursor(sel) :
            CaretBrowsing.makeAnchorCursor(sel);
        var previousStart = start.clone();
        var nodesCrossed = [];
        while (true) {
            var result;
            if (CaretBrowsing.isMoveByWordEvent(evt)) {
                result = TraverseUtil.getPreviousWord(
                    start, previousStart, nodesCrossed);
            } else {
                previousStart = start.clone();
                result = CaretBrowsing.backwards(start, nodesCrossed);
            }

            if (result === null) {
                break;
            }

            if (CaretBrowsing.setAndValidateSelection(
                evt.shiftKey ? end : start, start)) {
                break;
            }
        }

        if (!evt.shiftKey) {
            nodesCrossed.push(start.node);
            CaretBrowsing.setFocusToFirstFocusable(nodesCrossed);
        }

        return false;
    };


    /**
     * Called when the user presses the down arrow. If there's a selection,
     * moves the cursor to the end of the selection range. If it's a cursor,
     * attempts to move to the equivalent horizontal pixel position in the
     * subsequent line of text. If this is impossible, go to the first character
     * of the next line.
     * @param {Event} evt The DOM event.
     * @return {boolean} True if the default action should be performed.
     */
    CaretBrowsing.moveDown = function(evt) {
        var sel = window.getSelection();
        if (!evt.shiftKey && !CaretBrowsing.isCollapsed(sel)) {
            var right = CaretBrowsing.makeRightCursor(sel);
            CaretBrowsing.setAndValidateSelection(right, right);
            return false;
        }

        var start = CaretBrowsing.isAmbiguous(sel) ?
            CaretBrowsing.makeLeftCursor(sel) :
            CaretBrowsing.makeAnchorCursor(sel);
        var end = CaretBrowsing.isAmbiguous(sel) ?
            CaretBrowsing.makeRightCursor(sel) :
            CaretBrowsing.makeFocusCursor(sel);
        var endRect = CaretBrowsing.getCursorRect(end);
        if (CaretBrowsing.targetX === null) {
            CaretBrowsing.targetX = endRect.left;
        }
        var previousEnd = end.clone();
        var leftPos = end.clone();
        var rightPos = end.clone();
        var bestPos = null;
        var bestY = null;
        var bestDelta = null;
        var bestHeight = null;
        var nodesCrossed = [];
        var y = -1;
        while (true) {
            if (null === CaretBrowsing.forwards(rightPos, nodesCrossed)) {
                if (CaretBrowsing.setAndValidateSelection(
                    evt.shiftKey ? start : leftPos, leftPos)) {
                    break;
                } else {
                    return CaretBrowsing.moveLeft(evt);
                }
                break;
            }
            var range = document.createRange();
            range.setStart(leftPos.node, leftPos.index);
            range.setEnd(rightPos.node, rightPos.index);
            var rect = range.getBoundingClientRect();
            if (rect && rect.width < rect.height) {
                y = rect.top + window.pageYOffset;

                // Return the best match so far if we get half a line past the best.
                if (bestY != null && y > bestY + bestHeight / 2) {
                    if (CaretBrowsing.setAndValidateSelection(
                        evt.shiftKey ? start : bestPos, bestPos)) {
                        break;
                    } else {
                        bestY = null;
                    }
                }

                // Stop here if we're an entire line the wrong direction
                // (for example, we reached the top of the next column).
                if (y < endRect.top - endRect.height) {
                    if (CaretBrowsing.setAndValidateSelection(
                        evt.shiftKey ? start : leftPos, leftPos)) {
                        break;
                    }
                }

                // Otherwise look to see if this current position is on the
                // next line and better than the previous best match, if any.
                if (y >= endRect.top + endRect.height) {
                    var deltaLeft = Math.abs(CaretBrowsing.targetX - rect.left);
                    if ((bestDelta == null || deltaLeft < bestDelta) &&
                        (leftPos.node != end.node || leftPos.index != end.index)) {
                        bestPos = leftPos.clone();
                        bestY = y;
                        bestDelta = deltaLeft;
                        bestHeight = rect.height;
                    }
                    var deltaRight = Math.abs(CaretBrowsing.targetX - rect.right);
                    if (bestDelta == null || deltaRight < bestDelta) {
                        bestPos = rightPos.clone();
                        bestY = y;
                        bestDelta = deltaRight;
                        bestHeight = rect.height;
                    }

                    // Return the best match so far if the deltas are getting worse,
                    // not better.
                    if (bestDelta != null &&
                        deltaLeft > bestDelta &&
                        deltaRight > bestDelta) {
                        if (CaretBrowsing.setAndValidateSelection(
                            evt.shiftKey ? start : bestPos, bestPos)) {
                            break;
                        } else {
                            bestY = null;
                        }
                    }
                }
            }
            leftPos = rightPos.clone();
        }

        if (!evt.shiftKey) {
            CaretBrowsing.setFocusToNode(leftPos.node);
        }

        return false;
    };

    /**
     * Called when the user presses the up arrow. If there's a selection,
     * moves the cursor to the start of the selection range. If it's a cursor,
     * attempts to move to the equivalent horizontal pixel position in the
     * previous line of text. If this is impossible, go to the last character
     * of the previous line.
     * @param {Event} evt The DOM event.
     * @return {boolean} True if the default action should be performed.
     */
    CaretBrowsing.moveUp = function(evt) {
        var sel = window.getSelection();
        if (!evt.shiftKey && !CaretBrowsing.isCollapsed(sel)) {
            var left = CaretBrowsing.makeLeftCursor(sel);
            CaretBrowsing.setAndValidateSelection(left, left);
            return false;
        }

        var start = CaretBrowsing.isAmbiguous(sel) ?
            CaretBrowsing.makeLeftCursor(sel) :
            CaretBrowsing.makeFocusCursor(sel);
        var end = CaretBrowsing.isAmbiguous(sel) ?
            CaretBrowsing.makeRightCursor(sel) :
            CaretBrowsing.makeAnchorCursor(sel);
        var startRect = CaretBrowsing.getCursorRect(start);
        if (CaretBrowsing.targetX === null) {
            CaretBrowsing.targetX = startRect.left;
        }
        var previousStart = start.clone();
        var leftPos = start.clone();
        var rightPos = start.clone();
        var bestPos = null;
        var bestY = null;
        var bestDelta = null;
        var bestHeight = null;
        var nodesCrossed = [];
        var y = 999999;
        while (true) {
            if (null === CaretBrowsing.backwards(leftPos, nodesCrossed)) {
                CaretBrowsing.setAndValidateSelection(
                    evt.shiftKey ? end : rightPos, rightPos);
                break;
            }
            var range = document.createRange();
            range.setStart(leftPos.node, leftPos.index);
            range.setEnd(rightPos.node, rightPos.index);
            var rect = range.getBoundingClientRect();
            if (rect && rect.width < rect.height) {
                y = rect.top + window.pageYOffset;

                // Return the best match so far if we get half a line past the best.
                if (bestY != null && y < bestY - bestHeight / 2) {
                    if (CaretBrowsing.setAndValidateSelection(
                        evt.shiftKey ? end : bestPos, bestPos)) {
                        break;
                    } else {
                        bestY = null;
                    }
                }

                // Exit if we're an entire line the wrong direction
                // (for example, we reached the bottom of the previous column.)
                if (y > startRect.top + startRect.height) {
                    if (CaretBrowsing.setAndValidateSelection(
                        evt.shiftKey ? end : rightPos, rightPos)) {
                        break;
                    }
                }

                // Otherwise look to see if this current position is on the
                // next line and better than the previous best match, if any.
                if (y <= startRect.top - startRect.height) {
                    var deltaLeft = Math.abs(CaretBrowsing.targetX - rect.left);
                    if (bestDelta == null || deltaLeft < bestDelta) {
                        bestPos = leftPos.clone();
                        bestY = y;
                        bestDelta = deltaLeft;
                        bestHeight = rect.height;
                    }
                    var deltaRight = Math.abs(CaretBrowsing.targetX - rect.right);
                    if ((bestDelta == null || deltaRight < bestDelta) &&
                        (rightPos.node != start.node || rightPos.index != start.index)) {
                        bestPos = rightPos.clone();
                        bestY = y;
                        bestDelta = deltaRight;
                        bestHeight = rect.height;
                    }

                    // Return the best match so far if the deltas are getting worse,
                    // not better.
                    if (bestDelta != null &&
                        deltaLeft > bestDelta &&
                        deltaRight > bestDelta) {
                        if (CaretBrowsing.setAndValidateSelection(
                            evt.shiftKey ? end : bestPos, bestPos)) {
                            break;
                        } else {
                            bestY = null;
                        }
                    }
                }
            }
            rightPos = leftPos.clone();
        }

        if (!evt.shiftKey) {
            CaretBrowsing.setFocusToNode(rightPos.node);
        }

        return false;
    };

    /**
     * Set the document's selection to surround a control, so that the next
     * arrow key they press will allow them to explore the content before
     * or after a given control.
     * @param {Node} control The control to escape from.
     */
    CaretBrowsing.escapeFromControl = function(control) {
        control.blur();

        var start = new Cursor(control, 0, '');
        var previousStart = start.clone();
        var end = new Cursor(control, 0, '');
        var previousEnd = end.clone();

        var nodesCrossed = [];
        while (true) {
            if (null === CaretBrowsing.backwards(start, nodesCrossed)) {
                break;
            }

            var r = document.createRange();
            r.setStart(start.node, start.index);
            r.setEnd(previousStart.node, previousStart.index);
            if (r.getBoundingClientRect()) {
                break;
            }
            previousStart = start.clone();
        }
        while (true) {
            if (null === CaretBrowsing.forwards(end, nodesCrossed)) {
                break;
            }
            if (isDescendantOfNode(end.node, control)) {
                previousEnd = end.clone();
                continue;
            }

            var r = document.createRange();
            r.setStart(previousEnd.node, previousEnd.index);
            r.setEnd(end.node, end.index);
            if (r.getBoundingClientRect()) {
                break;
            }
        }

        if (!isDescendantOfNode(previousStart.node, control)) {
            start = previousStart.clone();
        }

        if (!isDescendantOfNode(previousEnd.node, control)) {
            end = previousEnd.clone();
        }

        CaretBrowsing.setAndValidateSelection(start, end);

        window.setTimeout(function() {
            CaretBrowsing.updateCaretOrSelection(true);
        }, 0);
    };

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
     * Event handler, called when a key is pressed.
     * @param {Event} evt The DOM event.
     * @return {boolean} True if the default action should be performed.
     */
    CaretBrowsing.onKeyDown = function(evt) {
        if (evt.defaultPrevented) {
            return;
        }

        if (evt.keyCode == 118) {  // F7
            CaretBrowsing.toggle();
        }

        if (!CaretBrowsing.isEnabled) {
            return true;
        }

        if (evt.target && CaretBrowsing.isControlThatNeedsArrowKeys(
            /** @type (Node) */(evt.target))) {
            if (evt.keyCode == 27) {
                CaretBrowsing.escapeFromControl(/** @type {Node} */(evt.target));
                evt.preventDefault();
                evt.stopPropagation();
                return false;
            } else {
                return true;
            }
        }

        // If the current selection doesn't have a range, try to escape out of
        // the current control. If that fails, return so we don't fail whe
        // trying to move the cursor or selection.
        var sel = window.getSelection();
        if (sel.rangeCount == 0) {
            if (document.activeElement) {
                CaretBrowsing.escapeFromControl(document.activeElement);
                sel = window.getSelection();
            }

            if (sel.rangeCount == 0) {
                return true;
            }
        }

        if (CaretBrowsing.caretElement) {
            CaretBrowsing.caretElement.style.visibility = 'visible';
            CaretBrowsing.blinkFlag = true;
        }

        var result = true;
        switch (evt.keyCode) {
            case 37:
                result = CaretBrowsing.moveLeft(evt);
                break;
            case 38:
                result = CaretBrowsing.moveUp(evt);
                break;
            case 39:
                result = CaretBrowsing.moveRight(evt);
                break;
            case 40:
                result = CaretBrowsing.moveDown(evt);
                break;
        }

        if (result == false) {
            evt.preventDefault();
            evt.stopPropagation();
        }

        window.setTimeout(function() {
            CaretBrowsing.updateCaretOrSelection(result == false);
        }, 0);

        return result;
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

        document.addEventListener('keydown', CaretBrowsing.onKeyDown, false);
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

    return funcs;
})();
