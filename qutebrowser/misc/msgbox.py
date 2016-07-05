# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Convenience functions to show message boxes."""


from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMessageBox


def msgbox(parent, title, text, *, icon, buttons=QMessageBox.Ok,
           on_finished=None, plain_text=None):
    """Display a QMessageBox with the given icon.

    Args:
        parent: The parent to set for the message box.
        title: The title to set.
        text: The text to set.
        buttons: The buttons to set (QMessageBox::StandardButtons)
        on_finished: A slot to connect to the 'finished' signal.
        plain_text: Whether to force plain text (True) or rich text (False).
                    None (the default) uses Qt's auto detection.

    Return:
        A new QMessageBox.
    """
    box = QMessageBox(parent)
    box.setIcon(icon)
    box.setStandardButtons(buttons)
    if on_finished is not None:
        box.finished.connect(on_finished)
    if plain_text:
        box.setTextFormat(Qt.PlainText)
    elif plain_text is not None:
        box.setTextFormat(Qt.RichText)
    box.setWindowTitle(title)
    box.setText(text)
    box.show()
    return box


def information(*args, **kwargs):
    """Display an information box.

    Args:
        *args: Passed to msgbox.
        **kwargs: Passed to msgbox.

    Return:
        A new QMessageBox.
    """
    return msgbox(*args, icon=QMessageBox.Information, **kwargs)
