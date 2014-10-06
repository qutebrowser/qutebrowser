# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

# pylint: disable=broad-except

"""The dialog which gets shown when qutebrowser crashes."""

import sys
import traceback
import getpass

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import (QDialog, QLabel, QTextEdit, QPushButton,
                             QVBoxLayout, QHBoxLayout)

from qutebrowser.utils import version, log, utils, objreg


class _CrashDialog(QDialog):

    """Dialog which gets shown after there was a crash.

    Attributes:
        These are just here to have a static reference to avoid GCing.
        _vbox: The main QVBoxLayout
        _lbl: The QLabel with the static text
        _txt: The QTextEdit with the crash information
        _hbox: The QHboxLayout containing the buttons
        _url: Pastebin URL QLabel.
        _crash_info: A list of tuples with title and crash information.

    Class attributes:
        CRASHTEXT: The text to be displayed in the dialog.
    """

    CRASHTEXT = ("Please review and edit the info below, then either submit "
                 "it to <a href='mailto:crash@qutebrowser.org'>"
                 "crash@qutebrowser.org</a> or click 'Report'.<br/><br/>"
                 "<i>Note that without your help, I can't fix the bug you "
                 "encountered. With the report, I most probably will."
                 "</i><br/><br/>")

    def __init__(self, parent=None):
        """Constructor for CrashDialog."""
        super().__init__(parent)
        # We don't set WA_DeleteOnClose here as on an exception, we'll get
        # closed anyways, and it only could have unintended side-effects.
        self._crash_info = None
        self._hbox = None
        self._lbl = None
        self._gather_crash_info()
        self.setWindowTitle("Whoops!")
        self.resize(QSize(800, 600))
        self._vbox = QVBoxLayout(self)
        self._init_text()
        self._txt = QTextEdit()
        self._txt.setText(self._format_crash_info())
        self._vbox.addWidget(self._txt)
        self._url = QLabel()
        self._set_text_flags(self._url)
        self._vbox.addWidget(self._url)
        self._init_buttons()

    def __repr__(self):
        return utils.get_repr(self)

    def _init_text(self):
        """Initialize the main text to be displayed on an exception.

        Should be extended by superclass to set the actual text."""
        self._lbl = QLabel()
        self._lbl.setWordWrap(True)
        self._set_text_flags(self._lbl)
        self._vbox.addWidget(self._lbl)

    def _init_buttons(self):
        """Initialize the buttons.

        Should be extended by superclass to provide the actual buttons.
        """
        self._hbox = QHBoxLayout()
        self._vbox.addLayout(self._hbox)
        self._hbox.addStretch()

    def _set_text_flags(self, obj):
        """Set text interaction flags of a widget to allow link clicking.

        Args:
            obj: A QLabel.
        """
        obj.setTextInteractionFlags(Qt.TextSelectableByMouse |
                                    Qt.TextSelectableByKeyboard |
                                    Qt.LinksAccessibleByMouse |
                                    Qt.LinksAccessibleByKeyboard)

    def _gather_crash_info(self):
        """Gather crash information to display.

        Args:
            pages: A list of lists of the open pages (URLs as strings)
            cmdhist: A list with the command history (as strings)
            exc: An exception tuple (type, value, traceback)
        """
        self._crash_info = [
            ("How did it happen?", ""),
        ]
        try:
            self._crash_info.append(("Contact info",
                                     "User: {}".format(getpass.getuser())))
        except Exception:
            self._crash_info.append(("Contact info", traceback.format_exc()))
        try:
            self._crash_info.append(("Version info", version.version()))
        except Exception:
            self._crash_info.append(("Version info", traceback.format_exc()))
        try:
            conf = objreg.get('config')
            self._crash_info.append(("Config", conf.dump_userconfig()))
        except Exception:
            self._crash_info.append(("Config", traceback.format_exc()))

    def _format_crash_info(self):
        """Format the gathered crash info to be displayed.

        Return:
            The string to display.
        """
        chunks = ["Please edit this report to remove sensitive info, and add "
                  "as much info as possible about how it happened.\n"
                  "If it's okay if I contact you about this bug report, "
                  "please also add your contact info (Mail/IRC/Jabber)."]
        for (header, body) in self._crash_info:
            if body is not None:
                h = '==== {} ===='.format(header)
                chunks.append('\n'.join([h, body]))
        return '\n\n'.join(chunks)

    def pastebin(self):
        """Paste the crash info into the pastebin."""
        try:
            url = utils.pastebin(self._txt.toPlainText())
        except Exception as e:
            log.misc.exception("Error while paste-binning")
            self._url.setText('Error while reporting: {}: {}'.format(
                e.__class__.__name__, e))
            return
        self._btn_pastebin.setEnabled(False)
        self._url.setText("Reported to: <a href='{}'>{}</a>".format(url, url))


