# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
import fnmatch
import functools
import glob

from PyQt5.QtCore import pyqtSignal, QObject

from qutebrowser.utils import log, standarddir
from qutebrowser.commands import cmdutils


def _scripts_dir():
    """Get the directory of the scripts."""
    return os.path.join(standarddir.data(), 'greasemonkey')


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
}}

function GM_addStyle(/* String */ styles) {{
    var head = document.getElementsByTagName("head")[0];
    if (head === undefined) {{
        document.onreadystatechange = function() {{
            if (document.readyState == "interactive") {{
                var oStyle = document.createElement("style");
                oStyle.setAttribute("type", "text/css");
                oStyle.appendChild(document.createTextNode(styles));
                document.getElementsByTagName("head")[0].appendChild(oStyle);
            }}
        }}
    }}
    else {{
        var oStyle = document.createElement("style");
        oStyle.setAttribute("type", "text/css");
        oStyle.appendChild(document.createTextNode(styles));
        head.appendChild(oStyle);
    }}
}}

unsafeWindow = window;
"""

    def __init__(self, properties, code):
        self._code = code
        self.includes = []
        self.excludes = []
        self.description = None
        self.name = None
        self.run_at = None
        for name, value in properties:
            if name == 'name':
                self.name = value
            elif name == 'description':
                self.description = value
            elif name in ['include', 'match']:
                self.includes.append(value)
            elif name in ['exclude', 'exclude_match']:
                self.excludes.append(value)
            elif name == 'run-at':
                self.run_at = value

    HEADER_REGEX = r'// ==UserScript==.|\n+// ==/UserScript==\n'
    PROPS_REGEX = r'// @(?P<prop>[^\s]+)\s+(?P<val>.+)'

    @classmethod
    def parse(cls, source):
        """GreaseMonkeyScript factory.

        Takes a userscript source and returns a GreaseMonkeyScript.
        Parses the greasemonkey metadata block, if present, to fill out
        attributes.
        """
        matches = re.split(cls.HEADER_REGEX, source, maxsplit=1)
        try:
            props, _code = matches
        except ValueError:
            props = ""
        script = cls(re.findall(cls.PROPS_REGEX, props), source)
        script.script_meta = '"{}"'.format("\\n".join(props.split('\n')[2:]))
        return script

    def code(self):
        """Return the processed javascript code of this script.

        Adorns the source code with GM_* methods for greasemonkey
        compatibility and wraps it in an IFFE to hide it within a
        lexical scope. Note that this means line numbers in your
        browser's debugger/inspector will not match up to the line
        numbers in the source script directly.
        """
        gm_bootstrap = self.GM_BOOTSTRAP_TEMPLATE.format(
            scriptName=self.name,
            scriptInfo=self._meta_json(),
            scriptMeta=self.script_meta)
        return '\n'.join([gm_bootstrap, self._code])

    def _meta_json(self):
        return json.dumps({
            'name': self.name,
            'description': self.description,
            'matches': self.includes,
            'includes': self.includes,
            'excludes': self.excludes,
            'run-at': self.run_at,
        })


class GreasemonkeyManager(QObject):

    """Manager of userscripts and a greasemonkey compatible environment.

    Signals:
        scripts_reloaded: Emitted when scripts are reloaded from disk.
            Any any cached or already-injected scripts should be
            considered obselete.
    """

    scripts_reloaded = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.load_scripts()

    @cmdutils.register(name='greasemonkey-reload',
                       instance='greasemonkey')
    def load_scripts(self):
        """Re-Read greasemonkey scripts from disk."""
        self._run_start = []
        self._run_end = []
        self._run_idle = []

        scripts_dir = os.path.abspath(_scripts_dir())
        log.greasemonkey.debug("Reading scripts from: {}".format(scripts_dir))
        for script_filename in glob.glob(os.path.join(scripts_dir, '*.js')):
            if not os.path.isfile(script_filename):
                continue
            script_path = os.path.join(scripts_dir, script_filename)
            with open(script_path, encoding='utf-8') as script_file:
                script = GreasemonkeyScript.parse(script_file.read())
                if not script.name:
                    script.name = script_filename

                if script.run_at == 'document-start':
                    self._run_start.append(script)
                elif script.run_at == 'document-end':
                    self._run_end.append(script)
                elif script.run_at == 'document-idle':
                    self._run_idle.append(script)
                else:
                    log.greasemonkey.warning("Script {} has invalid run-at "
                                             "defined, defaulting to "
                                             "document-end"
                                             .format(script_path))
                    # Default as per
                    # https://wiki.greasespot.net/Metadata_Block#.40run-at
                    self._run_end.append(script)
                log.greasemonkey.debug("Loaded script: {}".format(script.name))
        self.scripts_reloaded.emit()

    def scripts_for(self, url):
        """Fetch scripts that are registered to run for url.

        returns a tuple of lists of scripts meant to run at (document-start,
        document-end, document-idle)
        """
        match = functools.partial(fnmatch.fnmatch, url)
        tester = (lambda script:
                  any([match(pat) for pat in script.includes]) and
                  not any([match(pat) for pat in script.excludes]))
        return (
            [script for script in self._run_start if tester(script)],
            [script for script in self._run_end if tester(script)],
            [script for script in self._run_idle if tester(script)]
        )

    def all_scripts(self):
        """Return all scripts found in the configured script directory."""
        return self._run_start + self._run_end + self._run_idle
