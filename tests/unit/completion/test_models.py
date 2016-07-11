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

"""Tests for completion models."""

import collections
from datetime import datetime

import pytest
from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import QTreeView

from qutebrowser.completion.models import miscmodels, urlmodel, configmodel
from qutebrowser.browser.webkit import history
from qutebrowser.config import sections, value


def _get_completions(model):
    """Collect all the completion entries of a model, organized by category.

    The result is a list of form:
    [
        (CategoryName: [(name, desc, misc), ...]),
        (CategoryName: [(name, desc, misc), ...]),
        ...
    ]
    """
    completions = []
    for i in range(0, model.rowCount()):
        category = model.item(i)
        entries = []
        for j in range(0, category.rowCount()):
            name = category.child(j, 0)
            desc = category.child(j, 1)
            misc = category.child(j, 2)
            entries.append((name.text(), desc.text(), misc.text()))
        completions.append((category.text(), entries))
    return completions


def _patch_cmdutils(monkeypatch, stubs, symbol):
    """Patch the cmdutils module to provide fake commands."""
    cmd_utils = stubs.FakeCmdUtils({
        'stop': stubs.FakeCommand(name='stop', desc='stop qutebrowser'),
        'drop': stubs.FakeCommand(name='drop', desc='drop all user data'),
        'roll': stubs.FakeCommand(name='roll', desc='never gonna give you up'),
        'hide': stubs.FakeCommand(name='hide', hide=True),
        'depr': stubs.FakeCommand(name='depr', deprecated=True),
    })
    monkeypatch.setattr(symbol, cmd_utils)


def _patch_configdata(monkeypatch, stubs, symbol):
    """Patch the configdata module to provide fake data."""
    data = collections.OrderedDict([
        ('general', sections.KeyValue(
            ('time',
                value.SettingValue(stubs.FakeConfigType('fast', 'slow'),
                                   default='slow'),
                'Is an illusion.\n\nLunchtime doubly so.'),
            ('volume',
                value.SettingValue(stubs.FakeConfigType('0', '11'),
                                   default='11'),
                'Goes to 11'))),
        ('ui', sections.KeyValue(
            ('gesture',
                value.SettingValue(stubs.FakeConfigType(('on', 'off')),
                                   default='off'),
                'Waggle your hands to control qutebrowser'),
            ('mind',
                value.SettingValue(stubs.FakeConfigType(('on', 'off')),
                                   default='off'),
                'Enable mind-control ui (experimental)'),
            ('voice',
                value.SettingValue(stubs.FakeConfigType(('on', 'off')),
                                   default='off'),
                'Whether to respond to voice commands'))),
    ])
    monkeypatch.setattr(symbol, data)


def _patch_config_section_desc(monkeypatch, stubs, symbol):
    """Patch the configdata module to provide fake SECTION_DESC."""
    section_desc = {
        'general': 'General/miscellaneous options.',
        'ui': 'General options related to the user interface.',
    }
    monkeypatch.setattr(symbol, section_desc)


def _mock_view_index(model, category_idx, child_idx, qtbot):
    """Create a tree view from a model and set the current index.

    Args:
        model: model to create a fake view for.
        category_idx: index of the category to select.
        child_idx: index of the child item under that category to select.
    """
    view = QTreeView()
    qtbot.add_widget(view)
    view.setModel(model)
    idx = model.indexFromItem(model.item(category_idx).child(child_idx))
    view.setCurrentIndex(idx)
    return view


@pytest.fixture
def quickmarks(quickmark_manager_stub):
    """Pre-populate the quickmark-manager stub with some quickmarks."""
    quickmark_manager_stub.marks = collections.OrderedDict([
        ('aw', 'https://wiki.archlinux.org'),
        ('ddg', 'https://duckduckgo.com'),
        ('wiki', 'https://wikipedia.org'),
    ])
    return quickmark_manager_stub


@pytest.fixture
def bookmarks(bookmark_manager_stub):
    """Pre-populate the bookmark-manager stub with some quickmarks."""
    bookmark_manager_stub.marks = collections.OrderedDict([
        ('https://github.com', 'GitHub'),
        ('https://python.org', 'Welcome to Python.org'),
        ('http://qutebrowser.org', 'qutebrowser | qutebrowser'),
    ])
    return bookmark_manager_stub


@pytest.fixture
def web_history(stubs, web_history_stub):
    """Pre-populate the web-history stub with some history entries."""
    web_history_stub.history_dict = collections.OrderedDict([
        ('http://qutebrowser.org', history.Entry(
            datetime(2015, 9, 5).timestamp(),
            QUrl('http://qutebrowser.org'), 'qutebrowser | qutebrowser')),
        ('https://python.org', history.Entry(
            datetime(2016, 3, 8).timestamp(),
            QUrl('https://python.org'), 'Welcome to Python.org')),
        ('https://github.com', history.Entry(
            datetime(2016, 5, 1).timestamp(),
            QUrl('https://github.com'), 'GitHub')),
    ])
    return web_history_stub


