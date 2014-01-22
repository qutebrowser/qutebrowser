"""Various command utils and the Command base class"""

import inspect
import logging
import shlex

from PyQt5.QtCore import QObject, pyqtSignal

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
    for (name, cls) in inspect.getmembers(
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
    error = pyqtSignal(str) # Emitted if there's an error

    def parse(self, text):
        """Parses a command and runs its handler"""
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

    def check(self):
        try:
            self.cmd.check(self.args)
        except ArgumentCountError:
            self.error.emit("{}: invalid argument count".format(self.cmd))
            raise

    def run(self, count=None):
        if count is not None:
            self.cmd.run(self.args, count=count)
        else:
            self.cmd.run(self.args)

    def parse_check_run(self, text, count=None, ignore_exc=True):
        try:
            self.parse(text)
            self.check()
        except (ArgumentCountError, NoSuchCommandError):
            if ignore_exc:
                return
            else:
                raise
        self.run(count=count)

class Command(QObject):
    """Base skeleton for a command. See the module help for
    qutebrowser.commands.commands for details.
    """

    # FIXME:
    # we should probably have some kind of typing / argument casting for args
    # this might be combined with help texts or so as well

    nargs = 0
    name = None
    signal = None
    count = False
    split_args = True
    signal = pyqtSignal(tuple)

    def __init__(self):
        super().__init__()
        if self.name is None:
            self.name = self.__class__.__name__.lower()

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
        if isinstance(self.name, str):
            name = self.name
        else:
            name = self.name[0]
        dbgout = ["command called:", name]
        if args:
            dbgout += args
        if count is not None:
            dbgout.append("(count={})".format(count))
        logging.debug(' '.join(dbgout))

        argv = [name]
        if args is not None:
            argv += args
        self.signal.emit((count, argv))
