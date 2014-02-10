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

from PyQt5.QtWidgets import (QDialog, QLabel, QTextEdit, QVBoxLayout,
                             QHBoxLayout, QPushButton)

import qutebrowser.utils.config as config
from qutebrowser.utils.version import version


class CrashDialog(QDialog):

    """Dialog which gets shown after there was a crash."""

    def __init__(self, pages, cmdhist, exc):
        super().__init__()
        self.setFixedSize(500, 350)
        self.setWindowTitle('Whoops!')
        self.setModal(True)

        vbox = QVBoxLayout()
        lbl = QLabel(self)
        text = ('Argh! qutebrowser crashed unexpectedly.<br/>'
                'Please review the info below to remove sensitive data and '
                'then submit it to <a href="mailto:crash@qutebrowser.org">'
                'crash@qutebrowser.org</a>.<br/><br/>')
        if pages:
            text += ('You can click "Restore tabs" to attempt to reopen your '
                     'open tabs.')
        lbl.setText(text)
        lbl.setWordWrap(True)
        vbox.addWidget(lbl)

        txt = QTextEdit(self)
        txt.setReadOnly(True)
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

        txt.setText('\n\n'.join(chunks))
        vbox.addWidget(txt)
        self.setLayout(vbox)

        hbox = QHBoxLayout()
        btn_quit = QPushButton(self)
        btn_quit.setText('Quit')
        btn_quit.clicked.connect(self.reject)
        hbox.addWidget(btn_quit)
        if pages:
            btn_restore = QPushButton(self)
            btn_restore.setText('Restore tabs')
            btn_restore.clicked.connect(self.accept)
            btn_restore.setDefault(True)
            hbox.addWidget(btn_restore)

        vbox.addLayout(hbox)
        self.show()
