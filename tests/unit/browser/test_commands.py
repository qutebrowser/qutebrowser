# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import collections

import pytest

from qutebrowser.browser import commands
from qutebrowser.mainwindow import tabbedbrowser
from qutebrowser.utils import objreg
from qutebrowser.keyinput import modeman


ObjectsRet = collections.namedtuple('Dispatcher', ['tb', 'cd'])

pytestmark = pytest.mark.usefixtures('cookiejar_and_cache')


@pytest.yield_fixture
def objects(qtbot, default_config, key_config_stub, tab_registry,
            host_blocker_stub):
    """Fixture providing a CommandDispatcher and a fake TabbedBrowser."""
    win_id = 0
    modeman.init(win_id, parent=None)
    tabbed_browser = tabbedbrowser.TabbedBrowser(win_id)
    qtbot.add_widget(tabbed_browser)
    objreg.register('tabbed-browser', tabbed_browser, scope='window',
                    window=win_id)
    dispatcher = commands.CommandDispatcher(win_id, tabbed_browser)
    objreg.register('command-dispatcher', dispatcher, scope='window',
                    window=win_id)
    yield ObjectsRet(tabbed_browser, dispatcher)


@pytest.mark.skipif(True, reason="Work in progress")
def test_openurl(objects):
    objects.cd.openurl('localhost')
