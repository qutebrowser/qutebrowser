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
import html
import getpass
import traceback
import functools

from PyQt5.QtCore import pyqtSlot, Qt, QSize
from PyQt5.QtWidgets import (QDialog, QLabel, QTextEdit, QPushButton,
                             QVBoxLayout, QHBoxLayout, QCheckBox)

from qutebrowser.utils import version, log, utils, objreg
from qutebrowser.misc import miscwidgets
from qutebrowser.browser.network import pastebin


class _CrashDialog(QDialog):

    """Dialog which gets shown after there was a crash.

    Class attributes:
        NAME: The kind of condition we report.

    Attributes:
        These are just here to have a static reference to avoid GCing.
        _vbox: The main QVBoxLayout
        _lbl: The QLabel with the static text
        _debug_log: The QTextEdit with the crash information
        _hbox: The QHboxLayout containing the buttons
        _url: Pastebin URL QLabel.
        _crash_info: A list of tuples with title and crash information.
        _paste_client: A PastebinClient instance to use.
        _paste_text: The text to pastebin.
        _resolution: Whether the dialog should be accepted on close.
    """

    NAME = None

    def __init__(self, debug, parent=None):
        """Constructor for CrashDialog.

        Args:
            debug: Whether --debug was given.
        """
        super().__init__(parent)
        # We don't set WA_DeleteOnClose here as on an exception, we'll get
        # closed anyways, and it only could have unintended side-effects.
        self._buttons = []
        self._crash_info = []
        self._hbox = None
        self._lbl = None
        self._chk_report = None
        self._resolution = None
        self._paste_text = None
        self.setWindowTitle("Whoops!")
        self.resize(QSize(640, 600))
        self._vbox = QVBoxLayout(self)
        self._paste_client = pastebin.PastebinClient(self)
        self._init_text()

        info = QLabel("What were you doing when this crash/bug happened?")
        self._vbox.addWidget(info)
        self._info = QTextEdit(tabChangesFocus=True, acceptRichText=False)
        self._info.setPlaceholderText("- Opened http://www.example.com/\n"
                                      "- Switched tabs\n"
                                      "- etc...")
        self._vbox.addWidget(self._info, 5)
        contact = QLabel("How can I contact you if I need more info?")
        self._vbox.addWidget(contact)
        self._contact = QTextEdit(tabChangesFocus=True, acceptRichText=False)
        self._contact.setPlaceholderText("Github username, mail or IRC")
        self._vbox.addWidget(self._contact, 2)

        self._vbox.addSpacing(15)
        self._debug_log = QTextEdit(tabChangesFocus=True, acceptRichText=False,
                                    lineWrapMode=QTextEdit.NoWrap)
        self._debug_log.hide()
        info = QLabel("<i>You can edit the log below to remove sensitive "
                      "information.</i>", wordWrap=True)
        info.hide()
        self._fold = miscwidgets.DetailFold("Show log", self)
        self._fold.toggled.connect(self._debug_log.setVisible)
        self._fold.toggled.connect(info.setVisible)
        if debug:
            self._fold.toggle()
        self._vbox.addWidget(self._fold)
        self._vbox.addWidget(info)
        self._vbox.addWidget(self._debug_log, 10)
        self._vbox.addSpacing(15)

        self._init_checkboxes(debug)
        self._init_buttons()

    def __repr__(self):
        return utils.get_repr(self)

    def _init_text(self):
        """Initialize the main text to be displayed on an exception.

        Should be extended by superclass to set the actual text."""
        self._lbl = QLabel(wordWrap=True, openExternalLinks=True,
                           textInteractionFlags=Qt.LinksAccessibleByMouse)
        self._vbox.addWidget(self._lbl)

    def _init_checkboxes(self, debug):
        """Initialize the checkboxes.

        Args:
            debug: Whether a --debug arg was given.
        """
        self._chk_report = QCheckBox("Send a report")
        if not debug:
            self._chk_report.setChecked(True)
        self._vbox.addWidget(self._chk_report)
        info_label = QLabel("<i>Note that without your help, I can't fix the "
                            "bug you encountered.</i>", wordWrap=True)
        self._vbox.addWidget(info_label)

    def _init_buttons(self):
        """Initialize the buttons.

        Should be extended by subclasses to provide the actual buttons.
        """
        self._hbox = QHBoxLayout()
        self._vbox.addLayout(self._hbox)
        self._hbox.addStretch()

    def _gather_crash_info(self):
        """Gather crash information to display.

        Args:
            pages: A list of lists of the open pages (URLs as strings)
            cmdhist: A list with the command history (as strings)
            exc: An exception tuple (type, value, traceback)
        """
        try:
            self._crash_info.append(("Version info", version.version()))
        except Exception:
            self._crash_info.append(("Version info", traceback.format_exc()))
        try:
            conf = objreg.get('config')
            self._crash_info.append(("Config", conf.dump_userconfig()))
        except Exception:
            self._crash_info.append(("Config", traceback.format_exc()))

    def _set_crash_info(self):
        """Set/update the crash info."""
        self._crash_info = []
        self._gather_crash_info()
        chunks = []
        for (header, body) in self._crash_info:
            if body is not None:
                h = '==== {} ===='.format(header)
                chunks.append('\n'.join([h, body]))
        text = '\n\n'.join(chunks)
        self._debug_log.setText(text)

    def report(self):
        """Paste the crash info into the pastebin."""
        lines = []
        lines.append("========== Report ==========")
        lines.append(self._info.toPlainText())
        lines.append("========== Contact ==========")
        lines.append(self._contact.toPlainText())
        lines.append("========== Debug log ==========")
        lines.append(self._debug_log.toPlainText())
        self._paste_text = '\n\n'.join(lines)
        try:
            user = getpass.getuser()
        except Exception as e:
            log.misc.exception("Error while getting user")
            user = 'unknown'
        try:
            # parent: http://p.cmpl.cc/90286958
            self._paste_client.paste(user, "qutebrowser {}".format(self.NAME),
                                     self._paste_text, parent='90286958')
        except Exception as e:
            log.misc.exception("Error while paste-binning")
            exc_text = '{}: {}'.format(e.__class__.__name__, e)
            self.show_error(exc_text)

    @pyqtSlot()
    def on_button_clicked(self, button, accept):
        """Report and close dialog if button was clicked."""
        button.setText("Reporting...")
        for btn in self._buttons:
            btn.setEnabled(False)
        self._resolution = accept
        self._paste_client.success.connect(self.finish)
        self._paste_client.error.connect(self.show_error)
        reported = self.maybe_report()
        if not reported:
            self.finish()

    @pyqtSlot(str)
    def show_error(self, text):
        """Show a paste error dialog.

        Args:
            text: The paste text to show.
        """
        error_dlg = ReportErrorDialog(text, self._paste_text, self)
        error_dlg.finished.connect(self.finish)
        error_dlg.show()

    @pyqtSlot()
    def finish(self):
        """Accept/reject the dialog when reporting is done."""
        if self._resolution:
            self.accept()
        else:
            self.reject()

    @pyqtSlot()
    def maybe_report(self):
        """Report the bug if the user allowed us to.

        Return:
            True if a report was done, False otherwise.
        """
        if self._chk_report.isChecked():
            self.report()
            return True
        else:
            return False


