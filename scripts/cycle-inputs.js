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
var i = 0;
var k = 0;

function ishidden(el) {
    return hidden.test(el.attributes.value) || el.offsetParent === null;
}

for (i = 0; i < inputs.length; i++) {
    if (inputs[i] === document.activeElement) {
        for (k = i + 1; k < inputs.length; k++) {
            if (!ishidden(inputs[k]) && types.test(inputs[k].type)) {
                inputs[k].focus();
                found = true;
                break;
            }
        }
        break;
    }
}

if (!found) {
    for (i = 0; i < inputs.length; i++) {
        if (!ishidden(inputs[i]) && types.test(inputs[i].type)) {
            inputs[i].focus();
            break;
        }
    }
}

// vim: tw=0 expandtab tabstop=4 softtabstop=4 shiftwidth=4
