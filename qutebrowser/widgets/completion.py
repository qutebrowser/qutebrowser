"""Completion view for statusbar command section.

Defines a CompletionView which uses CompletionFiterModel and CompletionModel
subclasses to provide completions.

"""

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

import html

from PyQt5.QtWidgets import (QTreeView, QStyledItemDelegate, QStyle,
                             QStyleOptionViewItem, QSizePolicy)
from PyQt5.QtCore import (QRectF, QRect, QPoint, pyqtSignal, Qt,
                          QItemSelectionModel, QSize)
from PyQt5.QtGui import (QIcon, QPalette, QTextDocument, QTextOption,
                         QTextCursor)

import qutebrowser.utils.config as config
from qutebrowser.utils.completion import CompletionFilterModel
from qutebrowser.commands.utils import CommandCompletionModel


class CompletionView(QTreeView):

    """The view showing available completions.

    Based on QTreeView but heavily customized so root elements show as category
    headers, and children show as flat list.

    Highlights completions based on marks in the UserRole.

    """

    _stylesheet = """
        QTreeView {{
            font-family: {monospace};
            {color[completion.fg]}
            {color[completion.bg]}
            outline: 0;
        }}
        QTreeView::item {{
            {color[completion.item.fg]}
            {color[completion.item.bg]}
        }}
        QTreeView::item:has-children {{
            font-weight: bold;
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
    completion_models = {}
    append_cmd_text = pyqtSignal(str)
    ignore_next = False
    enabled = True
    completing = False

    def __init__(self, parent=None):
        super().__init__(parent)
        self.enabled = config.config.getboolean('general', 'show_completion')
        self.completion_models[''] = None
        self.completion_models['command'] = CommandCompletionModel()
        self.model = CompletionFilterModel()
        self.setModel(self.model)
        self.setmodel('command')
        self.setItemDelegate(CompletionItemDelegate())
        self.setStyleSheet(config.get_stylesheet(self._stylesheet))
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

    def setmodel(self, model):
        """Switch completion to a new model.

        Called from cmd_text_changed().

        model -- A QAbstractItemModel with available completions.

        """
        self.model.setsrc(self.completion_models[model])
        self.expandAll()
        self.resizeColumnToContents(0)

    def resize_to_bar(self, geom):
        """Resize the completion area to the statusbar geometry.

        Slot for the resized signal of the statusbar.
        geom -- A QRect containing the statusbar geometry.

        """
        bottomleft = geom.topLeft()
        bottomright = geom.topRight()
        delta = QPoint(0, 200)
        topleft = bottomleft - delta
        assert topleft.x() < bottomright.x()
        assert topleft.y() < bottomright.y()
        self.setGeometry(QRect(topleft, bottomright))

    def cmd_text_changed(self, text):
        """Check if completions are available and activate them.

        Slot for the textChanged signal of the statusbar command widget.
        text -- The new text

        """
        if self.ignore_next:
            # Text changed by a completion, so we don't have to complete again.
            self.ignore_next = False
            return
        # FIXME more sophisticated completions
        if ' ' in text or not text.startswith(':'):
            self.hide()
            self.completing = False
            return

        self.completing = True
        self.setmodel('command')
        text = text.lstrip(':')
        self.model.pattern = text
        self.model.srcmodel.mark_all_items(text)
        if self.enabled:
            self.show()

    def tab_handler(self, shift):
        """Handle a tab press for the CompletionView.

        Selects the previous/next item and writes the new text to the
        statusbar. Called by key_(s)tab_handler in statusbar.command.

        shift -- Whether shift is pressed or not.

        """
        if not self.completing:
            # No completion running at the moment, ignore keypress
            return
        idx = self._next_idx(shift)
        self.selectionModel().setCurrentIndex(
            idx, QItemSelectionModel.ClearAndSelect)
        data = self.model.data(idx)
        if data is not None:
            self.ignore_next = True
            self.append_cmd_text.emit(self.model.data(idx) + ' ')

    def _next_idx(self, upwards):
        """Get the previous/next QModelIndex displayed in the view.

        Used by tab_handler.

        upwards -- Get previous item, not next.

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


