# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>:
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

"""pytest fixtures for tests.keyinput."""

import pytest

from unittest import mock
from qutebrowser.utils import objreg


BINDINGS = {'test': {'<Ctrl-a>': 'ctrla',
                     'a': 'a',
                     'ba': 'ba',
                     'ax': 'ax',
                     'ccc': 'ccc',
                     '0': '0'},
            'test2': {'foo': 'bar', '<Ctrl+X>': 'ctrlx'},
            'normal': {'a': 'a', 'ba': 'ba'}}


@pytest.yield_fixture
def fake_keyconfig():
    """Create a mock of a KeyConfiguration and register it into objreg."""
    bindings = dict(BINDINGS)  # so the bindings can be changed later
    fake_keyconfig = mock.Mock(spec=['get_bindings_for'])
    fake_keyconfig.get_bindings_for.side_effect = lambda s: bindings[s]
    objreg.register('key-config', fake_keyconfig)
    yield bindings
    objreg.delete('key-config')
