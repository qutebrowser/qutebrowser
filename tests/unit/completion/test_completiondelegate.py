# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018 Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
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

from PyQt5.QtCore import QModelIndex
from PyQt5.QtWidgets import QStyleOptionViewItem, QStyledItemDelegate
from PyQt5.QtGui import QPainter

from qutebrowser.completion import completiondelegate


@pytest.fixture
def painter():
    """Create the CompletionView used for testing."""
    return mock.Mock(spec=QPainter)


def _qt_mock(klass, mocker):
    m = mocker.patch(
        'qutebrowser.completion.completiondelegate.{}'.format(klass),
        autospec=True)
    return m


@pytest.fixture
def mock_style_option(mocker):
    """Create the CompletionView used for testing."""
    return _qt_mock('QStyleOptionViewItem', mocker)


@pytest.fixture
def mock_text_document(mocker):
    """Create the CompletionView used for testing."""
    return _qt_mock('QTextDocument', mocker)


@pytest.fixture
def view():
    return mock.Mock()


@pytest.fixture
def delegate(mock_style_option, mock_text_document, config_stub, mocker, view):
    _qt_mock('QStyle', mocker)
    _qt_mock('QTextOption', mocker)
    _qt_mock('QAbstractTextDocumentLayout', mocker)
    completiondelegate._cached_stylesheet = mock.Mock()
    delegate = completiondelegate.CompletionItemDelegate()
    parent = mock.Mock()
    parent.return_value = view
    delegate.parent = parent
    delegate.initStyleOption = mock.Mock()
    delegate.setTextDirection = mock.Mock()
    return delegate


@pytest.mark.parametrize('pat,txt_in,txt_out', [
    # { and } represent the open/close html tags for highlighting
    ('foo', 'foo', '{foo}'),
    ('foo', 'foobar', '{foo}bar'),
    ('foo', 'barfoo', 'bar{foo}'),
    ('foo', 'barfoobaz', 'bar{foo}baz'),
    ('foo', 'barfoobazfoo', 'bar{foo}baz{foo}'),
    ('foo', 'foofoo', '{foo}{foo}'),
    ('a b', 'cadb', 'c{a}d{b}'),
    ('foo', '<foo>', '&lt;{foo}&gt;'),
    ('<a>', "<a>bc", '{&lt;a&gt;}bc'),

    # https://github.com/qutebrowser/qutebrowser/issues/4199
    ('foo', "'foo'", "'{foo}'"),
    ('x', "'x'", "'{x}'"),
])
def test_paint(delegate, painter, view, mock_style_option, mock_text_document,
               pat, txt_in, txt_out):
    """Ensure set_model actually sets the model and expands all categories."""
    view.pattern = pat
    mock_style_option().text = txt_in
    index = mock.Mock()
    index.column.return_value = 0
    index.model.return_value.columns_to_filter.return_value = [0]
    opt = mock_style_option()
    delegate.paint(painter, opt, index)
    expected = txt_out.replace(
        '{', '<span class="highlight">'
    ).replace(
        '}', '</span>'
    )
    mock_text_document().setHtml.assert_called_once_with(expected)
