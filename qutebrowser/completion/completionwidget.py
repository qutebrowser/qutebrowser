# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

from PyQt5.QtWidgets import QStyle, QTreeView, QSizePolicy
from PyQt5.QtCore import (pyqtSlot, pyqtSignal, Qt, QItemSelectionModel,
                          QItemSelection)

from qutebrowser.config import config, style
from qutebrowser.completion import completiondelegate
from qutebrowser.completion.models import base
from qutebrowser.utils import utils, usertypes
from qutebrowser.commands import cmdexc, cmdutils


class CompletionView(QTreeView):

    """The view showing available completions.

    Based on QTreeView but heavily customized so root elements show as category
    headers, and children show as flat list.

    Attributes:
        _win_id: The ID of the window this CompletionView is associated with.
        _height: The height to use for the CompletionView.
        _height_perc: Either None or a percentage if height should be relative.
        _delegate: The item delegate used.
        _column_widths: A list of column widths, in percent.
        _active: Whether a selection is active.

    Signals:
        resize_completion: Emitted when the completion should be resized.
        selection_changed: Emitted when the completion item selection changes.
    """

    # Drawing the item foreground will be done by CompletionItemDelegate, so we
    # don't define that in this stylesheet.
    STYLESHEET = """
        QTreeView {
            font: {{ font['completion'] }};
            background-color: {{ color['completion.bg'] }};
            alternate-background-color: {{ color['completion.alternate-bg'] }};
            outline: 0;
            border: 0px;
        }

        QTreeView::item:disabled {
            background-color: {{ color['completion.category.bg'] }};
            border-top: 1px solid
                {{ color['completion.category.border.top'] }};
            border-bottom: 1px solid
                {{ color['completion.category.border.bottom'] }};
        }

        QTreeView::item:selected, QTreeView::item:selected:hover {
            border-top: 1px solid
                {{ color['completion.item.selected.border.top'] }};
            border-bottom: 1px solid
                {{ color['completion.item.selected.border.bottom'] }};
            background-color: {{ color['completion.item.selected.bg'] }};
        }

        QTreeView:item::hover {
            border: 0px;
        }

        QTreeView QScrollBar {
            width: {{ config.get('completion', 'scrollbar-width') }}px;
            background: {{ color['completion.scrollbar.bg'] }};
        }

        QTreeView QScrollBar::handle {
            background: {{ color['completion.scrollbar.fg'] }};
            border: {{ config.get('completion', 'scrollbar-padding') }}px solid
                    {{ color['completion.scrollbar.bg'] }};
            min-height: 10px;
        }

        QTreeView QScrollBar::sub-line, QScrollBar::add-line {
            border: none;
            background: none;
        }
    """

    resize_completion = pyqtSignal()
    selection_changed = pyqtSignal(QItemSelection)

    def __init__(self, win_id, parent=None):
        super().__init__(parent)
        self._win_id = win_id
        # FIXME handle new aliases.
        # objreg.get('config').changed.connect(self.init_command_completion)

        self._column_widths = base.BaseCompletionModel.COLUMN_WIDTHS
        self._active = False

        self._delegate = completiondelegate.CompletionItemDelegate(self)
        self.setItemDelegate(self._delegate)
        style.set_register_stylesheet(self)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)
        self.setHeaderHidden(True)
        self.setAlternatingRowColors(True)
        self.setIndentation(0)
        self.setItemsExpandable(False)
        self.setExpandsOnDoubleClick(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # WORKAROUND
        # This is a workaround for weird race conditions with invalid
        # item indexes leading to segfaults in Qt.
        #
        # Some background: http://bugs.quassel-irc.org/issues/663
        # The proposed fix there was later reverted because it didn't help.
        self.setUniformRowHeights(True)
        self.hide()
        # FIXME set elidemode
        # https://github.com/The-Compiler/qutebrowser/issues/118

    def __repr__(self):
        return utils.get_repr(self)

    def _resize_columns(self):
        """Resize the completion columns based on column_widths."""
        width = self.size().width()
        pixel_widths = [(width * perc // 100) for perc in self._column_widths]
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
            if upwards:
                return self.model().last_item()
            else:
                return self.model().first_item()
        while True:
            idx = self.indexAbove(idx) if upwards else self.indexBelow(idx)
            # wrap around if we arrived at beginning/end
            if not idx.isValid() and upwards:
                return self.model().last_item()
            elif not idx.isValid() and not upwards:
                idx = self.model().first_item()
                self.scrollTo(idx.parent())
                return idx
            elif idx.parent().isValid():
                # Item is a real item, not a category header -> success
                return idx

    def _next_category_idx(self, upwards):
        """Get the index of the previous/next category.

        Args:
            upwards: Get previous item, not next.

        Return:
            A QModelIndex.
        """
        idx = self.selectionModel().currentIndex()
        if not idx.isValid():
            return self._next_idx(upwards).sibling(0, 0)
        idx = idx.parent()
        direction = -1 if upwards else 1
        while True:
            idx = idx.sibling(idx.row() + direction, 0)
            if not idx.isValid() and upwards:
                # wrap around to the first item of the last category
                return self.model().last_item().sibling(0, 0)
            elif not idx.isValid() and not upwards:
                # wrap around to the first item of the first category
                idx = self.model().first_item()
                self.scrollTo(idx.parent())
                return idx
            elif idx.isValid() and idx.child(0, 0).isValid():
                # scroll to ensure the category is visible
                self.scrollTo(idx)
                return idx.child(0, 0)

    @cmdutils.register(instance='completion', hide=True,
                       modes=[usertypes.KeyMode.command], scope='window')
    @cmdutils.argument('which', choices=['next', 'prev', 'next-category',
                                         'prev-category'])
    def completion_item_focus(self, which):
        """Shift the focus of the completion menu to another item.

        Args:
            which: 'next', 'prev', 'next-category', or 'prev-category'.
        """
        if not self._active:
            return
        selmodel = self.selectionModel()

        if which == 'next':
            idx = self._next_idx(upwards=False)
        elif which == 'prev':
            idx = self._next_idx(upwards=True)
        elif which == 'next-category':
            idx = self._next_category_idx(upwards=False)
        elif which == 'prev-category':
            idx = self._next_category_idx(upwards=True)

        if not idx.isValid():
            return

        selmodel.setCurrentIndex(
            idx, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)

        count = self.model().count()
        if count == 0:
            self.hide()
        elif count == 1 and config.get('completion', 'quick-complete'):
            self.hide()
        elif config.get('completion', 'show') == 'auto':
            self.show()

    def set_model(self, model, pattern=None):
        """Switch completion to a new model.

        Called from on_update_completion().

        Args:
            model: The model to use.
            pattern: The filter pattern to set (what the user entered).
        """
        if model is None:
            self._active = False
            self.hide()
            return

        old_model = self.model()
        if model is not old_model:
            sel_model = self.selectionModel()

            self.setModel(model)
            self._active = True

            if sel_model is not None:
                sel_model.deleteLater()
            if old_model is not None:
                old_model.deleteLater()

        if (config.get('completion', 'show') == 'always' and
                model.count() > 0):
            self.show()
        else:
            self.hide()

        for i in range(model.rowCount()):
            self.expand(model.index(i, 0))

        if pattern is not None:
            model.set_pattern(pattern)

        self._column_widths = model.srcmodel.COLUMN_WIDTHS
        self._resize_columns()
        self.maybe_resize_completion()

    @pyqtSlot()
    def maybe_resize_completion(self):
        """Emit the resize_completion signal if the config says so."""
        if config.get('completion', 'shrink'):
            self.resize_completion.emit()

    @pyqtSlot()
    def on_clear_completion_selection(self):
        """Clear the selection model when an item is activated."""
        self.hide()
        selmod = self.selectionModel()
        if selmod is not None:
            selmod.clearSelection()
            selmod.clearCurrentIndex()

    def selectionChanged(self, selected, deselected):
        """Extend selectionChanged to call completers selection_changed."""
        if not self._active:
            return
        super().selectionChanged(selected, deselected)
        self.selection_changed.emit(selected)

    def resizeEvent(self, e):
        """Extend resizeEvent to adjust column size."""
        super().resizeEvent(e)
        self._resize_columns()

    def showEvent(self, e):
        """Adjust the completion size and scroll when it's freshly shown."""
        self.resize_completion.emit()
        scrollbar = self.verticalScrollBar()
        if scrollbar is not None:
            scrollbar.setValue(scrollbar.minimum())
        super().showEvent(e)

    @cmdutils.register(instance='completion', hide=True,
                       modes=[usertypes.KeyMode.command], scope='window')
    def completion_item_del(self):
        """Delete the current completion item."""
        if not self.currentIndex().isValid():
            raise cmdexc.CommandError("No item selected!")
        try:
            self.model().srcmodel.delete_cur_item(self)
        except NotImplementedError:
            raise cmdexc.CommandError("Cannot delete this item.")
