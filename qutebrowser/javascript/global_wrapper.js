(function() {
    "use strict";
    if (!window.hasOwnProperty("_qutebrowser")) {
        window._qutebrowser = {"initialized": {}};
    }

    if (window._qutebrowser.initialized["{{name}}"]) {
        return;
    }
    {{code}}
    window._qutebrowser.initialized["{{name}}"] = true;
})();
