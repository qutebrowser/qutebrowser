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
import json

import yaml
import pytest
from PyQt5.QtCore import pyqtSignal, QUrl

from qutebrowser.misc import ipc
from qutebrowser.utils import log, utils, javascript
from helpers import utils as testutils
from end2end.fixtures import testprocess


instance_counter = itertools.count()


def is_ignored_qt_message(message):
    """Check if the message is listed in qt_log_ignore."""
    regexes = pytest.config.getini('qt_log_ignore')
    for regex in regexes:
        if re.match(regex, message):
            return True
    return False


class LogLine(testprocess.Line):

    """A parsed line from the qutebrowser log output.

    Attributes:
        timestamp/loglevel/category/module/function/line/message/levelname:
            Parsed from the log output.
        expected: Whether the message was expected or not.
    """

    def __init__(self, data):
        super().__init__(data)
        try:
            line = json.loads(data)
        except ValueError:
            raise testprocess.InvalidLine(data)
        if not isinstance(line, dict):
            raise testprocess.InvalidLine(data)

        self.timestamp = datetime.datetime.fromtimestamp(line['created'])
        self.msecs = line['msecs']
        self.loglevel = line['levelno']
        self.levelname = line['levelname']
        self.category = line['name']
        self.module = line['module']
        self.function = line['funcName']
        self.line = line['lineno']
        if self.function is None and self.line == 0:
            self.line = None
        self.traceback = line.get('traceback')
        self.message = line['message']

        self.expected = is_ignored_qt_message(self.message)
        self.use_color = False

    def __str__(self):
        return self.formatted_str(colorized=self.use_color)

    def formatted_str(self, colorized=True):
        """Return a formatted colorized line.

        This returns a line like qute without --json-logging would produce.

        Args:
            colorized: If True, ANSI color codes will be embedded.
        """
        r = logging.LogRecord(self.category, self.loglevel, '', self.line,
                              self.message, (), None)
        # Patch some attributes of the LogRecord
        if self.line is None:
            r.line = 0
        r.created = self.timestamp.timestamp()
        r.msecs = self.msecs
        r.module = self.module
        r.funcName = self.function

        format_str = log.EXTENDED_FMT
        format_str = format_str.replace('{asctime:8}',
                                        '{asctime:8}.{msecs:03.0f}')
        # Mark expected errors with (expected) so it's less confusing for tests
        # which expect errors but fail due to other errors.
        if self.expected and self.loglevel > logging.INFO:
            new_color = '{' + log.LOG_COLORS['DEBUG'] + '}'
            format_str = format_str.replace('{log_color}', new_color)
            format_str = re.sub(r'{levelname:(\d*)}',
                                # Leave away the padding because (expected) is
                                # longer anyway.
                                r'{levelname} (expected)', format_str)

        formatter = log.ColoredFormatter(format_str, log.DATEFMT, '{',
                                         use_colors=colorized)
        result = formatter.format(r)
        # Manually append the stringified traceback if one is present
        if self.traceback is not None:
            result += '\n' + self.traceback
        return result


