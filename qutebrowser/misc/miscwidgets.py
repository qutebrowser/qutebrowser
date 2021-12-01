# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Misc. widgets used at different places."""

from typing import Optional

from PyQt5.QtCore import pyqtSlot, pyqtSignal, Qt, QSize, QTimer
from PyQt5.QtWidgets import (QLineEdit, QWidget, QHBoxLayout, QLabel,
                             QStyleOption, QStyle, QLayout, QApplication,
                             QSplitter)
from PyQt5.QtGui import QValidator, QPainter, QResizeEvent

from qutebrowser.config import config, configfiles
from qutebrowser.utils import utils, log, usertypes
from qutebrowser.misc import cmdhistory
from qutebrowser.browser import inspector
from qutebrowser.keyinput import keyutils, modeman


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
        self._widget: Optional[QWidget] = None
        self._container: Optional[QWidget] = None

    def addItem(self, _widget):
        raise utils.Unreachable

    def sizeHint(self):
        """Get the size of the underlying widget."""
        if self._widget is None:
            return QSize()
        return self._widget.sizeHint()

    def itemAt(self, _index):
        return None

    def takeAt(self, _index):
        raise utils.Unreachable

    def setGeometry(self, rect):
        """Pass through setGeometry calls to the underlying widget."""
        if self._widget is None:
            return
        self._widget.setGeometry(rect)

    def wrap(self, container, widget):
        """Wrap the given widget in the given container."""
        self._container = container
        self._widget = widget
        container.setFocusProxy(widget)
        widget.setParent(container)

    def unwrap(self):
        """Remove the widget from this layout.

        Does nothing if it nothing was wrapped before.
        """
        if self._widget is None:
            return
        assert self._container is not None
        self._widget.setParent(None)  # type: ignore[call-overload]
        self._widget.deleteLater()
        self._widget = None
        self._container.setFocusProxy(None)  # type: ignore[arg-type]


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


class InspectorSplitter(QSplitter):

    """Allows putting an inspector inside the tab.

    Attributes:
        _main_idx: index of the main webview widget
        _position: position of the inspector (right/left/top/bottom)
        _preferred_size: the preferred size of the inpector widget in pixels

    Class attributes:
        _PROTECTED_MAIN_SIZE: How much space should be reserved for the main
                              content (website).
        _SMALL_SIZE_THRESHOLD: If the window size is under this threshold, we
                               consider this a temporary "emergency" situation.
    """

    _PROTECTED_MAIN_SIZE = 150
    _SMALL_SIZE_THRESHOLD = 300

    def __init__(self, win_id: int, main_webview: QWidget,
                 parent: QWidget = None) -> None:
        super().__init__(parent)
        self._win_id = win_id
        self.addWidget(main_webview)
        self.setFocusProxy(main_webview)
        self.splitterMoved.connect(self._on_splitter_moved)
        self._main_idx: Optional[int] = None
        self._inspector_idx: Optional[int] = None
        self._position: Optional[inspector.Position] = None
        self._preferred_size: Optional[int] = None

    def cycle_focus(self):
        """Cycle keyboard focus between the main/inspector widget."""
        if self.count() == 1:
            raise inspector.Error("No inspector inside main window")

        assert self._main_idx is not None
        assert self._inspector_idx is not None

        main_widget = self.widget(self._main_idx)
        inspector_widget = self.widget(self._inspector_idx)

        if not inspector_widget.isVisible():
            raise inspector.Error("No inspector inside main window")

        if main_widget.hasFocus():
            inspector_widget.setFocus()
            modeman.enter(self._win_id, usertypes.KeyMode.insert,
                          reason='Inspector focused', only_if_normal=True)
        elif inspector_widget.hasFocus():
            main_widget.setFocus()

    def set_inspector(self, inspector_widget: inspector.AbstractWebInspector,
                      position: inspector.Position) -> None:
        """Set the position of the inspector."""
        assert position != inspector.Position.window

        if position in [inspector.Position.right, inspector.Position.bottom]:
            self._main_idx = 0
            self._inspector_idx = 1
        else:
            self._inspector_idx = 0
            self._main_idx = 1

        self.setOrientation(Qt.Horizontal
                            if position in [inspector.Position.left,
                                            inspector.Position.right]
                            else Qt.Vertical)
        self.insertWidget(self._inspector_idx, inspector_widget)
        self._position = position
        self._load_preferred_size()
        self._adjust_size()

    def _save_preferred_size(self) -> None:
        """Save the preferred size of the inspector widget."""
        assert self._position is not None
        size = str(self._preferred_size)
        configfiles.state['inspector'][self._position.name] = size

    def _load_preferred_size(self) -> None:
        """Load the preferred size of the inspector widget."""
        assert self._position is not None
        full = (self.width() if self.orientation() == Qt.Horizontal
                else self.height())

        # If we first open the inspector with a window size of < 300px
        # (self._SMALL_SIZE_THRESHOLD), we don't want to default to half of the
        # window size as the small window is likely a temporary situation and
        # the inspector isn't very usable in that state.
        self._preferred_size = max(self._SMALL_SIZE_THRESHOLD, full // 2)

        try:
            size = int(configfiles.state['inspector'][self._position.name])
        except KeyError:
            # First start
            pass
        except ValueError as e:
            log.misc.error("Could not read inspector size: {}".format(e))
        else:
            self._preferred_size = int(size)

    def _adjust_size(self) -> None:
        """Adjust the size of the inspector similarly to Chromium.

        In general, we want to keep the absolute size of the inspector (rather
        than the ratio) the same, as it's confusing when the layout of its
        contents changes.

        We're essentially handling three different cases:

        1) We have plenty of space -> Keep inspector at the preferred absolute
           size.

        2) We're slowly running out of space. Make sure the page still has
           150px (self._PROTECTED_MAIN_SIZE) left, give the rest to the
           inspector.

        3) The window is very small (< 300px, self._SMALL_SIZE_THRESHOLD).
           Keep Qt's behavior of keeping the aspect ratio, as all hope is lost
           at this point.
        """
        sizes = self.sizes()
        total = sizes[0] + sizes[1]

        assert self._main_idx is not None
        assert self._inspector_idx is not None
        assert self._preferred_size is not None

        if total >= self._preferred_size + self._PROTECTED_MAIN_SIZE:
            # Case 1 above
            sizes[self._inspector_idx] = self._preferred_size
            sizes[self._main_idx] = total - self._preferred_size
            self.setSizes(sizes)
        elif (sizes[self._main_idx] < self._PROTECTED_MAIN_SIZE and
              total >= self._SMALL_SIZE_THRESHOLD):
            # Case 2 above
            handle_size = self.handleWidth()
            sizes[self._main_idx] = (
                self._PROTECTED_MAIN_SIZE - handle_size // 2)
            sizes[self._inspector_idx] = (
                total - self._PROTECTED_MAIN_SIZE + handle_size // 2)
            self.setSizes(sizes)
        else:
            # Case 3 above
            pass

    @pyqtSlot()
    def _on_splitter_moved(self) -> None:
        assert self._inspector_idx is not None
        sizes = self.sizes()
        self._preferred_size = sizes[self._inspector_idx]
        self._save_preferred_size()

    def resizeEvent(self, e: QResizeEvent) -> None:
        """Window resize event."""
        super().resizeEvent(e)
        if self.count() == 2:
            self._adjust_size()


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
