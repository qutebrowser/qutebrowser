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

import qutebrowser.config.config as config
from qutebrowser.utils.version import version


class CrashDialog(QDialog):

    """Dialog which gets shown after there was a crash.

    Attributes:
        These are just here to have a static reference to avoid GCing.
        _vbox: The main QVBoxLayout
        _lbl: The QLabel with the static text
        _txt: The QTextEdit with the crash information
        _hbox: The QHboxLayout containing the buttons
        _btn_quit: The quit button
        _btn_restore: the restore button

    """

    def __init__(self, pages, cmdhist, exc):
        """Constructor for CrashDialog.

        Args:
            pages: A list of the open pages (URLs as strings)
            cmdhist: A list with the command history (as strings)
            exc: An exception tuple (type, value, traceback)

        """
        super().__init__()
        self.setFixedSize(500, 350)
        self.setWindowTitle('Whoops!')
        self.setModal(True)

        self._vbox = QVBoxLayout(self)
        self._lbl = QLabel()
        text = ('Argh! qutebrowser crashed unexpectedly.<br/>'
                'Please review the info below to remove sensitive data and '
                'then submit it to <a href="mailto:crash@qutebrowser.org">'
                'crash@qutebrowser.org</a>.<br/><br/>')
        if pages:
            text += ('You can click "Restore tabs" to attempt to reopen your '
                     'open tabs.')
        self._lbl.setText(text)
        self._lbl.setWordWrap(True)
        self._vbox.addWidget(self._lbl)

        self._txt = QTextEdit()
        self._txt.setReadOnly(True)
        self._txt.setText(self._crash_info(pages, cmdhist, exc))
        self._vbox.addWidget(self._txt)

        self._hbox = QHBoxLayout()
        self._hbox.addStretch()
        self._btn_quit = QPushButton()
        self._btn_quit.setText('Quit')
        self._btn_quit.clicked.connect(self.reject)
        self._hbox.addWidget(self._btn_quit)
        if pages:
            self._btn_restore = QPushButton()
            self._btn_restore.setText('Restore tabs')
            self._btn_restore.clicked.connect(self.accept)
            self._btn_restore.setDefault(True)
            self._hbox.addWidget(self._btn_restore)

        self._vbox.addLayout(self._hbox)

    def _crash_info(self, pages, cmdhist, exc):
        """Gather crash information to display.

        Args:
            pages: A list of the open pages (URLs as strings)
            cmdhist: A list with the command history (as strings)
            exc: An exception tuple (type, value, traceback)

        Return:
            The string to display.

        """
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
            if body is not None:
                h = '==== {} ===='.format(header)
                chunks.append('\n'.join([h, body]))

        return '\n\n'.join(chunks)
