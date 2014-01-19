import inspect
import sys
import logging
from PyQt5.QtCore import QObject, pyqtSignal

cmd_dict = {}

def register_all():
    import qutebrowser.commands.commands
    def is_cmd(obj):
        return (inspect.isclass(obj) and
                obj.__module__ == 'qutebrowser.commands.commands')

    for (name, cls) in inspect.getmembers(qutebrowser.commands.commands,
                                          is_cmd):
        if cls.bind:
            obj = cls()
            cmd_dict[obj.name] = obj

class CommandParser(QObject):
    error = pyqtSignal(str)

    def parse(self, text):
        parts = text.strip().split(maxsplit=1)

        cmd = parts[0]
        try:
            obj = cmd_dict[cmd]
        except KeyError:
            self.error.emit("{}: no such command".format(cmd))
            return

        if obj.split_args:
            args = shlex.split(parts[1])
        else:
            args = [parts[1]]

        try:
            obj.check(args)
        except TypeError:
            self.error.emit("{}: invalid argument count".format(cmd))
            return
        obj.run(args)

class Command(QObject):
    nargs = 0
    name = None
    key = None
    signal = None
    count = False
    bind = True
    split_args = True
    signal = pyqtSignal(tuple)

    def __init__(self):
        super().__init__()
        if self.name is None:
            self.name = self.__class__.__name__.lower()

    def check(self, args):
        if ((isinstance(self.nargs, int) and len(args) != self.nargs) or
                      (self.nargs == '?' and len(args) > 1) or
                      (self.nargs == '+' and len(args) < 1)):
            raise TypeError("Invalid argument count!")

    def run(self, args=None, count=None):
        countstr = ' * {}'.format(count) if count is not None else ''
        argstr = ", ".join(args) if args else ''
        logging.debug("Cmd called: {}({}){}".format(self.name, argstr,
                                                    countstr))
        argv = [self.name]
        if args is not None:
            argv += args
        self.signal.emit((count, argv))