def test_command_completion(monkeypatch, stubs, config_stub, key_config_stub):
    """Test the results of command completion.

    Validates that:
        - only non-hidden and non-deprecated commands are included
        - commands are sorted by name
        - the command description is shown in the desc column
        - the binding (if any) is shown in the misc column
        - aliases are included
    """
    _patch_cmdutils(monkeypatch, stubs,
                    'qutebrowser.completion.models.miscmodels.cmdutils')
    config_stub.data['aliases'] = {'rock': 'roll'}
    key_config_stub.set_bindings_for('normal', {'s': 'stop', 'rr': 'roll'})
    actual = _get_completions(miscmodels.CommandCompletionModel())
    assert actual == [
        ("Commands", [
            ('drop', 'drop all user data', ''),
            ('rock', "Alias for 'roll'", ''),
            ('roll', 'never gonna give you up', 'rr'),
            ('stop', 'stop qutebrowser', 's')
        ])
    ]


def test_help_completion(monkeypatch, stubs):
    """Test the results of command completion.

    Validates that:
        - only non-hidden and non-deprecated commands are included
        - commands are sorted by name
        - the command description is shown in the desc column
        - the binding (if any) is shown in the misc column
        - aliases are included
        - only the first line of a multiline description is shown
    """
    module = 'qutebrowser.completion.models.miscmodels'
    _patch_cmdutils(monkeypatch, stubs, module + '.cmdutils')
    _patch_configdata(monkeypatch, stubs, module + '.configdata.DATA')
    actual = _get_completions(miscmodels.HelpCompletionModel())
    assert actual == [
        ("Commands", [
            (':drop', 'drop all user data', ''),
            (':roll', 'never gonna give you up', ''),
            (':stop', 'stop qutebrowser', '')
        ]),
        ("Settings", [
            ('general->time', 'Is an illusion.', ''),
            ('general->volume', 'Goes to 11', ''),
            ('ui->gesture', 'Waggle your hands to control qutebrowser', ''),
            ('ui->mind', 'Enable mind-control ui (experimental)', ''),
            ('ui->voice', 'Whether to respond to voice commands', ''),
        ])
    ]


def test_quickmark_completion(quickmarks):
    """Test the results of quickmark completion."""
    actual = _get_completions(miscmodels.QuickmarkCompletionModel())
    assert actual == [
        ("Quickmarks", [
            ('aw', 'https://wiki.archlinux.org', ''),
            ('ddg', 'https://duckduckgo.com', ''),
            ('wiki', 'https://wikipedia.org', ''),
        ])
    ]


def test_bookmark_completion(bookmarks):
    """Test the results of bookmark completion."""
    actual = _get_completions(miscmodels.BookmarkCompletionModel())
    assert actual == [
        ("Bookmarks", [
            ('https://github.com', 'GitHub', ''),
            ('https://python.org', 'Welcome to Python.org', ''),
            ('http://qutebrowser.org', 'qutebrowser | qutebrowser', ''),
        ])
    ]


def test_url_completion(config_stub, web_history, quickmarks, bookmarks):
    """Test the results of url completion.

    Verify that:
        - quickmarks, bookmarks, and urls are included
        - no more than 'web-history-max-items' history entries are included
        - the most recent entries are included
    """
    config_stub.data['completion'] = {'timestamp-format': '%Y-%m-%d',
                                      'web-history-max-items': 2}
    actual = _get_completions(urlmodel.UrlCompletionModel())
    assert actual == [
        ("Quickmarks", [
            ('https://wiki.archlinux.org', 'aw', ''),
            ('https://duckduckgo.com', 'ddg', ''),
            ('https://wikipedia.org', 'wiki', ''),
        ]),
        ("Bookmarks", [
            ('https://github.com', 'GitHub', ''),
            ('https://python.org', 'Welcome to Python.org', ''),
            ('http://qutebrowser.org', 'qutebrowser | qutebrowser', ''),
        ]),
        ("History", [
            ('https://python.org', 'Welcome to Python.org', '2016-03-08'),
            ('https://github.com', 'GitHub', '2016-05-01'),
        ]),
    ]


def test_url_completion_delete_bookmark(config_stub, web_history, quickmarks,
                                        bookmarks, qtbot):
    """Test deleting a bookmark from the url completion model."""
    config_stub.data['completion'] = {'timestamp-format': '%Y-%m-%d',
                                      'web-history-max-items': 2}
    model = urlmodel.UrlCompletionModel()
    # delete item (1, 0) -> (bookmarks, 'https://github.com' )
    view = _mock_view_index(model, 1, 0, qtbot)
    model.delete_cur_item(view)
    assert 'https://github.com' not in bookmarks.marks
    assert 'https://python.org' in bookmarks.marks
    assert 'http://qutebrowser.org' in bookmarks.marks


