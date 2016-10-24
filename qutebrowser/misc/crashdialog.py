# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import re
import os
import sys
import html
import getpass
import fnmatch
import traceback
import datetime

import pkg_resources
from PyQt5.QtCore import pyqtSlot, Qt, QSize
from PyQt5.QtWidgets import (QDialog, QLabel, QTextEdit, QPushButton,
                             QVBoxLayout, QHBoxLayout, QCheckBox,
                             QDialogButtonBox, QMessageBox, QApplication)

import qutebrowser
from qutebrowser.utils import version, log, utils, objreg
from qutebrowser.misc import (miscwidgets, autoupdate, msgbox, httpclient,
                              pastebin)
from qutebrowser.config import config


def parse_fatal_stacktrace(text):
    """Get useful information from a fatal faulthandler stacktrace.

    Args:
        text: The text to parse.

    Return:
        A tuple with the first element being the error type, and the second
        element being the first stacktrace frame.
    """
    lines = [
        r'Fatal Python error: (.*)',
        r' *',
        r'(Current )?[Tt]hread [^ ]* \(most recent call first\): *',
        r'  File ".*", line \d+ in (.*)',
    ]
    m = re.match('\n'.join(lines), text)
    if m is None:
        # We got some invalid text.
        return ('', '')
    else:
        return (m.group(1), m.group(3))


def get_fatal_crash_dialog(debug, data):
    """Get a fatal crash dialog based on a crash log.

    If the crash is a segfault in qt_mainloop and we're on an old Qt version
    this is a simple error dialog which lets the user know they should upgrade
    if possible.

    If it's anything else, it's a normal FatalCrashDialog with the possibility
    to report the crash.

    Args:
        debug: Whether the debug flag (--debug) was given.
        data: The crash log data.
    """
    ignored_frames = ['qt_mainloop', 'paintEvent']
    errtype, frame = parse_fatal_stacktrace(data)

    if errtype == 'Segmentation fault' and frame in ignored_frames:
        title = "qutebrowser was restarted after a fatal crash!"
        text = ("<b>qutebrowser was restarted after a fatal crash!</b><br/>"
                "Unfortunately, this crash occurred in Qt (the library "
                "qutebrowser uses), and QtWebKit (the current backend) is not "
                "maintained anymore.<br/><br/>Since I can't do much about "
                "those crashes I disabled the crash reporter for this case, "
                "but this will likely be resolved in the future with the new "
                "QtWebEngine backend.")
        box = QMessageBox(QMessageBox.Critical, title, text, QMessageBox.Ok)
        box.setAttribute(Qt.WA_DeleteOnClose)
        return box
    else:
        return FatalCrashDialog(debug, data)


def _get_environment_vars():
    """Gather environment variables for the crash info."""
    masks = ('DESKTOP_SESSION', 'DE', 'QT_*', 'PYTHON*', 'LC_*', 'LANG',
             'XDG_*', 'QUTE_*', 'PATH')
    info = []
    for key, value in os.environ.items():
        for m in masks:
            if fnmatch.fnmatch(key, m):
                info.append('{} = {}'.format(key, value))
    return '\n'.join(sorted(info))


