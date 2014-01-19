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
        parts = text.strip().split()
        cmd = parts[0]
        argv = parts[1:]
        try:
            obj = cmd_dict[cmd]
        except KeyError:
            self.error.emit("{}: no such command".format(cmd))
            return
        try:
            obj.check(argv)
        except TypeError:
            self.error.emit("{}: invalid argument count".format(cmd))
            return
        obj.run(argv)

class Command(QObject):
    nargs = 0
    name = None
    key = None
    signal = None
    bind = True

    def __init__(self):
        super().__init__()
        if self.name is None:
            self.name = self.__class__.__name__.lower()

    def check(self, argv):
        if ((isinstance(self.nargs, int) and len(argv) != self.nargs) or
                      (self.nargs == '?' and len(argv) > 1) or
                      (self.nargs == '+' and len(argv) < 1)):
            raise TypeError("Invalid argument count!")

    def run(self, argv=None):
        logging.debug("Cmd called: {}({})".format(self.__class__.__name__,
                      ", ".join(argv) if argv else ''))
        if not self.signal:
            raise NotImplementedError
        # some sane defaults
        if self.nargs == 0:
            self.signal.emit()
        elif self.nargs == 1:
            self.signal.emit(argv[0])
        else:
            raise NotImplementedError
