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

"""The dialog which gets shown when qutebrowser crashes."""

import sys
import traceback
from urllib.error import URLError
from getpass import getuser

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import (QDialog, QLabel, QTextEdit, QPushButton,
                             QVBoxLayout, QHBoxLayout)

import qutebrowser.config.config as config
import qutebrowser.utils.misc as utils
import qutebrowser.utils.log as logutils
from qutebrowser.utils.version import version


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
            pages: A list of the open pages (URLs as strings)
            cmdhist: A list with the command history (as strings)
            exc: An exception tuple (type, value, traceback)
        """
        self._crash_info = [
            ("How did it happen?", ""),
        ]
        try:
            self._crash_info.append(("Contact info",
                                     "User: {}".format(getuser())))
        except Exception as e:
            self._crash_info.append(("Contact info", "User: {}: {}".format(
                                         e.__class__.__name__, e)))
        self._crash_info.append(("Version info", version()))
        try:
            self._crash_info.append(("Config",
                                     config.instance().dump_userconfig()))
        except AttributeError as e:
            self._crash_info.append(("Config", "{}: {}".format(
                e.__class__.__name__, e)))

    def _format_crash_info(self):
        """Format the gathered crash info to be displayed.

        Return:
            The string to display.
        """
        chunks = ["Please edit this crash report to remove sensitive info, "
                  "and add as much info as possible about how it happened.\n"
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
        except (URLError, ValueError) as e:
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
        _pages: A list of the open pages (URLs as strings)
        _cmdhist: A list with the command history (as strings)
        _exc: An exception tuple (type, value, traceback)
        _widgets: A list of active widgets as string.
        _objects: A list of all QObjects as string.
    """

    def __init__(self, pages, cmdhist, exc, widgets, objects, parent=None):
        self._pages = pages
        self._cmdhist = cmdhist
        self._exc = exc
        self._btn_quit = None
        self._btn_restore = None
        self._btn_pastebin = None
        self._widgets = widgets
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
            ("Open Pages", '\n'.join(self._pages)),
            ("Command history", '\n'.join(self._cmdhist)),
            ("Widgets", self._widgets),
            ("Objects", self._objects),
        ]
        try:
            self._crash_info.append(("Debug log",
                                     logutils.ram_handler.dump_log()))
        except AttributeError as e:
            self._crash_info.append(("Debug log", "{}: {}".format(
                e.__class__.__name__, e)))


class FatalCrashDialog(_CrashDialog):

    """Dialog which gets shown when a fatal error occured.

    Attributes:
        _log: The log text to display.
        _btn_ok: The OK button.
        _btn_pastebin: The pastebin button.
    """

    def __init__(self, log, parent=None):
        self._log = log
        self._btn_ok = None
        self._btn_pastebin = None
        super().__init__(parent)

    def _init_text(self):
        super()._init_text()
        text = ("<b>qutebrowser was restarted after a fatal crash.<b><br/>"
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
