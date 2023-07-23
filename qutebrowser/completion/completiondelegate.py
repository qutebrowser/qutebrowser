# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Completion item delegate for CompletionView.

We use this to be able to highlight parts of the text.
"""

import re
import html

from qutebrowser.qt.widgets import QStyle, QStyleOptionViewItem, QStyledItemDelegate
from qutebrowser.qt.core import QRectF, QRegularExpression, QSize, Qt
from qutebrowser.qt.gui import (QIcon, QPalette, QTextDocument, QTextOption,
                         QAbstractTextDocumentLayout, QSyntaxHighlighter,
                         QTextCharFormat)

from qutebrowser.config import config
from qutebrowser.utils import qtutils
from qutebrowser.completion import completionwidget


class _Highlighter(QSyntaxHighlighter):

    def __init__(self, doc, pattern, color):
        super().__init__(doc)
        self._format = QTextCharFormat()
        self._format.setForeground(color)
        words = pattern.split()
        words.sort(key=len, reverse=True)
        pat = "|".join(re.escape(word) for word in words)
        self._expression = QRegularExpression(
            pat, QRegularExpression.PatternOption.CaseInsensitiveOption
        )
        qtutils.ensure_valid(self._expression)

    def highlightBlock(self, text):
        """Override highlightBlock for custom highlighting."""
        match_iterator = self._expression.globalMatch(text)
        while match_iterator.hasNext():
            match = match_iterator.next()
            self.setFormat(
                match.capturedStart(),
                match.capturedLength(),
                self._format
            )


class CompletionItemDelegate(QStyledItemDelegate):

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

    # FIXME this is horribly slow when resizing.
    # We should probably cache something in _get_textdoc or so, but as soon as
    # we implement eliding that cache probably isn't worth much anymore...
    # https://github.com/qutebrowser/qutebrowser/issues/121

    def __init__(self, parent=None):
        self._painter = None
        self._opt = None
        self._doc = None
        self._style = None
        super().__init__(parent)

    def _draw_background(self):
        """Draw the background of an ItemViewItem."""
        assert self._opt is not None
        assert self._style is not None
        self._style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, self._opt,
                                  self._painter, self._opt.widget)

    def _draw_icon(self):
        """Draw the icon of an ItemViewItem."""
        assert self._opt is not None
        assert self._style is not None

        icon_rect = self._style.subElementRect(
            QStyle.SubElement.SE_ItemViewItemDecoration, self._opt, self._opt.widget)
        if not icon_rect.isValid():
            # The rect seems to be wrong in all kind of ways if no icon should
            # be displayed.
            return

        mode = QIcon.Mode.Normal
        if not self._opt.state & QStyle.StateFlag.State_Enabled:
            mode = QIcon.Mode.Disabled
        elif self._opt.state & QStyle.StateFlag.State_Selected:
            mode = QIcon.Mode.Selected
        state = QIcon.State.On if self._opt.state & QStyle.StateFlag.State_Open else QIcon.State.Off
        self._opt.icon.paint(self._painter, icon_rect,
                             self._opt.decorationAlignment, mode, state)

    def _draw_text(self, index):
        """Draw the text of an ItemViewItem.

        This is the main part where we differ from the original implementation
        in Qt: We use a QTextDocument to draw text.

        Args:
            index: The QModelIndex of the item to draw.
        """
        assert self._opt is not None
        assert self._painter is not None
        assert self._style is not None
        if not self._opt.text:
            return

        text_rect_ = self._style.subElementRect(
            QStyle.SubElement.SE_ItemViewItemText, self._opt, self._opt.widget)
        qtutils.ensure_valid(text_rect_)
        margin = self._style.pixelMetric(QStyle.PixelMetric.PM_FocusFrameHMargin,
                                         self._opt, self._opt.widget) + 1
        # remove width padding
        text_rect = text_rect_.adjusted(margin, 0, -margin, 0)
        qtutils.ensure_valid(text_rect)
        # move text upwards a bit
        if index.parent().isValid():
            text_rect.adjust(0, -1, 0, -1)
        else:
            text_rect.adjust(0, -2, 0, -2)
        self._painter.save()
        state = self._opt.state
        if state & QStyle.StateFlag.State_Enabled and state & QStyle.StateFlag.State_Active:
            cg = QPalette.ColorGroup.Normal
        elif state & QStyle.StateFlag.State_Enabled:
            cg = QPalette.ColorGroup.Inactive
        else:
            cg = QPalette.ColorGroup.Disabled

        if state & QStyle.StateFlag.State_Selected:
            self._painter.setPen(self._opt.palette.color(
                cg, QPalette.ColorRole.HighlightedText))
            # This is a dirty fix for the text jumping by one pixel for
            # whatever reason.
            text_rect.adjust(0, -1, 0, 0)
        else:
            self._painter.setPen(self._opt.palette.color(cg, QPalette.ColorRole.Text))

        if state & QStyle.StateFlag.State_Editing:
            self._painter.setPen(self._opt.palette.color(cg, QPalette.ColorRole.Text))
            self._painter.drawRect(text_rect_.adjusted(0, 0, -1, -1))

        self._painter.translate(text_rect.left(), text_rect.top())
        self._get_textdoc(index)
        self._draw_textdoc(text_rect, index.column())
        self._painter.restore()

    def _draw_textdoc(self, rect, col):
        """Draw the QTextDocument of an item.

        Args:
            rect: The QRect to clip the drawing to.
        """
        assert self._painter is not None
        assert self._doc is not None
        assert self._opt is not None

        # We can't use drawContents because then the color would be ignored.
        clip = QRectF(0, 0, rect.width(), rect.height())
        self._painter.save()

        if self._opt.state & QStyle.StateFlag.State_Selected:
            color = config.cache['colors.completion.item.selected.fg']
        elif not self._opt.state & QStyle.StateFlag.State_Enabled:
            color = config.cache['colors.completion.category.fg']
        else:
            colors = config.cache['colors.completion.fg']
            # if multiple colors are set, use different colors per column
            color = colors[col % len(colors)]
        self._painter.setPen(color)

        ctx = QAbstractTextDocumentLayout.PaintContext()
        ctx.palette.setColor(QPalette.ColorRole.Text, self._painter.pen().color())
        if clip.isValid():
            self._painter.setClipRect(clip)
            ctx.clip = clip
        self._doc.documentLayout().draw(self._painter, ctx)
        self._painter.restore()

    def _get_textdoc(self, index):
        """Create the QTextDocument of an item.

        Args:
            index: The QModelIndex of the item to draw.
        """
        assert self._opt is not None
        # FIXME we probably should do eliding here. See
        # qcommonstyle.cpp:viewItemDrawText
        # https://github.com/qutebrowser/qutebrowser/issues/118
        text_option = QTextOption()
        if self._opt.features & QStyleOptionViewItem.ViewItemFeature.WrapText:
            text_option.setWrapMode(QTextOption.WrapMode.WordWrap)
        else:
            text_option.setWrapMode(QTextOption.WrapMode.ManualWrap)
        text_option.setTextDirection(self._opt.direction)
        text_option.setAlignment(QStyle.visualAlignment(
            self._opt.direction, self._opt.displayAlignment))

        if self._doc is not None:
            self._doc.deleteLater()
        self._doc = QTextDocument(self)
        self._doc.setDefaultFont(self._opt.font)
        self._doc.setDefaultTextOption(text_option)
        self._doc.setDocumentMargin(2)

        if index.parent().isValid():
            view = self.parent()
            assert isinstance(view, completionwidget.CompletionView), view
            pattern = view.pattern
            columns_to_filter = index.model().columns_to_filter(index)
            if index.column() in columns_to_filter and pattern:
                if self._opt.state & QStyle.StateFlag.State_Selected:
                    color = config.val.colors.completion.item.selected.match.fg
                else:
                    color = config.val.colors.completion.match.fg
                _Highlighter(self._doc, pattern, color)
            self._doc.setPlainText(self._opt.text)
        else:
            self._doc.setHtml(
                '<span style="font: {};">{}</span>'.format(
                    html.escape(config.val.fonts.completion.category),
                    html.escape(self._opt.text)))

    def _draw_focus_rect(self):
        """Draw the focus rectangle of an ItemViewItem."""
        assert self._opt is not None
        assert self._style is not None
        state = self._opt.state
        if not state & QStyle.StateFlag.State_HasFocus:
            return
        o = self._opt
        o.rect = self._style.subElementRect(
            QStyle.SubElement.SE_ItemViewItemFocusRect, self._opt, self._opt.widget)
        o.state |= QStyle.StateFlag.State_KeyboardFocusChange | QStyle.StateFlag.State_Item
        qtutils.ensure_valid(o.rect)
        if state & QStyle.StateFlag.State_Enabled:
            cg = QPalette.ColorGroup.Normal
        else:
            cg = QPalette.ColorGroup.Disabled
        if state & QStyle.StateFlag.State_Selected:
            role = QPalette.ColorRole.Highlight
        else:
            role = QPalette.ColorRole.Window
        o.backgroundColor = self._opt.palette.color(cg, role)
        self._style.drawPrimitive(QStyle.PrimitiveElement.PE_FrameFocusRect, o, self._painter,
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
        value = index.data(Qt.ItemDataRole.SizeHintRole)
        if value is not None:
            return value
        self._opt = QStyleOptionViewItem(option)
        self.initStyleOption(self._opt, index)
        self._style = self._opt.widget.style()
        assert self._style is not None

        self._get_textdoc(index)
        assert self._doc is not None

        docsize = self._doc.size().toSize()
        size = self._style.sizeFromContents(QStyle.ContentsType.CT_ItemViewItem, self._opt,
                                            docsize, self._opt.widget)
        qtutils.ensure_valid(size)
        return size + QSize(10, 3)

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
