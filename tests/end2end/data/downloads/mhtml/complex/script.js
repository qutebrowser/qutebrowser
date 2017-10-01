if (typeof String.prototype.endsWith !== 'function') {
    String.prototype.endsWith = function(suffix) {
        return this.indexOf(suffix, this.length - suffix.length) !== -1;
    };
}
window._keys = "";
document.onkeypress = function(evt) {
  var e = evt || window.event;
  window._keys += String.fromCharCode(e.charCode);
  if (window._keys.endsWith("qute")) {
    alert("It's just a qute browser!");
    window._keys = "";
  }
}