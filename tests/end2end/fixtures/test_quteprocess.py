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
import json

import pytest

from end2end.fixtures import quteprocess, testprocess
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
        quteproc.after_test(did_fail=False)


def test_quteproc_error_message_did_fail(qtbot, quteproc):
    """Make sure the test does not fail on teardown if the main test failed."""
    with qtbot.waitSignal(quteproc.got_error):
        quteproc.send_cmd(':message-error test')
    # Usually we wouldn't call this from inside a test, but here we force the
    # error to occur during the test rather than at teardown time.
    quteproc.after_test(did_fail=True)


def test_quteproc_skip_via_js(qtbot, quteproc):
    with pytest.raises(pytest.skip.Exception) as excinfo:
        quteproc.send_cmd(':jseval console.log("[SKIP] test");')
        quteproc.wait_for_js('[SKIP] test')

        # Usually we wouldn't call this from inside a test, but here we force
        # the error to occur during the test rather than at teardown time.
        quteproc.after_test(did_fail=False)

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


def test_quteprocess_quitting(qtbot, quteproc_process):
    """When qutebrowser quits, after_test should fail."""
    with qtbot.waitSignal(quteproc_process.proc.finished, timeout=15000):
        quteproc_process.send_cmd(':quit')
    with pytest.raises(testprocess.ProcessExited):
        quteproc_process.after_test(did_fail=False)


@pytest.mark.parametrize('data, attrs', [
    (
        # Normal message
        '{"created": 0, "levelname": "DEBUG", "name": "init", "module": '
        '"earlyinit", "funcName": "init_log", "lineno": 280, "levelno": 10, '
        '"message": "Log initialized."}',
        {
            'timestamp': datetime.datetime.fromtimestamp(0),
            'loglevel': logging.DEBUG,
            'category': 'init',
            'module': 'earlyinit',
            'function': 'init_log',
            'line': 280,
            'message': 'Log initialized.',
            'expected': False,
        }
    ),
    (
        # VDEBUG
        '{"created": 0, "levelname": "VDEBUG", "name": "foo", "module": '
        '"foo", "funcName": "foo", "lineno": 0, "levelno": 9, "message": ""}',
        {'loglevel': log.VDEBUG_LEVEL}
    ),
    (
        # Unknown module
        '{"created": 0, "levelname": "DEBUG", "name": "qt", "module": '
        'null, "funcName": null, "lineno": 0, "levelno": 10, "message": '
        '"test"}',
        {'module': None, 'function': None, 'line': None},
    ),
    (
        # Expected message
        '{"created": 0, "levelname": "VDEBUG", "name": "foo", "module": '
        '"foo", "funcName": "foo", "lineno": 0, "levelno": 9, "message": '
        '"SpellCheck: test"}',
        {'expected': True},
    ),
    (
        # Weird Qt location
        '{"created": 0, "levelname": "DEBUG", "name": "qt", "module": '
        '"qnetworkreplyhttpimpl", "funcName": '
        '"void QNetworkReplyHttpImplPrivate::error('
        'QNetworkReply::NetworkError, const QString&)", "lineno": 1929, '
        '"levelno": 10, "message": "QNetworkReplyImplPrivate::error: '
        'Internal problem, this method must only be called once."}',
        {
            'module': 'qnetworkreplyhttpimpl',
            'function': 'void QNetworkReplyHttpImplPrivate::error('
                        'QNetworkReply::NetworkError, const QString&)',
            'line': 1929
        }
    ),
    (
        '{"created": 0, "levelname": "DEBUG", "name": "qt", "module": '
        '"qxcbxsettings", "funcName": "QXcbXSettings::QXcbXSettings('
        'QXcbScreen*)", "lineno": 233, "levelno": 10, "message": '
        '"QXcbXSettings::QXcbXSettings(QXcbScreen*) Failed to get selection '
        'owner for XSETTINGS_S atom"}',
        {
            'module': 'qxcbxsettings',
            'function': 'QXcbXSettings::QXcbXSettings(QXcbScreen*)',
            'line': 233,
        }
    ),
    (
        # With [2s ago] marker
        '{"created": 0, "levelname": "DEBUG", "name": "foo", "module": '
        '"foo", "funcName": "foo", "lineno": 0, "levelno": 10, "message": '
        '"[2s ago] test"}',
        {'prefix': '2s ago', 'message': 'test'}
    ),
    (
        # ResourceWarning
        '{"created": 0, "levelname": "WARNING", "name": "py.warnings", '
        '"module": "app", "funcName": "qt_mainloop", "lineno": 121, "levelno":'
        ' 30, "message": '
        '".../app.py:121: ResourceWarning: unclosed file <_io.TextIOWrapper '
        'name=18 mode=\'r\' encoding=\'UTF-8\'>"}',
        {'category': 'py.warnings'}
    ),
], ids=['normal', 'vdebug', 'unknown module', 'expected message',
        'weird Qt location', 'QXcbXSettings', '2s ago marker',
        'resourcewarning'])
