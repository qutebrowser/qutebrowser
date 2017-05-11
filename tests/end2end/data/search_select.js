/* Select all elements marked with toselect */

var toSelect = document.getElementsByClassName("toselect");
var s = window.getSelection();

if(s.rangeCount > 0) s.removeAllRanges();

for(var i = 0; i < toSelect.length; i++) {
    var range = document.createRange();
    range.selectNode(toSelect[i]);
    s.addRange(range);
}