class ExceptionCrashDialog(_CrashDialog):

    """Dialog which gets shown on an exception.

    Attributes:
        _buttons: A list of buttons.
        _pages: A list of lists of the open pages (URLs as strings)
        _cmdhist: A list with the command history (as strings)
        _exc: An exception tuple (type, value, traceback)
        _objects: A list of all QObjects as string.
    """

    NAME = 'exception'

    def __init__(self, debug, pages, cmdhist, exc, objects, parent=None):
        self._chk_log = None
        super().__init__(debug, parent)
        self._pages = pages
        self._cmdhist = cmdhist
        self._exc = exc
        self._objects = objects
        self.setModal(True)
        self._set_crash_info()

    def _init_text(self):
        super()._init_text()
        text = "<b>Argh! qutebrowser crashed unexpectedly.</b>"
        self._lbl.setText(text)

    def _init_buttons(self):
        super()._init_buttons()
        btn_quit = QPushButton("Quit")
        btn_quit.clicked.connect(
            functools.partial(self.on_button_clicked, btn_quit, False))
        self._hbox.addWidget(btn_quit)

        btn_restart = QPushButton("Restart", default=True)
        btn_restart.clicked.connect(
            functools.partial(self.on_button_clicked, btn_restart, True))
        self._hbox.addWidget(btn_restart)

        self._buttons = [btn_quit, btn_restart]

    def _init_checkboxes(self, debug):
        """Add checkboxes to send crash report."""
        super()._init_checkboxes(debug)
        self._chk_log = QCheckBox("Include a debug log and a list of open "
                                  "pages", checked=True)
        if debug:
            self._chk_log.setChecked(False)
            self._chk_log.setEnabled(False)
        self._chk_log.toggled.connect(self._set_crash_info)
        self._vbox.addWidget(self._chk_log)
        info_label = QLabel("<i>This makes it a lot easier to diagnose the "
                            "crash, but it might contain sensitive "
                            "information such as which pages you visited "
                            "or keyboard input.</i>", wordWrap=True)
        self._vbox.addWidget(info_label)
        self._chk_report.toggled.connect(self.on_chk_report_toggled)

    def _gather_crash_info(self):
        self._crash_info += [
            ("Exception", ''.join(traceback.format_exception(*self._exc))),
        ]
        if self._chk_log.isChecked():
            self._crash_info += [
                ("Commandline args", ' '.join(sys.argv[1:])),
                ("Open Pages", '\n\n'.join('\n'.join(e) for e in self._pages)),
                ("Command history", '\n'.join(self._cmdhist)),
                ("Objects", self._objects),
            ]
            try:
                self._crash_info.append(
                    ("Debug log", log.ram_handler.dump_log()))
            except Exception:
                self._crash_info.append(
                    ("Debug log", traceback.format_exc()))
        super()._gather_crash_info()

    @pyqtSlot()
    def on_chk_report_toggled(self):
        """Disable log checkbox if report is disabled."""
        is_checked = self._chk_report.isChecked()
        self._chk_log.setEnabled(is_checked)
        self._chk_log.setChecked(is_checked)


