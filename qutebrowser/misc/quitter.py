# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Helpers related to quitting qutebrowser cleanly."""

import os
import os.path
import sys
import json
import atexit
import shutil
import typing
import argparse
import tokenize
import functools
import subprocess

from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from PyQt5.QtWidgets import QApplication
try:
    import hunter
except ImportError:
    hunter = None

import qutebrowser
from qutebrowser.api import cmdutils
from qutebrowser.config import config
from qutebrowser.utils import log
from qutebrowser.misc import sessions, ipc, objects
from qutebrowser.mainwindow import prompt
from qutebrowser.completion.models import miscmodels


instance = typing.cast('Quitter', None)


class Quitter(QObject):

    """Utility class to quit/restart the QApplication.

    Attributes:
        quit_status: The current quitting status.
        _is_shutting_down: Whether we're currently shutting down.
        _args: The argparse namespace.
    """

    shutting_down = pyqtSignal()  # Emitted immediately before shut down

    def __init__(self, *,
                 args: argparse.Namespace,
                 parent: QObject = None) -> None:
        super().__init__(parent)
        self.quit_status = {
            'crash': True,
            'tabs': False,
            'main': False,
        }
        self._is_shutting_down = False
        self._args = args

    def on_last_window_closed(self) -> None:
        """Slot which gets invoked when the last window was closed."""
        self.shutdown(last_window=True)

    def _compile_modules(self) -> None:
        """Compile all modules to catch SyntaxErrors."""
        if os.path.basename(sys.argv[0]) == 'qutebrowser':
            # Launched via launcher script
            return
        elif hasattr(sys, 'frozen'):
            return
        else:
            path = os.path.abspath(os.path.dirname(qutebrowser.__file__))
            if not os.path.isdir(path):
                # Probably running from a python egg.
                return

        for dirpath, _dirnames, filenames in os.walk(path):
            for fn in filenames:
                if os.path.splitext(fn)[1] == '.py' and os.path.isfile(fn):
                    with tokenize.open(os.path.join(dirpath, fn)) as f:
                        compile(f.read(), fn, 'exec')

    def _get_restart_args(
            self, pages: typing.Iterable[str] = (),
            session: str = None,
            override_args: typing.Mapping[str, str] = None
    ) -> typing.Sequence[str]:
        """Get args to relaunch qutebrowser.

        Args:
            pages: The pages to re-open.
            session: The session to load, or None.
            override_args: Argument overrides as a dict.

        Return:
            The commandline as a list of strings.
        """
        if os.path.basename(sys.argv[0]) == 'qutebrowser':
            # Launched via launcher script
            args = [sys.argv[0]]
        elif hasattr(sys, 'frozen'):
            args = [sys.executable]
        else:
            args = [sys.executable, '-m', 'qutebrowser']

        # Add all open pages so they get reopened.
        page_args = []  # type: typing.MutableSequence[str]
        for win in pages:
            page_args.extend(win)
            page_args.append('')

        # Serialize the argparse namespace into json and pass that to the new
        # process via --json-args.
        # We do this as there's no way to "unparse" the namespace while
        # ignoring some arguments.
        argdict = vars(self._args)
        argdict['session'] = None
        argdict['url'] = []
        argdict['command'] = page_args[:-1]
        argdict['json_args'] = None
        # Ensure the given session (or none at all) gets opened.
        if session is None:
            argdict['session'] = None
            argdict['override_restore'] = True
        else:
            argdict['session'] = session
            argdict['override_restore'] = False
        # Ensure :restart works with --temp-basedir
        if self._args.temp_basedir:
            argdict['temp_basedir'] = False
            argdict['temp_basedir_restarted'] = True

        if override_args is not None:
            argdict.update(override_args)

        # Dump the data
        data = json.dumps(argdict)
        args += ['--json-args', data]

        log.destroy.debug("args: {}".format(args))

        return args

    def restart(self, pages: typing.Sequence[str] = (),
                session: str = None,
                override_args: typing.Mapping[str, str] = None) -> bool:
        """Inner logic to restart qutebrowser.

        The "better" way to restart is to pass a session (_restart usually) as
        that'll save the complete state.

        However we don't do that (and pass a list of pages instead) when we
        restart because of an exception, as that's a lot simpler and we don't
        want to risk anything going wrong.

        Args:
            pages: A list of URLs to open.
            session: The session to load, or None.
            override_args: Argument overrides as a dict.

        Return:
            True if the restart succeeded, False otherwise.
        """
        self._compile_modules()
        log.destroy.debug("sys.executable: {}".format(sys.executable))
        log.destroy.debug("sys.path: {}".format(sys.path))
        log.destroy.debug("sys.argv: {}".format(sys.argv))
        log.destroy.debug("frozen: {}".format(hasattr(sys, 'frozen')))

        # Save the session if one is given.
        if session is not None:
            sessions.session_manager.save(session, with_private=True)

        # Make sure we're not accepting a connection from the new process
        # before we fully exited.
        assert ipc.server is not None
        ipc.server.shutdown()

        # Open a new process and immediately shutdown the existing one
        try:
            args = self._get_restart_args(pages, session, override_args)
            subprocess.Popen(args)
        except OSError:
            log.destroy.exception("Failed to restart")
            return False
        else:
            return True

    def shutdown(self, status: int = 0,
                 session: sessions.ArgType = None,
                 last_window: bool = False,
                 is_restart: bool = False) -> None:
        """Quit qutebrowser.

        Args:
            status: The status code to exit with.
            session: A session name if saving should be forced.
            last_window: If the shutdown was triggered due to the last window
                            closing.
            is_restart: If we're planning to restart.
        """
        if self._is_shutting_down:
            return
        self._is_shutting_down = True
        log.destroy.debug("Shutting down with status {}, session {}...".format(
            status, session))
        if sessions.session_manager is not None:
            if session is not None:
                sessions.session_manager.save(session,
                                              last_window=last_window,
                                              load_next_time=True)
            elif config.val.auto_save.session:
                sessions.session_manager.save(sessions.default,
                                              last_window=last_window,
                                              load_next_time=True)

        if prompt.prompt_queue.shutdown():
            # If shutdown was called while we were asking a question, we're in
            # a still sub-eventloop (which gets quit now) and not in the main
            # one.
            # This means we need to defer the real shutdown to when we're back
            # in the real main event loop, or we'll get a segfault.
            log.destroy.debug("Deferring real shutdown because question was "
                              "active.")
            QTimer.singleShot(0, functools.partial(self._shutdown_2, status,
                                                   is_restart=is_restart))
        else:
            # If we have no questions to shut down, we are already in the real
            # event loop, so we can shut down immediately.
            self._shutdown_2(status, is_restart=is_restart)

    def _shutdown_2(self, status: int, is_restart: bool) -> None:
        """Second stage of shutdown."""
        log.destroy.debug("Stage 2 of shutting down...")

        # Tell everything to shut itself down
        self.shutting_down.emit()

        # Delete temp basedir
        if ((self._args.temp_basedir or self._args.temp_basedir_restarted) and
                not is_restart):
            atexit.register(shutil.rmtree, self._args.basedir,
                            ignore_errors=True)

        # Now we can hopefully quit without segfaults
        log.destroy.debug("Deferring QApplication::exit...")
        # We use a singleshot timer to exit here to minimize the likelihood of
        # segfaults.
        QTimer.singleShot(0, functools.partial(self._shutdown_3, status))

    def _shutdown_3(self, status: int) -> None:
        """Finally shut down the QApplication."""
        log.destroy.debug("Now calling QApplication::exit.")
        if 'debug-exit' in objects.debug_flags:
            if hunter is None:
                print("Not logging late shutdown because hunter could not be "
                      "imported!", file=sys.stderr)
            else:
                print("Now logging late shutdown.", file=sys.stderr)
                hunter.trace()
        QApplication.instance().exit(status)


