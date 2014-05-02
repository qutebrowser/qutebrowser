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

import logging
import html

from PyQt5.QtWidgets import (QStyle, QStyleOptionViewItem, QTreeView,
                             QStyledItemDelegate, QSizePolicy)
from PyQt5.QtCore import (pyqtSlot, pyqtSignal, Qt, QRectF, QSize,
                          QItemSelectionModel)
from PyQt5.QtGui import (QIcon, QPalette, QTextDocument, QTextOption,
                         QTextCursor)

import qutebrowser.config.config as config
import qutebrowser.commands.utils as cmdutils
import qutebrowser.config.configdata as configdata
from qutebrowser.models.basecompletion import ROLE_MARKS, NoCompletionsError
from qutebrowser.config.style import set_register_stylesheet, get_stylesheet
from qutebrowser.commands.managers import split_cmdline
from qutebrowser.models.completionfilter import CompletionFilterModel as CFM
from qutebrowser.models.completion import (
    CommandCompletionModel, SettingSectionCompletionModel,
    SettingOptionCompletionModel, SettingValueCompletionModel)
from qutebrowser.utils.usertypes import FakeDict


class CompletionView(QTreeView):

    """The view showing available completions.

    Based on QTreeView but heavily customized so root elements show as category
    headers, and children show as flat list.

    Highlights completions based on marks in the ROLE_MARKS data.

    Class attributes:
        STYLESHEET: The stylesheet template for the CompletionView.
        COLUMN_WIDTHS: A list of column widths, in percent.

    Attributes:
        _model: The currently active filter model.
        _lastmodel: The model set in the last iteration.
        _models: dict of available completion models.
        _enabled: Whether showing the CompletionView is enabled.
        _completing: Whether we're currently completing something.
        _height: The height to use for the CompletionView.
        _height_perc: Either None or a percentage if height should be relative.
        _delegate: The item delegate used.

    Signals:
        change_completed_part: Text which should be substituted for the word
                               we're currently completing.
    """

    STYLESHEET = """
        QTreeView {{
            {font[completion]}
            {color[completion.fg]}
            {color[completion.bg]}
            outline: 0;
        }}

        QTreeView::item:enabled {{
            {color[completion.item.fg]}
            {color[completion.item.bg]}
        }}

        QTreeView::item:disabled {{
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
    COLUMN_WIDTHS = [20, 70, 10]

    change_completed_part = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._enabled = config.get('completion', 'show')
        self._model = None
        self._lastmodel = None
        self._models = {
            'option': {},
            'value': {},
        }
        self._init_command_completion()
        self._init_setting_completions()
        self._completing = False

        self._delegate = _CompletionItemDelegate(self)
        self.setItemDelegate(self._delegate)
        set_register_stylesheet(self)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)
        self.setHeaderHidden(True)
        self.setIndentation(0)
        self.setItemsExpandable(False)
        self.setExpandsOnDoubleClick(False)
        # QTBUG? This is a workaround for weird race conditions with invalid
        # item indexes leading to segfaults in Qt.
        #
        # Some background: http://bugs.quassel-irc.org/issues/663
        # The proposed fix there was later reverted because it didn't help.
        self.setUniformRowHeights(True)
        self.hide()
        # FIXME set elidemode

    def _init_command_completion(self):
        """Initialize the command completion model."""
        self._models['command'] = CFM(CommandCompletionModel(self))

    def _init_setting_completions(self):
        """Initialize setting completion models."""
        self._models['section'] = CFM(SettingSectionCompletionModel(self))
        self._models['option'] = {}
        self._models['value'] = {}
        for sectname, sect in configdata.DATA.items():
            optmodel = CFM(SettingOptionCompletionModel(sectname, self))
            self._models['option'][sectname] = optmodel
            config.instance.changed.connect(optmodel.srcmodel.on_config_changed)
            if hasattr(sect, 'valtype'):
                # Same type for all values (ValueList)
                try:
                    model = CFM(SettingValueCompletionModel(
                        sectname, parent=self))
                    self._models['value'][sectname] = FakeDict(model)
                except NoCompletionsError:
                    pass
            else:
                self._models['value'][sectname] = {}
                for opt in configdata.DATA[sectname].keys():
                    try:
                        self._models['value'][sectname][opt] = CFM(
                            SettingValueCompletionModel(sectname, opt, self))
                    except NoCompletionsError:
                        pass

    def _resize_columns(self):
        """Resize the completion columns based on COLUMN_WIDTHS."""
        width = self.size().width()
        pixel_widths = [(width * perc // 100) for perc in self.COLUMN_WIDTHS]
        if self.verticalScrollBar().isVisible():
            pixel_widths[-1] -= self.style().pixelMetric(
                QStyle.PM_ScrollBarExtent) + 5
        for i, w in enumerate(pixel_widths):
            self.setColumnWidth(i, w)

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
            return self._model.first_item()
        while True:
            idx = self.indexAbove(idx) if upwards else self.indexBelow(idx)
            # wrap around if we arrived at beginning/end
            if not idx.isValid() and upwards:
                return self._model.last_item()
            elif not idx.isValid() and not upwards:
                idx = self._model.first_item()
                self.scrollTo(idx.parent())
                return idx
            elif idx.parent().isValid():
                # Item is a real item, not a category header -> success
                return idx

    def _get_new_completion(self, parts):
        """Get a new completion model.

        parts: The command chunks to get a completion for.
        """
        if len(parts) == 1:
            # parts = [''] or something like ['set']
            return self._models['command']
        # delegate completion to command
        try:
            completions = cmdutils.cmd_dict[parts[0]].completion
        except KeyError:
            # entering an unknown command
            return None
        logging.debug("completions: {}".format(completions))
        if completions is None:
            # command without any available completions
            return None
        try:
            idx = len(parts[1:]) - 1
            completion_name = completions[idx]
            logging.debug('partlen: {}, modelname {}'.format(
                len(parts[1:]), completion_name))
        except IndexError:
            # More arguments than completions
            return None
        if completion_name == 'option':
            section = parts[-2]
            model = self._models['option'].get(section)
        elif completion_name == 'value':
            section = parts[-3]
            option = parts[-2]
            try:
                model = self._models['value'][section][option]
            except KeyError:
                model = None
        else:
            model = self._models.get(completion_name)
        return model

    def _next_prev_item(self, prev):
        """Handle a tab press for the CompletionView.

        Select the previous/next item and write the new text to the
        statusbar.

        Args:
            prev: True for prev item, False for next one.

        Emit:
            change_completed_part: When a completion took place.
        """
        if not self._completing:
            # No completion running at the moment, ignore keypress
            return
        idx = self._next_idx(prev)
        self.selectionModel().setCurrentIndex(
            idx, QItemSelectionModel.ClearAndSelect |
            QItemSelectionModel.Rows)

    def set_model(self, model):
        """Switch completion to a new model.

        Called from cmd_text_changed().

        Args:
            model: The model to use.
        """
        logging.debug("Setting model to {}".format(model.__class__.__name__))
        self.setModel(model)
        self._model = model
        self.expandAll()
        self._resize_columns()

    @pyqtSlot(str, str)
    def on_config_changed(self, section, option):
        """Update self._enabled when the config changed."""
        if section == 'completion' and option == 'show':
            self._enabled = config.get('completion', 'show')
        elif section == 'aliases':
            self._init_command_completion()

    @pyqtSlot(str)
    def on_cmd_text_changed(self, text):
        """Check if completions are available and activate them.

        Slot for the textChanged signal of the statusbar command widget.

        Args:
            text: The new text
        """
        # FIXME we should also consider the cursor position
        if not text.startswith(':'):
            # This is a search or gibberish, so we don't need to complete
            # anything (yet)
            # FIXME complete searchs
            self.hide()
            self._completing = False
            return

        text = text.lstrip(':')
        parts = split_cmdline(text)

        model = self._get_new_completion(parts)
        if model is None:
            logging.debug("No completion model for {}.".format(parts))
        else:
            logging.debug("New completion: {} / last: {}".format(
                model.srcmodel.__class__.__name__,
                self._lastmodel.srcmodel.__class__.__name__ if self._lastmodel
                is not None else "None"))
        if model != self._lastmodel:
            self._lastmodel = model
            if model is None:
                self.hide()
                self._completing = False
                return
            self.set_model(model)
            self._completing = True

        if model is None:
            return

        pattern = parts[-1] if parts else ''
        self._model.pattern = pattern
        self._model.srcmodel.mark_all_items(pattern)
        if self._enabled:
            self.show()

    @pyqtSlot()
    def on_clear_completion_selection(self):
        """Clear the selection model when an item is activated."""
        selmod = self.selectionModel()
        if selmod is not None:
            selmod.clearSelection()
            selmod.clearCurrentIndex()

    @cmdutils.register(instance='mainwindow.completion', hide=True,
                       modes=['command'])
    def completion_item_prev(self):
        """Select the previous completion item."""
        self._next_prev_item(prev=True)

    @cmdutils.register(instance='mainwindow.completion', hide=True,
                       modes=['command'])
    def completion_item_next(self):
        """Select the next completion item."""
        self._next_prev_item(prev=False)

    def selectionChanged(self, selected, deselected):
        """Extend selectionChanged to emit change_completed_part if necessary.

        Args:
            selected: New selection.
            delected: Previous selection.

        Emit:
            change_completed_part: Emitted when there's data for the new item.
        """
        indexes = selected.indexes()
        if indexes:
            data = self._model.data(indexes[0])
            if data is not None:
                self.change_completed_part.emit(data)
        super().selectionChanged(selected, deselected)

    def resizeEvent(self, e):
        """Extend resizeEvent to adjust column size."""
        super().resizeEvent(e)
        self._resize_columns()


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

    # FIXME this is horribly slow when resizing.
    # We should probably cache something in _get_textdoc or so, but as soon as
    # we implement eliding that cache probably isn't worth much anymore...

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
            index: The QModelIndex of the item to draw.
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
        self._doc.setDefaultStyleSheet(get_stylesheet("""
            .highlight {{
                {color[completion.match.fg]}
            }}
        """))
        self._doc.setDocumentMargin(2)

        if index.column() == 0:
            marks = index.data(ROLE_MARKS)
            if marks is None:
                return
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
