# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Tests for QtWebEngine JavaScript quirks.

This tests JS functionality which is missing in older QtWebEngine releases, but we have
polyfills for. They should either pass because the polyfill is active, or pass because
the native functionality exists.
"""

import pytest

from PyQt5.QtCore import QUrl
from qutebrowser.utils import usertypes


@pytest.mark.parametrize('base_url, source, expected', [
    pytest.param(
        QUrl(),
        '"This is a test".replaceAll("test", "fest")',
        "This is a fest",
        id='replace-all',
    ),
    pytest.param(
        QUrl(),
        '"This is a test".replaceAll(/[tr]est/g, "fest")',
        "This is a fest",
        id='replace-all-regex',
    ),
    pytest.param(
        QUrl(),
        '"This is a [test[".replaceAll("[", "<")',
        "This is a <test<",
        id='replace-all-reserved-string',
    ),
    pytest.param(
        QUrl('https://test.qutebrowser.org/test'),
        'typeof globalThis.setTimeout === "function"',
        True,
        id='global-this',
    ),
    pytest.param(
        QUrl(),
        'Object.fromEntries([["0", "a"], ["1", "b"]])',
        {'0': 'a', '1': 'b'},
        id='object-fromentries',
    ),
])
def test_js_quirks(config_stub, js_tester_webengine, base_url, source, expected):
    config_stub.val.content.site_specific_quirks.skip = []
    js_tester_webengine.tab._scripts._inject_site_specific_quirks()
    js_tester_webengine.load('base.html', base_url=base_url)
    js_tester_webengine.run(source, expected, world=usertypes.JsWorld.main)
