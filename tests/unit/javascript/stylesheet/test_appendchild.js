// Taken from acid3 bucket 5
// https://github.com/w3c/web-platform-tests/blob/37cf5607a39357a0f213ab5df2e6b30499b0226f/acid/acid3/test.html#L2320

// test 65: bring in a couple of SVG files and some HTML files dynamically - preparation for later tests in this bucket
// NOTE FROM 2011 UPDATE: The svg.xml file still contains the SVG font, but it is no longer used
kungFuDeathGrip = document.createElement('p');
kungFuDeathGrip.className = 'removed';
var iframe, object;
// svg iframe
iframe = document.createElement('iframe');
iframe.onload = function () { kungFuDeathGrip.title += '1' };
// iframe.src = "svg.xml";
kungFuDeathGrip.appendChild(iframe);
// object iframe
object = document.createElement('object');
object.onload = function () { kungFuDeathGrip.title += '2' };
// object.data = "svg.xml";
kungFuDeathGrip.appendChild(object);
// xml iframe
iframe = document.createElement('iframe');
iframe.onload = function () { kungFuDeathGrip.title += '3' };
// iframe.src = "empty.xml";
kungFuDeathGrip.appendChild(iframe);
// html iframe
iframe = document.createElement('iframe');
iframe.onload = function () { kungFuDeathGrip.title += '4' };
// iframe.src = "empty.html";
kungFuDeathGrip.appendChild(iframe);
// html iframe
iframe = document.createElement('iframe');
iframe.onload = function () { kungFuDeathGrip.title += '5' };
// iframe.src = "xhtml.1";
kungFuDeathGrip.appendChild(iframe);
// html iframe
iframe = document.createElement('iframe');
iframe.onload = function () { kungFuDeathGrip.title += '6' };
// iframe.src = "xhtml.2";
kungFuDeathGrip.appendChild(iframe);
// html iframe
iframe = document.createElement('iframe');
iframe.onload = function () { kungFuDeathGrip.title += '7' };
// iframe.src = "xhtml.3";
kungFuDeathGrip.appendChild(iframe);
// add the lot to the document

// Modified as we don't have a 'map'
document.getElementsByTagName('head')[0].appendChild(kungFuDeathGrip);
