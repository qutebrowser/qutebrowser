# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Dialogs shown when there was a problem with a backend choice."""

import os
import sys
import functools

import attr
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QApplication, QDialog, QPushButton, QHBoxLayout,
                             QVBoxLayout, QLabel)

from qutebrowser.config import config
from qutebrowser.utils import usertypes, objreg, version
from qutebrowser.misc import objects


_Result = usertypes.enum('_Result', ['quit', 'restart'], is_int=True,
                         start=QDialog.Accepted + 1)


@attr.s
class _Button:

    """A button passed to BackendProblemDialog."""

    text = attr.ib()
    setting = attr.ib()
    value = attr.ib()
    default = attr.ib(default=False)


class _Dialog(QDialog):

    """A dialog which gets shown if there are issues with the backend."""

    def __init__(self, because, text, backend, buttons=None, parent=None):
        super().__init__(parent)
        vbox = QVBoxLayout(self)

        other_backend = {
            usertypes.Backend.QtWebKit: usertypes.Backend.QtWebEngine,
            usertypes.Backend.QtWebEngine: usertypes.Backend.QtWebKit,
        }[backend]
        other_setting = other_backend.name.lower()[2:]

        label = QLabel(
            "<b>Failed to start with the {backend} backend!</b>"
            "<p>qutebrowser tried to start with the {backend} backend but "
            "failed because {because}.</p>{text}"
            "<p><b>Forcing the {other_backend.name} backend</b></p>"
            "<p>This forces usage of the {other_backend.name} backend. "
            "This sets the <i>backend = '{other_setting}'</i> setting "
            "(if you have a <i>config.py</i> file, you'll need to set "
            "this manually).</p>".format(
                backend=backend.name, because=because, text=text,
                other_backend=other_backend, other_setting=other_setting),
            wordWrap=True)
        label.setTextFormat(Qt.RichText)
        vbox.addWidget(label)

        hbox = QHBoxLayout()
        buttons = [] if buttons is None else buttons

        quit_button = QPushButton("Quit")
        quit_button.clicked.connect(lambda: self.done(_Result.quit))
        hbox.addWidget(quit_button)

        backend_button = QPushButton("Force {} backend".format(
            other_backend.name))
        backend_button.clicked.connect(functools.partial(
            self._change_setting, 'backend', other_setting))
        hbox.addWidget(backend_button)

        for button in buttons:
            btn = QPushButton(button.text, default=button.default)
            btn.clicked.connect(functools.partial(
                self._change_setting, button.setting, button.value))
            hbox.addWidget(btn)

        vbox.addLayout(hbox)

    def _change_setting(self, setting, value):
        """Change the given setting and restart."""
        config.instance.set_obj(setting, value, save_yaml=True)
        self.done(_Result.restart)


def _show_dialog(*args, **kwargs):
    """Show a dialog for a backend problem."""
    dialog = _Dialog(*args, **kwargs)

    status = dialog.exec_()

    if status == _Result.quit:
        sys.exit(usertypes.Exit.err_init)
    elif status == _Result.restart:
        # FIXME pass --backend webengine
        quitter = objreg.get('quitter')
        quitter.restart()
        sys.exit(usertypes.Exit.err_init)


def _handle_nouveau_graphics():
    force_sw_var = 'QT_XCB_FORCE_SOFTWARE_OPENGL'

    if version.opengl_vendor() != 'nouveau':
        return

    if (os.environ.get('LIBGL_ALWAYS_SOFTWARE') == '1' or
            force_sw_var in os.environ):
        return

    if config.force_software_rendering:
        os.environ[force_sw_var] = '1'
        return

    button = _Button("Force software rendering", 'force_software_rendering',
                     True)
    _show_dialog(
        backend=usertypes.Backend.QtWebEngine,
        because="you're using Nouveau graphics",
        text="<p>There are two ways to fix this:</p>"
             "<p><b>Forcing software rendering</b></p>"
             "<p>This allows you to use the newer QtWebEngine backend (based "
             "on Chromium) but could have noticable performance impact "
             "(depending on your hardware). "
             "This sets the <i>force_software_rendering = True</i> setting "
             "(if you have a <i>config.py</i> file, you'll need to set this "
             "manually).</p>",
        buttons=[button],
    )

    # Should never be reached
    assert False


def _handle_wayland():
    if QApplication.instance().platformName() not in ['wayland', 'wayland-egl']:
        return
    if os.environ.get('DISPLAY'):
        # When DISPLAY is set but with the wayland/wayland-egl platform plugin,
        # QtWebEngine will do the right hting.
        return

    _show_dialog(
        backend=usertypes.Backend.QtWebEngine,
        because="you're using Wayland",
        text="<p>There are two ways to fix this:</p>"
             "<p><b>Set up XWayland</b></p>"
             "<p>This allows you to use the newer QtWebEngine backend (based "
             "on Chromium). "
    )

    # Should never be reached
    assert False


def init():
    if objects.backend == usertypes.Backend.QtWebEngine:
        _handle_wayland()
        _handle_nouveau_graphics()
    else:
        assert objects.backend == usertypes.Backend.QtWebKit, objects.backend
