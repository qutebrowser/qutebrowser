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
import logging
import contextlib
from unittest import mock

from PyQt5.QtGui import QKeyEvent


@contextlib.contextmanager
def environ_set_temp(env):
    """Set temporary environment variables.

    Args:
        env: A dictionary with name: value pairs.
             If value is None, the variable is temporarily deleted.
    """
    old_env = {}

    for name, value in env.items():
        try:
            old_env[name] = os.environ[name]
        except KeyError:
            pass
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    yield

    for name, value in env.items():
        if name in old_env:
            os.environ[name] = old_env[name]
        elif value is not None:
            del os.environ[name]


@contextlib.contextmanager
def disable_logger(name):
    """Temporarily disable a logger."""
    logging.getLogger(name).propagate = False
    try:
        yield
    finally:
        logging.getLogger(name).propagate = True


def fake_keyevent(key, modifiers=0, text=''):
    """Generate a new fake QKeyPressEvent."""
    evtmock = mock.create_autospec(QKeyEvent, instance=True)
    evtmock.key.return_value = key
    evtmock.modifiers.return_value = modifiers
    evtmock.text.return_value = text
    return evtmock


class MessageModule:

    """A drop-in replacement for qutebrowser.utils.message."""

    def error(self, _win_id, message, _immediately=False):
        logging.getLogger('message').error(message)

    def warning(self, win_id, message, immediately=False):
        logging.getLogger('message').warning(message)

    def info(self, win_id, message, immediately=True):
        logging.getLogger('message').info(message)
