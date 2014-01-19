from PyQt5.QtCore import pyqtSignal
from qutebrowser.commands.utils import Command

class Open(Command):
    nargs = 1
    key = 'o'
    signal = pyqtSignal(str)

class TabOpen(Command):
    nargs = 1
    key = 'O'
    signal = pyqtSignal(str)

class TabClose(Command):
    nargs = 0
    key = 'd'
    signal = pyqtSignal()

class TabNext(Command):
    nargs = 0
    key = 'J'
    signal = pyqtSignal()

class TabPrev(Command):
    nargs = 0
    key = 'K'
    signal = pyqtSignal()

class Quit(Command):
    nargs = 0
    signal = pyqtSignal()

class Reload(Command):
    nargs = 0
    key = 'r'
    signal = pyqtSignal()

class Stop(Command):
    nargs = 0
    signal = pyqtSignal()

class Back(Command):
    nargs = 0
    key = 'H'
    signal = pyqtSignal()

class Forward(Command):
    nargs = 0
    key = 'L'
    signal = pyqtSignal()

class Print(Command):
    nargs = 0
    signal = pyqtSignal()

# FIXME implement count
class ScrollLeft(Command):
    nargs = 0
    key = 'h'
    signal = pyqtSignal()

# FIXME implement count
class ScrollDown(Command):
    nargs = 0
    key = 'j'
    signal = pyqtSignal()

# FIXME implement count
class ScrollUp(Command):
    nargs = 0
    key = 'k'
    signal = pyqtSignal()

# FIXME implement count
class ScrollRight(Command):
    nargs = 0
    key = 'l'
    signal = pyqtSignal()

class Undo(Command):
    nargs = 0
    key = 'u'
    signal = pyqtSignal()

class ScrollStart(Command):
    nargs = 0
    key = 'gg'
    signal = pyqtSignal()

class ScrollEnd(Command):
    nargs = 0
    key = 'G'
    signal = pyqtSignal()
