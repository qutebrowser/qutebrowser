# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Misc. widgets used at different places."""

import typing

from PyQt5.QtCore import pyqtSlot, pyqtSignal, Qt, QSize, QTimer
from PyQt5.QtWidgets import (QLineEdit, QWidget, QHBoxLayout, QLabel,
                             QStyleOption, QStyle, QLayout, QApplication)
from PyQt5.QtGui import QValidator, QPainter

from qutebrowser.config import config
from qutebrowser.utils import utils
from qutebrowser.misc import cmdhistory
from qutebrowser.keyinput import keyutils


class MinimalLineEditMixin:

    """A mixin to give a QLineEdit a minimal look and nicer repr()."""

    def __init__(self):
        self.setStyleSheet(  # type: ignore[attr-defined]
            """
            QLineEdit {
                border: 0px;
                padding-left: 1px;
                background-color: transparent;
            }
            """
        )
        self.setAttribute(  # type: ignore[attr-defined]
            Qt.WA_MacShowFocusRect, False)

    def keyPressEvent(self, e):
        """Override keyPressEvent to paste primary selection on Shift + Ins."""
        if e.key() == Qt.Key_Insert and e.modifiers() == Qt.ShiftModifier:
            try:
                text = utils.get_clipboard(selection=True, fallback=True)
            except utils.ClipboardError:
                e.ignore()
            else:
                e.accept()
                self.insert(text)  # type: ignore[attr-defined]
            return
        super().keyPressEvent(e)  # type: ignore[misc]

    def __repr__(self):
        return utils.get_repr(self)


class CommandLineEdit(QLineEdit):

    """A QLineEdit with a history and prompt chars.

    Attributes:
        history: The command history object.
        _validator: The current command validator.
        _promptlen: The length of the current prompt.
    """

    def __init__(self, *, parent=None):
        super().__init__(parent)
        self.history = cmdhistory.History(parent=self)
        self._validator = _CommandValidator(self)
        self.setValidator(self._validator)
        self.textEdited.connect(self.on_text_edited)
        self.cursorPositionChanged.connect(self.__on_cursor_position_changed)
        self._promptlen = 0

    def __repr__(self):
        return utils.get_repr(self, text=self.text())

    @pyqtSlot(str)
    def on_text_edited(self, _text):
        """Slot for textEdited. Stop history browsing."""
        self.history.stop()

    @pyqtSlot(int, int)
    def __on_cursor_position_changed(self, _old, new):
        """Prevent the cursor moving to the prompt.

        We use __ here to avoid accidentally overriding it in subclasses.
        """
        if new < self._promptlen:
            self.cursorForward(self.hasSelectedText(), self._promptlen - new)

    def set_prompt(self, text):
        """Set the current prompt to text.

        This updates the validator, and makes sure the user can't move the
        cursor behind the prompt.
        """
        self._validator.prompt = text
        self._promptlen = len(text)


class _CommandValidator(QValidator):

    """Validator to prevent the : from getting deleted.

    Attributes:
        prompt: The current prompt.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.prompt = None

    def validate(self, string, pos):
        """Override QValidator::validate.

        Args:
            string: The string to validate.
            pos: The current cursor position.

        Return:
            A tuple (status, string, pos) as a QValidator should.
        """
        if self.prompt is None or string.startswith(self.prompt):
            return (QValidator.Acceptable, string, pos)
        else:
            return (QValidator.Invalid, string, pos)


class DetailFold(QWidget):

    """A "fold" widget with an arrow to show/hide details.

    Attributes:
        _folded: Whether the widget is currently folded or not.
        _hbox: The HBoxLayout the arrow/label are in.
        _arrow: The FoldArrow widget.

    Signals:
        toggled: Emitted when the widget was folded/unfolded.
                 arg 0: bool, if the contents are currently visible.
    """

    toggled = pyqtSignal(bool)

    def __init__(self, text, parent=None):
        super().__init__(parent)
        self._folded = True
        self._hbox = QHBoxLayout(self)
        self._hbox.setContentsMargins(0, 0, 0, 0)
        self._arrow = _FoldArrow()
        self._hbox.addWidget(self._arrow)
        label = QLabel(text)
        self._hbox.addWidget(label)
        self._hbox.addStretch()

    def toggle(self):
        """Toggle the fold of the widget."""
        self._folded = not self._folded
        self._arrow.fold(self._folded)
        self.toggled.emit(not self._folded)

    def mousePressEvent(self, e):
        """Toggle the fold if the widget was pressed.

        Args:
            e: The QMouseEvent.
        """
        if e.button() == Qt.LeftButton:
            e.accept()
            self.toggle()
        else:
            super().mousePressEvent(e)


class _FoldArrow(QWidget):

    """The arrow shown for the DetailFold widget.

    Attributes:
        _folded: Whether the widget is currently folded or not.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._folded = True

    def fold(self, folded):
        """Fold/unfold the widget.

        Args:
            folded: The new desired state.
        """
        self._folded = folded
        self.update()

    def paintEvent(self, _event):
        """Paint the arrow.

        Args:
            _paint: The QPaintEvent (unused).
        """
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        if self._folded:
            elem = QStyle.PE_IndicatorArrowRight
        else:
            elem = QStyle.PE_IndicatorArrowDown
        self.style().drawPrimitive(elem, opt, painter, self)

    def minimumSizeHint(self):
        """Return a sensible size."""
        return QSize(8, 8)


