# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Helpers needed by tests."""

import os
import contextlib
from unittest import mock

from PyQt5.QtGui import QKeyEvent


@contextlib.contextmanager
def environ_set_temp(name, value):
    """Set a temporary environment variable."""
    try:
        oldval = os.environ[name]
    except KeyError:
        oldval = None
    os.environ[name] = value
    yield
    if oldval is not None:
        os.environ[name] = oldval
    else:
        del os.environ[name]


def fake_keyevent(key, modifiers=0, text=''):
    """Generate a new fake QKeyPressEvent."""
    evtmock = mock.create_autospec(QKeyEvent, instance=True)
    evtmock.key.return_value = key
    evtmock.modifiers.return_value = modifiers
    evtmock.text.return_value = text
    return evtmock
