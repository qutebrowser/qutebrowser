from PyQt5.QtCore import pyqtSignal
from qutebrowser.commands.utils import Command

class Open(Command):
    nargs = 1
    split_args = False

class TabOpen(Command):
    nargs = 1
    split_args = False

class TabClose(Command):
    nargs = 0

class TabNext(Command):
    nargs = 0

class TabPrev(Command):
    nargs = 0

class Quit(Command):
    nargs = 0

class Reload(Command):
    nargs = 0

class Stop(Command):
    nargs = 0

class Back(Command):
    nargs = 0

class Forward(Command):
    nargs = 0

class Print(Command):
    nargs = 0

class ScrollLeft(Command):
    nargs = 0
    count = True

class ScrollDown(Command):
    nargs = 0
    count = True

class ScrollUp(Command):
    nargs = 0
    count = True

class ScrollRight(Command):
    nargs = 0
    count = True

class Undo(Command):
    nargs = 0

class ScrollStart(Command):
    nargs = 0

class ScrollEnd(Command):
    nargs = 0

class PyEval(Command):
    nargs = 1
    split_args = False
