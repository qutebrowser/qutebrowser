(function() {
    const _qute_script_id = "__gm_" + {{ scriptName | tojson }};

    function GM_log(text) {
        console.log(text);
    }

    const GM_info = {
        'script': {{ scriptInfo }},
        'scriptMetaStr': {{ scriptMeta | tojson }},
        'scriptWillUpdate': false,
        'version': "0.0.1",
        // so scripts don't expect exportFunction
        'scriptHandler': 'Tampermonkey',
    };

    function checkKey(key, funcName) {
        if (typeof key !== "string") {
          throw new Error(`${funcName} requires the first parameter to be of type string, not '${typeof key}'`);
        }
    }

    function GM_setValue(key, value) {
        checkKey(key, "GM_setValue");
        if (typeof value !== "string" &&
            typeof value !== "number" &&
            typeof value !== "boolean") {
          throw new Error(`GM_setValue requires the second parameter to be of type string, number or boolean, not '${typeof value}'`);
        }
        localStorage.setItem(_qute_script_id + key, value);
    }

    function GM_getValue(key, default_) {
        checkKey(key, "GM_getValue");
        return localStorage.getItem(_qute_script_id + key) || default_;
    }

    function GM_deleteValue(key) {
        checkKey(key, "GM_deleteValue");
        localStorage.removeItem(_qute_script_id + key);
    }

    function GM_listValues() {
        const keys = [];
        for (let i = 0; i < localStorage.length; i++) {
            if (localStorage.key(i).startsWith(_qute_script_id)) {
                keys.push(localStorage.key(i).slice(_qute_script_id.length));
            }
        }
        return keys;
    }

    function GM_openInTab(url) {
        window.open(url);
    }


    // Almost verbatim copy from Eric
    function GM_xmlhttpRequest(/* object */ details) {
        details.method = details.method ? details.method.toUpperCase() : "GET";

        if (!details.url) {
            throw new Error("GM_xmlhttpRequest requires an URL.");
        }

        // build XMLHttpRequest object
        const oXhr = new XMLHttpRequest();
        // run it
        if ("onreadystatechange" in details) {
            oXhr.onreadystatechange = function() {
                details.onreadystatechange(oXhr);
            };
        }
        if ("onload" in details) {
            oXhr.onload = function() { details.onload(oXhr); };
        }
        if ("onerror" in details) {
            oXhr.onerror = function () { details.onerror(oXhr); };
        }

        oXhr.open(details.method, details.url, true);

        if ("headers" in details) {
            for (const header in details.headers) {
                oXhr.setRequestHeader(header, details.headers[header]);
            }
        }

        if ("data" in details) {
            oXhr.send(details.data);
        } else {
            oXhr.send();
        }
    }

    function GM_addStyle(/* String */ styles) {
        const oStyle = document.createElement("style");
        oStyle.setAttribute("type", "text/css");
        oStyle.appendChild(document.createTextNode(styles));

        const head = document.getElementsByTagName("head")[0];
        if (head === undefined) {
            document.onreadystatechange = function() {
                if (document.readyState === "interactive") {
                    document.getElementsByTagName("head")[0].appendChild(oStyle);
                }
            };
        } else {
            head.appendChild(oStyle);
        }
    }

    const unsafeWindow = window;

    // ====== The actual user script source ====== //
{{ scriptSource }}
    // ====== End User Script ====== //
})();
