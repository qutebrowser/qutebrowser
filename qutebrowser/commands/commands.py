from PyQt5.QtCore import pyqtSignal
from qutebrowser.commands.utils import Command

class Empty(Command):
    nargs = 0
    name = ''
    key = ':'

class Open(Command):
    nargs = 1
    name = 'open'
    key = 'o'
    signal = pyqtSignal(str)

class TabOpen(Command):
    nargs = 1
    name = 'tabopen'
    key = 'Shift+o'
    signal = pyqtSignal(str)

class TabClose(Command):
    nargs = 0
    name = 'tabclose'
    key = 'd'
    signal = pyqtSignal()

class TabNext(Command):
    nargs = 0
    name = 'tabnext'
    key = 'Shift+j'
    signal = pyqtSignal()

class TabPrev(Command):
    nargs = 0
    name = 'tabprev'
    key = 'Shift+k'
    signal = pyqtSignal()

class Quit(Command):
    nargs = 0
    name = 'quit'
    signal = pyqtSignal()
