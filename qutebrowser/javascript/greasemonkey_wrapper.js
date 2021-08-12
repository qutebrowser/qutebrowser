(function() {
    const _qute_script_id = "__gm_{{ scriptName }}";

    function GM_log(text) {
        console.log(text);
    }

    const GM_info = {
        'script': {{ scriptInfo }},
        'scriptMetaStr': "{{ scriptMeta }}",
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
            throw new Error("GM_xmlhttpRequest requires a URL.");
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
        if ("overrideMimeType" in details) {
            oXhr.overrideMimeType(details.overrideMimeType);
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
            // no head yet, stick it wherever
            document.documentElement.appendChild(oStyle);
        } else {
            head.appendChild(oStyle);
        }
    }

    // Stub these two so that the gm4 polyfill script doesn't try to
    // create broken versions as attributes of window.
    function GM_getResourceText(caption, commandFunc, accessKey) {
        console.error(`${GM_info.script.name} called unimplemented GM_getResourceText`);
    }

    function GM_registerMenuCommand(caption, commandFunc, accessKey) {
        console.error(`${GM_info.script.name} called unimplemented GM_registerMenuCommand`);
    }

    // Mock the greasemonkey 4.0 async API.
    const GM = {};
    GM.info = GM_info;
    const entries = {
        'log': GM_log,
        'addStyle': GM_addStyle,
        'deleteValue': GM_deleteValue,
        'getValue': GM_getValue,
        'listValues': GM_listValues,
        'openInTab': GM_openInTab,
        'setValue': GM_setValue,
        'xmlHttpRequest': GM_xmlhttpRequest,
    }
    for (newKey in entries) {
        let old = entries[newKey];
        if (old && (typeof GM[newKey] == 'undefined')) {
            GM[newKey] = function(...args) {
                return new Promise((resolve, reject) => {
                    try {
                        resolve(old(...args));
                    } catch (e) {
                        reject(e);
                    }
                });
            };
        }
    };

    const unsafeWindow = window;
    {% if use_proxy %}
    /*
     * Try to give userscripts an environment that they expect. Which seems
     * to be that the global window object should look the same as the page's
     * one and that if a script writes to an attribute of window all other
     * scripts should be able to access that variable in the global scope.
     * Use a Proxy to stop scripts from actually changing the global window
     * (that's what unsafeWindow is for). Use the "with" statement to make
     * the proxy provide what looks like global scope.
     *
     * There are other Proxy functions that we may need to override.  set,
     * get and has are definitely required.
     */

    if (!window._qute_gm_window_proxy) {
        const qute_gm_window_shadow = {}; // stores local changes to window
        const qute_gm_windowProxyHandler = {
            get: function (target, prop) {
                if (prop in qute_gm_window_shadow)
                    return qute_gm_window_shadow[prop];
                if (prop in target) {
                    if (typeof target[prop] === 'function' && typeof target[prop].prototype == 'undefined')
                        // Getting TypeError: Illegal Execution when callers try
                        // to execute eg addEventListener from here because they
                        // were returned unbound
                        return target[prop].bind(target);
                    return target[prop];
                }
            },
            set: function(target, prop, val) {
                return qute_gm_window_shadow[prop] = val;
            },
            has: function(target, key) {
                return key in qute_gm_window_shadow || key in target;
            }
        };
        window._qute_gm_window_proxy = new Proxy(unsafeWindow, qute_gm_windowProxyHandler);
    }
    const qute_gm_window_proxy = window._qute_gm_window_proxy;
    with (qute_gm_window_proxy) {
        // We can't return `this` or `qute_gm_window_proxy` from
        // `qute_gm_window_proxy.get('window')` because the Proxy implementation
        // does typechecking on read-only things. So we have to shadow `window`
        // more conventionally here.
        const window = qute_gm_window_proxy;
        // ====== The actual user script source ====== //
{{ scriptSource }}
        // ====== End User Script ====== //
    };
    {% else %}
        // ====== The actual user script source ====== //
{{ scriptSource }}
        // ====== End User Script ====== //
    {% endif %}
})();