class QuteProc(testprocess.Process):

    """A running qutebrowser process used for tests.

    Attributes:
        _ipc_socket: The IPC socket of the started instance.
        _webengine: Whether to use QtWebEngine
        basedir: The base directory for this instance.
        request: The request object for the current test.
        _focus_ready: Whether the main window got focused.
        _load_ready: Whether the about:blank page got loaded.
        _instance_id: A unique ID for this QuteProc instance
        _run_counter: A counter to get a unique ID for each run.

    Signals:
        got_error: Emitted when there was an error log line.
    """

    got_error = pyqtSignal()

    KEYS = ['timestamp', 'loglevel', 'category', 'module', 'function', 'line',
            'message']

    def __init__(self, request, *, parent=None):
        super().__init__(parent)
        self._ipc_socket = None
        self.basedir = None
        self._focus_ready = False
        self._load_ready = False
        self._instance_id = next(instance_counter)
        self._run_counter = itertools.count()
        self.request = request

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

    def _process_line(self, log_line):
        """Check if the line matches any initial lines we're interested in."""
        start_okay_message_load = (
            "load status for <qutebrowser.browser.* tab_id=0 "
            "url='about:blank'>: LoadStatus.success")
        start_okay_message_focus = (
            "Focus object changed: "
            "<qutebrowser.browser.* tab_id=0 url='about:blank'>")
        # With QtWebEngine the QOpenGLWidget has the actual focus
        start_okay_message_focus_qtwe = (
            "Focus object changed: <PyQt5.QtWidgets.QOpenGLWidget object at *>"
        )

        if (log_line.category == 'ipc' and
                log_line.message.startswith("Listening as ")):
            self._ipc_socket = log_line.message.split(' ', maxsplit=2)[2]
        elif (log_line.category == 'webview' and
              testutils.pattern_match(pattern=start_okay_message_load,
                                      value=log_line.message)):
            if not self._load_ready:
                log_line.waited_for = True
            self._is_ready('load')
        elif (log_line.category == 'misc' and
              testutils.pattern_match(pattern=start_okay_message_focus,
                                      value=log_line.message)):
            self._is_ready('focus')
        elif (log_line.category == 'misc' and
              testutils.pattern_match(pattern=start_okay_message_focus_qtwe,
                                      value=log_line.message)):
            self._is_ready('focus')
        elif (log_line.category == 'init' and
              log_line.module == 'standarddir' and
              log_line.function == 'init' and
              log_line.message.startswith('Base directory:')):
            self.basedir = log_line.message.split(':', maxsplit=1)[1].strip()
        elif self._is_error_logline(log_line):
            self.got_error.emit()

    def _parse_line(self, line):
        try:
            log_line = LogLine(line)
        except testprocess.InvalidLine:
            if not line.strip():
                return None
            elif 'Running without the SUID sandbox!' in line:
                # QtWebEngine error
                return None
            elif line.startswith('Xlib: sequence lost'):
                # https://travis-ci.org/The-Compiler/qutebrowser/jobs/157941720
                # ???
                return None
            elif is_ignored_qt_message(line):
                return None
            else:
                raise

        log_line.use_color = self.request.config.getoption('--color') != 'no'
        verbose = self.request.config.getoption('--verbose')
        if log_line.loglevel > logging.VDEBUG or verbose:
            self._log(log_line)
        self._process_line(log_line)
        return log_line

    def _executable_args(self):
        profile = self.request.config.getoption('--qute-profile-subprocs')
        if hasattr(sys, 'frozen'):
            if profile:
                raise Exception("Can't profile with sys.frozen!")
            executable = os.path.join(os.path.dirname(sys.executable),
                                      'qutebrowser')
            args = []
        else:
            executable = sys.executable
            if profile:
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
                args = ['-bb', '-m', 'qutebrowser']
        return executable, args

    def _default_args(self):
        backend = 'webengine' if self.request.config.webengine else 'webkit'
        return ['--debug', '--no-err-windows', '--temp-basedir',
                '--json-logging', '--loglevel', 'vdebug',
                '--backend', backend, 'about:blank']

    def path_to_url(self, path, *, port=None, https=False):
        """Get a URL based on a filename for the localhost webserver.

        URLs like about:... and qute:... are handled specially and returned
        verbatim.
        """
        if path.startswith('about:') or path.startswith('qute:'):
            return path
        else:
            httpbin = self.request.getfixturevalue('httpbin')
            return '{}://localhost:{}/{}'.format(
                'https' if https else 'http',
                httpbin.port if port is None else port,
                path if path != '/' else '')

    def wait_for_js(self, message):
        """Wait for the given javascript console message.

        Return:
            The LogLine.
        """
        line = self.wait_for(category='js',
                             function='javaScriptConsoleMessage',
                             message='[*] {}'.format(message))
        line.expected = True
        return line

    def wait_scroll_pos_changed(self, x=None, y=None):
        """Wait until a "Scroll position changed" message was found.

        With QtWebEngine, on older Qt versions which lack
        QWebEnginePage.scrollPositionChanged, this also skips the test.
        """
        __tracebackhide__ = (lambda e:
                             e.errisinstance(testprocess.WaitForTimeout))
        if (x is None and y is not None) or (y is None and x is not None):
            raise ValueError("Either both x/y or neither must be given!")

        if self.request.config.webengine:
            # pylint: disable=no-name-in-module,useless-suppression
            from PyQt5.QtWebEngineWidgets import QWebEnginePage
            # pylint: enable=no-name-in-module,useless-suppression
            if not hasattr(QWebEnginePage, 'scrollPositionChanged'):
                # Qt < 5.7
                pytest.skip("QWebEnginePage.scrollPositionChanged missing")
        if x is None and y is None:
            point = 'PyQt5.QtCore.QPoint(*, *)'  # not counting 0/0 here
        elif x == '0' and y == '0':
            point = 'PyQt5.QtCore.QPoint()'
        else:
            point = 'PyQt5.QtCore.QPoint({}, {})'.format(x, y)
        self.wait_for(category='webview',
                      message='Scroll position changed to ' + point)

    def wait_for(self, timeout=None, **kwargs):
        """Extend wait_for to add divisor if a test is xfailing."""
        __tracebackhide__ = (lambda e:
                             e.errisinstance(testprocess.WaitForTimeout))
        xfail = self.request.node.get_marker('xfail')
        if xfail and xfail.args[0]:
            kwargs['divisor'] = 10
        else:
            kwargs['divisor'] = 1
        return super().wait_for(timeout=timeout, **kwargs)

    def _is_error_logline(self, msg):
        """Check if the given LogLine is some kind of error message."""
        is_js_error = (msg.category == 'js' and
                       msg.function == 'javaScriptConsoleMessage' and
                       testutils.pattern_match(pattern='[*] [FAIL] *',
                                               value=msg.message))
        # Try to complain about the most common mistake when accidentally
        # loading external resources.
        is_ddg_load = testutils.pattern_match(
            pattern="load status for <* tab_id=* url='*duckduckgo*'>: *",
            value=msg.message)

        is_log_error = (msg.loglevel > logging.INFO and
                        not msg.message.startswith('STUB:'))
        return is_log_error or is_js_error or is_ddg_load

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

    def _after_start(self):
        """Adjust some qutebrowser settings after starting."""
        settings = [
            ('ui', 'message-timeout', '0'),
            ('general', 'auto-save-interval', '0'),
            ('general', 'new-instance-open-target.window', 'last-opened')
        ]
        if not self.request.config.webengine:
            settings.append(('network', 'ssl-strict', 'false'))

        for sect, opt, value in settings:
            self.set_setting(sect, opt, value)

    def after_test(self):
        """Handle unexpected/skip logging and clean up after each test."""
        __tracebackhide__ = lambda e: e.errisinstance(pytest.fail.Exception)
        bad_msgs = [msg for msg in self._data
                    if self._is_error_logline(msg) and not msg.expected]

        try:
            call = self.request.node.rep_call
        except AttributeError:
            pass
        else:
            if call.failed or hasattr(call, 'wasxfail'):
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

    def send_ipc(self, commands, target_arg=''):
        """Send a raw command to the running IPC socket."""
        delay = self.request.config.getoption('--qute-delay')
        time.sleep(delay / 1000)

        assert self._ipc_socket is not None
        ipc.send_to_running_instance(self._ipc_socket, commands, target_arg)
        self.wait_for(category='ipc', module='ipc', function='on_ready_read',
                      message='Read from socket *')

    def send_cmd(self, command, count=None, invalid=False, *, escape=True):
        """Send a command to the running qutebrowser instance.

        Args:
            count: The count to pass to the command.
            invalid: If True, we don't wait for "command called: ..." in the
                     log
            escape: Escape backslashes in the command
        """
        summary = command
        if count is not None:
            summary += ' (count {})'.format(count)
        self.log_summary(summary)

        if escape:
            command = command.replace('\\', r'\\')

        if count is not None:
            command = ':{}:{}'.format(count, command.lstrip(':'))

        self.send_ipc([command])
        if not invalid:
            self.wait_for(category='commands', module='command',
                          function='run', message='command called: *')

    def get_setting(self, sect, opt):
        """Get the value of a qutebrowser setting."""
        self.send_cmd(':set {} {}?'.format(sect, opt))
        msg = self.wait_for(loglevel=logging.INFO, category='message',
                            message='{} {} = *'.format(sect, opt))
        return msg.message.split(' = ')[1]

    def set_setting(self, sect, opt, value):
        # \ and " in a value should be treated literally, so escape them
        value = value.replace('\\', r'\\')
        value = value.replace('"', '\\"')
        self.send_cmd(':set "{}" "{}" "{}"'.format(sect, opt, value),
                      escape=False)
        self.wait_for(category='config', message='Config option changed: *')

    @contextlib.contextmanager
    def temp_setting(self, sect, opt, value):
        """Context manager to set a setting and reset it on exit."""
        old_value = self.get_setting(sect, opt)
        self.set_setting(sect, opt, value)
        yield
        self.set_setting(sect, opt, old_value)

    def open_path(self, path, *, new_tab=False, new_window=False, as_url=False,
                  port=None, https=False, wait=True):
        """Open the given path on the local webserver in qutebrowser."""
        url = self.path_to_url(path, port=port, https=https)
        self.open_url(url, new_tab=new_tab, new_window=new_window,
                      as_url=as_url, wait=wait)

    def open_url(self, url, *, new_tab=False, new_window=False, as_url=False,
                 wait=True):
        """Open the given url in qutebrowser."""
        if new_tab and new_window:
            raise ValueError("new_tab and new_window given!")

        if as_url:
            self.send_cmd(url, invalid=True)
        elif new_tab:
            self.send_cmd(':open -t ' + url)
        elif new_window:
            self.send_cmd(':open -w ' + url)
        else:
            self.send_cmd(':open ' + url)

        if wait:
            self.wait_for_load_finished_url(url)

    def mark_expected(self, category=None, loglevel=None, message=None):
        """Mark a given logging message as expected."""
        line = self.wait_for(category=category, loglevel=loglevel,
                             message=message)
        line.expected = True

    def wait_for_load_finished_url(self, url, *, timeout=None,
                                   load_status='success'):
        """Wait until a URL has finished loading."""
        __tracebackhide__ = (lambda e: e.errisinstance(
            testprocess.WaitForTimeout))

        if timeout is None:
            if 'CI' in os.environ:
                timeout = 15000
            else:
                timeout = 5000

        # We really need the same representation that the webview uses in its
        # __repr__
        qurl = QUrl(url)
        if not qurl.isValid():
            raise ValueError("Invalid URL {}: {}".format(url,
                                                         qurl.errorString()))
        url = utils.elide(qurl.toDisplayString(QUrl.EncodeUnicode), 100)
        assert url

        pattern = re.compile(
            r"(load status for <qutebrowser\.browser\..* "
            r"tab_id=\d+ url='{url}/?'>: LoadStatus\.{load_status}|fetch: "
            r"PyQt5\.QtCore\.QUrl\('{url}'\) -> .*)".format(
                load_status=re.escape(load_status), url=re.escape(url)))

        try:
            self.wait_for(message=pattern, timeout=timeout)
        except testprocess.WaitForTimeout:
            raise testprocess.WaitForTimeout("Timed out while waiting for {} "
                                             "to be loaded".format(url))

    def wait_for_load_finished(self, path, *, port=None, https=False,
                               timeout=None, load_status='success'):
        """Wait until a path has finished loading."""
        __tracebackhide__ = (lambda e: e.errisinstance(
            testprocess.WaitForTimeout))
        url = self.path_to_url(path, port=port, https=https)
        self.wait_for_load_finished_url(url, timeout=timeout,
                                        load_status=load_status)

    def get_session(self):
        """Save the session and get the parsed session data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session = os.path.join(tmpdir, 'session.yml')
            self.send_cmd(':session-save "{}"'.format(session))
            self.wait_for(category='message', loglevel=logging.INFO,
                          message='Saved session {}.'.format(session))
            with open(session, encoding='utf-8') as f:
                data = f.read()

        self._log('\nCurrent session data:\n' + data)
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

    def click_element_by_text(self, text):
        """Click the element with the given text."""
        # Use Javascript and XPath to find the right element, use console.log
        # to return an error (no element found, ambiguous element)
        script = (
            'var _es = document.evaluate(\'//*[text()={text}]\', document, '
            'null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);'
            'if (_es.snapshotLength == 0) {{ console.log("qute:no elems"); }} '
            'else if (_es.snapshotLength > 1) {{ console.log("qute:ambiguous '
            'elems") }} '
            'else {{ console.log("qute:okay"); _es.snapshotItem(0).click() }}'
        ).format(text=javascript.string_escape(_xpath_escape(text)))
        self.send_cmd(':jseval ' + script, escape=False)
        message = self.wait_for_js('qute:*').message
        if message.endswith('qute:no elems'):
            raise ValueError('No element with {!r} found'.format(text))
        elif message.endswith('qute:ambiguous elems'):
            raise ValueError('Element with {!r} is not unique'.format(text))
        elif not message.endswith('qute:okay'):
            raise ValueError('Invalid response from qutebrowser: {}'
                             .format(message))

    def compare_session(self, expected):
        """Compare the current sessions against the given template.

        partial_compare is used, which means only the keys/values listed will
        be compared.
        """
        __tracebackhide__ = lambda e: e.errisinstance(pytest.fail.Exception)
        # Translate ... to ellipsis in YAML.
        loader = yaml.SafeLoader(expected)
        loader.add_constructor('!ellipsis', lambda loader, node: ...)
        loader.add_implicit_resolver('!ellipsis', re.compile(r'\.\.\.'), None)

        data = self.get_session()
        expected = loader.get_data()
        outcome = testutils.partial_compare(data, expected)
        if not outcome:
            msg = "Session comparison failed: {}".format(outcome.error)
            msg += '\nsee stdout for details'
            pytest.fail(msg)


def _xpath_escape(text):
    """Escape a string to be used in an XPath expression.

    The resulting string should still be escaped with javascript.string_escape,
    to prevent javascript from interpreting the quotes.

    This function is needed because XPath does not provide any character
    escaping mechanisms, so to get the string
        "I'm back", he said
    you have to use concat like
        concat('"I', "'m back", '", he said')

    Args:
        text: Text to escape

    Return:
        The string "escaped" as a concat() call.
    """
    # Shortcut if at most a single quoting style is used
    if "'" not in text or '"' not in text:
        return repr(text)
    parts = re.split('([\'"])', text)
    # Python's repr() of strings will automatically choose the right quote
    # type. Since each part only contains one "type" of quote, no escaping
    # should be necessary.
    parts = [repr(part) for part in parts if part]
    return 'concat({})'.format(', '.join(parts))


@pytest.fixture(scope='module')
def quteproc_process(qapp, httpbin, request):
    """Fixture for qutebrowser process which is started once per file."""
    # Passing request so it has an initial config
    proc = QuteProc(request)
    proc.start()
    yield proc
    proc.terminate()


@pytest.fixture
def quteproc(quteproc_process, httpbin, request):
    """Per-test qutebrowser fixture which uses the per-file process."""
    request.node._quteproc_log = quteproc_process.captured_log
    quteproc_process.before_test()
    quteproc_process.request = request
    yield quteproc_process
    quteproc_process.after_test()


@pytest.fixture
def quteproc_new(qapp, httpbin, request):
    """Per-test qutebrowser process to test invocations."""
    proc = QuteProc(request)
    request.node._quteproc_log = proc.captured_log
    # Not calling before_test here as that would start the process
    yield proc
    proc.after_test()
    proc.terminate()
