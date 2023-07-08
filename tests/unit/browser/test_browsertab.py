# Copyright 2022 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

import pytest

from qutebrowser.qt.core import QUrl
from qutebrowser.browser import browsertab


class TestAction:

    def test_run_string_valid(self, qtbot, web_tab):
        url_1 = QUrl("qute://testdata/data/backforward/1.txt")
        url_2 = QUrl("qute://testdata/data/backforward/2.txt")

        with qtbot.wait_signal(web_tab.load_finished):
            web_tab.load_url(url_1)
        with qtbot.wait_signal(web_tab.load_finished):
            web_tab.load_url(url_2)

        assert web_tab.url() == url_2
        with qtbot.wait_signal(web_tab.load_finished):
            web_tab.action.run_string("Back")
        assert web_tab.url() == url_1

    @pytest.mark.parametrize("member", ["blah", "PermissionUnknown"])
    def test_run_string_invalid(self, qtbot, web_tab, member):
        with pytest.raises(
            browsertab.WebTabError,
            match=f"{member} is not a valid web action!",
        ):
            web_tab.action.run_string(member)