class _CrashDialog(QDialog):

    """Dialog which gets shown after there was a crash.

    Attributes:
        These are just here to have a static reference to avoid GCing.
        _vbox: The main QVBoxLayout
        _lbl: The QLabel with the static text
        _debug_log: The QTextEdit with the crash information
        _btn_box: The QDialogButtonBox containing the buttons.
        _url: Pastebin URL QLabel.
        _crash_info: A list of tuples with title and crash information.
        _paste_client: A PastebinClient instance to use.
        _pypi_client: A PyPIVersionClient instance to use.
        _paste_text: The text to pastebin.
    """

    def __init__(self, debug, parent=None):
        """Constructor for CrashDialog.

        Args:
            debug: Whether --debug was given.
        """
        super().__init__(parent)
        # We don't set WA_DeleteOnClose here as on an exception, we'll get
        # closed anyways, and it only could have unintended side-effects.
        self._crash_info = []
        self._btn_box = None
        self._btn_report = None
        self._btn_cancel = None
        self._lbl = None
        self._paste_text = None
        self.setWindowTitle("Whoops!")
        self.resize(QSize(640, 600))
        self._vbox = QVBoxLayout(self)
        http_client = httpclient.HTTPClient()
        self._paste_client = pastebin.PastebinClient(http_client, self)
        self._pypi_client = autoupdate.PyPIVersionClient(self)
        self._init_text()

        contact = QLabel("I'd like to be able to follow up with you, to keep "
                         "you posted on the status of this crash and get more "
                         "information if I need it - how can I contact you?",
                         wordWrap=True)
        self._vbox.addWidget(contact)
        self._contact = QTextEdit(tabChangesFocus=True, acceptRichText=False)
        try:
            state = objreg.get('state-config')
            try:
                self._contact.setPlainText(state['general']['contact-info'])
            except KeyError:
                self._contact.setPlaceholderText("Mail or IRC nickname")
        except Exception:
            log.misc.exception("Failed to get contact information!")
            self._contact.setPlaceholderText("Mail or IRC nickname")
        self._vbox.addWidget(self._contact, 2)

        info = QLabel("What were you doing when this crash/bug happened?")
        self._vbox.addWidget(info)
        self._info = QTextEdit(tabChangesFocus=True, acceptRichText=False)
        self._info.setPlaceholderText("- Opened http://www.example.com/\n"
                                      "- Switched tabs\n"
                                      "- etc...")
        self._vbox.addWidget(self._info, 5)

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

        self._init_checkboxes()
        self._init_info_text()
        self._init_buttons()

    def __repr__(self):
        return utils.get_repr(self)

    def _init_text(self):
        """Initialize the main text to be displayed on an exception.

        Should be extended by subclasses to set the actual text.
        """
        self._lbl = QLabel(wordWrap=True, openExternalLinks=True,
                           textInteractionFlags=Qt.LinksAccessibleByMouse)
        self._vbox.addWidget(self._lbl)

    def _init_checkboxes(self):
        """Initialize the checkboxes."""
        pass

    def _init_buttons(self):
        """Initialize the buttons."""
        self._btn_box = QDialogButtonBox()
        self._vbox.addWidget(self._btn_box)

        self._btn_report = QPushButton("Report", default=True)
        self._btn_report.clicked.connect(self.on_report_clicked)
        self._btn_box.addButton(self._btn_report, QDialogButtonBox.AcceptRole)

        self._btn_cancel = QPushButton("Don't report", autoDefault=False)
        self._btn_cancel.clicked.connect(self.finish)
        self._btn_box.addButton(self._btn_cancel, QDialogButtonBox.RejectRole)

    def _init_info_text(self):
        """Add an info text encouraging the user to report crashes."""
        info_label = QLabel("<br/><b>Note that without your help, I can't fix "
                            "the bug you encountered.<br/> Crash reports are "
                            "currently publicly accessible.</b>",
                            wordWrap=True)
        self._vbox.addWidget(info_label)

    def _gather_crash_info(self):
        """Gather crash information to display.

        Args:
            pages: A list of lists of the open pages (URLs as strings)
            cmdhist: A list with the command history (as strings)
            exc: An exception tuple (type, value, traceback)
        """
        try:
            application = QApplication.instance()
            launch_time = application.launch_time.ctime()
            crash_time = datetime.datetime.now().ctime()
            text = 'Launch: {}\nCrash: {}'.format(launch_time, crash_time)
            self._crash_info.append(('Timestamps', text))
        except Exception:
            self._crash_info.append(("Launch time", traceback.format_exc()))
        try:
            self._crash_info.append(("Version info", version.version()))
        except Exception:
            self._crash_info.append(("Version info", traceback.format_exc()))
        try:
            conf = objreg.get('config')
            self._crash_info.append(("Config", conf.dump_userconfig()))
        except Exception:
            self._crash_info.append(("Config", traceback.format_exc()))
        try:
            self._crash_info.append(("Environment", _get_environment_vars()))
        except Exception:
            self._crash_info.append(("Environment", traceback.format_exc()))

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

    def _get_error_type(self):
        """Get the type of the error we're reporting."""
        raise NotImplementedError

    def _get_paste_title_desc(self):
        """Get a short description of the paste."""
        return ''

    def _get_paste_title(self):
        """Get a title for the paste."""
        desc = self._get_paste_title_desc()
        title = "qute {} {}".format(qutebrowser.__version__,
                                    self._get_error_type())
        if desc:
            title += ' {}'.format(desc)
        return title

    def _save_contact_info(self):
        """Save the contact info to disk."""
        try:
            state = objreg.get('state-config')
            state['general']['contact-info'] = self._contact.toPlainText()
        except Exception:
            log.misc.exception("Failed to save contact information!")

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
            self._paste_client.paste(user, self._get_paste_title(),
                                     self._paste_text, parent='90286958')
        except Exception as e:
            log.misc.exception("Error while paste-binning")
            exc_text = '{}: {}'.format(e.__class__.__name__, e)
            self.show_error(exc_text)

    @pyqtSlot()
    def on_report_clicked(self):
        """Report and close dialog if report button was clicked."""
        self._btn_report.setEnabled(False)
        self._btn_cancel.setEnabled(False)
        self._btn_report.setText("Reporting...")
        self._paste_client.success.connect(self.on_paste_success)
        self._paste_client.error.connect(self.show_error)
        self.report()

    @pyqtSlot()
    def on_paste_success(self):
        """Get the newest version from PyPI when the paste is done."""
        self._pypi_client.success.connect(self.on_version_success)
        self._pypi_client.error.connect(self.on_version_error)
        self._pypi_client.get_version()

    @pyqtSlot(str)
    def show_error(self, text):
        """Show a paste error dialog.

        Args:
            text: The paste text to show.
        """
        error_dlg = ReportErrorDialog(text, self._paste_text, self)
        error_dlg.finished.connect(self.finish)
        error_dlg.show()

    @pyqtSlot(str)
    def on_version_success(self, newest):
        """Called when the version was obtained from self._pypi_client.

        Args:
            newest: The newest version as a string.
        """
        new_version = pkg_resources.parse_version(newest)
        cur_version = pkg_resources.parse_version(qutebrowser.__version__)
        lines = ['The report has been sent successfully. Thanks!']
        if new_version > cur_version:
            lines.append("<b>Note:</b> The newest available version is v{}, "
                         "but you're currently running v{} - please "
                         "update!".format(newest, qutebrowser.__version__))
        text = '<br/><br/>'.join(lines)
        self.finish()
        msgbox.information(self, "Report successfully sent!", text,
                           on_finished=self.finish, plain_text=False)

    @pyqtSlot(str)
    def on_version_error(self, msg):
        """Called when the version was not obtained from self._pypi_client.

        Args:
            msg: The error message to show.
        """
        lines = ['The report has been sent successfully. Thanks!']
        lines.append("There was an error while getting the newest version: "
                     "{}. Please check for a new version on "
                     "<a href=https://www.qutebrowser.org/>qutebrowser.org</a> "
                     "by yourself.".format(msg))
        text = '<br/><br/>'.join(lines)
        self.finish()
        msgbox.information(self, "Report successfully sent!", text,
                           on_finished=self.finish, plain_text=False)

    @pyqtSlot()
    def finish(self):
        """Save contact info and close the dialog."""
        self._save_contact_info()
        self.accept()