class FatalCrashDialog(_CrashDialog):

    """Dialog which gets shown when a fatal error occured.

    Attributes:
        _log: The log text to display.
    """

    NAME = 'segfault'

    def __init__(self, debug, text, parent=None):
        super().__init__(debug, parent)
        self._log = text
        self.setAttribute(Qt.WA_DeleteOnClose)
        self._set_crash_info()

    def _init_text(self):
        super()._init_text()
        text = ("<b>qutebrowser was restarted after a fatal crash.</b><br/>"
                "<br/>Note: Crash reports for fatal crashes sometimes don't "
                "contain the information necessary to fix an issue. Please "
                "follow the steps in <a href='https://github.com/The-Compiler/"
                "qutebrowser/blob/master/doc/stacktrace.asciidoc'>"
                "stacktrace.asciidoc</a> to submit a stacktrace.<br/>")
        self._lbl.setText(text)

    def _init_buttons(self):
        super()._init_buttons()
        btn_ok = QPushButton(text="OK", default=True)
        btn_ok.clicked.connect(
            functools.partial(self.on_button_clicked, btn_ok, True))
        self._hbox.addWidget(btn_ok)
        self._buttons = [btn_ok]

    def _gather_crash_info(self):
        self._crash_info += [
            ("Fault log", self._log),
        ]
        super()._gather_crash_info()


class ReportDialog(_CrashDialog):

    """Dialog which gets shown when the user wants to report an issue by hand.

    Attributes:
        _pages: A list of the open pages (URLs as strings)
        _cmdhist: A list with the command history (as strings)
        _objects: A list of all QObjects as string.
    """

    NAME = 'report'

    def __init__(self, pages, cmdhist, objects, parent=None):
        super().__init__(False, parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self._btn_report = None
        self._pages = pages
        self._cmdhist = cmdhist
        self._objects = objects
        self._set_crash_info()

    def _init_text(self):
        super()._init_text()
        text = "Please describe the bug you encountered below."
        self._lbl.setText(text)

    def _init_buttons(self):
        super()._init_buttons()
        self._btn_report = QPushButton("Report", default=True)
        self._btn_report.clicked.connect(
            functools.partial(self.on_button_clicked, self._btn_report, True))
        self._hbox.addWidget(self._btn_report)

    def _init_checkboxes(self, _debug):
        """We don't want any checkboxes as the user wanted to report."""
        pass

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

    @pyqtSlot()
    def maybe_report(self):
        """Report the crash.

        We don't have a "Send a report" checkbox here because it was a manual
        report, which would be pretty useless without this info.
        """
        self.report()
        return True


class ReportErrorDialog(QDialog):

    """An error dialog shown on unsuccessful reports."""

    def __init__(self, exc_text, text, parent=None):
        super().__init__(parent)
        vbox = QVBoxLayout(self)
        label = QLabel("<b>There was an error while reporting the crash</b>:"
                       "<br/>{}<br/><br/>"
                       "Please copy the text below and send a mail to "
                       "<a href='mailto:crash@qutebrowser.org'>"
                       "crash@qutebrowser.org</a> - Thanks!".format(
                           html.escape(exc_text)))
        vbox.addWidget(label)
        txt = QTextEdit(readOnly=True, tabChangesFocus=True,
                        acceptRichText=False)
        txt.setText(text)
        txt.selectAll()
        vbox.addWidget(txt)

        hbox = QHBoxLayout()
        hbox.addStretch()
        btn = QPushButton("Close")
        btn.clicked.connect(self.close)
        hbox.addWidget(btn)
        vbox.addLayout(hbox)
