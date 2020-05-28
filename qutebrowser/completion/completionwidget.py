# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import typing

from PyQt5.QtWidgets import QTreeView, QSizePolicy, QStyleFactory, QWidget
from PyQt5.QtCore import pyqtSlot, pyqtSignal, Qt, QItemSelectionModel, QSize

from qutebrowser.config import config, stylesheet
from qutebrowser.completion import completiondelegate
from qutebrowser.utils import utils, usertypes, debug, log
from qutebrowser.api import cmdutils
if typing.TYPE_CHECKING:
    from qutebrowser.mainwindow.statusbar import command


class CompletionView(QTreeView):

    """The view showing available completions.

    Based on QTreeView but heavily customized so root elements show as category
    headers, and children show as flat list.

    Attributes:
        pattern: Current filter pattern, used for highlighting.
        _win_id: The ID of the window this CompletionView is associated with.
        _height: The height to use for the CompletionView.
        _height_perc: Either None or a percentage if height should be relative.
        _delegate: The item delegate used.
        _column_widths: A list of column widths, in percent.
        _active: Whether a selection is active.
        _cmd: The statusbar Command object.

    Signals:
        update_geometry: Emitted when the completion should be resized.
        selection_changed: Emitted when the completion item selection changes.
    """

    # Drawing the item foreground will be done by CompletionItemDelegate, so we
    # don't define that in this stylesheet.
    STYLESHEET = """
        QTreeView {
            font: {{ conf.fonts.completion.entry }};
            background-color: {{ conf.colors.completion.even.bg }};
            alternate-background-color: {{ conf.colors.completion.odd.bg }};
            outline: 0;
            border: 0px;
        }

        QTreeView::item:disabled {
            background-color: {{ conf.colors.completion.category.bg }};
            border-top: 1px solid
                {{ conf.colors.completion.category.border.top }};
            border-bottom: 1px solid
                {{ conf.colors.completion.category.border.bottom }};
        }

        QTreeView::item:selected, QTreeView::item:selected:hover {
            border-top: 1px solid
                {{ conf.colors.completion.item.selected.border.top }};
            border-bottom: 1px solid
                {{ conf.colors.completion.item.selected.border.bottom }};
            background-color: {{ conf.colors.completion.item.selected.bg }};
        }

        QTreeView:item::hover {
            border: 0px;
        }

        QTreeView QScrollBar {
            width: {{ conf.completion.scrollbar.width }}px;
            background: {{ conf.colors.completion.scrollbar.bg }};
        }

        QTreeView QScrollBar::handle {
            background: {{ conf.colors.completion.scrollbar.fg }};
            border: {{ conf.completion.scrollbar.padding }}px solid
                    {{ conf.colors.completion.scrollbar.bg }};
            min-height: 10px;
        }

        QTreeView QScrollBar::sub-line, QScrollBar::add-line {
            border: none;
            background: none;
        }
    """

    update_geometry = pyqtSignal()
    selection_changed = pyqtSignal(str)

    def __init__(self, *,
                 cmd: 'command.Command',
                 win_id: int,
                 parent: QWidget = None) -> None:
        super().__init__(parent)
        self.pattern = None  # type: typing.Optional[str]
        self._win_id = win_id
        self._cmd = cmd
        self._active = False

        config.instance.changed.connect(self._on_config_changed)

        self._delegate = completiondelegate.CompletionItemDelegate(self)
        self.setItemDelegate(self._delegate)
        self.setStyle(QStyleFactory.create('Fusion'))
        stylesheet.set_register(self)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setHeaderHidden(True)
        self.setAlternatingRowColors(True)
        self.setIndentation(0)
        self.setItemsExpandable(False)
        self.setExpandsOnDoubleClick(False)
        self.setAnimated(False)
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
        # https://github.com/qutebrowser/qutebrowser/issues/118

    def __repr__(self):
        return utils.get_repr(self)

    @pyqtSlot(str)
    def _on_config_changed(self, option):
        if option in ['completion.height', 'completion.shrink']:
            self.update_geometry.emit()

    def _resize_columns(self):
        """Resize the completion columns based on column_widths."""
        if self.model() is None:
            return
        width = self.size().width()
        column_widths = self.model().column_widths
        pixel_widths = [(width * perc // 100) for perc in column_widths]

        delta = self.verticalScrollBar().sizeHint().width()
        if pixel_widths[-1] > delta:
            pixel_widths[-1] -= delta
        else:
            pixel_widths[-2] -= delta

        for i, w in enumerate(pixel_widths):
            assert w >= 0, i
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

        raise utils.Unreachable

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

        raise utils.Unreachable

    @cmdutils.register(instance='completion',
                       modes=[usertypes.KeyMode.command], scope='window')
    @cmdutils.argument('which', choices=['next', 'prev', 'next-category',
                                         'prev-category'])
    @cmdutils.argument('history', flag='H')
    def completion_item_focus(self, which, history=False):
        """Shift the focus of the completion menu to another item.

        Args:
            which: 'next', 'prev', 'next-category', or 'prev-category'.
            history: Navigate through command history if no text was typed.
        """
        if history:
            if (self._cmd.text() == ':' or self._cmd.history.is_browsing() or
                    not self._active):
                if which == 'next':
                    self._cmd.command_history_next()
                    return
                elif which == 'prev':
                    self._cmd.command_history_prev()
                    return
                else:
                    raise cmdutils.CommandError("Can't combine --history with "
                                                "{}!".format(which))

        if not self._active:
            return

        selmodel = self.selectionModel()
        indices = {
            'next': self._next_idx(upwards=False),
            'prev': self._next_idx(upwards=True),
            'next-category': self._next_category_idx(upwards=False),
            'prev-category': self._next_category_idx(upwards=True),
        }
        idx = indices[which]

        if not idx.isValid():
            return

        selmodel.setCurrentIndex(
            idx,
            QItemSelectionModel.ClearAndSelect |  # type: ignore[arg-type]
            QItemSelectionModel.Rows)

        # if the last item is focused, try to fetch more
        if idx.row() == self.model().rowCount(idx.parent()) - 1:
            self.expandAll()

        count = self.model().count()
        if count == 0:
            self.hide()
        elif count == 1 and config.val.completion.quick:
            self.hide()
        elif config.val.completion.show == 'auto':
            self.show()

    def set_model(self, model):
        """Switch completion to a new model.

        Called from on_update_completion().

        Args:
            model: The model to use.
        """
        if self.model() is not None and model is not self.model():
            self.model().deleteLater()
            self.selectionModel().deleteLater()

        self.setModel(model)

        if model is None:
            self._active = False
            self.hide()
            return

        model.setParent(self)
        self._active = True
        self.pattern = None
        self._maybe_show()

        self._resize_columns()
        for i in range(model.rowCount()):
            self.expand(model.index(i, 0))

    def set_pattern(self, pattern: str) -> None:
        """Set the pattern on the underlying model."""
        if not self.model():
            return
        if self.pattern == pattern:
            # no changes, abort
            log.completion.debug(
                "Ignoring pattern set request as pattern has not changed.")
            return
        self.pattern = pattern
        with debug.log_time(log.completion, 'Set pattern {}'.format(pattern)):
            self.model().set_pattern(pattern)
            self.selectionModel().clear()
            self._maybe_update_geometry()
            self._maybe_show()

    def _maybe_show(self):
        if (config.val.completion.show == 'always' and
                self.model().count() > 0):
            self.show()
        else:
            self.hide()

    def _maybe_update_geometry(self):
        """Emit the update_geometry signal if the config says so."""
        if config.val.completion.shrink:
            self.update_geometry.emit()

    @pyqtSlot()
    def on_clear_completion_selection(self):
        """Clear the selection model when an item is activated."""
        self.hide()
        selmod = self.selectionModel()
        if selmod is not None:
            selmod.clearSelection()
            selmod.clearCurrentIndex()

    def sizeHint(self):
        """Get the completion size according to the config."""
        # Get the configured height/percentage.
        confheight = str(config.val.completion.height)
        if confheight.endswith('%'):
            perc = int(confheight.rstrip('%'))
            height = self.window().height() * perc // 100
        else:
            height = int(confheight)
        # Shrink to content size if needed and shrinking is enabled
        if config.val.completion.shrink:
            contents_height = (
                self.viewportSizeHint().height() +
                self.horizontalScrollBar().sizeHint().height())
            if contents_height <= height:
                height = contents_height
        # The width isn't really relevant as we're expanding anyways.
        return QSize(-1, height)

    def selectionChanged(self, selected, deselected):
        """Extend selectionChanged to call completers selection_changed."""
        if not self._active:
            return
        super().selectionChanged(selected, deselected)
        indexes = selected.indexes()
        if not indexes:
            return
        data = str(self.model().data(indexes[0]))
        self.selection_changed.emit(data)

    def resizeEvent(self, e):
        """Extend resizeEvent to adjust column size."""
        super().resizeEvent(e)
        self._resize_columns()

    def showEvent(self, e):
        """Adjust the completion size and scroll when it's freshly shown."""
        self.update_geometry.emit()
        scrollbar = self.verticalScrollBar()
        if scrollbar is not None:
            scrollbar.setValue(scrollbar.minimum())
        super().showEvent(e)

    @cmdutils.register(instance='completion',
                       modes=[usertypes.KeyMode.command], scope='window')
    def completion_item_del(self):
        """Delete the current completion item."""
        index = self.currentIndex()
        if not index.isValid():
            raise cmdutils.CommandError("No item selected!")
        self.model().delete_cur_item(index)

    @cmdutils.register(instance='completion',
                       modes=[usertypes.KeyMode.command], scope='window')
    def completion_item_yank(self, sel=False):
        """Yank the current completion item into the clipboard.

        Args:
            sel: Use the primary selection instead of the clipboard.
        """
        text = self._cmd.selectedText()
        if not text:
            index = self.currentIndex()
            if not index.isValid():
                raise cmdutils.CommandError("No item selected!")
            text = self.model().data(index)
        utils.set_clipboard(text, selection=sel)