class ExceptionCrashDialog(_CrashDialog):

    """Dialog which gets shown on an exception.

    Attributes:
        _pages: A list of lists of the open pages (URLs as strings)
        _cmdhist: A list with the command history (as strings)
        _exc: An exception tuple (type, value, traceback)
        _objects: A list of all QObjects as string.
    """

    def __init__(self, debug, pages, cmdhist, exc, objects, parent=None):
        self._chk_log = None
        self._chk_restore = None
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

    def _init_checkboxes(self):
        """Add checkboxes to the dialog."""
        super()._init_checkboxes()
        self._chk_restore = QCheckBox("Restore open pages")
        self._chk_restore.setChecked(True)
        self._vbox.addWidget(self._chk_restore)
        self._chk_log = QCheckBox("Include a debug log in the report",
                                  checked=True)
        try:
            if config.get('general', 'private-browsing'):
                self._chk_log.setChecked(False)
        except Exception:
            log.misc.exception("Error while checking private browsing mode")
        self._chk_log.toggled.connect(self._set_crash_info)
        self._vbox.addWidget(self._chk_log)
        info_label = QLabel("<i>This makes it a lot easier to diagnose the "
                            "crash, but it might contain sensitive "
                            "information such as which pages you visited "
                            "or keyboard input.</i>", wordWrap=True)
        self._vbox.addWidget(info_label)

    def _get_error_type(self):
        return 'exc'

    def _get_paste_title_desc(self):
        desc = traceback.format_exception_only(self._exc[0], self._exc[1])
        return desc[0].rstrip()

    def _gather_crash_info(self):
        self._crash_info += [
            ("Exception", ''.join(traceback.format_exception(*self._exc))),
        ]
        super()._gather_crash_info()
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
                self._crash_info.append(("Debug log", traceback.format_exc()))

    @pyqtSlot()
    def finish(self):
        self._save_contact_info()
        if self._chk_restore.isChecked():
            self.accept()
        else:
            self.reject()


