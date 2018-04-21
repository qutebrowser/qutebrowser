(function() {
    "use strict";
    if (!("_qutebrowser" in window)) {
        window._qutebrowser = {"initialized": {}};
    }

    if (window._qutebrowser.initialized["{{name}}"]) {
        return;
    }
    {{code}}
    window._qutebrowser.initialized["{{name}}"] = true;
})();
