# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Functions to execute a userscript."""

import os
import os.path
import tempfile

from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, QSocketNotifier

from qutebrowser.utils import message, log, objreg, standarddir
from qutebrowser.commands import runners
from qutebrowser.config import config
from qutebrowser.misc import guiprocess
from qutebrowser.browser.webkit import downloads


class _QtFIFOReader(QObject):

    """A FIFO reader based on a QSocketNotifier.

    Attributes:
        _filepath: The path to the opened FIFO.
        _fifo: The Python file object for the FIFO.
        _notifier: The QSocketNotifier used.

    Signals:
        got_line: Emitted when a whole line arrived.
    """

    got_line = pyqtSignal(str)

    def __init__(self, filepath, parent=None):
        super().__init__(parent)
        self._filepath = filepath
        # We open as R/W so we never get EOF and have to reopen the pipe.
        # See http://www.outflux.net/blog/archives/2008/03/09/using-select-on-a-fifo/
        # We also use os.open and os.fdopen rather than built-in open so we
        # can add O_NONBLOCK.
        # pylint: disable=no-member,useless-suppression
        fd = os.open(filepath, os.O_RDWR | os.O_NONBLOCK)
        self._fifo = os.fdopen(fd, 'r')
        self._notifier = QSocketNotifier(fd, QSocketNotifier.Read, self)
        self._notifier.activated.connect(self.read_line)

    @pyqtSlot()
    def read_line(self):
        """(Try to) read a line from the FIFO."""
        log.procs.debug("QSocketNotifier triggered!")
        self._notifier.setEnabled(False)
        for line in self._fifo:
            self.got_line.emit(line.rstrip('\r\n'))
        self._notifier.setEnabled(True)

    def cleanup(self):
        """Clean up so the FIFO can be closed."""
        self._notifier.setEnabled(False)
        for line in self._fifo:
            self.got_line.emit(line.rstrip('\r\n'))
        self._fifo.close()


