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

var inputs = document.getElementsByTagName("input");
var found = false;
var types = /text|password|date|email|month|number|range|search|tel|time|url|week/;
var hidden = /hidden/;

function ishidden(el) {
	return hidden.test(el.attributes.value) || el.offsetParent === null;
}

for (var i = 0; i < inputs.length; i++) {
	if (inputs[i] == document.activeElement) {
		for (var j = i+1; j < inputs.length; j++) {
			if (! ishidden(inputs[j]) && types.test(inputs[j].type)) {
				inputs[j].focus();
				found = true;
				break;
			}
		}
		break;
	}
}

if (! found) {
	for (i = 0; i < inputs.length; i++) {
		if (! ishidden(inputs[i]) && types.test(inputs[i].type)) {
			inputs[i].focus();
			break;
		}
	}
}

// vim: tw=0
