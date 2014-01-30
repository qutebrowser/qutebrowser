"""The Qt widgets needed by qutebrowser."""

import sys
import traceback

from PyQt5.QtWidgets import (QDialog, QLabel, QTextEdit, QVBoxLayout,
                             QHBoxLayout, QPushButton)

import qutebrowser.utils as utils


class CrashDialog(QDialog):
    """Dialog which gets shown after there was a crash."""

    def __init__(self, pages, cmdhist, exc):
        super().__init__()
        self.setFixedSize(500, 350)
        self.setWindowTitle('Whoops!')

        vbox = QVBoxLayout()
        lbl = QLabel(self)
        lbl.setText(
            'Argh! qutebrowser crashed unexpectedly.<br/>'
            'Please review the info below to remove sensitive data and then '
            'submit it to '
            '<a href="mailto:qutebrowser@the-compiler.org">'
            'qutebrowser@the-compiler.org</a>.<br/><br/>'
            'You can click "Restore tabs" to attempt to reopen your '
            'open tabs.'
        )
        lbl.setWordWrap(True)
        vbox.addWidget(lbl)

        txt = QTextEdit(self)
        txt.setReadOnly(True)
        txt.setText(
            '==== Version info ====\n{}\n\n'.format(utils.version()) +
            '==== Exception ====\n{}\n'.format(
                ''.join(traceback.format_exception(*exc))) +
            '==== Open pages ====\n{}\n\n'.format('\n'.join(pages)) +
            '==== Command history ====\n{}\n\n'.format('\n'.join(cmdhist)) +
            '==== Commandline args ====\n{}'.format(' '.join(sys.argv[1:]))
        )
        vbox.addWidget(txt)
        self.setLayout(vbox)

        hbox = QHBoxLayout()
        btn_quit = QPushButton(self)
        btn_quit.setText('Quit')
        btn_quit.clicked.connect(self.reject)
        hbox.addWidget(btn_quit)
        btn_restore = QPushButton(self)
        btn_restore.setText('Restore tabs')
        btn_restore.clicked.connect(self.accept)
        btn_restore.setDefault(True)
        hbox.addWidget(btn_restore)

        vbox.addLayout(hbox)
        self.show()
