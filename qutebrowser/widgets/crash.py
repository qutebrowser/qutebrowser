# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

"""The dialog which gets shown when qutebrowser crashes."""

import sys
import traceback

from PyQt5.QtWidgets import (QDialog, QLabel, QTextEdit, QPushButton,
                             QVBoxLayout, QHBoxLayout)

import qutebrowser.utils.config as config
from qutebrowser.utils.version import version


class CrashDialog(QDialog):

    """Dialog which gets shown after there was a crash."""

    vbox = None
    lbl = None
    txt = None
    hbox = None
    btn_quit = None
    btn_restore = None

    def __init__(self, pages, cmdhist, exc):
        super().__init__()
        self.setFixedSize(500, 350)
        self.setWindowTitle('Whoops!')
        self.setModal(True)

        self.vbox = QVBoxLayout(self)
        self.lbl = QLabel()
        text = ('Argh! qutebrowser crashed unexpectedly.<br/>'
                'Please review the info below to remove sensitive data and '
                'then submit it to <a href="mailto:crash@qutebrowser.org">'
                'crash@qutebrowser.org</a>.<br/><br/>')
        if pages:
            text += ('You can click "Restore tabs" to attempt to reopen your '
                     'open tabs.')
        self.lbl.setText(text)
        self.lbl.setWordWrap(True)
        self.vbox.addWidget(self.lbl)

        self.txt = QTextEdit()
        self.txt.setReadOnly(True)
        self.txt.setText(self._crash_info(pages, cmdhist, exc))
        self.vbox.addWidget(self.txt)

        self.hbox = QHBoxLayout()
        self.btn_quit = QPushButton()
        self.btn_quit.setText('Quit')
        self.btn_quit.clicked.connect(self.reject)
        self.hbox.addWidget(self.btn_quit)
        if pages:
            self.btn_restore = QPushButton()
            self.btn_restore.setText('Restore tabs')
            self.btn_restore.clicked.connect(self.accept)
            self.btn_restore.setDefault(True)
            self.hbox.addWidget(self.btn_restore)

        self.vbox.addLayout(self.hbox)

    def _crash_info(self, pages, cmdhist, exc):
        """Gather crash information to display."""
        outputs = [
            ('Version info', version()),
            ('Exception', ''.join(traceback.format_exception(*exc))),
            ('Open Pages', '\n'.join(pages)),
            ('Command history', '\n'.join(cmdhist)),
            ('Commandline args', ' '.join(sys.argv[1:])),
            ('Config', config.config.dump_userconfig()),
        ]
        chunks = []
        for (header, body) in outputs:
            h = '==== {} ===='.format(header)
            chunks.append('\n'.join([h, body]))

        return '\n\n'.join(chunks)
