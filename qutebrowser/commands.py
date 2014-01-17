from PyQt5.QtCore import QObject, pyqtSignal
import inspect, sys

cmd_dict = {}

def register_all():
    def is_cmd(obj):
        return (inspect.isclass(obj) and obj.__module__ == __name__ and
                obj.__name__.endswith('Cmd'))

    for (name, cls) in inspect.getmembers(sys.modules[__name__], is_cmd):
        cls.bind()

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

    @classmethod
    def bind(cls):
        if cls.name is not None:
            cmd_dict[cls.name] = cls()

    def check(self, argv):
        if ((isinstance(self.nargs, int) and len(argv) != self.nargs) or
                      (self.nargs == '?' and len(argv) > 1) or
                      (self.nargs == '+' and len(argv) < 1)):
            raise TypeError("Invalid argument count!")

    def run(self, argv):
        if not self.signal:
            raise NotImplementedError
        self.signal.emit()

class EmptyCmd(Command):
    nargs = 0
    name = ''
    key = ':'

class OpenCmd(Command):
    nargs = 1
    name = 'open'
    key = 'o'
    signal = pyqtSignal(str)

    def run(self, argv):
        self.signal.emit(argv[0])

class TabOpenCmd(Command):
    nargs = 1
    name = 'tabopen'
    key = 'Shift+o'
    signal = pyqtSignal(str)

    def run(self, argv):
        self.signal.emit(argv[0])

class QuitCmd(Command):
    nargs = 0
    name = 'quit'
    signal = pyqtSignal()

register_all()
