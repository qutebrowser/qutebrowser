from PyQt5.QtCore import pyqtSignal
from qutebrowser.commands.utils import Command

class Open(Command):
    nargs = 1
    key = 'o'
    signal = pyqtSignal(str)

class TabOpen(Command):
    nargs = 1
    key = 'Shift+o'
    signal = pyqtSignal(str)

class TabClose(Command):
    nargs = 0
    key = 'd'
    signal = pyqtSignal()

class TabNext(Command):
    nargs = 0
    key = 'Shift+j'
    signal = pyqtSignal()

class TabPrev(Command):
    nargs = 0
    key = 'Shift+k'
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
    key = 'Shift+H'
    signal = pyqtSignal()

class Forward(Command):
    nargs = 0
    key = 'Shift+L'
    signal = pyqtSignal()

class Print(Command):
    nargs = 0
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
