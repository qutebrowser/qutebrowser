# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2020 Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
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

from unittest import mock

import pytest

from qutebrowser.completion import completionwidget
from qutebrowser.completion.models import completionmodel, listcategory
from qutebrowser.api import cmdutils


@pytest.fixture
def completionview(qtbot, status_command_stub, config_stub, win_registry,
                   mocker):
    """Create the CompletionView used for testing."""
    # mock the Completer that the widget creates in its constructor
    mocker.patch('qutebrowser.completion.completer.Completer', autospec=True)
    mocker.patch(
        'qutebrowser.completion.completiondelegate.CompletionItemDelegate',
        new=lambda *_: None)
    view = completionwidget.CompletionView(cmd=status_command_stub, win_id=0)
    qtbot.addWidget(view)
    return view


def test_set_model(completionview):
    """Ensure set_model actually sets the model and expands all categories."""
    model = completionmodel.CompletionModel()
    for _i in range(3):
        model.add_category(listcategory.ListCategory('', [('foo',)]))
    completionview.set_model(model)
    assert completionview.model() is model
    for i in range(3):
        assert completionview.isExpanded(model.index(i, 0))


def test_set_pattern(completionview):
    model = completionmodel.CompletionModel()
    model.set_pattern = mock.Mock(spec=[])
    completionview.set_model(model)
    completionview.set_pattern('foo')
    model.set_pattern.assert_called_with('foo')
    assert not completionview.selectionModel().currentIndex().isValid()


def test_set_pattern_no_model(completionview):
    """Ensure that setting a pattern with no model does not fail."""
    completionview.set_pattern('foo')


def test_maybe_update_geometry(completionview, config_stub, qtbot):
    """Ensure completion is resized only if shrink is True."""
    with qtbot.assertNotEmitted(completionview.update_geometry):
        completionview._maybe_update_geometry()
    config_stub.val.completion.shrink = True
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
    model = completionmodel.CompletionModel()
    for catdata in tree:
        cat = listcategory.ListCategory('', ((x,) for x in catdata))
        model.add_category(cat)
    completionview.set_model(model)
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
    model = completionmodel.CompletionModel()
    completionview.set_model(model)
    completionview.set_model(None)
    with qtbot.assertNotEmitted(completionview.selection_changed):
        completionview.completion_item_focus(which)


def test_completion_item_focus_fetch(completionview, qtbot):
    """Test that on_next_prev_item moves the selection properly.

    Args:
        which: the direction in which to move the selection.
        tree: Each list represents a completion category, with each string
              being an item under that category.
        expected: expected argument from on_selection_changed for each
                  successive movement. None implies no signal should be
                  emitted.
    """
    model = completionmodel.CompletionModel()
    cat = mock.Mock(spec=[
        'layoutChanged', 'layoutAboutToBeChanged', 'canFetchMore',
        'fetchMore', 'rowCount', 'index', 'data'])
    cat.canFetchMore = lambda *_: True
    cat.rowCount = lambda *_: 2
    cat.fetchMore = mock.Mock()
    model.add_category(cat)
    completionview.set_model(model)
    # clear the fetchMore call that happens on set_model
    cat.reset_mock()

    # not at end, fetchMore shouldn't be called
    completionview.completion_item_focus('next')
    assert not cat.fetchMore.called

    # at end, fetchMore should be called
    completionview.completion_item_focus('next')
    assert cat.fetchMore.called


@pytest.mark.parametrize('show', ['always', 'auto', 'never'])
@pytest.mark.parametrize('rows', [[], ['Aa'], ['Aa', 'Bb']])
@pytest.mark.parametrize('quick_complete', [True, False])
def test_completion_show(show, rows, quick_complete, completionview,
                         config_stub):
    """Test that the completion widget is shown at appropriate times.

    Args:
        show: The completion show config setting.
        rows: Each entry represents a completion category with only one item.
        quick_complete: The `completion.quick` config setting.
    """
    config_stub.val.completion.show = show
    config_stub.val.completion.quick = quick_complete

    model = completionmodel.CompletionModel()
    for name in rows:
        cat = listcategory.ListCategory('', [(name,)])
        model.add_category(cat)

    assert not completionview.isVisible()
    completionview.set_model(model)
    assert completionview.isVisible() == (show == 'always' and len(rows) > 0)
    completionview.completion_item_focus('next')
    expected = (show != 'never' and len(rows) > 0 and
                not (quick_complete and len(rows) == 1))
    assert completionview.isVisible() == expected
    completionview.set_model(None)
    completionview.completion_item_focus('next')
    assert not completionview.isVisible()


def test_completion_item_del(completionview):
    """Test that completion_item_del invokes delete_cur_item in the model."""
    func = mock.Mock(spec=[])
    model = completionmodel.CompletionModel()
    cat = listcategory.ListCategory('', [('foo', 'bar')], delete_func=func)
    model.add_category(cat)
    completionview.set_model(model)
    completionview.completion_item_focus('next')
    completionview.completion_item_del()
    func.assert_called_once_with(['foo', 'bar'])


def test_completion_item_del_no_selection(completionview):
    """Test that completion_item_del with an invalid index."""
    func = mock.Mock(spec=[])
    model = completionmodel.CompletionModel()
    cat = listcategory.ListCategory('', [('foo',)], delete_func=func)
    model.add_category(cat)
    completionview.set_model(model)
    with pytest.raises(cmdutils.CommandError, match='No item selected!'):
        completionview.completion_item_del()
    func.assert_not_called()


@pytest.mark.parametrize('sel', [True, False])
def test_completion_item_yank(completionview, mocker, sel):
    """Test that completion_item_yank invokes delete_cur_item in the model."""
    m = mocker.patch(
        'qutebrowser.completion.completionwidget.utils',
        autospec=True)
    model = completionmodel.CompletionModel()
    cat = listcategory.ListCategory('', [('foo', 'bar')])
    model.add_category(cat)

    completionview.set_model(model)
    completionview.completion_item_focus('next')
    completionview.completion_item_yank(sel)

    m.set_clipboard.assert_called_once_with('foo', sel)


@pytest.mark.parametrize('sel', [True, False])
def test_completion_item_yank_selected(completionview, status_command_stub,
                                       mocker, sel):
    """Test that completion_item_yank yanks selected text."""
    m = mocker.patch(
        'qutebrowser.completion.completionwidget.utils',
        autospec=True)
    model = completionmodel.CompletionModel()
    cat = listcategory.ListCategory('', [('foo', 'bar')])
    model.add_category(cat)

    completionview.set_model(model)
    completionview.completion_item_focus('next')

    status_command_stub.selectedText = mock.Mock(return_value='something')
    completionview.completion_item_yank(sel)

    m.set_clipboard.assert_called_once_with('something', sel)


def test_resize_no_model(completionview, qtbot):
    """Ensure no crash if resizeEvent is triggered with no model (#2854)."""
    completionview.resizeEvent(None)
