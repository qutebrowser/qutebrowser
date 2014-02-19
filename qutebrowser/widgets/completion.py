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

"""Completion view for statusbar command section.

Defines a CompletionView which uses CompletionFiterModel and CompletionModel
subclasses to provide completions.

"""

import html

from PyQt5.QtWidgets import (QStyle, QStyleOptionViewItem, QTreeView,
                             QStyledItemDelegate, QSizePolicy)
from PyQt5.QtCore import (pyqtSlot, pyqtSignal, Qt, QRect, QRectF, QPoint,
                          QSize, QItemSelectionModel)
from PyQt5.QtGui import (QIcon, QPalette, QTextDocument, QTextOption,
                         QTextCursor)

import qutebrowser.utils.config as config
from qutebrowser.models.completionfilter import CompletionFilterModel
from qutebrowser.models.commandcompletion import CommandCompletionModel


class CompletionView(QTreeView):

    """The view showing available completions.

    Based on QTreeView but heavily customized so root elements show as category
    headers, and children show as flat list.

    Highlights completions based on marks in the UserRole.

    Attributes:
        _STYLESHEET: The stylesheet template for the CompletionView.
        _completion_models: dict of available completion models.
        _ignore_next: Whether to ignore the next cmd_text_changed signal.
        _enabled: Whether showing the CompletionView is enabled.
        _completing: Whether we're currently completing something.
        _height: The height to use for the CompletionView.
        _height_perc: Either None or a percentage if height should be relative.
        _delegate: The item delegate used.

    Signals:
        append_cmd_text: Command text which should be appended to the
                         statusbar.

    """

    _STYLESHEET = """
        QTreeView {{
            {font[completion]}
            {color[completion.fg]}
            {color[completion.bg]}
            outline: 0;
        }}
        QTreeView::item {{
            {color[completion.item.fg]}
            {color[completion.item.bg]}
        }}
        QTreeView::item:has-children {{
            {color[completion.category.fg]}
            {color[completion.category.bg]}
            border-top: 1px solid {color[completion.category.border.top]};
            border-bottom: 1px solid
                {color[completion.category.border.bottom]};
        }}
        QTreeView::item:selected {{
            border-top: 1px solid {color[completion.item.selected.border.top]};
            border-bottom: 1px solid
                {color[completion.item.selected.border.bottom]};
            {color[completion.item.selected.bg]}
            {color[completion.item.selected.fg]}
        }}
    """
    # FIXME because we use :has-children, if a category is empty, it won't look
    # like one anymore
    # FIXME somehow only the first column is yellow, even with
    # setAllColumnsShowFocus
    append_cmd_text = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        height = config.config.get('general', 'completion_height')
        if height.endswith('%'):
            self._height = QPoint(0, 200)  # just a temporary sane value
            self._height_perc = int(height.rstrip('%'))
        else:
            self._height = QPoint(0, int(height))
            self._height_perc = None
        self._enabled = config.config.getboolean('general', 'show_completion')
        self._completion_models = {}
        self._completion_models[''] = None
        self._completion_models['command'] = CommandCompletionModel()
        self._ignore_next = False
        self._completing = False

        self.model = CompletionFilterModel()
        self.setModel(self.model)
        self.setmodel('command')
        self._delegate = _CompletionItemDelegate(self)
        self.setItemDelegate(self._delegate)
        self.setStyleSheet(config.get_stylesheet(self._STYLESHEET))
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)
        self.setHeaderHidden(True)
        self.setIndentation(0)
        self.setItemsExpandable(False)
        # FIXME This is a workaround for weird race conditions with invalid
        # item indexes leading to segfaults in Qt.
        #
        # Some background: http://bugs.quassel-irc.org/issues/663
        # The proposed fix there was later reverted because it didn't help.
        self.setUniformRowHeights(True)
        self.hide()
        # FIXME set elidemode

    def _next_idx(self, upwards):
        """Get the previous/next QModelIndex displayed in the view.

        Used by tab_handler.

        Args:
            upwards: Get previous item, not next.

        Return:
            A QModelIndex.

        """
        idx = self.selectionModel().currentIndex()
        if not idx.isValid():
            # No item selected yet
            return self.model.first_item()
        while True:
            idx = self.indexAbove(idx) if upwards else self.indexBelow(idx)
            # wrap around if we arrived at beginning/end
            if not idx.isValid() and upwards:
                return self.model.last_item()
            elif not idx.isValid() and not upwards:
                return self.model.first_item()
            elif idx.parent().isValid():
                # Item is a real item, not a category header -> success
                return idx

    def setmodel(self, model):
        """Switch completion to a new model.

        Called from cmd_text_changed().

        Args:
            model: A QAbstractItemModel with available completions.

        """
        self.model.srcmodel = self._completion_models[model]
        self.expandAll()
        self.resizeColumnToContents(0)

    @pyqtSlot('QRect')
    def resize_to_bar(self, geom):
        """Resize the completion area to the statusbar geometry.

        Slot for the resized signal of the statusbar.

        Args:
            geom: A QRect containing the statusbar geometry.

        Raises:
            AssertionError if new geometry is invalid.

        """
        bottomleft = geom.topLeft()
        bottomright = geom.topRight()
        topleft = bottomleft - self._height
        assert topleft.x() < bottomright.x()
        assert topleft.y() < bottomright.y()
        self.setGeometry(QRect(topleft, bottomright))

    @pyqtSlot('QRect')
    def on_browser_resized(self, geom):
        """Slot for the resized signal of the browser window.

        Adjust the height of the completion if it was configured as a
        percentage.

        Args:
            geom: A QRect containing the browser geometry.

        """
        if self._height_perc is None:
            return
        else:
            height = int(geom.height() * self._height_perc / 100)
            self._height = QPoint(0, height)

    @pyqtSlot('QPoint')
    def move_to_bar(self, pos):
        """Move the completion area to the statusbar geometry.

        Slot for the moved signal of the statusbar.

        Args:
            pos: A QPoint containing the statusbar position.

        """
        self.move(pos - self._height)

    @pyqtSlot(str)
    def on_cmd_text_changed(self, text):
        """Check if completions are available and activate them.

        Slot for the textChanged signal of the statusbar command widget.

        Args:
            text: The new text

        """
        if self._ignore_next:
            # Text changed by a completion, so we don't have to complete again.
            self._ignore_next = False
            return
        # FIXME more sophisticated completions
        if ' ' in text or not text.startswith(':'):
            self.hide()
            self._completing = False
            return

        self._completing = True
        self.setmodel('command')
        text = text.lstrip(':')
        self.model.pattern = text
        self.model.srcmodel.mark_all_items(text)
        if self._enabled:
            self.show()

    @pyqtSlot(bool)
    def on_tab_pressed(self, shift):
        """Handle a tab press for the CompletionView.

        Select the previous/next item and write the new text to the
        statusbar. Called by key_(s)tab_handler in statusbar.command.

        Args:
            shift: Whether shift is pressed or not.

        Emit:
            append_cmd_text: When a command text should be set/appended.

        """
        if not self._completing:
            # No completion running at the moment, ignore keypress
            return
        idx = self._next_idx(shift)
        self.selectionModel().setCurrentIndex(
            idx, QItemSelectionModel.ClearAndSelect)
        data = self.model.data(idx)
        if data is not None:
            self._ignore_next = True
            self.append_cmd_text.emit(self.model.data(idx) + ' ')


