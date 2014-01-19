from PyQt5.QtCore import pyqtSignal
from qutebrowser.commands.utils import Command

class Open(Command):
    nargs = 1
    key = 'o'
    split_args = False

class TabOpen(Command):
    nargs = 1
    key = 'O'
    split_args = False

class TabClose(Command):
    nargs = 0
    key = 'd'

class TabNext(Command):
    nargs = 0
    key = 'J'

class TabPrev(Command):
    nargs = 0
    key = 'K'

class Quit(Command):
    nargs = 0

class Reload(Command):
    nargs = 0
    key = 'r'

class Stop(Command):
    nargs = 0

class Back(Command):
    nargs = 0
    key = 'H'

class Forward(Command):
    nargs = 0
    key = 'L'

class Print(Command):
    nargs = 0

class ScrollLeft(Command):
    nargs = 0
    key = 'h'
    count = True

class ScrollDown(Command):
    nargs = 0
    key = 'j'
    count = True

class ScrollUp(Command):
    nargs = 0
    key = 'k'
    count = True

class ScrollRight(Command):
    nargs = 0
    key = 'l'
    count = True

class Undo(Command):
    nargs = 0
    key = 'u'

class ScrollStart(Command):
    nargs = 0
    key = 'gg'

class ScrollEnd(Command):
    nargs = 0
    key = 'G'

class PyEval(Command):
    nargs = 1
    split_args = False
