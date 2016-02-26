# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Alexander Cogneau <alexander.cogneau@gmail.com>
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

"""Tests for qutebrowser.completion.models column widths."""

import pytest

from qutebrowser.completion.models.base import BaseCompletionModel
from qutebrowser.completion.models.configmodel import (
    SettingOptionCompletionModel, SettingSectionCompletionModel,
    SettingValueCompletionModel)
from qutebrowser.completion.models.miscmodels import (
    CommandCompletionModel, HelpCompletionModel, QuickmarkCompletionModel,
    BookmarkCompletionModel, SessionCompletionModel)
from qutebrowser.completion.models.urlmodel import UrlCompletionModel


class TestColumnWidths:

    """Tests for the column widths of the completion models."""

    CLASSES = [BaseCompletionModel, SettingOptionCompletionModel,
               SettingOptionCompletionModel, SettingSectionCompletionModel,
               SettingValueCompletionModel, CommandCompletionModel,
               HelpCompletionModel, QuickmarkCompletionModel,
               BookmarkCompletionModel, SessionCompletionModel,
               UrlCompletionModel]

    @pytest.mark.parametrize("model", CLASSES)
    def test_list_size(self, model):
        """Test if there are 3 items in the COLUMN_WIDTHS property."""
        assert len(model.COLUMN_WIDTHS) == 3

    @pytest.mark.parametrize("model", CLASSES)
    def test_column_width_sum(self, model):
        """Test if the sum of the widths asserts to 100."""
        assert sum(model.COLUMN_WIDTHS) == 100
