# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2019 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import json
import os
import signal
import sys
import textwrap
import time

import pytest_bdd as bdd

from qutebrowser.utils import utils

bdd.scenarios('editor.feature')



@bdd.when(bdd.parsers.parse('I set up a fake editor replacing "{text}" by '
                            '"{replacement}"'))
def set_up_editor_replacement(quteproc, server, tmpdir, text, replacement):
    """Set up editor.command to a small python script doing a replacement."""
    text = text.replace('(port)', str(server.port))
    script = tmpdir / 'script.py'
    script.write(textwrap.dedent("""
        import sys

        with open(sys.argv[1], encoding='utf-8') as f:
            data = f.read()

        data = data.replace("{text}", "{replacement}")

        with open(sys.argv[1], 'w', encoding='utf-8') as f:
            f.write(data)
    """.format(text=text, replacement=replacement)))
    editor = json.dumps([sys.executable, str(script), '{}'])
    quteproc.set_setting('editor.command', editor)


@bdd.when(bdd.parsers.parse('I set up a fake editor returning "{text}"'))
def set_up_editor(quteproc, tmpdir, text):
    """Set up editor.command to a small python script inserting a text."""
    script = tmpdir / 'script.py'
    script.write(textwrap.dedent("""
        import sys

        with open(sys.argv[1], 'w', encoding='utf-8') as f:
            f.write({text!r})
    """.format(text=text)))
    editor = json.dumps([sys.executable, str(script), '{}'])
    quteproc.set_setting('editor.command', editor)


@bdd.when(bdd.parsers.parse('I set up a fake editor returning empty text'))
def set_up_editor_empty(quteproc, tmpdir):
    """Set up editor.command to a small python script inserting empty text."""
    set_up_editor(quteproc, tmpdir, "")


@bdd.when(bdd.parsers.parse('I set up a fake editor that writes "{text}" on '
                            'save'))
def set_up_editor_wait(quteproc, tmpdir, text):
    """Set up editor.command to a small python script inserting a text."""
    assert not utils.is_windows
    pidfile = tmpdir / 'editor_pid'
    script = tmpdir / 'script.py'
    script.write(textwrap.dedent("""
        import os
        import sys
        import time
        import signal

        def handle(sig, _frame):
            filename = sys.argv[1]
            old_mtime = new_mtime = os.stat(filename).st_mtime
            while old_mtime == new_mtime:
                time.sleep(0.1)
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write({text!r})
                new_mtime = os.stat(filename).st_mtime
            if sig == signal.SIGUSR1:
                sys.exit(0)

        signal.signal(signal.SIGUSR1, handle)
        signal.signal(signal.SIGUSR2, handle)

        with open(r'{pidfile}', 'w') as f:
            f.write(str(os.getpid()))

        time.sleep(100)
    """.format(pidfile=pidfile, text=text)))
    editor = json.dumps([sys.executable, str(script), '{}'])
    quteproc.set_setting('editor.command', editor)


@bdd.when(bdd.parsers.parse('I kill the waiting editor'))
def kill_editor_wait(tmpdir):
    """Kill the waiting editor."""
    pidfile = tmpdir / 'editor_pid'
    pid = int(pidfile.read())
    # windows has no SIGUSR1, but we don't run this on windows anyways
    # for posix, there IS a member so we need to ignore useless-suppression
    # pylint: disable=no-member,useless-suppression
    os.kill(pid, signal.SIGUSR1)


@bdd.when(bdd.parsers.parse('I save without exiting the editor'))
def save_editor_wait(tmpdir):
    """Trigger the waiting editor to write without exiting."""
    pidfile = tmpdir / 'editor_pid'
    # give the "editor" process time to write its pid
    for _ in range(10):
        if pidfile.check():
            break
        time.sleep(1)
    pid = int(pidfile.read())
    # windows has no SIGUSR2, but we don't run this on windows anyways
    # for posix, there IS a member so we need to ignore useless-suppression
    # pylint: disable=no-member,useless-suppression
    os.kill(pid, signal.SIGUSR2)
