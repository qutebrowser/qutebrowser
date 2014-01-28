"""Various command utils and the Command base class"""

import inspect
import logging
import shlex

from PyQt5.QtCore import QObject, pyqtSignal

from qutebrowser.utils.completion import CompletionModel

cmd_dict = {}


class ArgumentCountError(TypeError):
    pass


class NoSuchCommandError(ValueError):
    pass


def register_all():
    """Register and initialize all commands."""
    # We do this here to avoid a circular import, since commands.commands
    # imports Command from this module.
    import qutebrowser.commands
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
        """Parses a command"""
        self.text = text
        parts = self.text.strip().split(maxsplit=1)
        cmdstr = parts[0]
        try:
            cmd = cmd_dict[cmdstr]
        except KeyError:
            self.error.emit("{}: no such command".format(cmdstr))
            raise NoSuchCommandError

        if len(parts) == 1:
            args = []
        elif cmd.split_args:
            args = shlex.split(parts[1])
        else:
            args = [parts[1]]
        self.cmd = cmd
        self.args = args

    def _check(self):
        try:
            self.cmd.check(self.args)
        except ArgumentCountError:
            self.error.emit("{}: invalid argument count".format(
                self.cmd.mainname))
            raise

    def _run(self, count=None):
        if count is not None:
            self.cmd.run(self.args, count=count)
        else:
            self.cmd.run(self.args)

    def run(self, text, count=None, ignore_exc=True):
        try:
            self._parse(text)
            self._check()
        except (ArgumentCountError, NoSuchCommandError):
            if ignore_exc:
                return
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
                cmdlist.append([obj.mainname, obj.desc])
        self._data['Commands'] = sorted(cmdlist)
        self.init_data()


class Command(QObject):
    """Base skeleton for a command. See the module help for
    qutebrowser.commands.commands for details.
    """

    # FIXME:
    # we should probably have some kind of typing / argument casting for args
    # this might be combined with help texts or so as well

    nargs = 0
    name = None
    mainname = None
    signal = None
    count = False
    split_args = True
    signal = pyqtSignal(tuple)
    hide = False
    desc = ""  # FIXME add descriptions everywhere

    def __init__(self):
        super().__init__()
        if self.name is None:
            self.name = self.__class__.__name__.lower()
        if isinstance(self.name, str):
            self.mainname = self.name
        else:
            self.mainname = self.name[0]

    def check(self, args):
        """Check if the argument count is valid. Raise ArgumentCountError if
        not.
        """
        if ((isinstance(self.nargs, int) and len(args) != self.nargs) or
                (self.nargs == '?' and len(args) > 1) or
                (self.nargs == '+' and len(args) < 1)):
            # for nargs == '*', anything is okay
            raise ArgumentCountError

    def run(self, args=None, count=None):
        """Runs the command.

        args -- Arguments to the command.
        count -- Command repetition count.
        """
        dbgout = ["command called:", self.mainname]
        if args:
            dbgout += args
        if count is not None:
            dbgout.append("(count={})".format(count))
        logging.debug(' '.join(dbgout))

        argv = [self.mainname]
        if args is not None:
            argv += args
        self.signal.emit((count, argv))
