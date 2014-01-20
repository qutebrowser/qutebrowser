"""Various command utils and the Command base class"""

import inspect
import logging
import shlex

from PyQt5.QtCore import QObject, pyqtSignal

cmd_dict = {}

class ArgumentCountError(TypeError):
    pass

def register_all():
    """Register and initialize all commands."""
    # We do this here to avoid a circular import, since commands.commands
    # imports Command from this module.
    import qutebrowser.commands.commands
    for (name, cls) in inspect.getmembers(
            qutebrowser.commands.commands, (lambda o: inspect.isclass(o) and
            o.__module__ == 'qutebrowser.commands.commands')):
        obj = cls()
        cmd_dict[obj.name] = obj

class CommandParser(QObject):
    """Parser for qutebrowser commandline commands"""
    error = pyqtSignal(str) # Emitted if there's an error

    def parse(self, text):
        """Parses a command and runs its handler"""
        parts = text.strip().split(maxsplit=1)

        # FIXME maybe we should handle unambigious shorthands for commands
        # here? Or at least we should add :q for :quit.
        cmd = parts[0]
        try:
            obj = cmd_dict[cmd]
        except KeyError:
            self.error.emit("{}: no such command".format(cmd))
            return

        if len(parts) == 1:
            args = []
        elif obj.split_args:
            args = shlex.split(parts[1])
        else:
            args = [parts[1]]

        try:
            obj.check(args)
        except ArgumentCountError:
            self.error.emit("{}: invalid argument count".format(cmd))
            return
        obj.run(args)

class Command(QObject):
    """Base skeleton for a command. See the module help for
    qutebrowser.commands.commands for details.
    """
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
        dbgout = ["command called:", self.name]
        if args:
            dbgout += args
        if count is not None:
            dbgout.append("* {}".format(count))
        logging.debug(' '.join(dbgout))

        argv = [self.name]
        if args is not None:
            argv += args
        self.signal.emit((count, argv))
