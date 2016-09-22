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
            'show': 'always',
            'scrollbar-width': 12,
            'scrollbar-padding': 2,
            'shrink': False,
            'quick-complete': False,
            'height': '50%',
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
            'completion': 'Comic Sans Monospace',
            'completion.category': 'Comic Sans Monospace bold',
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
    completionview.set_model(model, 'foo')
    model.set_pattern.assert_called_with('foo')


def test_maybe_update_geometry(completionview, config_stub, qtbot):
    """Ensure completion is resized only if shrink is True."""
    with qtbot.assertNotEmitted(completionview.update_geometry):
        completionview._maybe_update_geometry()
    config_stub.data['completion']['shrink'] = True
    with qtbot.waitSignal(completionview.update_geometry):
        completionview._maybe_update_geometry()


@pytest.mark.parametrize('which, tree, expected', [
    ('next', [['Aa']], ['Aa', None, None]),
    ('prev', [['Aa']], ['Aa', None, None]),
    ('next', [['Aa'], ['Ba']], ['Aa', 'Ba', 'Aa']),
    ('prev', [['Aa'], ['Ba']], ['Ba', 'Aa', 'Ba']),
    ('next', [['Aa', 'Ab', 'Ac'], ['Ba', 'Bb'], ['Ca']],
        ['Aa', 'Ab', 'Ac', 'Ba', 'Bb', 'Ca', 'Aa']),
    ('prev', [['Aa', 'Ab', 'Ac'], ['Ba', 'Bb'], ['Ca']],
        ['Ca', 'Bb', 'Ba', 'Ac', 'Ab', 'Aa', 'Ca']),
    ('next', [[], ['Ba', 'Bb']], ['Ba', 'Bb', 'Ba']),
    ('prev', [[], ['Ba', 'Bb']], ['Bb', 'Ba', 'Bb']),
    ('next', [[], [], ['Ca', 'Cb']], ['Ca', 'Cb', 'Ca']),
    ('prev', [[], [], ['Ca', 'Cb']], ['Cb', 'Ca', 'Cb']),
    ('next', [['Aa'], []], ['Aa', None]),
    ('prev', [['Aa'], []], ['Aa', None]),
    ('next', [['Aa'], [], []], ['Aa', None]),
    ('prev', [['Aa'], [], []], ['Aa', None]),
    ('next', [['Aa'], [], ['Ca', 'Cb']], ['Aa', 'Ca', 'Cb', 'Aa']),
    ('prev', [['Aa'], [], ['Ca', 'Cb']], ['Cb', 'Ca', 'Aa', 'Cb']),
    ('next', [[]], [None, None]),
    ('prev', [[]], [None, None]),
    ('next-category', [['Aa']], ['Aa', None, None]),
    ('prev-category', [['Aa']], ['Aa', None, None]),
    ('next-category', [['Aa'], ['Ba']], ['Aa', 'Ba', 'Aa']),
    ('prev-category', [['Aa'], ['Ba']], ['Ba', 'Aa', 'Ba']),
    ('next-category', [['Aa', 'Ab', 'Ac'], ['Ba', 'Bb'], ['Ca']],
        ['Aa', 'Ba', 'Ca', 'Aa']),
    ('prev-category', [['Aa', 'Ab', 'Ac'], ['Ba', 'Bb'], ['Ca']],
        ['Ca', 'Ba', 'Aa', 'Ca']),
    ('next-category', [[], ['Ba', 'Bb']], ['Ba', None, None]),
    ('prev-category', [[], ['Ba', 'Bb']], ['Ba', None, None]),
    ('next-category', [[], [], ['Ca', 'Cb']], ['Ca', None, None]),
    ('prev-category', [[], [], ['Ca', 'Cb']], ['Ca', None, None]),
    ('next-category', [['Aa'], [], []], ['Aa', None, None]),
    ('prev-category', [['Aa'], [], []], ['Aa', None, None]),
    ('next-category', [['Aa'], [], ['Ca', 'Cb']], ['Aa', 'Ca', 'Aa']),
    ('prev-category', [['Aa'], [], ['Ca', 'Cb']], ['Ca', 'Aa', 'Ca']),
    ('next-category', [[]], [None, None]),
    ('prev-category', [[]], [None, None]),
])
def test_completion_item_focus(which, tree, expected, completionview, qtbot):
    """Test that on_next_prev_item moves the selection properly.

    Args:
        which: the direction in which to move the selection.
        tree: Each list represents a completion category, with each string
              being an item under that category.
        expected: expected argument from on_selection_changed for each
                  successive movement. None implies no signal should be
                  emitted.
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
    for entry in expected:
        if entry is None:
            with qtbot.assertNotEmitted(completionview.selection_changed):
                completionview.completion_item_focus(which)
        else:
            with qtbot.waitSignal(completionview.selection_changed) as sig:
                completionview.completion_item_focus(which)
                assert sig.args == [entry]


@pytest.mark.parametrize('which', ['next', 'prev', 'next-category',
                                   'prev-category'])
def test_completion_item_focus_no_model(which, completionview, qtbot):
    """Test that selectionChanged is not fired when the model is None.

    Validates #1812: help completion repeatedly completes
    """
    with qtbot.assertNotEmitted(completionview.selection_changed):
        completionview.completion_item_focus(which)
    model = base.BaseCompletionModel()
    filtermodel = sortfilter.CompletionFilterModel(model,
                                                   parent=completionview)
    completionview.set_model(filtermodel)
    completionview.set_model(None)
    with qtbot.assertNotEmitted(completionview.selection_changed):
        completionview.completion_item_focus(which)


@pytest.mark.parametrize('show', ['always', 'auto', 'never'])
@pytest.mark.parametrize('rows', [[], ['Aa'], ['Aa', 'Bb']])
@pytest.mark.parametrize('quick_complete', [True, False])
def test_completion_show(show, rows, quick_complete, completionview,
                         config_stub):
    """Test that the completion widget is shown at appropriate times.

    Args:
        show: The completion show config setting.
        rows: Each entry represents a completion category with only one item.
        quick_complete: The completion quick-complete config setting.
    """
    config_stub.data['completion']['show'] = show
    config_stub.data['completion']['quick-complete'] = quick_complete

    model = base.BaseCompletionModel()
    for name in rows:
        cat = QStandardItem()
        model.appendRow(cat)
        cat.appendRow(QStandardItem(name))
    filtermodel = sortfilter.CompletionFilterModel(model,
                                                   parent=completionview)

    assert not completionview.isVisible()
    completionview.set_model(filtermodel)
    assert completionview.isVisible() == (show == 'always' and len(rows) > 0)
    completionview.completion_item_focus('next')
    expected = (show != 'never' and len(rows) > 0 and
                not (quick_complete and len(rows) == 1))
    assert completionview.isVisible() == expected
    completionview.set_model(None)
    completionview.completion_item_focus('next')
    assert not completionview.isVisible()
