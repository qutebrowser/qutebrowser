// Based on: https://vanillajstoolkit.com/polyfills/stringreplaceall/
/* eslint-disable no-extend-native */

/**
 * String.prototype.replaceAll() polyfill
 * https://gomakethings.com/how-to-replace-a-section-of-a-string-with-another-one-with-vanilla-js/
 * @author Chris Ferdinandi
 * @license MIT
 */

"use strict";

if (!String.prototype.replaceAll) {
    String.prototype.replaceAll = function(str, newStr) {
        // If a regex pattern
        if (Object.prototype.toString.call(str).toLowerCase() === "[object regexp]") {
            return this.replace(str, newStr);
        }

        // If a string
        return this.replace(new RegExp(str, "g"), newStr);
    };
}
