"""Completion view which appears when something is typed in the statusbar
command section.

Defines a CompletionView which uses CompletionFiterModel and CompletionModel
subclasses to provide completions.
"""

import html
import logging

from PyQt5.QtWidgets import (QTreeView, QStyledItemDelegate, QStyle,
                             QStyleOptionViewItem, QSizePolicy)
from PyQt5.QtCore import (QRectF, QRect, QPoint, pyqtSignal, Qt,
                          QItemSelectionModel)
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
        self.model.setSourceModel(self.completion_models['command'])
        self.setItemDelegate(CompletionItemDelegate())
        self.setStyleSheet(config.get_stylesheet(self._stylesheet))
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)
        self.expandAll()
        self.setHeaderHidden(True)
        self.setIndentation(0)
        self.setItemsExpandable(False)
        self.hide()
        # FIXME set elidemode

    def resizeEvent(self, e):
        """Extends resizeEvent of QTreeView.

        Always adjusts the column width to the new window width.

        e -- The QResizeEvent.
        """
        super().resizeEvent(e)
        width = e.size().width()
        cols = self.model.columnCount()
        colwidth = int(width / cols)
        logging.debug('width {}, {} columns -> colwidth {}'.format(width, cols,
                                                                   colwidth))
        assert cols >= 1
        assert colwidth > 1
        for i in range(cols):
            self.setColumnWidth(i, colwidth)

    def setmodel(self, model):
        """Switch completion to a new model.

        Called from cmd_text_changed().

        model -- A QAbstractItemModel with available completions.
        """
        self.model.setSourceModel(self.completion_models[model])
        self.model.pattern = ''
        self.expandAll()

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
        self.model.sourceModel().mark_all_items(text)
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

    def paint(self, painter, option, index):
        """Overrides the QStyledItemDelegate paint function."""
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
        """Draw the background of an ItemViewItem"""
        self.style.drawPrimitive(self.style.PE_PanelItemViewItem, self.opt,
                                 self.painter, self.opt.widget)

    def _draw_icon(self):
        """Draw the icon of an ItemViewItem"""
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

        index -- The QModelIndex of the item to draw.
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
        self._draw_textdoc(index, text_rect)
        self.painter.restore()

    def _draw_textdoc(self, index, text_rect):
        """Draw the QTextDocument of an item.

        index -- The QModelIndex of the item to draw.
        text_rect -- The QRect to clip the drawing to.
        """
        # FIXME we probably should do eliding here. See
        # qcommonstyle.cpp:viewItemDrawText
        clip = QRectF(0, 0, text_rect.width(), text_rect.height())

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
        doc.setDocumentMargin(0)

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
        doc.drawContents(self.painter, clip)

    def _draw_focus_rect(self):
        """Draws the focus rectangle of an ItemViewItem"""
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
