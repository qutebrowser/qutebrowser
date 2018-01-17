/* Cycle <input> text boxes.
 * works with the types defined in 'types'.
 * Note: Does not work for <textarea>.
 *
 * Example keybind:
 * CYCLE_INPUTS = "jseval -q -f ~/.config/qutebrowser/cycle-inputs.js"
 * config.bind('gi', CYCLE_INPUTS)
 *
 * By dive on freenode <dave@dawoodfall.net>
 */

"use strict";
var inputs = document.getElementsByTagName("input");
var types = /text|password|date|email|month|number|range|search|tel|time|url|week/;
var hidden = /hidden/;
var found = false;
var ii = 0;
var jj = 0;

function ishidden(el) {
    return hidden.test(el.attributes.value) || el.offsetParent === null;
}

for (ii = 0; ii < inputs.length; ii++) {
    if (inputs[ii] === document.activeElement) {
        for (jj = ii + 1; jj < inputs.length; jj++) {
            if (!ishidden(inputs[jj]) && types.test(inputs[jj].type)) {
                inputs[jj].focus();
                found = true;
                break;
            }
        }
        break;
    }
}

if (!found) {
    for (ii = 0; ii < inputs.length; ii++) {
        if (!ishidden(inputs[ii]) && types.test(inputs[ii].type)) {
            inputs[ii].focus();
            break;
        }
    }
}

// vim: tw=0 expandtab tabstop=4 softtabstop=4 shiftwidth=4