class ExceptionCrashDialog(_CrashDialog):

    """Dialog which gets shown on an exception.

    Attributes:
        _btn_quit: The quit button
        _btn_restore: the restore button
        _btn_pastebin: the pastebin button
        _pages: A list of lists of the open pages (URLs as strings)
        _cmdhist: A list with the command history (as strings)
        _exc: An exception tuple (type, value, traceback)
        _objects: A list of all QObjects as string.
    """

    def __init__(self, pages, cmdhist, exc, objects, parent=None):
        self._pages = pages
        self._cmdhist = cmdhist
        self._exc = exc
        self._btn_quit = None
        self._btn_restore = None
        self._btn_pastebin = None
        self._objects = objects
        super().__init__(parent)
        self.setModal(True)

    def _init_text(self):
        super()._init_text()
        text = ("<b>Argh! qutebrowser crashed unexpectedly.</b><br/><br/>" +
                self.CRASHTEXT)
        if self._pages:
            text += ("You can click 'Restore tabs' after reporting to attempt "
                     "to reopen your open tabs.")
        self._lbl.setText(text)

    def _init_buttons(self):
        super()._init_buttons()
        self._btn_quit = QPushButton()
        self._btn_quit.setText("Quit")
        self._btn_quit.clicked.connect(self.reject)
        self._hbox.addWidget(self._btn_quit)
        if self._pages:
            self._btn_restore = QPushButton()
            self._btn_restore.setText("Restore tabs")
            self._btn_restore.clicked.connect(self.accept)
            self._hbox.addWidget(self._btn_restore)
        self._btn_pastebin = QPushButton()
        self._btn_pastebin.setText("Report")
        self._btn_pastebin.clicked.connect(self.pastebin)
        self._btn_pastebin.setDefault(True)
        self._hbox.addWidget(self._btn_pastebin)

    def _gather_crash_info(self):
        super()._gather_crash_info()
        self._crash_info += [
            ("Exception", ''.join(traceback.format_exception(*self._exc))),
            ("Commandline args", ' '.join(sys.argv[1:])),
            ("Open Pages", '\n\n'.join('\n'.join(e) for e in self._pages)),
            ("Command history", '\n'.join(self._cmdhist)),
            ("Objects", self._objects),
        ]
        try:
            self._crash_info.append(("Debug log", log.ram_handler.dump_log()))
        except Exception:
            self._crash_info.append(("Debug log", traceback.format_exc()))


class FatalCrashDialog(_CrashDialog):

    """Dialog which gets shown when a fatal error occured.

    Attributes:
        _log: The log text to display.
        _btn_ok: The OK button.
        _btn_pastebin: The pastebin button.
    """

    def __init__(self, text, parent=None):
        self._log = text
        self._btn_ok = None
        self._btn_pastebin = None
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)

    def _init_text(self):
        super()._init_text()
        text = ("<b>qutebrowser was restarted after a fatal crash.</b><br/>"
                "<br/>" + self.CRASHTEXT)
        self._lbl.setText(text)

    def _init_buttons(self):
        super()._init_buttons()
        self._btn_ok = QPushButton()
        self._btn_ok.setText("OK")
        self._btn_ok.clicked.connect(self.accept)
        self._hbox.addWidget(self._btn_ok)
        self._btn_pastebin = QPushButton()
        self._btn_pastebin.setText("Report")
        self._btn_pastebin.clicked.connect(self.pastebin)
        self._btn_pastebin.setDefault(True)
        self._hbox.addWidget(self._btn_pastebin)

    def _gather_crash_info(self):
        super()._gather_crash_info()
        self._crash_info += [
            ("Fault log", self._log),
        ]


class ReportDialog(_CrashDialog):

    """Dialog which gets shown when the user wants to report an issue by hand.

    Attributes:
        _btn_ok: The OK button.
        _btn_pastebin: The pastebin button.
        _pages: A list of the open pages (URLs as strings)
        _cmdhist: A list with the command history (as strings)
        _objects: A list of all QObjects as string.
    """

    def __init__(self, pages, cmdhist, objects, parent=None):
        self._pages = pages
        self._cmdhist = cmdhist
        self._btn_ok = None
        self._btn_pastebin = None
        self._objects = objects
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)

    def _init_text(self):
        super()._init_text()
        text = ("Please describe the bug you encountered below, then either "
                "submit it to <a href='mailto:crash@qutebrowser.org'>"
                "crash@qutebrowser.org</a> or click 'Report'.")
        self._lbl.setText(text)

    def _init_buttons(self):
        super()._init_buttons()
        self._btn_ok = QPushButton()
        self._btn_ok.setText("OK")
        self._btn_ok.clicked.connect(self.accept)
        self._hbox.addWidget(self._btn_ok)
        self._btn_pastebin = QPushButton()
        self._btn_pastebin.setText("Report")
        self._btn_pastebin.clicked.connect(self.pastebin)
        self._btn_pastebin.setDefault(True)
        self._hbox.addWidget(self._btn_pastebin)

    def _gather_crash_info(self):
        super()._gather_crash_info()
        self._crash_info += [
            ("Commandline args", ' '.join(sys.argv[1:])),
            ("Open Pages", '\n\n'.join('\n'.join(e) for e in self._pages)),
            ("Command history", '\n'.join(self._cmdhist)),
            ("Objects", self._objects),
        ]
        try:
            self._crash_info.append(("Debug log", log.ram_handler.dump_log()))
        except Exception:
            self._crash_info.append(("Debug log", traceback.format_exc()))
