# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Jan Verbeek (blyxxyz) <ring@openmailbox.org>
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

"""Keyboard macro system."""

from qutebrowser.commands import cmdexc, cmdutils, runners
from qutebrowser.keyinput import modeman
from qutebrowser.utils import message, objreg, usertypes


class MacroRecorder:

    """An object for recording and running keyboard macros.

    Attributes:
        _macros: A list of commands for each macro register.
        _recording_macro: The register to which a macro is being recorded.
        _macro_count: The count passed to run_macro_command for each window.
                      Stored for use by run_macro, which may be called from
                      keyinput/modeparsers.py after a key input.
    """

    def __init__(self):
        self._macros = {}
        self._recording_macro = None
        self._macro_count = {}

    @cmdutils.register(instance='macro-recorder', name='record-macro')
    @cmdutils.argument('win_id', win_id=True)
    def record_macro_command(self, win_id, register=None):
        """Start or stop recording a macro.

        Args:
            register: Which register to store the macro in.
        """
        if self._recording_macro is None:
            if register is None:
                mode_manager = modeman.instance(win_id)
                mode_manager.enter(usertypes.KeyMode.record_macro,
                                   'record_macro')
            else:
                self.record_macro(register)
        else:
            message.info("Macro '{}' recorded.".format(self._recording_macro))
            self._recording_macro = None

    def record_macro(self, register):
        """Start recording a macro."""
        message.info("Recording macro '{}'...".format(register))
        self._macros[register] = []
        self._recording_macro = register

    @cmdutils.register(instance='macro-recorder', name='run-macro')
    @cmdutils.argument('win_id', win_id=True)
    @cmdutils.argument('count', count=True)
    def run_macro_command(self, win_id, count=1, register=None):
        """Run a recorded macro.

        Args:
            count: How many times to run the macro.
            register: Which macro to run.
        """
        self._macro_count[win_id] = count
        if register is None:
            mode_manager = modeman.instance(win_id)
            mode_manager.enter(usertypes.KeyMode.run_macro, 'run_macro')
        else:
            self.run_macro(win_id, register)

    def run_macro(self, win_id, register):
        """Run a recorded macro."""
        if register not in self._macros:
            raise cmdexc.CommandError(
                "No macro recorded in '{}'!".format(register))
        commandrunner = runners.CommandRunner(win_id)
        for _ in range(self._macro_count[win_id]):
            for cmd in self._macros[register]:
                commandrunner.run_safely(*cmd)

    def record_command(self, text, count):
        """Record a command if a macro is being recorded."""
        if self._recording_macro is not None:
            self._macros[self._recording_macro].append((text, count))


def init():
    """Initialize the MacroRecorder."""
    macro_recorder = MacroRecorder()
    objreg.register('macro-recorder', macro_recorder)
