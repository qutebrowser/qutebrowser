"""Various command utils and the Command base class"""

import inspect
import shlex

from PyQt5.QtCore import QObject, pyqtSignal

import qutebrowser.commands
from qutebrowser.commands.exceptions import (ArgumentCountError,
                                             NoSuchCommandError)
from qutebrowser.utils.completion import CompletionModel

cmd_dict = {}


def register_all():
    """Register and initialize all commands."""
    for (name, cls) in inspect.getmembers(  # pylint: disable=unused-variable
            qutebrowser.commands, (lambda o: inspect.isclass(o) and
                                   o.__module__ == 'qutebrowser.commands')):
        obj = cls()
        if isinstance(obj.name, str):
            names = [obj.name]
        else:
            names = obj.name
        for n in names:
            cmd_dict[n] = obj


class CommandParser(QObject):
    """Parser for qutebrowser commandline commands"""
    text = ''
    cmd = ''
    args = []
    error = pyqtSignal(str)  # Emitted if there's an error

    def _parse(self, text):
        self.text = text
        parts = self.text.strip().split(maxsplit=1)
        cmdstr = parts[0]
        try:
            cmd = cmd_dict[cmdstr]
        except KeyError:
            raise NoSuchCommandError(cmdstr)

        if len(parts) == 1:
            args = []
        elif cmd.split_args:
            args = shlex.split(parts[1])
        else:
            args = [parts[1]]
        self.cmd = cmd
        self.args = args

    def _check(self):
        self.cmd.check(self.args)

    def _run(self, count=None):
        if count is not None:
            self.cmd.run(self.args, count=count)
        else:
            self.cmd.run(self.args)

    def run(self, text, count=None, ignore_exc=True):
        """Parses a command from a line of text.
        If ignore_exc is True, ignores exceptions and returns True/False
        instead.
        Raises NoSuchCommandError if a command wasn't found, and
        ArgumentCountError if a command was called with the wrong count of
        arguments.
        """
        try:
            self._parse(text)
            self._check()
        except ArgumentCountError:
            if ignore_exc:
                self.error.emit("{}: invalid argument count".format(
                    self.cmd.mainname))
                return False
            else:
                raise
        except NoSuchCommandError as e:
            if ignore_exc:
                self.error.emit("{}: no such command".format(e))
                return False
            else:
                raise
        self._run(count=count)


class CommandCompletionModel(CompletionModel):
    # pylint: disable=abstract-method
    def __init__(self, parent=None):
        super().__init__(parent)
        assert cmd_dict
        cmdlist = []
        for obj in set(cmd_dict.values()):
            if not obj.hide:
                doc = obj.__doc__.splitlines()[0].strip().rstrip('.')
                cmdlist.append([obj.mainname, doc])
        self._data['Commands'] = sorted(cmdlist)
        self.init_data()