@cmdutils.register(name='quit')
@cmdutils.argument('session', completion=miscmodels.session)
def quit_(save: bool = False,
          session: sessions.ArgType = None) -> None:
    """Quit qutebrowser.

    Args:
        save: When given, save the open windows even if auto_save.session
                is turned off.
        session: The name of the session to save.
    """
    if session is not None and not save:
        raise cmdutils.CommandError("Session name given without --save!")
    if save:
        if session is None:
            session = sessions.default
        instance.shutdown(session=session)
    else:
        instance.shutdown()


@cmdutils.register()
def restart() -> None:
    """Restart qutebrowser while keeping existing tabs open."""
    try:
        ok = instance.restart(session='_restart')
    except sessions.SessionError as e:
        log.destroy.exception("Failed to save session!")
        raise cmdutils.CommandError("Failed to save session: {}!"
                                    .format(e))
    except SyntaxError as e:
        log.destroy.exception("Got SyntaxError")
        raise cmdutils.CommandError("SyntaxError in {}:{}: {}".format(
            e.filename, e.lineno, e))
    if ok:
        instance.shutdown(is_restart=True)


def init(args: argparse.Namespace) -> None:
    """Initialize the global Quitter instance."""
    global instance
    qapp = QApplication.instance()
    instance = Quitter(args=args, parent=qapp)
    instance.shutting_down.connect(log.shutdown_log)
    qapp.lastWindowClosed.connect(instance.on_last_window_closed)
