# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# Copyright 2016-2018 Jan Verbeek (blyxxyz) <ring@openmailbox.org>
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

import typing

from qutebrowser.commands import runners
from qutebrowser.api import cmdutils
from qutebrowser.keyinput import modeman
from qutebrowser.utils import message, objreg, usertypes


_CommandType = typing.Tuple[str, int]  # command, type

macro_recorder = typing.cast('MacroRecorder', None)


class MacroRecorder:

    """An object for recording and running keyboard macros.

    Attributes:
        _macros: A list of commands for each macro register.
        _recording_macro: The register to which a macro is being recorded.
        _macro_count: The count passed to run_macro_command for each window.
                      Stored for use by run_macro, which may be called from
                      keyinput/modeparsers.py after a key input.
        _last_register: The macro which did run last.
    """

    def __init__(self) -> None:
        self._macros = {}  # type: typing.Dict[str, typing.List[_CommandType]]
        self._recording_macro = None  # type: typing.Optional[str]
        self._macro_count = {}  # type: typing.Dict[int, int]
        self._last_register = None  # type: typing.Optional[str]

    @cmdutils.register(instance='macro-recorder', name='record-macro')
    @cmdutils.argument('win_id', value=cmdutils.Value.win_id)
    def record_macro_command(self, win_id: int, register: str = None) -> None:
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

    def record_macro(self, register: str) -> None:
        """Start recording a macro."""
        message.info("Recording macro '{}'...".format(register))
        self._macros[register] = []
        self._recording_macro = register

    @cmdutils.register(instance='macro-recorder', name='run-macro')
    @cmdutils.argument('win_id', value=cmdutils.Value.win_id)
    @cmdutils.argument('count', value=cmdutils.Value.count)
    def run_macro_command(self, win_id: int,
                          count: int = 1,
                          register: str = None) -> None:
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

    def run_macro(self, win_id: int, register: str) -> None:
        """Run a recorded macro."""
        if register == '@':
            if self._last_register is None:
                raise cmdutils.CommandError("No previous macro")
            register = self._last_register
        self._last_register = register

        if register not in self._macros:
            raise cmdutils.CommandError(
                "No macro recorded in '{}'!".format(register))

        commandrunner = runners.CommandRunner(win_id)
        for _ in range(self._macro_count[win_id]):
            for cmd in self._macros[register]:
                commandrunner.run_safely(*cmd)

    def record_command(self, text: str, count: int) -> None:
        """Record a command if a macro is being recorded."""
        if self._recording_macro is not None:
            self._macros[self._recording_macro].append((text, count))


def init() -> None:
    """Initialize the MacroRecorder."""
    global macro_recorder
    macro_recorder = MacroRecorder()
    objreg.register('macro-recorder', macro_recorder, command_only=True)
