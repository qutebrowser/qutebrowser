/* Select all elements marked with toselect */

var toSelect = document.getElementsByClassName("toselect");
var s = window.getSelection();

if(s.rangeCount > 0) s.removeAllRanges();

for(var i = 0; i < toSelect.length; i++) {
    var range = document.createRange();
    if (toSelect[i].childNodes.length > 0) {
        range.selectNodeContents(toSelect[i].childNodes[0]);
        s.addRange(range);
    }
}
