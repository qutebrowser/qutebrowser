# Copyright 2015-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

"""Tests for qutebrowser.utils.error."""

import logging

import pytest
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QMessageBox

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
            assert w.icon() == QMessageBox.Critical
            assert w.standardButtons() == QMessageBox.Ok
            assert w.text() == expected
        finally:
            w.close()

    QTimer.singleShot(10, err_window_check)

    with caplog.at_level(logging.ERROR):
        error.handle_fatal_exc(ValueError("exception"), 'title',
                               pre_text=pre_text, post_text=post_text,
                               no_err_windows=False)
