# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# Copyright 2014-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

"""Tests for qutebrowser.browser.greasemonkey."""

import os
import copy
import logging
import tempfile

import pytest
from PyQt5.QtCore import QObject, QUrl

from qutebrowser.browser import greasemonkey
from qutebrowser.browser.greasemonkey import GreasemonkeyScript

test_gm_script="""
// ==UserScript==
// @name Qutebrowser test userscript
// @namespace invalid.org
// @include http://localhost:*/data/title.html
// @match http://trolol*
// @exclude https://badhost.xxx/*
// @run-at document-start
// ==/UserScript==
console.log("Script is running.");
"""

def save_script(script_text, filename):
    script_path = greasemonkey._scripts_dir()
    try:
        os.mkdir(script_path)
    except FileExistsError:
        pass
    file_path = os.path.join(script_path, filename)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(script_text)

class TestGreasemonkeyManager:

    def test_all(self, data_tmpdir):
        """Test that a script gets read from file, parsed and returned."""
        save_script(test_gm_script, 'test.user.js')

        gm_manager = greasemonkey.GreasemonkeyManager()
        assert (gm_manager.all_scripts()[0].name ==
                "Qutebrowser test userscript")
        
    def test_get_scripts_by_url(self, data_tmpdir):
        """Check @include, @match and @exclude work as expected via
        scripts_for."""
        save_script(test_gm_script, 'test.user.js')
        gm_manager = greasemonkey.GreasemonkeyManager()

        scripts = gm_manager.scripts_for(QUrl('http://trololololololo.com/'))
        assert len(scripts.start + scripts.end + scripts.idle) == 1
        scripts = gm_manager.scripts_for(QUrl('http://aaaaaaaaaa.com/'))
        assert len(scripts.start + scripts.end + scripts.idle) == 0
        scripts = gm_manager.scripts_for(QUrl('https://badhost.xxx/'))
        assert len(scripts.start + scripts.end + scripts.idle) == 0

    def test_no_metadata(self, caplog, data_tmpdir):
        """Scripts with no metadata should run on all sites at document-end"""
        save_script("var nothing = true;\n", 'nothing.user.js')

        with caplog.at_level(logging.WARNING):
            gm_manager = greasemonkey.GreasemonkeyManager()

        scripts = gm_manager.scripts_for(QUrl('http://notamatch.invalid/'))
        assert len(scripts.start + scripts.end + scripts.idle) == 1
        assert len(scripts.end) == 1

    def test_bad_scheme(self, caplog, data_tmpdir):
        """qute:// isn't in the list of allowed schemes."""
        save_script("var nothing = true;\n", 'nothing.user.js')

        with caplog.at_level(logging.WARNING):
            gm_manager = greasemonkey.GreasemonkeyManager()

        scripts = gm_manager.scripts_for(QUrl('qute://settings'))
        assert len(scripts.start + scripts.end + scripts.idle) == 0

    def test_load_emits_signal(self, data_tmpdir, qtbot):
        gm_manager = greasemonkey.GreasemonkeyManager()
        # maybe should figure out how to call the greasemonkey-reload command
        # to check it is being registered correctly
        with qtbot.wait_signal(gm_manager.scripts_reloaded):
            gm_manager.load_scripts()