class _CompletionItemDelegate(QStyledItemDelegate):

    """Delegate used by CompletionView to draw individual items.

    Mainly a cleaned up port of Qt's way to draw a TreeView item, except it
    uses a QTextDocument to draw the text and add marking.

    Original implementation:
        qt/src/gui/styles/qcommonstyle.cpp:drawControl:2153

    Attributes:
        _opt: The QStyleOptionViewItem which is used.
        _style: The style to be used.
        _painter: The QPainter to be used.
        _doc: The QTextDocument to be used.

    """

    def __init__(self, parent=None):
        self._painter = None
        self._opt = None
        self._doc = None
        self._style = None
        super().__init__(parent)

    def _draw_background(self):
        """Draw the background of an ItemViewItem."""
        self._style.drawPrimitive(self._style.PE_PanelItemViewItem, self._opt,
                                  self._painter, self._opt.widget)

    def _draw_icon(self):
        """Draw the icon of an ItemViewItem."""
        icon_rect = self._style.subElementRect(
            self._style.SE_ItemViewItemDecoration, self._opt, self._opt.widget)

        mode = QIcon.Normal
        if not self._opt.state & QStyle.State_Enabled:
            mode = QIcon.Disabled
        elif self._opt.state & QStyle.State_Selected:
            mode = QIcon.Selected
        state = QIcon.On if self._opt.state & QStyle.State_Open else QIcon.Off
        self._opt.icon.paint(self._painter, icon_rect,
                             self._opt.decorationAlignment, mode, state)

    def _draw_text(self, index):
        """Draw the text of an ItemViewItem.

        This is the main part where we differ from the original implementation
        in Qt: We use a QTextDocument to draw text.

        Args:
            index -- The QModelIndex of the item to draw.

        """
        if not self._opt.text:
            return

        text_rect_ = self._style.subElementRect(
            self._style.SE_ItemViewItemText, self._opt, self._opt.widget)
        margin = self._style.pixelMetric(QStyle.PM_FocusFrameHMargin,
                                         self._opt, self._opt.widget) + 1
        # remove width padding
        text_rect = text_rect_.adjusted(margin, 0, -margin, 0)
        # move text upwards a bit
        if index.parent().isValid():
            text_rect.adjust(0, -1, 0, -1)
        else:
            text_rect.adjust(0, -2, 0, -2)
        self._painter.save()
        state = self._opt.state
        if state & QStyle.State_Enabled and state & QStyle.State_Active:
            cg = QPalette.Normal
        elif state & QStyle.State_Enabled:
            cg = QPalette.Inactive
        else:
            cg = QPalette.Disabled

        if state & QStyle.State_Selected:
            self._painter.setPen(self._opt.palette.color(
                cg, QPalette.HighlightedText))
            # FIXME this is a dirty fix for the text jumping by one pixel...
            # we really should do this properly somehow
            text_rect.adjust(0, -1, 0, 0)
        else:
            self._painter.setPen(self._opt.palette.color(cg, QPalette.Text))

        if state & QStyle.State_Editing:
            self._painter.setPen(self._opt.palette.color(cg, QPalette.Text))
            self._painter.drawRect(text_rect_.adjusted(0, 0, -1, -1))

        self._painter.translate(text_rect.left(), text_rect.top())
        self._get_textdoc(index)
        self._draw_textdoc(text_rect)
        self._painter.restore()

    def _draw_textdoc(self, text_rect):
        """Draw the QTextDocument of an item.

        Args:
            text_rect: The QRect to clip the drawing to.

        """
        clip = QRectF(0, 0, text_rect.width(), text_rect.height())
        self._doc.drawContents(self._painter, clip)

    def _get_textdoc(self, index):
        """Create the QTextDocument of an item.

        Args:
            index: The QModelIndex of the item to draw.

        """
        # FIXME we probably should do eliding here. See
        # qcommonstyle.cpp:viewItemDrawText
        text_option = QTextOption()
        if self._opt.features & QStyleOptionViewItem.WrapText:
            text_option.setWrapMode(QTextOption.WordWrap)
        else:
            text_option.setWrapMode(QTextOption.ManualWrap)
        text_option.setTextDirection(self._opt.direction)
        text_option.setAlignment(QStyle.visualAlignment(
            self._opt.direction, self._opt.displayAlignment))

        self._doc = QTextDocument(self)
        if index.parent().isValid():
            self._doc.setPlainText(self._opt.text)
        else:
            self._doc.setHtml('<b>{}</b>'.format(html.escape(self._opt.text)))
        self._doc.setDefaultFont(self._opt.font)
        self._doc.setDefaultTextOption(text_option)
        self._doc.setDefaultStyleSheet(config.get_stylesheet("""
            .highlight {{
                {color[completion.match.fg]}
            }}
        """))
        self._doc.setDocumentMargin(2)

        if index.column() == 0:
            marks = index.data(Qt.UserRole)
            for mark in marks:
                cur = QTextCursor(self._doc)
                cur.setPosition(mark[0])
                cur.setPosition(mark[1], QTextCursor.KeepAnchor)
                txt = cur.selectedText()
                cur.removeSelectedText()
                cur.insertHtml('<span class="highlight">{}</span>'.format(
                    html.escape(txt)))

    def _draw_focus_rect(self):
        """Draw the focus rectangle of an ItemViewItem."""
        state = self._opt.state
        if not state & QStyle.State_HasFocus:
            return
        o = self._opt
        o.rect = self._style.subElementRect(
            self._style.SE_ItemViewItemFocusRect, self._opt, self._opt.widget)
        o.state |= QStyle.State_KeyboardFocusChange | QStyle.State_Item
        if state & QStyle.State_Enabled:
            cg = QPalette.Normal
        else:
            cg = QPalette.Disabled
        if state & QStyle.State_Selected:
            role = QPalette.Highlight
        else:
            role = QPalette.Window
        o.backgroundColor = self._opt.palette.color(cg, role)
        self._style.drawPrimitive(QStyle.PE_FrameFocusRect, o, self._painter,
                                  self._opt.widget)

    def sizeHint(self, option, index):
        """Override sizeHint of QStyledItemDelegate.

        Return the cell size based on the QTextDocument size, but might not
        work correctly yet.

        Args:
            option: const QStyleOptionViewItem & option
            index: const QModelIndex & index

        Return:
            A QSize with the recommended size.

        """
        value = index.data(Qt.SizeHintRole)
        if value is not None:
            return value
        self._opt = QStyleOptionViewItem(option)
        self.initStyleOption(self._opt, index)
        self._style = self._opt.widget.style()
        self._get_textdoc(index)
        docsize = self._doc.size().toSize()
        size = self._style.sizeFromContents(QStyle.CT_ItemViewItem, self._opt,
                                            docsize, self._opt.widget)
        return size + QSize(10, 1)

    def paint(self, painter, option, index):
        """Override the QStyledItemDelegate paint function.

        Args:
            painter: QPainter * painter
            option: const QStyleOptionViewItem & option
            index: const QModelIndex & index

        """
        self._painter = painter
        self._painter.save()
        self._opt = QStyleOptionViewItem(option)
        self.initStyleOption(self._opt, index)
        self._style = self._opt.widget.style()

        self._draw_background()
        self._draw_icon()
        self._draw_text(index)
        self._draw_focus_rect()

        self._painter.restore()
