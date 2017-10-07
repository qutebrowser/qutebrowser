(function () {
    var _qute_script_id = "__gm_"+{{ scriptName | tojson }};

    function GM_log(text) {
        console.log(text);
    }

    var GM_info = (function () {
        return {
            'script': {{ scriptInfo | tojson }},
            'scriptMetaStr': {{ scriptMeta | tojson }},
            'scriptWillUpdate': false,
            'version': '0.0.1',
            'scriptHandler': 'Tampermonkey' // so scripts don't expect exportFunction
        };
    }());

    function GM_setValue(key, value) {
        if (typeof key !== "string") {
          throw new Error("GM_setValue requires the first parameter to be of type string, not '"+typeof key+"'");
        }
        if (typeof value !== "string" ||
            typeof value !== "number" ||
            typeof value !== "boolean") {
          throw new Error("GM_setValue requires the second parameter to be of type string, number or boolean, not '"+typeof value+"'");
        }
        localStorage.setItem(_qute_script_id + key, value);
    }

    function GM_getValue(key, default_) {
        if (typeof key !== "string") {
          throw new Error("GM_getValue requires the first parameter to be of type string, not '"+typeof key+"'");
        }
        return localStorage.getItem(_qute_script_id + key) || default_;
    }

    function GM_deleteValue(key) {
        if (typeof key !== "string") {
          throw new Error("GM_deleteValue requires the first parameter to be of type string, not '"+typeof key+"'");
        }
        localStorage.removeItem(_qute_script_id + key);
    }

    function GM_listValues() {
        var i, keys = [];
        for (i = 0; i < localStorage.length; i = i + 1) {
            if (localStorage.key(i).startsWith(_qute_script_id)) {
                keys.push(localStorage.key(i));
            }
        }
        return keys;
    }

    function GM_openInTab(url) {
        window.open(url);
    }


    // Almost verbatim copy from Eric
    function GM_xmlhttpRequest(/* object */ details) {
        details.method = details.method.toUpperCase() || "GET";

        if (!details.url) {
            throw ("GM_xmlhttpRequest requires an URL.");
        }

        // build XMLHttpRequest object
        var oXhr = new XMLHttpRequest();
        // run it
        if ("onreadystatechange" in details) {
            oXhr.onreadystatechange = function () {
                details.onreadystatechange(oXhr);
            };
        }
        if ("onload" in details) {
            oXhr.onload = function () { details.onload(oXhr) };
        }
        if ("onerror" in details) {
            oXhr.onerror = function () { details.onerror(oXhr) };
        }

        oXhr.open(details.method, details.url, true);

        if ("headers" in details) {
            for (var header in details.headers) {
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
        var head = document.getElementsByTagName("head")[0];
        if (head === undefined) {
            document.onreadystatechange = function () {
                if (document.readyState == "interactive") {
                    var oStyle = document.createElement("style");
                    oStyle.setAttribute("type", "text/css");
                    oStyle.appendChild(document.createTextNode(styles));
                    document.getElementsByTagName("head")[0].appendChild(oStyle);
                }
            }
        }
        else {
            var oStyle = document.createElement("style");
            oStyle.setAttribute("type", "text/css");
            oStyle.appendChild(document.createTextNode(styles));
            head.appendChild(oStyle);
        }
    }

    unsafeWindow = window;

    //====== The actual user script source ======//
{{ scriptSource }}
    //====== End User Script ======//
})();
