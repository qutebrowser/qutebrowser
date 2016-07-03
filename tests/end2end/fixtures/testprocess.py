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

"""Base class for a subprocess run for tests.."""

import re
import os
import time

import pytest
import pytestqt.plugin
from PyQt5.QtCore import (pyqtSlot, pyqtSignal, QProcess, QObject,
                          QElapsedTimer, QProcessEnvironment)
from PyQt5.QtTest import QSignalSpy

from helpers import utils

from qutebrowser.utils import utils as quteutils


class InvalidLine(Exception):

    """Raised when the process prints a line which is not parsable."""

    pass


class ProcessExited(Exception):

    """Raised when the child process did exit."""

    pass


class WaitForTimeout(Exception):

    """Raised when wait_for didn't get the expected message."""


class BlacklistedMessageError(Exception):

    """Raised when ensure_not_logged found a message."""


class Line:

    """Container for a line of data the process emits.

    Attributes:
        data: The raw data passed to the constructor.
        waited_for: If Process.wait_for was used on this line already.
    """

    def __init__(self, data):
        self.data = data
        self.waited_for = False

    def __repr__(self):
        return '{}({!r})'.format(self.__class__.__name__, self.data)


def _render_log(data, threshold=100):
    """Shorten the given log without -v and convert to a string."""
    # pylint: disable=no-member
    data = [str(d) for d in data]
    is_exception = any('Traceback (most recent call last):' in line
                       for line in data)
    if (len(data) > threshold and
            not pytest.config.getoption('--verbose') and
            not is_exception):
        msg = '[{} lines suppressed, use -v to show]'.format(
            len(data) - threshold)
        data = [msg] + data[-threshold:]
    return '\n'.join(data)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Add qutebrowser/httpbin sections to captured output if a test failed."""
    outcome = yield
    if call.when not in ['call', 'teardown']:
        return
    report = outcome.get_result()

    if report.passed:
        return

    quteproc_log = getattr(item, '_quteproc_log', None)
    httpbin_log = getattr(item, '_httpbin_log', None)

    if not hasattr(report.longrepr, 'addsection'):
        # In some conditions (on OS X and Windows it seems), report.longrepr is
        # actually a tuple. This is handled similarily in pytest-qt too.
        return

    # pylint: disable=no-member
    if pytest.config.getoption('--capture') == 'no':
        # Already printed live
        return

    if quteproc_log is not None:
        report.longrepr.addsection("qutebrowser output",
                                   _render_log(quteproc_log))
    if httpbin_log is not None:
        report.longrepr.addsection("httpbin output", _render_log(httpbin_log))


class Process(QObject):

    """Abstraction over a running test subprocess process.

    Reads the log from its stdout and parses it.

    Attributes:
        _invalid: A list of lines which could not be parsed.
        _data: A list of parsed lines.
        proc: The QProcess for the underlying process.
        exit_expected: Whether the process is expected to quit.

    Signals:
        ready: Emitted when the server finished starting up.
        new_data: Emitted when a new line was parsed.
    """

    ready = pyqtSignal()
    new_data = pyqtSignal(object)
    KEYS = ['data']

    def __init__(self, parent=None):
        super().__init__(parent)
        self.captured_log = []
        self._invalid = []
        self._data = []
        self.proc = QProcess()
        self.proc.setReadChannel(QProcess.StandardError)
        self.exit_expected = False

    def _log(self, line):
        """Add the given line to the captured log output."""
        # pylint: disable=no-member
        if pytest.config.getoption('--capture') == 'no':
            print(line)
        self.captured_log.append(line)

    def log_summary(self, text):
        """Log the given line as summary/title."""
        text = '\n{line} {text} {line}\n'.format(line='='*30, text=text)
        self._log(text)

    def _parse_line(self, line):
        """Parse the given line from the log.

        Return:
            A self.ParseResult member.
        """
        raise NotImplementedError

    def _executable_args(self):
        """Get the executable and necessary arguments as a tuple."""
        raise NotImplementedError

    def _default_args(self):
        """Get the default arguments to use if none were passed to start()."""
        raise NotImplementedError

    def _get_data(self):
        """Get the parsed data for this test.

        Also waits for 0.5s to make sure any new data is received.

        Subprocesses are expected to alias this to a public method with a
        better name.
        """
        self.proc.waitForReadyRead(500)
        self.read_log()
        return self._data

    def _wait_signal(self, signal, timeout=5000, raising=True):
        """Wait for a signal to be emitted.

        Should be used in a contextmanager.
        """
        blocker = pytestqt.plugin.SignalBlocker(timeout=timeout,
                                                raising=raising)
        blocker.connect(signal)
        return blocker

    @pyqtSlot()
    def read_log(self):
        """Read the log from the process' stdout."""
        if not hasattr(self, 'proc'):
            # I have no idea how this happens, but it does...
            return
        while self.proc.canReadLine():
            line = self.proc.readLine()
            line = bytes(line).decode('utf-8', errors='ignore').rstrip('\r\n')

            try:
                parsed = self._parse_line(line)
            except InvalidLine:
                self._invalid.append(line)
                self._log("INVALID: {}".format(line))
                continue

            if parsed is None:
                if self._invalid:
                    self._log("IGNORED: {}".format(line))
            else:
                self._data.append(parsed)
                self.new_data.emit(parsed)

    def start(self, args=None, *, env=None):
        """Start the process and wait until it started."""
        self._start(args, env=env)
        timeout = 60 if 'CI' in os.environ else 20
        for _ in range(timeout):
            with self._wait_signal(self.ready, timeout=1000,
                                   raising=False) as blocker:
                pass

            if not self.is_running():
                # _start ensures it actually started, but it might quit shortly
                # afterwards
                raise ProcessExited()

            if blocker.signal_triggered:
                self._after_start()
                return

        raise WaitForTimeout("Timed out while waiting for process start.")

    def _start(self, args, env):
        """Actually start the process."""
        executable, exec_args = self._executable_args()
        if args is None:
            args = self._default_args()

        if env is None:
            procenv = QProcessEnvironment.systemEnvironment()
        else:
            procenv = QProcessEnvironment()
            for k, v in env.items():
                procenv.insert(k, v)

            passthrough_vars = ['DISPLAY', 'HOME']  # so --no-xvfb works
            for var in passthrough_vars:
                if var in os.environ:
                    procenv.insert(var, os.environ[var])

        self.proc.readyRead.connect(self.read_log)
        self.proc.setProcessEnvironment(procenv)
        self.proc.start(executable, exec_args + args)
        ok = self.proc.waitForStarted()
        assert ok
        assert self.is_running()

    def _after_start(self):
        """Do things which should be done immediately after starting."""
        pass

    def before_test(self):
        """Restart process before a test if it exited before."""
        self._invalid = []
        if not self.is_running():
            self.start()

    def after_test(self):
        """Clean up data after each test.

        Also checks self._invalid so the test counts as failed if there were
        unexpected output lines earlier.
        """
        __tracebackhide__ = True
        self.captured_log = []
        if self._invalid:
            # Wait for a bit so the full error has a chance to arrive
            time.sleep(1)
            # Exit the process to make sure we're in a defined state again
            self.terminate()
            self.clear_data()
            raise InvalidLine

        self.clear_data()
        if not self.is_running() and not self.exit_expected:
            raise ProcessExited
        self.exit_expected = False

    def clear_data(self):
        """Clear the collected data."""
        self._data.clear()

    def terminate(self):
        """Clean up and shut down the process."""
        self.proc.terminate()
        self.proc.waitForFinished()

    def is_running(self):
        """Check if the process is currently running."""
        return self.proc.state() == QProcess.Running

    def _match_data(self, value, expected):
        """Helper for wait_for to match a given value.

        The behavior of this method is slightly different depending on the
        types of the filtered values:

        - If expected is None, the filter always matches.
        - If the value is a string or bytes object and the expected value is
          too, the pattern is treated as a glob pattern (with only * active).
        - If the value is a string or bytes object and the expected value is a
          compiled regex, it is used for matching.
        - If the value is any other type, == is used.

        Return:
            A bool
        """
        regex_type = type(re.compile(''))
        if expected is None:
            return True
        elif isinstance(expected, regex_type):
            return expected.match(value)
        elif isinstance(value, (bytes, str)):
            return utils.pattern_match(pattern=expected, value=value)
        else:
            return value == expected

    def _wait_for_existing(self, override_waited_for, **kwargs):
        """Check if there are any line in the history for wait_for.

        Return: either the found line or None.
        """
        __tracebackhide__ = True
        for line in self._data:
            matches = []

            for key, expected in kwargs.items():
                value = getattr(line, key)
                matches.append(self._match_data(value, expected))

            if all(matches) and (not line.waited_for or override_waited_for):
                # If we waited for this line, chances are we don't mean the
                # same thing the next time we use wait_for and it matches
                # this line again.
                line.waited_for = True
                if 'message' in kwargs:
                    self._log("\n----> Already found {!r} in the log".format(
                        kwargs['message']))
                return line
        return None

    def _wait_for_new(self, timeout, do_skip, **kwargs):
        """Wait for a log message which doesn't exist yet.

        Called via wait_for.
        """
        __tracebackhide__ = True
        message = kwargs.get('message', None)
        if message is not None:
            elided = quteutils.elide(repr(message), 50)
            self._log("\n----> Waiting for {} in the log".format(elided))

        spy = QSignalSpy(self.new_data)
        elapsed_timer = QElapsedTimer()
        elapsed_timer.start()

        while True:
            # Skip if there are pending messages causing a skip
            self._maybe_skip()
            got_signal = spy.wait(timeout)
            if not got_signal or elapsed_timer.hasExpired(timeout):
                msg = "Timed out after {}ms waiting for {!r}.".format(
                    timeout, kwargs)
                if do_skip:
                    pytest.skip(msg)
                else:
                    raise WaitForTimeout(msg)

            match = self._wait_for_match(spy, kwargs)
            if match is not None:
                if message is not None:
                    self._log("----> found it")
                return match

    def _wait_for_match(self, spy, kwargs):
        """Try matching the kwargs with the given QSignalSpy."""
        for args in spy:
            assert len(args) == 1
            line = args[0]

            matches = []

            for key, expected in kwargs.items():
                value = getattr(line, key)
                matches.append(self._match_data(value, expected))

            if all(matches):
                # If we waited for this line, chances are we don't mean the
                # same thing the next time we use wait_for and it matches
                # this line again.
                line.waited_for = True
                return line
        return None

    def _maybe_skip(self):
        """Can be overridden by subclasses to skip on certain log lines.

        We can't run pytest.skip directly while parsing the log, as that would
        lead to a pytest.skip.Exception error in a virtual Qt method, which
        means pytest-qt fails the test.

        Instead, we check for skip messages periodically in
        QuteProc._maybe_skip, and call _maybe_skip after every parsed message
        in wait_for (where it's most likely that new messages arrive).
        """
        pass

    def wait_for(self, timeout=None, *, override_waited_for=False,
                 do_skip=False, **kwargs):
        """Wait until a given value is found in the data.

        Keyword arguments to this function get interpreted as attributes of the
        searched data. Every given argument is treated as a pattern which
        the attribute has to match against.

        Args:
            timeout: How long to wait for the message.
            override_waited_for: If set, gets triggered by previous messages
                                 again.
            do_skip: If set, call pytest.skip on a timeout.

        Return:
            The matched line.
        """
        __tracebackhide__ = True

        if timeout is None:
            if do_skip:
                timeout = 2000
            elif 'CI' in os.environ:
                timeout = 15000
            else:
                timeout = 5000
        if not kwargs:
            raise TypeError("No keyword arguments given!")
        for key in kwargs:
            assert key in self.KEYS

        existing = self._wait_for_existing(override_waited_for, **kwargs)
        if existing is not None:
            return existing
        else:
            return self._wait_for_new(timeout=timeout, do_skip=do_skip,
                                      **kwargs)

    def ensure_not_logged(self, delay=500, **kwargs):
        """Make sure the data matching the given arguments is not logged.

        If nothing is found in the log, we wait for delay ms to make sure
        nothing arrives.
        """
        __tracebackhide__ = True
        try:
            line = self.wait_for(timeout=delay, override_waited_for=True,
                                 **kwargs)
        except WaitForTimeout:
            return
        else:
            raise BlacklistedMessageError(line)

    def wait_for_quit(self):
        """Wait until the process has quit."""
        self.exit_expected = True
        with self._wait_signal(self.proc.finished, timeout=15000):
            pass
