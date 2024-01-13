# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Convenience functions to show message boxes."""

from qutebrowser.qt.core import Qt
from qutebrowser.qt.widgets import QMessageBox

from qutebrowser.misc import objects
from qutebrowser.utils import log


class DummyBox:

    """A dummy QMessageBox returned when --no-err-windows is used."""

    def exec(self):
        pass


def msgbox(parent, title, text, *, icon, buttons=QMessageBox.StandardButton.Ok,
           on_finished=None, plain_text=None):
    """Display a QMessageBox with the given icon.

    Args:
        parent: The parent to set for the message box.
        title: The title to set.
        text: The text to set.
        icon: The QIcon to show in the box.
        buttons: The buttons to set (QMessageBox::StandardButtons)
        on_finished: A slot to connect to the 'finished' signal.
        plain_text: Whether to force plain text (True) or rich text (False).
                    None (the default) uses Qt's auto detection.

    Return:
        A new QMessageBox.
    """
    if objects.args.no_err_windows:
        log.misc.info(f'{title}\n\n{text}')
        return DummyBox()

    box = QMessageBox(parent)
    box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    box.setIcon(icon)
    box.setStandardButtons(buttons)
    if on_finished is not None:
        box.finished.connect(on_finished)
    if plain_text:
        box.setTextFormat(Qt.TextFormat.PlainText)
    elif plain_text is not None:
        box.setTextFormat(Qt.TextFormat.RichText)
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
    return msgbox(*args, icon=QMessageBox.Icon.Information, **kwargs)