class _BaseUserscriptRunner(QObject):

    """Common part between the Windows and the POSIX userscript runners.

    Attributes:
        _filepath: The path of the file/FIFO which is being read.
        _proc: The GUIProcess which is being executed.
        _win_id: The window ID this runner is associated with.
        _cleaned_up: Whether temporary files were cleaned up.
        _text_stored: Set when the page text was stored async.
        _html_stored: Set when the page html was stored async.
        _args: Arguments to pass to _run_process.
        _kwargs: Keyword arguments to pass to _run_process.

    Signals:
        got_cmd: Emitted when a new command arrived and should be executed.
        finished: Emitted when the userscript finished running.
    """

    got_cmd = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, win_id, parent=None):
        super().__init__(parent)
        self._cleaned_up = False
        self._win_id = win_id
        self._filepath = None
        self._proc = None
        self._env = {}
        self._text_stored = False
        self._html_stored = False
        self._args = None
        self._kwargs = None

    def store_text(self, text):
        """Called as callback when the text is ready from the web backend."""
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                         suffix='.txt',
                                         delete=False) as txt_file:
            txt_file.write(text)
            self._env['QUTE_TEXT'] = txt_file.name

        self._text_stored = True
        log.procs.debug("Text stored from webview")
        if self._text_stored and self._html_stored:
            log.procs.debug("Both text/HTML stored, kicking off userscript!")
            self._run_process(*self._args, **self._kwargs)

    def store_html(self, html):
        """Called as callback when the html is ready from the web backend."""
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                         suffix='.html',
                                         delete=False) as html_file:
            html_file.write(html)
            self._env['QUTE_HTML'] = html_file.name

        self._html_stored = True
        log.procs.debug("HTML stored from webview")
        if self._text_stored and self._html_stored:
            log.procs.debug("Both text/HTML stored, kicking off userscript!")
            self._run_process(*self._args, **self._kwargs)

    def _run_process(self, cmd, *args, env=None, verbose=False):
        """Start the given command.

        Args:
            cmd: The command to be started.
            *args: The arguments to hand to the command
            env: A dictionary of environment variables to add.
            verbose: Show notifications when the command started/exited.
        """
        self._env['QUTE_FIFO'] = self._filepath
        if env is not None:
            self._env.update(env)
        self._proc = guiprocess.GUIProcess(self._win_id, 'userscript',
                                           additional_env=self._env,
                                           verbose=verbose, parent=self)
        self._proc.finished.connect(self.on_proc_finished)
        self._proc.error.connect(self.on_proc_error)
        self._proc.start(cmd, args)

    def _cleanup(self):
        """Clean up temporary files."""
        if self._cleaned_up:
            return
        self._cleaned_up = True
        tempfiles = [self._filepath]
        if 'QUTE_HTML' in self._env:
            tempfiles.append(self._env['QUTE_HTML'])
        if 'QUTE_TEXT' in self._env:
            tempfiles.append(self._env['QUTE_TEXT'])
        for fn in tempfiles:
            log.procs.debug("Deleting temporary file {}.".format(fn))
            try:
                os.remove(fn)
            except OSError as e:
                # NOTE: Do not replace this with "raise CommandError" as it's
                # executed async.
                message.error(
                    self._win_id, "Failed to delete tempfile {} ({})!".format(
                        fn, e))
        self._filepath = None
        self._proc = None
        self._env = {}
        self._text_stored = False
        self._html_stored = False

    def prepare_run(self, *args, **kwargs):
        """Prepare running the userscript given.

        Needs to be overridden by subclasses.
        The script will actually run after store_text and store_html have been
        called.

        Args:
            Passed to _run_process.
        """
        raise NotImplementedError

    @pyqtSlot()
    def on_proc_finished(self):
        """Called when the process has finished.

        Needs to be overridden by subclasses.
        """
        raise NotImplementedError

    @pyqtSlot()
    def on_proc_error(self):
        """Called when the process encountered an error.

        Needs to be overridden by subclasses.
        """
        raise NotImplementedError


