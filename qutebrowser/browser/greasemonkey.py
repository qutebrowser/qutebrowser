# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

"""Load, parse and make avalaible greasemonkey scripts."""

import re
import os
import json
from fnmatch import fnmatch
from functools import partial

from PyQt5.QtCore import QDir

from qutebrowser.config import config
from qutebrowser.utils import log, standarddir

# TODO: GM_ bootstrap


def _scripts_dir():
    """Get the directory of the scripts."""
    directory = config.val.content.javascript.userjs_directory
    if directory is None:
        directory = os.path.join(standarddir.data(), 'greasemonkey')
    return directory


class GreasemonkeyScript:
    """Container class for userscripts, parses metadata blocks."""

    GM_BOOTSTRAP_TEMPLATE = r"""var _qute_script_id = "__gm_{scriptName}";

function GM_log(text) {{
    console.log(text);
}}

GM_info = (function() {{
    return {{
        'script': {scriptInfo},
        'scriptMetaStr': {scriptMeta},
        'scriptWillUpdate': false,
        'version': '0.0.1',
        'scriptHandler': 'Tampermonkey' //so scripts don't expect exportFunction
    }};
}}());

function GM_setValue(key, value) {{
    if (localStorage !== null &&
        typeof key === "string" &&
        (typeof value === "string" ||
            typeof value === "number" ||
            typeof value == "boolean")) {{
        localStorage.setItem(_qute_script_id + key, value);
    }}
}}

function GM_getValue(key, default_) {{
    if (localStorage !== null && typeof key === "string") {{
        return localStorage.getItem(_qute_script_id + key) || default_;
    }}
}}

function GM_deleteValue(key) {{
    if (localStorage !== null && typeof key === "string") {{
        localStorage.removeItem(_qute_script_id + key);
    }}
}}

function GM_listValues() {{
    var i;
    var keys = [];
    for (i = 0; i < localStorage.length; ++i) {{
        if (localStorage.key(i).startsWith(_qute_script_id)) {{
            keys.push(localStorage.key(i));
        }}
    }}
    return keys;
}}

function GM_openInTab(url) {{
    window.open(url);
}}


// Almost verbatim copy from Eric
function GM_xmlhttpRequest(/* object */ details) {{
    details.method = details.method.toUpperCase() || "GET";

    if(!details.url) {{
        throw("GM_xmlhttpRequest requires an URL.");
    }}

    // build XMLHttpRequest object
    var oXhr = new XMLHttpRequest;
    // run it
    if(oXhr) {{
        if("onreadystatechange" in details)
            oXhr.onreadystatechange = function() {{
                details.onreadystatechange(oXhr)
            }};
        if("onload" in details)
            oXhr.onload = function() {{ details.onload(oXhr) }};
        if("onerror" in details)
            oXhr.onerror = function() {{ details.onerror(oXhr) }};

        oXhr.open(details.method, details.url, true);

        if("headers" in details)
            for(var header in details.headers)
                oXhr.setRequestHeader(header, details.headers[header]);

        if("data" in details)
            oXhr.send(details.data);
        else
            oXhr.send();
    }} else
        throw ("This Browser is not supported, please upgrade.")
}}

function GM_addStyle(/* String */ styles) {{
    var head = document.getElementsByTagName("head")[0];
    if (head === undefined) {{
        document.onreadystatechange = function() {{
            if (document.readyState == "interactive") {{
                var oStyle = document.createElement("style");
                oStyle.setAttribute("type", "text\/css");
                oStyle.appendChild(document.createTextNode(styles));
                document.getElementsByTagName("head")[0].appendChild(oStyle);
            }}
        }}
    }}
    else {{
        var oStyle = document.createElement("style");
        oStyle.setAttribute("type", "text\/css");
        oStyle.appendChild(document.createTextNode(styles));
        head.appendChild(oStyle);
    }}
}}

unsafeWindow = window;
"""

    def __init__(self, properties, code):
        self._code = code
        self._includes = []
        self._excludes = []
        self._description = None
        for name, value in properties:
            if name == 'name':
                self._name = value
            if name == 'description':
                self._description = value
            if name in ['include', 'match']:
                self._includes.append(value)
            if name in ['exclude', 'exclude_match']:
                self._excludes.append(value)
            if name == 'run-at':
                self._run_at = value

    HEADER_REGEX = r'\/\/ ==UserScript==.|\n+\/\/ ==\/UserScript==\n'
    PROPS_REGEX = r'\/\/ @(?P<prop>[^\s]+)\s+(?P<val>.+)'

    @classmethod
    def parse(cls, source):
        props, code = re.split(cls.HEADER_REGEX, source)
        return cls(re.findall(cls.PROPS_REGEX, props), code)

    def includes(self):
        return self._includes

    def excludes(self):
        return self._excludes

    def name(self):
        return self._name

    def run_at(self):
        return self._run_at

    def code(self):
        gm_bootstrap = self.GM_BOOTSTRAP_TEMPLATE.format(
            scriptName=self._name,
            scriptInfo=self.meta_json() or 'null',
            scriptMeta=self.meta_raw() or 'null')
        return '\n'.join([gm_bootstrap, self._code])

    def meta_json(self):
        return json.dumps({
            'name': self._name,
            'description': self._description,
            'matches': self._includes,
            'includes': self._includes,
            'excludes': self._excludes,
            'run-at': self._run_at,
        })

    def meta_raw(self):
        pass


class GreasemonkeyManager:

    def __init__(self):
        self._run_start = []
        self._run_end = []

        scripts_dir = QDir(_scripts_dir())
        log.greasemonkey.debug("Reading scripts from: %s",
                               scripts_dir.absolutePath())
        for script_filename in scripts_dir.entryList(['*.js'], QDir.Files):
            script_path = scripts_dir.absoluteFilePath(script_filename)
            log.greasemonkey.debug("Trying to load script: %s", script_path)
            with open(script_path, encoding='utf-8') as script_file:
                try:
                    script = GreasemonkeyScript.parse(script_file.read())
                except Exception as err:
                    log.greasemonkey.warning("Unable to load: %s %s",
                                             script_path, err)
                    # Catch-all :/
                    continue
                if script.run_at() == 'document-start':
                    self._run_start.append(script)
                elif script.run_at() == 'document-end':
                    self._run_end.append(script)
                else:
                    log.greasemonkey.warning(("Script %s has invalid run-at "
                                              "defined, defaulting to "
                                              "document-end"), script_path)
                    continue
                log.greasemonkey.debug("Loaded script: %s", script.name())

    def scripts_for(self, url):
        match = partial(fnmatch, url)
        tester = lambda script: any(map(match, script.includes())) \
                        and not any(map(match, script.excludes()))
        return list(filter(tester, self._run_start)), \
               list(filter(tester, self._run_end))

    def all_scripts(self):
        """Return all scripts found in the configured script directory."""
        return self._run_start + self._run_end
