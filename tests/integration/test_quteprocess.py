# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Test the quteproc fixture used for tests."""

import logging
import datetime

import pytest

import quteprocess
import testprocess
from qutebrowser.utils import log


@pytest.mark.parametrize('cmd', [
    ':message-error test',
    ':jseval console.log("[FAIL] test");'
])
def test_quteproc_error_message(qtbot, quteproc, cmd):
    """Make sure the test fails with an unexpected error message."""
    with qtbot.waitSignal(quteproc.got_error):
        quteproc.send_cmd(cmd)
    # Usually we wouldn't call this from inside a test, but here we force the
    # error to occur during the test rather than at teardown time.
    with pytest.raises(pytest.fail.Exception):
        quteproc.after_test()


def test_quteproc_skip_via_js(qtbot, quteproc):
    with pytest.raises(pytest.skip.Exception) as excinfo:
        quteproc.send_cmd(':jseval console.log("[SKIP] test");')
        quteproc.wait_for_js('[SKIP] test')

        # Usually we wouldn't call this from inside a test, but here we force
        # the error to occur during the test rather than at teardown time.
        quteproc.after_test()

    assert str(excinfo.value) == 'test'


def test_quteproc_skip_and_wait_for(qtbot, quteproc):
    """This test will skip *again* during teardown, but we don't care."""
    with pytest.raises(pytest.skip.Exception):
        quteproc.send_cmd(':jseval console.log("[SKIP] foo");')
        quteproc.wait_for_js("[SKIP] foo")
        quteproc.wait_for(message='This will not match')


def test_qt_log_ignore(qtbot, quteproc):
    """Make sure the test passes when logging a qt_log_ignore message."""
    with qtbot.waitSignal(quteproc.got_error):
        quteproc.send_cmd(':message-error "SpellCheck: test"')


@pytest.mark.parametrize('data, attrs', [
    (
        # Normal message
        '01:02:03 DEBUG    init       earlyinit:init_log:280 Log initialized.',
        {
            'timestamp': datetime.datetime(year=1900, month=1, day=1,
                                           hour=1, minute=2, second=3),
            'loglevel': logging.DEBUG,
            'category': 'init',
            'module': 'earlyinit',
            'function': 'init_log',
            'line':  280,
            'message': 'Log initialized.',
            'expected': False,
        }
    ),
    (
        # VDEBUG
        '00:00:00 VDEBUG    foo       foo:foo:0 test',
        {'loglevel': log.VDEBUG_LEVEL}
    ),
    (
        # Unknown module
        '00:00:00 WARNING  qt         Unknown module:none:0 test',
        {'module': None, 'function': None, 'line': None},
    ),
    (
        # Expected message
        '00:00:00 VDEBUG    foo       foo:foo:0 SpellCheck: test',
        {'expected': True},
    ),
    (
        # Weird Qt location
        '00:00:00 DEBUG    qt         qnetworkreplyhttpimpl:"void '
        'QNetworkReplyHttpImplPrivate::error(QNetworkReply::NetworkError, '
        'const QString&)":1929 QNetworkReplyImplPrivate::error: Internal '
        'problem, this method must only be called once.',
        {
            'module': 'qnetworkreplyhttpimpl',
            'function': 'void QNetworkReplyHttpImplPrivate::error('
                        'QNetworkReply::NetworkError, const QString&)',
            'line': 1929
        }
    ),
    (
	'00:00:00 WARNING  qt         qxcbxsettings:"QXcbXSettings::'
	'QXcbXSettings(QXcbScreen*)":233 '
	'QXcbXSettings::QXcbXSettings(QXcbScreen*) Failed to get selection '
	'owner for XSETTINGS_S atom ',
        {
            'module': 'qxcbxsettings',
            'function': 'QXcbXSettings::QXcbXSettings(QXcbScreen*)',
            'line': 233,
        }
    ),
    (
        # With [2s ago] marker
        '00:00:00 DEBUG    foo       foo:foo:0 [2s ago] test',
        {'prefix': '2s ago', 'message': 'test'}
    ),
], ids=['normal', 'vdebug', 'unknown module', 'expected message',
        'weird Qt location', 'QXcbXSettings', '2s ago marker'])
def test_log_line_parse(data, attrs):
    line = quteprocess.LogLine(data)
    for name, expected in attrs.items():
        actual = getattr(line, name)
        assert actual == expected, name


def test_log_line_no_match():
    with pytest.raises(testprocess.InvalidLine):
        quteprocess.LogLine("Hello World!")
