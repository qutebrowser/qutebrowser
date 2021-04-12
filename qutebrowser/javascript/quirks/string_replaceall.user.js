/* eslint-disable no-extend-native,no-implicit-globals */

"use strict";

// https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Regular_Expressions
function escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// Based on: https://vanillajstoolkit.com/polyfills/stringreplaceall/
/**
 * String.prototype.replaceAll() polyfill
 * https://gomakethings.com/how-to-replace-a-section-of-a-string-with-another-one-with-vanilla-js/
 * @author Chris Ferdinandi
 * @license MIT
 */
if (!String.prototype.replaceAll) {
    String.prototype.replaceAll = function(str, newStr) {
        // If a regex pattern
        if (Object.prototype.toString.call(str) === "[object RegExp]") {
            return this.replace(str, newStr);
        }

        // If a string
        return this.replace(new RegExp(escapeRegExp(str), "g"), newStr);
    };
}
