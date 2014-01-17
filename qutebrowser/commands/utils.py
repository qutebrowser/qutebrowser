from PyQt5.QtCore import QObject, pyqtSignal
import inspect, sys

cmd_dict = {}

def register_all():
    import qutebrowser.commands.commands
    def is_cmd(obj):
        return (inspect.isclass(obj) and
                obj.__module__ == 'qutebrowser.commands.commands')

    for (name, cls) in inspect.getmembers(qutebrowser.commands.commands,
                                          is_cmd):
        if cls.bind:
            if cls.name is None:
                name = cls.__name__.tolower()
            else:
                name = cls.name
            cmd_dict[name] = cls()

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

    def check(self, argv):
        if ((isinstance(self.nargs, int) and len(argv) != self.nargs) or
                      (self.nargs == '?' and len(argv) > 1) or
                      (self.nargs == '+' and len(argv) < 1)):
            raise TypeError("Invalid argument count!")

    def run(self, argv=None):
        if not self.signal:
            raise NotImplementedError
        # some sane defaults
        if self.nargs == 0:
            self.signal.emit()
        elif self.nargs == 1:
            self.signal.emit(argv[0])
        else:
            raise NotImplementedError
