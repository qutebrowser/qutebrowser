import logging
import html

from PyQt5.QtWidgets import (QTreeView, QStyledItemDelegate, QStyle,
                             QStyleOptionViewItem)
from PyQt5.QtCore import (QRectF, QRect, QPoint, pyqtSignal, Qt,
                          QItemSelectionModel)
from PyQt5.QtGui import (QIcon, QPalette, QTextDocument, QTextOption,
                         QTextCursor)

import qutebrowser.utils.config as config
from qutebrowser.utils.completion import CompletionFilterModel
from qutebrowser.commands.utils import CommandCompletionModel

class CompletionView(QTreeView):
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
            border-bottom: 1px solid {color[completion.category.border.bottom]};
        }}
        QTreeView::item:selected {{
            border-top: 1px solid {color[completion.item.selected.border.top]};
            border-bottom: 1px solid {color[completion.item.selected.border.bottom]};
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
        self.enabled = config.config.getboolean('general', 'show_completion',
                                                fallback=True)
        self.completion_models[''] = None
        self.completion_models['command'] = CommandCompletionModel()
        self.model = CompletionFilterModel()
        self.setModel(self.model)
        self.model.setSourceModel(self.completion_models['command'])
        self.model.pattern_changed.connect(self.resort)
        self.setItemDelegate(CompletionItemDelegate())
        self.setStyleSheet(config.get_stylesheet(self._stylesheet)
        self.expandAll()
        self.setHeaderHidden(True)
        self.setIndentation(0)
        self.setItemsExpandable(False)
        self.hide()
        # FIXME set elidemode

    def resizeEvent(self, e):
        width = e.size().width()
        for i in range(self.model.columnCount()):
            self.setColumnWidth(i, width/2)
        super().resizeEvent(e)

    def setmodel(self, model):
        self.model.setSourceModel(self.completion_models[model])
        self.model.pattern = ''
        self.expandAll()

    def resort(self, pattern):
        try:
            self.model.sourceModel().sort(0)
        except NotImplementedError:
            self.model.sort(0)

    def resize_to_bar(self, geom):
        bottomleft = geom.topLeft()
        bottomright = geom.topRight()
        delta = QPoint(0, 200)
        topleft = bottomleft - delta
        self.setGeometry(QRect(topleft, bottomright))

    def cmd_text_changed(self, text):
        if self.ignore_next:
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
        self.mark_all_items(text)
        if self.enabled:
            self.show()

    def first_item(self):
        cat = self.model.index(0, 0)
        return self.model.index(0, 0, cat)

    def last_item(self):
        cat = self.model.index(self.model.rowCount() - 1, 0)
        return self.model.index(self.model.rowCount(cat) - 1, 0, cat)

    def mark_all_items(self, needle):
        for i in range(self.model.rowCount()):
            cat = self.model.index(i, 0)
            for k in range(self.model.rowCount(cat)):
                idx = self.model.index(k, 0, cat)
                old = self.model.data(idx)
                marks = self.get_marks(needle, old)
                self.model.setData(idx, marks, Qt.UserRole)

    def get_marks(self, needle, haystack):
        pos1 = pos2 = 0
        marks = []
        if not needle:
            return marks
        while True:
            pos1 = haystack.find(needle, pos2)
            if pos1 == -1:
                break
            pos2 = pos1 + len(needle)
            marks.append((pos1, pos2))
        return marks

    def tab_handler(self, shift):
        if not self.completing:
            return
        idx = self._next_idx(shift)
        self.ignore_next = True
        self.selectionModel().setCurrentIndex(
            idx, QItemSelectionModel.ClearAndSelect)
        data = self.model.data(idx)
        if data is not None:
            self.append_cmd_text.emit(self.model.data(idx) + ' ')

    def _next_idx(self, shift):
        idx = self.selectionModel().currentIndex()
        if not idx.isValid():
            # No item selected yet
            return self.first_item()
        while True:
            idx = self.indexAbove(idx) if shift else self.indexBelow(idx)
            if not idx.isValid():
                # wrap around if we arrived at beginning/end
                return self.last_item() if shift else self.first_item()
            if idx.parent().isValid():
                # Item is a real item, not a category header -> success
                return idx

class CompletionItemDelegate(QStyledItemDelegate):
    opt = None
    style = None
    painter = None

    def paint(self, painter, option, index):
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
        self.style.drawPrimitive(self.style.PE_PanelItemViewItem, self.opt,
                                 self.painter, self.opt.widget)

    def _draw_icon(self):
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
        if (state & QStyle.State_Enabled and state & QStyle.State_Active):
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

        # FIXME we probably should do eliding here. See
        # qcommonstyle.cpp:viewItemDrawText

        self.painter.restore()

    def _draw_focus_rect(self):
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
