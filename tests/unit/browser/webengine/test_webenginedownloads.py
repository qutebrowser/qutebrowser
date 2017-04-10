# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import os.path

import pytest

pytest.importorskip('PyQt5.QtWebEngineWidgets')

from qutebrowser.browser.webengine import webenginedownloads
from qutebrowser.utils import qtutils

qt58 = pytest.mark.skipif(
    qtutils.version_check('5.9'), reason="Needs Qt 5.8 or earlier")
qt59 = pytest.mark.skipif(
    not qtutils.version_check('5.9'), reason="Needs Qt 5.9 or newer")


@pytest.mark.parametrize('path, expected', [
    (os.path.join('subfolder', 'foo'), 'foo'),
    ('foo(1)', 'foo'),
    ('foo(a)', 'foo(a)'),
    ('foo1', 'foo1'),
    qt58(('foo%20bar', 'foo bar')),
    qt58(('foo%2Fbar', 'bar')),
    qt59(('foo%20bar', 'foo%20bar')),
    qt59(('foo%2Fbar', 'foo%2Fbar')),
])
def test_get_suggested_filename(path, expected):
    assert webenginedownloads._get_suggested_filename(path) == expected
