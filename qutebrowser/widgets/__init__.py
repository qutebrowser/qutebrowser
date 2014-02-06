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
            ('Version info', utils.version()),
            ('Exception', ''.join(traceback.format_exception(*exc))),
            ('Open Pages', '\n'.join(pages)),
            ('Command history', '\n'.join(cmdhist)),
            ('Commandline args', ' '.join(sys.argv[1:])),
            ('Config', utils.config.config.dump_userconfig()),
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