class FatalCrashDialog(_CrashDialog):

    """Dialog which gets shown when a fatal error occurred.

    Attributes:
        _log: The log text to display.
        _type: The type of error which occurred.
        _func: The function (top of the stack) in which the error occurred.
        _chk_history: A checkbox for the user to decide if page history should
                      be sent.
    """

    def __init__(self, debug, text, parent=None):
        self._chk_history = None
        super().__init__(debug, parent)
        self._log = text
        self.setAttribute(Qt.WA_DeleteOnClose)
        self._set_crash_info()
        self._type, self._func = parse_fatal_stacktrace(self._log)

    def _get_error_type(self):
        if self._type == 'Segmentation fault':
            return 'segv'
        else:
            return self._type

    def _get_paste_title_desc(self):
        return self._func

    def _init_text(self):
        super()._init_text()
        text = ("<b>qutebrowser was restarted after a fatal crash.</b><br/>"
                "<br/>Note: Crash reports for fatal crashes sometimes don't "
                "contain the information necessary to fix an issue. Please "
                "follow the steps in <a href='https://github.com/The-Compiler/"
                "qutebrowser/blob/master/doc/stacktrace.asciidoc'>"
                "stacktrace.asciidoc</a> to submit a stacktrace.<br/>")
        self._lbl.setText(text)

    def _init_checkboxes(self):
        """Add checkboxes to the dialog."""
        super()._init_checkboxes()
        self._chk_history = QCheckBox("Include a history of the last "
                                      "accessed pages in the report.",
                                      checked=True)
        try:
            if config.get('general', 'private-browsing'):
                self._chk_history.setChecked(False)
        except Exception:
            log.misc.exception("Error while checking private browsing mode")
        self._chk_history.toggled.connect(self._set_crash_info)
        self._vbox.addWidget(self._chk_history)

    def _gather_crash_info(self):
        self._crash_info.append(("Fault log", self._log))
        super()._gather_crash_info()
        if self._chk_history.isChecked():
            try:
                history = objreg.get('web-history').get_recent()
                self._crash_info.append(("History", ''.join(history)))
            except Exception:
                self._crash_info.append(("History", traceback.format_exc()))


class ReportDialog(_CrashDialog):

    """Dialog which gets shown when the user wants to report an issue by hand.

    Attributes:
        _pages: A list of the open pages (URLs as strings)
        _cmdhist: A list with the command history (as strings)
        _objects: A list of all QObjects as string.
    """

    def __init__(self, pages, cmdhist, objects, parent=None):
        super().__init__(False, parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self._pages = pages
        self._cmdhist = cmdhist
        self._objects = objects
        self._set_crash_info()

    def _init_text(self):
        super()._init_text()
        text = "Please describe the bug you encountered below."
        self._lbl.setText(text)

    def _init_info_text(self):
        """We don't want an info text as the user wanted to report."""
        pass

    def _get_error_type(self):
        return 'report'

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


def dump_exception_info(exc, pages, cmdhist, objects):
    """Dump exception info to stderr.

    Args:
        exc: An exception tuple (type, value, traceback)
        pages: A list of lists of the open pages (URLs as strings)
        cmdhist: A list with the command history (as strings)
        objects: A list of all QObjects as string.
    """
    print(file=sys.stderr)
    print("\n\n===== Handling exception with --no-err-windows... =====\n\n",
          file=sys.stderr)
    print("\n---- Exceptions ----", file=sys.stderr)
    print(''.join(traceback.format_exception(*exc)), file=sys.stderr)
    print("\n---- Version info ----", file=sys.stderr)
    try:
        print(version.version(), file=sys.stderr)
    except Exception:
        traceback.print_exc()
    print("\n---- Config ----", file=sys.stderr)
    try:
        conf = objreg.get('config')
        print(conf.dump_userconfig(), file=sys.stderr)
    except Exception:
        traceback.print_exc()
    print("\n---- Commandline args ----", file=sys.stderr)
    print(' '.join(sys.argv[1:]), file=sys.stderr)
    print("\n---- Open pages ----", file=sys.stderr)
    print('\n\n'.join('\n'.join(e) for e in pages), file=sys.stderr)
    print("\n---- Command history ----", file=sys.stderr)
    print('\n'.join(cmdhist), file=sys.stderr)
    print("\n---- Objects ----", file=sys.stderr)
    print(objects, file=sys.stderr)
    print("\n---- Environment ----", file=sys.stderr)
    try:
        print(_get_environment_vars(), file=sys.stderr)
    except Exception:
        traceback.print_exc()