class WrapperLayout(QLayout):

    """A Qt layout which simply wraps a single widget.

    This is used so the widget is hidden behind a defined API and can't
    easily be accidentally accessed.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._widget = typing.cast(QWidget, None)

    def addItem(self, _widget):
        raise utils.Unreachable

    def sizeHint(self):
        return self._widget.sizeHint()

    def itemAt(self, _index):
        return None

    def takeAt(self, _index):
        raise utils.Unreachable

    def setGeometry(self, rect):
        self._widget.setGeometry(rect)

    def wrap(self, container, widget):
        """Wrap the given widget in the given container."""
        self._widget = widget
        container.setFocusProxy(widget)
        widget.setParent(container)

    def unwrap(self):
        self._widget.setParent(None)  # type: ignore[call-overload]
        self._widget.deleteLater()


class PseudoLayout(QLayout):

    """A layout which isn't actually a real layout.

    This is used to replace QWebEngineView's internal layout, as a WORKAROUND
    for https://bugreports.qt.io/browse/QTBUG-68224 and other related issues.

    This is partly inspired by https://codereview.qt-project.org/#/c/230894/
    which does something similar as part of Qt.
    """

    def addItem(self, item):
        assert self.parent() is not None
        item.widget().setParent(self.parent())

    def removeItem(self, item):
        item.widget().setParent(None)

    def count(self):
        return 0

    def itemAt(self, _pos):
        return None

    def widget(self):
        return self.parent().render_widget()

    def setGeometry(self, rect):
        """Resize the render widget when the view is resized."""
        widget = self.widget()
        if widget is not None:
            widget.setGeometry(rect)

    def sizeHint(self):
        """Make sure the view has the sizeHint of the render widget."""
        widget = self.widget()
        if widget is not None:
            return widget.sizeHint()
        return QSize()


class FullscreenNotification(QLabel):

    """A label telling the user this page is now fullscreen."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            background-color: rgba(50, 50, 50, 80%);
            color: white;
            border-radius: 20px;
            padding: 30px;
        """)

        all_bindings = config.key_instance.get_reverse_bindings_for('normal')
        bindings = all_bindings.get('fullscreen --leave')
        if bindings:
            key = bindings[0]
            self.setText("Press {} to exit fullscreen.".format(key))
        else:
            self.setText("Page is now fullscreen.")

        self.resize(self.sizeHint())
        if config.val.content.fullscreen.window:
            geom = self.parentWidget().geometry()
        else:
            geom = QApplication.desktop().screenGeometry(self)
        self.move((geom.width() - self.sizeHint().width()) // 2, 30)

    def set_timeout(self, timeout):
        """Hide the widget after the given timeout."""
        QTimer.singleShot(timeout, self._on_timeout)

    @pyqtSlot()
    def _on_timeout(self):
        """Hide and delete the widget."""
        self.hide()
        self.deleteLater()


class KeyTesterWidget(QWidget):

    """Widget displaying key presses."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self._layout = QHBoxLayout(self)
        self._label = QLabel(text="Waiting for keypress...")
        self._layout.addWidget(self._label)

    def keyPressEvent(self, e):
        """Show pressed keys."""
        lines = [
            str(keyutils.KeyInfo.from_event(e)),
            '',
            'key: 0x{:x}'.format(int(e.key())),
            'modifiers: 0x{:x}'.format(int(e.modifiers())),
            'text: {!r}'.format(e.text()),
        ]
        self._label.setText('\n'.join(lines))
