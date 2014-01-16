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
    def parse(self, test):
        parts = text.lstrip(':').strip().split()
        cmd = parts[0]
        args = parts[1:]
        obj = cmd_dict[cmd]()
        try:
            obj.check(args)
        except TypeError:
            # TODO
            raise
        obj.run(args)

class Command(QObject):
    nargs = 0
    name = ''
    signal = None

    @classmethod
    def bind(cls):
        if cls.name:
            cmd_dict[cls.name] = cls

    def check(self, *args):
        if ((isinstance(self.nargs, int) and len(args) != self.nargs) or
                      (self.nargs == '?' and len(args) > 1) or
                      (self.nargs == '+' and len(args) < 1)):
            raise TypeError("Invalid argument count!")

    def run(self, *args):
        if not self.signal:
            raise NotImplementedError
        self.signal.emit(*args)

class OpenCmd(Command):
    nargs = 1
    name = 'open'
    signal = pyqtSignal(str)

class TabOpenCmd(Command):
    nargs = 1
    name = 'tabopen'
    signal = pyqtSignal(str)

class QuitCmd(Command):
    nargs = 0
    name = 'quit'
    signal = pyqtSignal()

register_all()