class CompletionItemDelegate(QStyledItemDelegate):

    """Delegate used by CompletionView to draw individual items.

    Mainly a cleaned up port of Qt's way to draw a TreeView item, except it
    uses a QTextDocument to draw the text and add marking.

    Original implementation:
        qt/src/gui/styles/qcommonstyle.cpp:drawControl:2153

    """

    opt = None
    style = None
    painter = None

    def sizeHint(self, option, index):
        """Override sizeHint of QStyledItemDelegate.

        Returns the cell size based on the QTextDocument size, but might not
        work correctly yet.

        """
        value = index.data(Qt.SizeHintRole)
        if value is not None:
            return value
        self.opt = QStyleOptionViewItem(option)
        self.initStyleOption(self.opt, index)
        style = self.opt.widget.style()
        doc = self._get_textdoc(index)
        docsize = doc.size().toSize()
        return style.sizeFromContents(QStyle.CT_ItemViewItem, self.opt,
                                      docsize, self.opt.widget) + QSize(10, 0)

    def paint(self, painter, option, index):
        """Override the QStyledItemDelegate paint function."""
        painter.save()

        self.painter = painter
        self.opt = QStyleOptionViewItem(option)
        self.initStyleOption(self.opt, index)
        self.style = self.opt.widget.style()

        self._draw_background()
        self._draw_icon()
        self._draw_text(index)
        self._draw_focus_rect()

        painter.restore()

    def _draw_background(self):
        """Draw the background of an ItemViewItem."""
        self.style.drawPrimitive(self.style.PE_PanelItemViewItem, self.opt,
                                 self.painter, self.opt.widget)

    def _draw_icon(self):
        """Draw the icon of an ItemViewItem."""
        icon_rect = self.style.subElementRect(
            self.style.SE_ItemViewItemDecoration, self.opt, self.opt.widget)

        mode = QIcon.Normal
        if not self.opt.state & QStyle.State_Enabled:
            mode = QIcon.Disabled
        elif self.opt.state & QStyle.State_Selected:
            mode = QIcon.Selected
        state = QIcon.On if self.opt.state & QStyle.State_Open else QIcon.Off
        self.opt.icon.paint(self.painter, icon_rect,
                            self.opt.decorationAlignment, mode, state)

    def _draw_text(self, index):
        """Draw the text of an ItemViewItem.

        This is the main part where we differ from the original implementation
        in Qt: We use a QTextDocument to draw text.

        index of the item of the item -- The QModelIndex of the item to draw.

        """
        if not self.opt.text:
            return

        text_rect_ = self.style.subElementRect(self.style.SE_ItemViewItemText,
                                               self.opt, self.opt.widget)
        margin = self.style.pixelMetric(QStyle.PM_FocusFrameHMargin, self.opt,
                                        self.opt.widget) + 1
        # remove width padding
        text_rect = text_rect_.adjusted(margin, 0, -margin, 0)
        self.painter.save()
        state = self.opt.state
        if state & QStyle.State_Enabled and state & QStyle.State_Active:
            cg = QPalette.Normal
        elif state & QStyle.State_Enabled:
            cg = QPalette.Inactive
        else:
            cg = QPalette.Disabled

        if state & QStyle.State_Selected:
            self.painter.setPen(self.opt.palette.color(
                cg, QPalette.HighlightedText))
            # FIXME this is a dirty fix for the text jumping by one pixel...
            # we really should do this properly somehow
            text_rect.adjust(0, -1, 0, 0)
        else:
            self.painter.setPen(self.opt.palette.color(cg, QPalette.Text))

        if state & QStyle.State_Editing:
            self.painter.setPen(self.opt.palette.color(cg, QPalette.Text))
            self.painter.drawRect(text_rect_.adjusted(0, 0, -1, -1))

        self.painter.translate(text_rect.left(), text_rect.top())
        doc = self._get_textdoc(index)
        self._draw_textdoc(doc, text_rect)
        self.painter.restore()

    def _draw_textdoc(self, doc, text_rect):
        """Draw the QTextDocument of an item.

        doc -- The QTextDocument to draw.
        text_rect -- The QRect to clip the drawing to.

        """
        clip = QRectF(0, 0, text_rect.width(), text_rect.height())
        doc.drawContents(self.painter, clip)

    def _get_textdoc(self, index):
        """Return the QTextDocument of an item.

        index -- The QModelIndex of the item to draw.

        """
        # FIXME we probably should do eliding here. See
        # qcommonstyle.cpp:viewItemDrawText
        text_option = QTextOption()
        if self.opt.features & QStyleOptionViewItem.WrapText:
            text_option.setWrapMode(QTextOption.WordWrap)
        else:
            text_option.setWrapMode(QTextOption.ManualWrap)
        text_option.setTextDirection(self.opt.direction)
        text_option.setAlignment(QStyle.visualAlignment(
            self.opt.direction, self.opt.displayAlignment))

        doc = QTextDocument()
        if index.parent().isValid():
            doc.setPlainText(self.opt.text)
        else:
            doc.setHtml('<b>{}</b>'.format(html.escape(self.opt.text)))
        doc.setDefaultFont(self.opt.font)
        doc.setDefaultTextOption(text_option)
        doc.setDefaultStyleSheet(config.get_stylesheet("""
            .highlight {{
                {color[completion.match.fg]}
            }}
        """))
        doc.setDocumentMargin(2)

        if index.column() == 0:
            marks = index.data(Qt.UserRole)
            for mark in marks:
                cur = QTextCursor(doc)
                cur.setPosition(mark[0])
                cur.setPosition(mark[1], QTextCursor.KeepAnchor)
                txt = cur.selectedText()
                cur.removeSelectedText()
                cur.insertHtml('<span class="highlight">{}</span>'.format(
                    html.escape(txt)))
        return doc

    def _draw_focus_rect(self):
        """Draw the focus rectangle of an ItemViewItem."""
        state = self.opt.state
        if not state & QStyle.State_HasFocus:
            return
        o = self.opt
        o.rect = self.style.subElementRect(self.style.SE_ItemViewItemFocusRect,
                                           self.opt, self.opt.widget)
        o.state |= QStyle.State_KeyboardFocusChange | QStyle.State_Item
        if state & QStyle.State_Enabled:
            cg = QPalette.Normal
        else:
            cg = QPalette.Disabled
        if state & QStyle.State_Selected:
            role = QPalette.Highlight
        else:
            role = QPalette.Window
        o.backgroundColor = self.opt.palette.color(cg, role)
        self.style.drawPrimitive(QStyle.PE_FrameFocusRect, o, self.painter,
                                 self.opt.widget)