def test_url_completion_delete_quickmark(config_stub, web_history, quickmarks,
                                        bookmarks, qtbot):
    """Test deleting a bookmark from the url completion model."""
    config_stub.data['completion'] = {'timestamp-format': '%Y-%m-%d',
                                      'web-history-max-items': 2}
    model = urlmodel.UrlCompletionModel()
    # delete item (0, 1) -> (quickmarks, 'ddg' )
    view = _mock_view_index(model, 0, 1, qtbot)
    model.delete_cur_item(view)
    assert 'aw' in quickmarks.marks
    assert 'ddg' not in quickmarks.marks
    assert 'wiki' in quickmarks.marks


def test_session_completion(session_manager_stub):
    session_manager_stub.sessions = ['default', '1', '2']
    actual = _get_completions(miscmodels.SessionCompletionModel())
    assert actual == [
        ("Sessions", [('default', '', ''), ('1', '', ''), ('2', '', '')])
    ]


def test_tab_completion(fake_web_tab, app_stub, win_registry,
                        tabbed_browser_stubs):
    tabbed_browser_stubs[0].tabs = [
        fake_web_tab(QUrl('https://github.com'), 'GitHub', 0),
        fake_web_tab(QUrl('https://wikipedia.org'), 'Wikipedia', 1),
        fake_web_tab(QUrl('https://duckduckgo.com'), 'DuckDuckGo', 2),
    ]
    tabbed_browser_stubs[1].tabs = [
        fake_web_tab(QUrl('https://wiki.archlinux.org'), 'ArchWiki', 0),
    ]
    actual = _get_completions(miscmodels.TabCompletionModel())
    assert actual == [
        ('0', [
            ('0/1', 'https://github.com', 'GitHub'),
            ('0/2', 'https://wikipedia.org', 'Wikipedia'),
            ('0/3', 'https://duckduckgo.com', 'DuckDuckGo')
        ]),
        ('1', [
            ('1/1', 'https://wiki.archlinux.org', 'ArchWiki'),
        ])
    ]


def test_tab_completion_delete(fake_web_tab, qtbot, app_stub, win_registry,
                               tabbed_browser_stubs):
    """Verify closing a tab by deleting it from the completion widget."""
    tabbed_browser_stubs[0].tabs = [
        fake_web_tab(QUrl('https://github.com'), 'GitHub', 0),
        fake_web_tab(QUrl('https://wikipedia.org'), 'Wikipedia', 1),
        fake_web_tab(QUrl('https://duckduckgo.com'), 'DuckDuckGo', 2)
    ]
    tabbed_browser_stubs[1].tabs = [
        fake_web_tab(QUrl('https://wiki.archlinux.org'), 'ArchWiki', 0),
    ]
    model = miscmodels.TabCompletionModel()
    view = _mock_view_index(model, 0, 1, qtbot)
    qtbot.add_widget(view)
    model.delete_cur_item(view)
    actual = [tab.url() for tab in tabbed_browser_stubs[0].tabs]
    assert actual == [QUrl('https://github.com'),
                      QUrl('https://duckduckgo.com')]


def test_setting_section_completion(monkeypatch, stubs):
    module = 'qutebrowser.completion.models.configmodel'
    _patch_configdata(monkeypatch, stubs, module + '.configdata.DATA')
    _patch_config_section_desc(monkeypatch, stubs,
                               module + '.configdata.SECTION_DESC')
    actual = _get_completions(configmodel.SettingSectionCompletionModel())
    assert actual == [
        ("Sections", [
            ('general', 'General/miscellaneous options.', ''),
            ('ui', 'General options related to the user interface.', ''),
        ])
    ]


def test_setting_option_completion(monkeypatch, stubs, config_stub):
    module = 'qutebrowser.completion.models.configmodel'
    _patch_configdata(monkeypatch, stubs, module + '.configdata.DATA')
    config_stub.data = {'ui': {'gesture': 'off',
                               'mind': 'on',
                               'voice': 'sometimes'}}
    actual = _get_completions(configmodel.SettingOptionCompletionModel('ui'))
    assert actual == [
        ("ui", [
            ('gesture', 'Waggle your hands to control qutebrowser', 'off'),
            ('mind', 'Enable mind-control ui (experimental)', 'on'),
            ('voice', 'Whether to respond to voice commands', 'sometimes'),
        ])
    ]


def test_setting_value_completion(monkeypatch, stubs, config_stub):
    module = 'qutebrowser.completion.models.configmodel'
    _patch_configdata(monkeypatch, stubs, module + '.configdata.DATA')
    config_stub.data = {'general': {'volume': '0'}}
    model = configmodel.SettingValueCompletionModel('general', 'volume')
    actual = _get_completions(model)
    assert actual == [
        ("Current/Default", [
            ('0', 'Current value', ''),
            ('11', 'Default value', ''),
        ]),
        ("Completions", [
            ('0', '', ''),
            ('11', '', ''),
        ])
    ]
