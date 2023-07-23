# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>:
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""pytest fixtures for tests.keyinput."""

import pytest

import contextlib
from qutebrowser.keyinput import keyutils


BINDINGS = {'prompt': {'<Ctrl-a>': 'message-info ctrla',
                       'a': 'message-info a',
                       'ba': 'message-info ba',
                       'ax': 'message-info ax',
                       'ccc': 'message-info ccc',
                       'yY': 'yank -s',
                       '0': 'message-info 0',
                       '1': 'message-info 1'},
            'command': {'foo': 'message-info bar',
                        '<Ctrl+X>': 'message-info ctrlx'},
            'normal': {'a': 'message-info a', 'ba': 'message-info ba'}}
MAPPINGS = {
    'x': 'a',
    'b': 'a',
}


@pytest.fixture
def keyinput_bindings(config_stub, key_config_stub):
    """Register some test bindings."""
    config_stub.val.bindings.default = {}
    config_stub.val.bindings.commands = dict(BINDINGS)
    config_stub.val.bindings.key_mappings = dict(MAPPINGS)


@pytest.fixture
def pyqt_enum_workaround():
    """Get a context manager to ignore invalid key errors and skip the test.

    WORKAROUND for
    https://www.riverbankcomputing.com/pipermail/pyqt/2022-April/044607.html
    """
    @contextlib.contextmanager
    def _pyqt_enum_workaround(exctype=keyutils.InvalidKeyError):
        try:
            yield
        except exctype as e:
            pytest.skip(f"PyQt enum workaround: {e}")

    return _pyqt_enum_workaround