class _POSIXUserscriptRunner(_BaseUserscriptRunner):

    """Userscript runner to be used on POSIX. Uses _QtFIFOReader.

    Commands are executed immediately when they arrive in the FIFO.

    Attributes:
        _reader: The _QtFIFOReader instance.
    """

    def __init__(self, win_id, parent=None):
        super().__init__(win_id, parent)
        self._reader = None

    def prepare_run(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs

        try:
            # tempfile.mktemp is deprecated and discouraged, but we use it here
            # to create a FIFO since the only other alternative would be to
            # create a directory and place the FIFO there, which sucks. Since
            # os.mkfifo will raise an exception anyways when the path doesn't
            # exist, it shouldn't be a big issue.
            self._filepath = tempfile.mktemp(prefix='qutebrowser-userscript-',
                                             dir=standarddir.runtime())
            # pylint: disable=no-member,useless-suppression
            os.mkfifo(self._filepath)
        except OSError as e:
            message.error(self._win_id,
                          "Error while creating FIFO: {}".format(e))
            return

        self._reader = _QtFIFOReader(self._filepath)
        self._reader.got_line.connect(self.got_cmd)

    @pyqtSlot()
    def on_proc_finished(self):
        self._cleanup()

    @pyqtSlot()
    def on_proc_error(self):
        self._cleanup()

    def _cleanup(self):
        """Clean up reader and temporary files."""
        if self._cleaned_up:
            return
        log.procs.debug("Cleaning up")
        self._reader.cleanup()
        self._reader.deleteLater()
        self._reader = None
        super()._cleanup()
        self.finished.emit()


class _WindowsUserscriptRunner(_BaseUserscriptRunner):

    """Userscript runner to be used on Windows.

    This is a much more dumb implementation compared to POSIXUserscriptRunner.
    It uses a normal flat file for commands and executes them all at once when
    the process has finished, as Windows doesn't really understand the concept
    of using files as named pipes.

    This also means the userscript *has* to use >> (append) rather than >
    (overwrite) to write to the file!

    Attributes:
        _oshandle: The oshandle of the temp file.
    """

    def __init__(self, win_id, parent=None):
        super().__init__(win_id, parent)
        self._oshandle = None

    def _cleanup(self):
        """Clean up temporary files after the userscript finished."""
        if self._cleaned_up:
            return

        try:
            with open(self._filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    self.got_cmd.emit(line.rstrip())
        except OSError:
            log.procs.exception("Failed to read command file!")

        try:
            os.close(self._oshandle)
        except OSError:
            log.procs.exception("Failed to close file handle!")
        super()._cleanup()
        self._oshandle = None
        self.finished.emit()

    @pyqtSlot()
    def on_proc_error(self):
        self._cleanup()

    @pyqtSlot()
    def on_proc_finished(self):
        """Read back the commands when the process finished."""
        self._cleanup()

    def prepare_run(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs

        try:
            self._oshandle, self._filepath = tempfile.mkstemp(text=True)
        except OSError as e:
            message.error(self._win_id, "Error while creating tempfile: "
                                        "{}".format(e))
            return


class UnsupportedError(Exception):

    """Raised when userscripts aren't supported on this platform."""

    def __str__(self):
        return "Userscripts are not supported on this platform!"


def run_async(tab, cmd, *args, win_id, env, verbose=False):
    """Run a userscript after dumping page html/source.

    Raises:
        UnsupportedError if userscripts are not supported on the current
        platform.

    Args:
        tab: The WebKitTab/WebEngineTab to get the source from.
        cmd: The userscript binary to run.
        *args: The arguments to pass to the userscript.
        win_id: The window id the userscript is executed in.
        env: A dictionary of variables to add to the process environment.
        verbose: Show notifications when the command started/exited.
    """
    tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                window=win_id)
    commandrunner = runners.CommandRunner(win_id, parent=tabbed_browser)

    if os.name == 'posix':
        runner = _POSIXUserscriptRunner(win_id, tabbed_browser)
    elif os.name == 'nt':  # pragma: no cover
        runner = _WindowsUserscriptRunner(win_id, tabbed_browser)
    else:  # pragma: no cover
        raise UnsupportedError

    runner.got_cmd.connect(
        lambda cmd:
        log.commands.debug("Got userscript command: {}".format(cmd)))
    runner.got_cmd.connect(commandrunner.run_safely)
    user_agent = config.get('network', 'user-agent')
    if user_agent is not None:
        env['QUTE_USER_AGENT'] = user_agent
    config_dir = standarddir.config()
    if config_dir is not None:
        env['QUTE_CONFIG_DIR'] = config_dir
    data_dir = standarddir.data()
    if data_dir is not None:
        env['QUTE_DATA_DIR'] = data_dir
    download_dir = downloads.download_dir()
    if download_dir is not None:
        env['QUTE_DOWNLOAD_DIR'] = download_dir
    cmd_path = os.path.expanduser(cmd)

    # if cmd is not given as an absolute path, look it up
    # ~/.local/share/qutebrowser/userscripts (or $XDG_DATA_DIR)
    if not os.path.isabs(cmd_path):
        log.misc.debug("{} is no absolute path".format(cmd_path))
        cmd_path = os.path.join(standarddir.data(), "userscripts", cmd)
        if not os.path.exists(cmd_path):
            cmd_path = os.path.join(standarddir.system_data(),
                                    "userscripts", cmd)
    log.misc.debug("Userscript to run: {}".format(cmd_path))

    runner.finished.connect(commandrunner.deleteLater)
    runner.finished.connect(runner.deleteLater)

    runner.prepare_run(cmd_path, *args, env=env, verbose=verbose)
    tab.dump_async(runner.store_html)
    tab.dump_async(runner.store_text, plain=True)
