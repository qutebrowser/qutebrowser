# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import pytest

from qutebrowser.extensions import loader
from qutebrowser.misc import objects


def test_on_walk_error():
    with pytest.raises(ImportError, match='Failed to import foo'):
        loader._on_walk_error('foo')


def test_walk_normal():
    names = [info.name for info in loader._walk_normal()]
    assert 'qutebrowser.components.scrollcommands' in names


def test_walk_pyinstaller():
    # We can't test whether we get something back without being frozen by
    # PyInstaller, but at least we can test that we don't crash.
    list(loader._walk_pyinstaller())


def test_load_component(monkeypatch):
    monkeypatch.setattr(objects, 'commands', {})

    info = loader.ExtensionInfo(name='qutebrowser.components.scrollcommands')
    module = loader._load_component(info, skip_hooks=True)

    assert hasattr(module, 'scroll_to_perc')
    assert 'scroll-to-perc' in objects.commands
