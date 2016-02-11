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

"""Fixtures to run qutebrowser in a QProcess and communicate."""

import os
import re
import sys
import time
import os.path
import datetime
import logging
import tempfile
import contextlib
import itertools

import yaml
import pytest
from PyQt5.QtCore import pyqtSignal, QUrl

import testprocess
from qutebrowser.misc import ipc
from qutebrowser.utils import log, utils
from helpers import utils as testutils


instance_counter = itertools.count()


def is_ignored_qt_message(message):
    """Check if the message is listed in qt_log_ignore."""
    # pylint: disable=no-member
    # WORKAROUND for https://bitbucket.org/logilab/pylint/issues/717/
    # we should switch to generated-members after that
    regexes = pytest.config.getini('qt_log_ignore')
    for regex in regexes:
        if re.match(regex, message):
            return True
    return False


class LogLine(testprocess.Line):

    """A parsed line from the qutebrowser log output.

    Attributes:
        timestamp/loglevel/category/module/function/line/message:
            Parsed from the log output.
        expected: Whether the message was expected or not.
    """

    LOG_RE = re.compile(r"""
        (?P<timestamp>\d\d:\d\d:\d\d)
        \ (?P<loglevel>VDEBUG|DEBUG|INFO|WARNING|ERROR)
        \ +(?P<category>\w+)
        \ +(?P<module>(\w+|Unknown\ module)):
           (?P<function>[^"][^:]*|"[^"]+"):
           (?P<line>\d+)
        \ (?P<message>.+)
    """, re.VERBOSE)

    def __init__(self, data):
        super().__init__(data)
        match = self.LOG_RE.match(data)
        if match is None:
            raise testprocess.InvalidLine(data)

        self.timestamp = datetime.datetime.strptime(match.group('timestamp'),
                                                    '%H:%M:%S')
        loglevel = match.group('loglevel')
        if loglevel == 'VDEBUG':
            self.loglevel = log.VDEBUG_LEVEL
        else:
            self.loglevel = getattr(logging, loglevel)

        self.category = match.group('category')

        module = match.group('module')
        if module == 'Unknown module':
            self.module = None
        else:
            self.module = module

        function = match.group('function')
        if function == 'none':
            self.function = None
        else:
            self.function = function.strip('"')

        line = int(match.group('line'))
        if self.function is None and line == 0:
            self.line = None
        else:
            self.line = line

        msg_match = re.match(r'^(\[(?P<prefix>\d+s ago)\] )?(?P<message>.*)',
                             match.group('message'))
        self.prefix = msg_match.group('prefix')
        self.message = msg_match.group('message')

        self.expected = is_ignored_qt_message(self.message)


