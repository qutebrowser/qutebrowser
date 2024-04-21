# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for qutebrowser.misc.crashsignal."""

import signal

import pytest

from qutebrowser.config import configexc
from qutebrowser.qt.widgets import QApplication
from qutebrowser.misc import crashsignal, quitter


@pytest.fixture
def read_config_mock(mocker):
    # covers reload_config
    mocker.patch.object(
        crashsignal.standarddir,
        "config_py",
        return_value="config.py-unittest",
    )
    return mocker.patch.object(
        crashsignal.configfiles,
        "read_config_py",
        autospec=True,
    )


@pytest.fixture
def signal_handler(qtbot, mocker, read_config_mock):
    """Signal handler instance with all external methods mocked out."""
    # covers init
    mocker.patch.object(crashsignal.sys, "exit", autospec=True)
    signal_handler = crashsignal.SignalHandler(
        app=mocker.Mock(spec=QApplication),
        quitter=mocker.Mock(spec=quitter.Quitter),
    )

    return signal_handler


def test_handlers_registered(signal_handler):
    signal_handler.activate()

    for sig, handler in signal_handler._handlers.items():
        registered = signal.signal(sig, signal.SIG_DFL)
        assert registered == handler


def test_handlers_deregistered(signal_handler):
    known_handler = lambda *_args: None
    for sig in signal_handler._handlers:
        signal.signal(sig, known_handler)

    signal_handler.activate()
    signal_handler.deactivate()

    for sig in signal_handler._handlers:
        registered = signal.signal(sig, signal.SIG_DFL)
        assert registered == known_handler


def test_interrupt_repeatedly(signal_handler):
    signal_handler.activate()
    test_signal = signal.SIGINT

    expected_handlers = [
        signal_handler.interrupt,
        signal_handler.interrupt_forcefully,
        signal_handler.interrupt_really_forcefully,
    ]

    # Call the SIGINT handler multiple times and make sure it calls the
    # expected sequence of functions.
    for expected in expected_handlers:
        registered = signal.signal(test_signal, signal.SIG_DFL)
        assert registered == expected
        expected(test_signal, None)


@pytest.mark.posix
def test_reload_config_call_on_hup(signal_handler, read_config_mock):
    signal_handler._handlers[signal.SIGHUP](None, None)

    read_config_mock.assert_called_once_with("config.py-unittest")


@pytest.mark.posix
def test_reload_config_displays_errors(signal_handler, read_config_mock, mocker):
    read_config_mock.side_effect = configexc.ConfigFileErrors(
        "config.py",
        [
            configexc.ConfigErrorDesc("no config.py", ValueError("asdf"))
        ]
    )
    message_mock = mocker.patch.object(crashsignal.message, "error")

    signal_handler._handlers[signal.SIGHUP](None, None)

    message_mock.assert_called_once_with(
        "Errors occurred while reading config.py:\n  no config.py: asdf"
    )