def test_log_line_parse(data, attrs):
    line = quteprocess.LogLine(data)
    for name, expected in attrs.items():
        actual = getattr(line, name)
        assert actual == expected, name


@pytest.mark.parametrize('data, colorized, expect_error, expected', [
    (
        {'created': 0, 'levelname': 'DEBUG', 'name': 'foo', 'module': 'bar',
         'funcName': 'qux', 'lineno': 10, 'levelno': 10, 'message': 'quux'},
        False, False,
        '{timestamp} DEBUG    foo        bar:qux:10 quux',
    ),
    # Traceback attached
    (
        {'created': 0, 'levelname': 'DEBUG', 'name': 'foo', 'module': 'bar',
         'funcName': 'qux', 'lineno': 10, 'levelno': 10, 'message': 'quux',
         'traceback': 'Traceback (most recent call last):\n    here be '
         'dragons'},
        False, False,
        '{timestamp} DEBUG    foo        bar:qux:10 quux\n'
        'Traceback (most recent call last):\n'
        '    here be dragons',
    ),
    # Colorized
    (
        {'created': 0, 'levelname': 'DEBUG', 'name': 'foo', 'module': 'bar',
         'funcName': 'qux', 'lineno': 10, 'levelno': 10, 'message': 'quux'},
        True, False,
        '\033[32m{timestamp}\033[0m \033[37mDEBUG   \033[0m \033[36mfoo     '
        '   bar:qux:10\033[0m \033[37mquux\033[0m',
    ),
    # Expected error
    (
        {'created': 0, 'levelname': 'ERROR', 'name': 'foo', 'module': 'bar',
         'funcName': 'qux', 'lineno': 10, 'levelno': 40, 'message': 'quux'},
        False, True,
        '{timestamp} ERROR (expected) foo        bar:qux:10 quux',
    ),
    # Expected other message (i.e. should make no difference)
    (
        {'created': 0, 'levelname': 'DEBUG', 'name': 'foo', 'module': 'bar',
         'funcName': 'qux', 'lineno': 10, 'levelno': 10, 'message': 'quux'},
        False, True,
        '{timestamp} DEBUG    foo        bar:qux:10 quux',
    ),
    # Expected error colorized (shouldn't be red)
    (
        {'created': 0, 'levelname': 'ERROR', 'name': 'foo', 'module': 'bar',
         'funcName': 'qux', 'lineno': 10, 'levelno': 40, 'message': 'quux'},
        True, True,
        '\033[32m{timestamp}\033[0m \033[37mERROR (expected)\033[0m '
        '\033[36mfoo        bar:qux:10\033[0m \033[37mquux\033[0m',
    ),
], ids=['normal', 'traceback', 'colored', 'expected error', 'expected other',
        'expected error colorized'])
def test_log_line_formatted(data, colorized, expect_error, expected):
    line = json.dumps(data)
    record = quteprocess.LogLine(line)
    record.expected = expect_error
    ts = datetime.datetime.fromtimestamp(data['created']).strftime('%H:%M:%S')
    expected = expected.format(timestamp=ts)
    assert record.formatted_str(colorized=colorized) == expected


def test_log_line_no_match():
    with pytest.raises(testprocess.InvalidLine):
        quteprocess.LogLine("Hello World!")


class TestClickElement:

    @pytest.fixture(autouse=True)
    def open_page(self, quteproc):
        quteproc.open_path('data/click_element.html')

    def test_click_element(self, quteproc):
        quteproc.click_element('Test Element')
        quteproc.wait_for_js('click_element clicked')

    def test_click_special_chars(self, quteproc):
        quteproc.click_element('"Don\'t", he shouted')
        quteproc.wait_for_js('click_element special chars')

    def test_duplicate(self, quteproc):
        with pytest.raises(ValueError) as excinfo:
            quteproc.click_element('Duplicate')
        assert 'not unique' in str(excinfo.value)

    def test_nonexistent(self, quteproc):
        with pytest.raises(ValueError) as excinfo:
            quteproc.click_element('no element exists with this text')
        assert 'No element' in str(excinfo.value)


@pytest.mark.parametrize('string, expected', [
    ('Test', "'Test'"),
    ("Don't", '"Don\'t"'),
    # This is some serious string escaping madness
    ('"Don\'t", he said',
     "concat('\"', 'Don', \"'\", 't', '\"', ', he said')"),
])
def test_xpath_escape(string, expected):
    assert quteprocess._xpath_escape(string) == expected


@pytest.mark.parametrize('value', [
    'foo',
    'foo"bar',  # Make sure a " is preserved
])
def test_set(quteproc, value):
    quteproc.set_setting('network', 'accept-language', value)
    read_back = quteproc.get_setting('network', 'accept-language')
    assert read_back == value
