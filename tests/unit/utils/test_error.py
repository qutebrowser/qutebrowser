# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for qutebrowser.utils.error."""

import logging

import pytest
from qutebrowser.qt.core import QTimer
from qutebrowser.qt.widgets import QMessageBox

from qutebrowser.utils import error, utils
from qutebrowser.misc import ipc


class Error(Exception):

    pass


@pytest.mark.parametrize('exc, name, exc_text', [
    # "builtins." stripped
    (ValueError('exception'), 'ValueError', 'exception'),
    (ValueError, 'ValueError', 'none'),
    # "qutebrowser." stripped
    (ipc.Error, 'misc.ipc.Error', 'none'),
    (Error, 'test_error.Error', 'none'),
])
def test_no_err_windows(caplog, exc, name, exc_text):
    """Test handle_fatal_exc with no_err_windows = True."""
    try:
        raise exc
    except Exception as e:
        with caplog.at_level(logging.ERROR):
            error.handle_fatal_exc(e, 'title', pre_text='pre',
                                   post_text='post', no_err_windows=True)

    expected = [
        'Handling fatal {} with --no-err-windows!'.format(name),
        '',
        'title: title',
        'pre_text: pre',
        'post_text: post',
        'exception text: {}'.format(exc_text),
    ]
    assert caplog.messages == ['\n'.join(expected)]


# This happens on Xvfb for some reason
# See https://github.com/qutebrowser/qutebrowser/issues/984
@pytest.mark.qt_log_ignore(r'^QXcbConnection: XCB error: 8 \(BadMatch\), '
                           r'sequence: \d+, resource id: \d+, major code: 42 '
                           r'\(SetInputFocus\), minor code: 0$',
                           r'^QIODevice::write: device not open')
@pytest.mark.parametrize('pre_text, post_text, expected', [
    ('', '', 'exception'),
    ('foo', '', 'foo: exception'),
    ('foo', 'bar', 'foo: exception\n\nbar'),
    ('', 'bar', 'exception\n\nbar'),
], ids=repr)
def test_err_windows(qtbot, qapp, pre_text, post_text, expected, caplog):

    def err_window_check():
        w = qapp.activeModalWidget()
        assert w is not None
        try:
            qtbot.add_widget(w)
            if not utils.is_mac:
                assert w.windowTitle() == 'title'
            assert w.icon() == QMessageBox.Icon.Critical
            assert w.standardButtons() == QMessageBox.StandardButton.Ok
            assert w.text() == expected
        finally:
            w.close()

    QTimer.singleShot(10, err_window_check)

    with caplog.at_level(logging.ERROR):
        error.handle_fatal_exc(ValueError("exception"), 'title',
                               pre_text=pre_text, post_text=post_text,
                               no_err_windows=False)
