# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
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

"""Tests for the CompletionView Object."""

import unittest.mock

import pytest
from PyQt5.QtGui import QStandardItem, QColor

from qutebrowser.completion import completionwidget
from qutebrowser.completion.models import base, sortfilter


@pytest.fixture
def completionview(qtbot, status_command_stub, config_stub, win_registry,
                   mocker):
    """Create the CompletionView used for testing."""
    config_stub.data = {
        'completion': {
            'show': True,
            'auto-open': True,
            'scrollbar-width': 12,
            'scrollbar-padding': 2,
            'shrink': False,
        },
        'colors': {
            'completion.fg': QColor(),
            'completion.bg': QColor(),
            'completion.alternate-bg': QColor(),
            'completion.category.fg': QColor(),
            'completion.category.bg': QColor(),
            'completion.category.border.top': QColor(),
            'completion.category.border.bottom': QColor(),
            'completion.item.selected.fg': QColor(),
            'completion.item.selected.bg': QColor(),
            'completion.item.selected.border.top': QColor(),
            'completion.item.selected.border.bottom': QColor(),
            'completion.match.fg': QColor(),
            'completion.scrollbar.fg': QColor(),
            'completion.scrollbar.bg': QColor(),
        },
        'fonts': {
            'completion': 'Comic Sans Monospace'
        }
    }
    # mock the Completer that the widget creates in its constructor
    mocker.patch('qutebrowser.completion.completer.Completer', autospec=True)
    view = completionwidget.CompletionView(win_id=0)
    qtbot.addWidget(view)
    return view


def test_set_model(completionview):
    """Ensure set_model actually sets the model and expands all categories."""
    model = base.BaseCompletionModel()
    filtermodel = sortfilter.CompletionFilterModel(model)
    for i in range(3):
        model.appendRow(QStandardItem(str(i)))
    completionview.set_model(filtermodel)
    assert completionview.model() is filtermodel
    for i in range(model.rowCount()):
        assert completionview.isExpanded(filtermodel.index(i, 0))


def test_set_pattern(completionview):
    model = sortfilter.CompletionFilterModel(base.BaseCompletionModel())
    model.set_pattern = unittest.mock.Mock()
    completionview.set_model(model)
    completionview.set_pattern('foo')
    model.set_pattern.assert_called_with('foo')


def test_maybe_resize_completion(completionview, config_stub, qtbot):
    """Ensure completion is resized only if shrink is True."""
    with qtbot.assertNotEmitted(completionview.resize_completion):
        completionview.maybe_resize_completion()
    config_stub.data = {'completion': {'shrink': True}}
    with qtbot.waitSignal(completionview.resize_completion):
        completionview.maybe_resize_completion()


@pytest.mark.parametrize('tree, count, expected', [
    ([['Aa']], 1, 'Aa'),
    ([['Aa']], -1, 'Aa'),
    ([['Aa'], ['Ba']], 1, 'Aa'),
    ([['Aa'], ['Ba']], -1, 'Ba'),
    ([['Aa'], ['Ba']], 2, 'Ba'),
    ([['Aa'], ['Ba']], -2, 'Aa'),
    ([['Aa', 'Ab', 'Ac'], ['Ba', 'Bb'], ['Ca']], 3, 'Ac'),
    ([['Aa', 'Ab', 'Ac'], ['Ba', 'Bb'], ['Ca']], 4, 'Ba'),
    ([['Aa', 'Ab', 'Ac'], ['Ba', 'Bb'], ['Ca']], 6, 'Ca'),
    ([['Aa', 'Ab', 'Ac'], ['Ba', 'Bb'], ['Ca']], 7, 'Aa'),
    ([['Aa', 'Ab', 'Ac'], ['Ba', 'Bb'], ['Ca']], -1, 'Ca'),
    ([['Aa', 'Ab', 'Ac'], ['Ba', 'Bb'], ['Ca']], -2, 'Bb'),
    ([['Aa', 'Ab', 'Ac'], ['Ba', 'Bb'], ['Ca']], -4, 'Ac'),
    ([[], ['Ba', 'Bb']], 1, 'Ba'),
    ([[], ['Ba', 'Bb']], -1, 'Bb'),
    ([[], [], ['Ca', 'Cb']], 1, 'Ca'),
    ([[], [], ['Ca', 'Cb']], -1, 'Cb'),
    ([['Aa'], []], 1, 'Aa'),
    ([['Aa'], []], -1, 'Aa'),
    ([['Aa'], [], []], 1, 'Aa'),
    ([['Aa'], [], []], -1, 'Aa'),
])
def test_completion_item_next_prev(tree, count, expected, completionview):
    """Test that on_next_prev_item moves the selection properly.

    Args:
        tree: Each list represents a completion category, with each string
              being an item under that category.
        count: Number of times to go forward (or back if negative).
        expected: item data that should be selected after going back/forward.
    """
    model = base.BaseCompletionModel()
    for catdata in tree:
        cat = QStandardItem()
        model.appendRow(cat)
        for name in catdata:
            cat.appendRow(QStandardItem(name))
    filtermodel = sortfilter.CompletionFilterModel(model,
                                                   parent=completionview)
    completionview.set_model(filtermodel)
    if count < 0:
        for _ in range(-count):
            completionview.completion_item_prev()
    else:
        for _ in range(count):
            completionview.completion_item_next()
    idx = completionview.selectionModel().currentIndex()
    assert filtermodel.data(idx) == expected
