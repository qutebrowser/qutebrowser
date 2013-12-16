from PyQt5.QtCore import QObject, pyqtSignal

class CommandParser(QObject):
    openurl = pyqtSignal(str)
    tabopen = pyqtSignal(str)

    def parse(self, cmd):
        c = cmd.split()
        if c[0] == ':open':
            self.openurl.emit(c[1])
        elif c[0] == ':tabopen':
            self.tabopen.emit(c[1])
