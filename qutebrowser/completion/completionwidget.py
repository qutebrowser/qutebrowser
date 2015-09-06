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

"""Completion view for statusbar command section.

Defines a CompletionView which uses CompletionFiterModel and CompletionModel
subclasses to provide completions.
"""

from PyQt5.QtWidgets import QStyle, QTreeView, QSizePolicy
from PyQt5.QtCore import pyqtSlot, pyqtSignal, Qt, QItemSelectionModel

from qutebrowser.config import config, style
from qutebrowser.completion import completiondelegate, completer
from qutebrowser.completion.models import base
from qutebrowser.utils import qtutils, objreg, utils


class CompletionView(QTreeView):

    """The view showing available completions.

    Based on QTreeView but heavily customized so root elements show as category
    headers, and children show as flat list.

    Attributes:
        enabled: Whether showing the CompletionView is enabled.
        _win_id: The ID of the window this CompletionView is associated with.
        _height: The height to use for the CompletionView.
        _height_perc: Either None or a percentage if height should be relative.
        _delegate: The item delegate used.
        _column_widths: A list of column widths, in percent.

    Signals:
        resize_completion: Emitted when the completion should be resized.
    """

    # Drawing the item foreground will be done by CompletionItemDelegate, so we
    # don't define that in this stylesheet.
    STYLESHEET = """
        QTreeView {
            {{ font['completion'] }}
            {{ color['completion.bg'] }}
            alternate-background-color: {{ color['completion.alternate-bg'] }};
            outline: 0;
            border: 0px;
        }

        QTreeView::item:disabled {
            {{ color['completion.category.bg'] }}
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
            {{ color['completion.item.selected.bg'] }}
        }

        QTreeView:item::hover {
            border: 0px;
        }
    """

    # FIXME style scrollbar
    # https://github.com/The-Compiler/qutebrowser/issues/117

    resize_completion = pyqtSignal()

    def __init__(self, win_id, parent=None):
        super().__init__(parent)
        self._win_id = win_id
        objreg.register('completion', self, scope='window', window=win_id)
        cmd = objreg.get('status-command', scope='window', window=win_id)
        completer_obj = completer.Completer(cmd, win_id, self)
        completer_obj.next_prev_item.connect(self.on_next_prev_item)
        objreg.register('completer', completer_obj, scope='window',
                        window=win_id)
        self.enabled = config.get('completion', 'show')
        objreg.get('config').changed.connect(self.set_enabled)
        # FIXME handle new aliases.
        # objreg.get('config').changed.connect(self.init_command_completion)

        self._column_widths = base.BaseCompletionModel.COLUMN_WIDTHS

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

    @pyqtSlot(bool)
    def on_next_prev_item(self, prev):
        """Handle a tab press for the CompletionView.

        Select the previous/next item and write the new text to the
        statusbar.

        Called from the Completer's next_prev_item signal.

        Args:
            prev: True for prev item, False for next one.
        """
        if not self.isVisible():
            # No completion running at the moment, ignore keypress
            return
        idx = self._next_idx(prev)
        qtutils.ensure_valid(idx)
        self.selectionModel().setCurrentIndex(
            idx, QItemSelectionModel.ClearAndSelect |
            QItemSelectionModel.Rows)

    def set_model(self, model):
        """Switch completion to a new model.

        Called from on_update_completion().

        Args:
            model: The model to use.
        """
        old_model = self.model()
        sel_model = self.selectionModel()

        self.setModel(model)

        if sel_model is not None:
            sel_model.deleteLater()
        if old_model is not None:
            old_model.deleteLater()

        for i in range(model.rowCount()):
            self.expand(model.index(i, 0))

        self._column_widths = model.srcmodel.COLUMN_WIDTHS
        self._resize_columns()
        self.maybe_resize_completion()

    def set_pattern(self, pattern):
        """Set the completion pattern for the current model.

        Called from on_update_completion().

        Args:
            pattern: The filter pattern to set (what the user entered).
        """
        self.model().set_pattern(pattern)
        self.maybe_resize_completion()

    @pyqtSlot()
    def maybe_resize_completion(self):
        """Emit the resize_completion signal if the config says so."""
        if config.get('completion', 'shrink'):
            self.resize_completion.emit()

    @config.change_filter('completion', 'show')
    def set_enabled(self):
        """Update self.enabled when the config changed."""
        self.enabled = config.get('completion', 'show')

    @pyqtSlot()
    def on_clear_completion_selection(self):
        """Clear the selection model when an item is activated."""
        selmod = self.selectionModel()
        if selmod is not None:
            selmod.clearSelection()
            selmod.clearCurrentIndex()

    def selectionChanged(self, selected, deselected):
        """Extend selectionChanged to call completers selection_changed."""
        super().selectionChanged(selected, deselected)
        completer_obj = objreg.get('completer', scope='window',
                                   window=self._win_id)
        completer_obj.selection_changed(selected, deselected)

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