class QuteProc(testprocess.Process):

    """A running qutebrowser process used for tests.

    Attributes:
        _delay: Delay to wait between commands.
        _ipc_socket: The IPC socket of the started instance.
        _httpbin: The HTTPBin webserver.
        basedir: The base directory for this instance.
        _focus_ready: Whether the main window got focused.
        _load_ready: Whether the about:blank page got loaded.
        _profile: If True, do profiling of the subprocesses.
        _instance_id: An unique ID for this QuteProc instance
        _run_counter: A counter to get an unique ID for each run.

    Signals:
        got_error: Emitted when there was an error log line.
    """

    got_error = pyqtSignal()

    KEYS = ['timestamp', 'loglevel', 'category', 'module', 'function', 'line',
            'message']

    def __init__(self, httpbin, delay, *, profile=False, parent=None):
        super().__init__(parent)
        self._profile = profile
        self._delay = delay
        self._httpbin = httpbin
        self._ipc_socket = None
        self.basedir = None
        self._focus_ready = False
        self._load_ready = False
        self._instance_id = next(instance_counter)
        self._run_counter = itertools.count()

    def _is_ready(self, what):
        """Called by _parse_line if loading/focusing is done.

        When both are done, emits the 'ready' signal.
        """
        if what == 'load':
            self._load_ready = True
        elif what == 'focus':
            self._focus_ready = True
        else:
            raise ValueError("Invalid value {!r} for 'what'.".format(what))
        if self._load_ready and self._focus_ready:
            self.ready.emit()

    def _parse_line(self, line):
        try:
            log_line = LogLine(line)
        except testprocess.InvalidLine:
            if line.startswith('  '):
                # Multiple lines in some log output...
                return None
            elif not line.strip():
                return None
            elif is_ignored_qt_message(line):
                return None
            else:
                raise

        self._log(line)

        start_okay_message_load = (
            "load status for <qutebrowser.browser.webview.WebView tab_id=0 "
            "url='about:blank'>: LoadStatus.success")
        start_okay_message_focus = (
            "Focus object changed: <qutebrowser.browser.webview.WebView "
            "tab_id=0 url='about:blank'>")

        if (log_line.category == 'ipc' and
                log_line.message.startswith("Listening as ")):
            self._ipc_socket = log_line.message.split(' ', maxsplit=2)[2]
        elif (log_line.category == 'webview' and
                log_line.message == start_okay_message_load):
            self._is_ready('load')
        elif (log_line.category == 'misc' and
                log_line.message == start_okay_message_focus):
            self._is_ready('focus')
        elif (log_line.category == 'init' and
                log_line.module == 'standarddir' and
                log_line.function == 'init' and
                log_line.message.startswith('Base directory:')):
            self.basedir = log_line.message.split(':', maxsplit=1)[1].strip()
        elif self._is_error_logline(log_line):
            self.got_error.emit()

        return log_line

    def _executable_args(self):
        if hasattr(sys, 'frozen'):
            if self._profile:
                raise Exception("Can't profile with sys.frozen!")
            executable = os.path.join(os.path.dirname(sys.executable),
                                      'qutebrowser')
            args = []
        else:
            executable = sys.executable
            if self._profile:
                profile_dir = os.path.join(os.getcwd(), 'prof')
                profile_id = '{}_{}'.format(self._instance_id,
                                            next(self._run_counter))
                profile_file = os.path.join(profile_dir,
                                            '{}.pstats'.format(profile_id))
                try:
                    os.mkdir(profile_dir)
                except FileExistsError:
                    pass
                args = [os.path.join('scripts', 'dev', 'run_profile.py'),
                        '--profile-tool', 'none',
                        '--profile-file', profile_file]
            else:
                args = ['-m', 'qutebrowser']
        return executable, args

    def _default_args(self):
        return ['--debug', '--no-err-windows', '--temp-basedir', 'about:blank']

    def path_to_url(self, path, *, port=None, https=False):
        """Get a URL based on a filename for the localhost webserver.

        URLs like about:... and qute:... are handled specially and returned
        verbatim.
        """
        if path.startswith('about:') or path.startswith('qute:'):
            return path
        else:
            return '{}://localhost:{}/{}'.format(
                'https' if https else 'http',
                self._httpbin.port if port is None else port,
                path if path != '/' else '')

    def wait_for_js(self, message):
        """Wait for the given javascript console message."""
        self.wait_for(category='js', function='javaScriptConsoleMessage',
                      message='[*] {}'.format(message))

    def _is_error_logline(self, msg):
        """Check if the given LogLine is some kind of error message."""
        is_js_error = (msg.category == 'js' and
                       msg.function == 'javaScriptConsoleMessage' and
                       testutils.pattern_match(pattern='[*] [FAIL] *',
                                               value=msg.message))
        # Try to complain about the most common mistake when accidentally
        # loading external resources. A fuzzy_url line gets logged when
        # initializing settings though, so ignore those.
        is_ddg_page = (
            'duckduckgo' in msg.message and not (msg.module == 'urlutils' and
                                                 msg.function == 'fuzzy_url'))
        return msg.loglevel > logging.INFO or is_js_error or is_ddg_page

    def _maybe_skip(self):
        """Skip the test if [SKIP] lines were logged."""
        skip_texts = []

        for msg in self._data:
            if (msg.category == 'js' and
                    msg.function == 'javaScriptConsoleMessage' and
                    testutils.pattern_match(pattern='[*] [SKIP] *',
                                            value=msg.message)):
                skip_texts.append(msg.message.partition(' [SKIP] ')[2])

        if skip_texts:
            pytest.skip(', '.join(skip_texts))

    def after_test(self, did_fail):  # pylint: disable=arguments-differ
        """Handle unexpected/skip logging and clean up after each test.

        Args:
            did_fail: Set if the main test failed already, then logged errors
                      are ignored.
        """
        __tracebackhide__ = True
        bad_msgs = [msg for msg in self._data
                    if self._is_error_logline(msg) and not msg.expected]

        if did_fail:
            super().after_test()
            return

        try:
            if bad_msgs:
                text = 'Logged unexpected errors:\n\n' + '\n'.join(
                    str(e) for e in bad_msgs)
                # We'd like to use pytrace=False here but don't as a WORKAROUND
                # for https://github.com/pytest-dev/pytest/issues/1316
                pytest.fail(text)
            else:
                self._maybe_skip()
        finally:
            super().after_test()

    def send_cmd(self, command, count=None):
        """Send a command to the running qutebrowser instance."""
        assert self._ipc_socket is not None

        time.sleep(self._delay / 1000)

        if count is not None:
            command = ':{}:{}'.format(count, command.lstrip(':'))

        ipc.send_to_running_instance(self._ipc_socket, [command],
                                     target_arg='')
        self.wait_for(category='commands', module='command', function='run',
                      message='command called: *')

    def get_setting(self, sect, opt):
        """Get the value of a qutebrowser setting."""
        self.send_cmd(':set {} {}?'.format(sect, opt))
        msg = self.wait_for(loglevel=logging.INFO, category='message',
                            message='{} {} = *'.format(sect, opt))
        return msg.message.split(' = ')[1]

    def set_setting(self, sect, opt, value):
        self.send_cmd(':set "{}" "{}" "{}"'.format(sect, opt, value))
        self.wait_for(category='config', message='Config option changed: *')

    @contextlib.contextmanager
    def temp_setting(self, sect, opt, value):
        """Context manager to set a setting and reset it on exit."""
        old_value = self.get_setting(sect, opt)
        self.set_setting(sect, opt, value)
        yield
        self.set_setting(sect, opt, old_value)

    def open_path(self, path, *, new_tab=False, new_window=False, port=None,
                  https=False):
        """Open the given path on the local webserver in qutebrowser."""
        if new_tab and new_window:
            raise ValueError("new_tab and new_window given!")

        url = self.path_to_url(path, port=port, https=https)
        if new_tab:
            self.send_cmd(':open -t ' + url)
        elif new_window:
            self.send_cmd(':open -w ' + url)
        else:
            self.send_cmd(':open ' + url)

    def mark_expected(self, category=None, loglevel=None, message=None):
        """Mark a given logging message as expected."""
        line = self.wait_for(category=category, loglevel=loglevel,
                             message=message)
        line.expected = True

    def wait_for_load_finished(self, path, *, port=None, https=False,
                               timeout=None, load_status='success'):
        """Wait until any tab has finished loading."""
        if timeout is None:
            if 'CI' in os.environ:
                timeout = 15000
            else:
                timeout = 5000

        url = self.path_to_url(path, port=port, https=https)
        # We really need the same representation that the webview uses in its
        # __repr__
        url = utils.elide(QUrl(url).toDisplayString(QUrl.EncodeUnicode), 100)
        pattern = re.compile(
            r"(load status for <qutebrowser\.browser\.webview\.WebView "
            r"tab_id=\d+ url='{url}'>: LoadStatus\.{load_status}|fetch: "
            r"PyQt5\.QtCore\.QUrl\('{url}'\) -> .*)".format(
                load_status=re.escape(load_status), url=re.escape(url)))
        self.wait_for(message=pattern, timeout=timeout)

    def get_session(self):
        """Save the session and get the parsed session data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session = os.path.join(tmpdir, 'session.yml')
            self.send_cmd(':session-save "{}"'.format(session))
            self.wait_for(category='message', loglevel=logging.INFO,
                          message='Saved session {}.'.format(session))
            with open(session, encoding='utf-8') as f:
                data = f.read()

        self._log(data)
        return yaml.load(data)

    def get_content(self, plain=True):
        """Get the contents of the current page."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'page')

            if plain:
                self.send_cmd(':debug-dump-page --plain "{}"'.format(path))
            else:
                self.send_cmd(':debug-dump-page "{}"'.format(path))

            self.wait_for(category='message', loglevel=logging.INFO,
                          message='Dumped page to {}.'.format(path))

            with open(path, 'r', encoding='utf-8') as f:
                return f.read()

    def press_keys(self, keys):
        """Press the given keys using :fake-key."""
        self.send_cmd(':fake-key -g "{}"'.format(keys))


@pytest.yield_fixture(scope='module')
def quteproc_process(qapp, httpbin, request):
    """Fixture for qutebrowser process which is started once per file."""
    delay = request.config.getoption('--qute-delay')
    profile = request.config.getoption('--qute-profile-subprocs')
    proc = QuteProc(httpbin, delay, profile=profile)
    proc.start()
    yield proc
    proc.terminate()


@pytest.yield_fixture
def quteproc(quteproc_process, httpbin, request):
    """Per-test qutebrowser fixture which uses the per-file process."""
    request.node._quteproc_log = quteproc_process.captured_log
    quteproc_process.before_test()
    yield quteproc_process
    quteproc_process.after_test(did_fail=request.node.rep_call.failed)


@pytest.yield_fixture
def quteproc_new(qapp, httpbin, request):
    """Per-test qutebrowser process to test invocations."""
    delay = request.config.getoption('--qute-delay')
    profile = request.config.getoption('--qute-profile-subprocs')
    proc = QuteProc(httpbin, delay, profile=profile)
    request.node._quteproc_log = proc.captured_log
    # Not calling before_test here as that would start the process
    yield proc
    proc.after_test(did_fail=request.node.rep_call.failed)
