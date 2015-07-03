# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Completion item delegate for CompletionView.

We use this to be able to highlight parts of the text.
"""

import re
import html

from PyQt5.QtWidgets import QStyle, QStyleOptionViewItem, QStyledItemDelegate
from PyQt5.QtCore import QRectF, QSize, Qt
from PyQt5.QtGui import (QIcon, QPalette, QTextDocument, QTextOption,
                         QAbstractTextDocumentLayout)

from qutebrowser.config import config, configexc, style
from qutebrowser.utils import qtutils


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
    # https://github.com/The-Compiler/qutebrowser/issues/121

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
        if not icon_rect.isValid():
            # The rect seems to be wrong in all kind of ways if no icon should
            # be displayed.
            return

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
            index: The QModelIndex of the item to draw.
        """
        if not self._opt.text:
            return

        text_rect_ = self._style.subElementRect(
            self._style.SE_ItemViewItemText, self._opt, self._opt.widget)
        qtutils.ensure_valid(text_rect_)
        margin = self._style.pixelMetric(QStyle.PM_FocusFrameHMargin,
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
        if state & QStyle.State_Enabled and state & QStyle.State_Active:
            cg = QPalette.Normal
        elif state & QStyle.State_Enabled:
            cg = QPalette.Inactive
        else:
            cg = QPalette.Disabled

        if state & QStyle.State_Selected:
            self._painter.setPen(self._opt.palette.color(
                cg, QPalette.HighlightedText))
            # This is a dirty fix for the text jumping by one pixel for
            # whatever reason.
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

    def _draw_textdoc(self, rect):
        """Draw the QTextDocument of an item.

        Args:
            rect: The QRect to clip the drawing to.
        """
        # We can't use drawContents because then the color would be ignored.
        clip = QRectF(0, 0, rect.width(), rect.height())
        self._painter.save()
        if self._opt.state & QStyle.State_Selected:
            option = 'completion.item.selected.fg'
        elif not self._opt.state & QStyle.State_Enabled:
            option = 'completion.category.fg'
        else:
            option = 'completion.fg'
        try:
            self._painter.setPen(config.get('colors', option))
        except configexc.NoOptionError:
            self._painter.setPen(config.get('colors', 'completion.fg'))
        ctx = QAbstractTextDocumentLayout.PaintContext()
        ctx.palette.setColor(QPalette.Text, self._painter.pen().color())
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
        # FIXME we probably should do eliding here. See
        # qcommonstyle.cpp:viewItemDrawText
        # https://github.com/The-Compiler/qutebrowser/issues/118
        text_option = QTextOption()
        if self._opt.features & QStyleOptionViewItem.WrapText:
            text_option.setWrapMode(QTextOption.WordWrap)
        else:
            text_option.setWrapMode(QTextOption.ManualWrap)
        text_option.setTextDirection(self._opt.direction)
        text_option.setAlignment(QStyle.visualAlignment(
            self._opt.direction, self._opt.displayAlignment))

        self._doc = QTextDocument(self)
        self._doc.setDefaultFont(self._opt.font)
        self._doc.setDefaultTextOption(text_option)
        self._doc.setDefaultStyleSheet(style.get_stylesheet("""
            .highlight {
                {{ color['completion.match.fg'] }}
            }
        """))
        self._doc.setDocumentMargin(2)

        if index.parent().isValid():
            pattern = index.model().pattern
            if index.column() == 0 and pattern:
                repl = r'<span class="highlight">\g<0></span>'
                text = re.sub(re.escape(pattern), repl, self._opt.text,
                              flags=re.IGNORECASE)
                self._doc.setHtml(text)
            else:
                self._doc.setPlainText(self._opt.text)
        else:
            self._doc.setHtml('<b>{}</b>'.format(html.escape(self._opt.text)))

    def _draw_focus_rect(self):
        """Draw the focus rectangle of an ItemViewItem."""
        state = self._opt.state
        if not state & QStyle.State_HasFocus:
            return
        o = self._opt
        o.rect = self._style.subElementRect(
            self._style.SE_ItemViewItemFocusRect, self._opt, self._opt.widget)
        o.state |= QStyle.State_KeyboardFocusChange | QStyle.State_Item
        qtutils.ensure_valid(o.rect)
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
