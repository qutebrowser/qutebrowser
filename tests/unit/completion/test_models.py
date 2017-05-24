# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2017 Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
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

from qutebrowser.browser import history
from qutebrowser.completion.models import miscmodels, urlmodel, configmodel
from qutebrowser.config import sections, value
from qutebrowser.misc import sql


def _check_completions(model, expected):
    """Check that a model contains the expected items in any order.

    Args:
        expected: A dict of form
            {
                CategoryName: [(name, desc, misc), ...],
                CategoryName: [(name, desc, misc), ...],
                ...
            }
    """
    actual = {}
    assert model.rowCount() == len(expected)
    for i in range(0, model.rowCount()):
        catidx = model.index(i, 0)
        catname = model.data(catidx)
        actual[catname] = []
        for j in range(model.rowCount(catidx)):
            name = model.data(model.index(j, 0, parent=catidx))
            desc = model.data(model.index(j, 1, parent=catidx))
            misc = model.data(model.index(j, 2, parent=catidx))
            actual[catname].append((name, desc, misc))
    assert actual == expected
    # sanity-check the column_widths
    assert len(model.column_widths) == 3
    assert sum(model.column_widths) == 100


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
        ('searchengines', sections.ValueList(
            stubs.FakeConfigType(), stubs.FakeConfigType(),
            ('DEFAULT', 'https://duckduckgo.com/?q={}'),
        )),
    ])
    monkeypatch.setattr(symbol, data)


def _patch_config_section_desc(monkeypatch, stubs, symbol):
    """Patch the configdata module to provide fake SECTION_DESC."""
    section_desc = {
        'general': 'General/miscellaneous options.',
        'ui': 'General options related to the user interface.',
        'searchengines': 'Definitions of search engines ...',
    }
    monkeypatch.setattr(symbol, section_desc)


def _mock_view_index(model, category_num, child_num, qtbot):
    """Create a tree view from a model and set the current index.

    Args:
        model: model to create a fake view for.
        category_idx: index of the category to select.
        child_idx: index of the child item under that category to select.
    """
    view = QTreeView()
    qtbot.add_widget(view)
    view.setModel(model)
    parent = model.index(category_num, 0)
    child = model.index(child_num, 0, parent=parent)
    view.setCurrentIndex(child)
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
def web_history_stub(stubs, init_sql):
    return sql.SqlTable("History", ['url', 'title', 'atime', 'redirect'])


@pytest.fixture
def web_history(web_history_stub, init_sql):
    """Pre-populate the web-history database."""
    web_history_stub.insert(['http://some-redirect.example.com', 'redirect',
                            datetime(2016, 9, 5).timestamp(), True])
    web_history_stub.insert(['http://qutebrowser.org', 'qutebrowser',
                            datetime(2015, 9, 5).timestamp(), False])
    web_history_stub.insert(['https://python.org', 'Welcome to Python.org',
                            datetime(2016, 2, 8).timestamp(), False])
    web_history_stub.insert(['https://python.org', 'Welcome to Python.org',
                            datetime(2016, 3, 8).timestamp(), False])
    web_history_stub.insert(['https://python.org', 'Welcome to Python.org',
                            datetime(2014, 3, 8).timestamp(), False])
    web_history_stub.insert(['https://github.com', 'https://github.com',
                            datetime(2016, 5, 1).timestamp(), False])
    return web_history_stub


def test_command_completion(qtmodeltester, monkeypatch, stubs, config_stub,
                            key_config_stub):
    """Test the results of command completion.

    Validates that:
        - only non-hidden and non-deprecated commands are included
        - the command description is shown in the desc column
        - the binding (if any) is shown in the misc column
        - aliases are included
    """
    _patch_cmdutils(monkeypatch, stubs,
                    'qutebrowser.completion.models.miscmodels.cmdutils')
    config_stub.data['aliases'] = {'rock': 'roll'}
    key_config_stub.set_bindings_for('normal', {'s': 'stop',
                                                'rr': 'roll',
                                                'ro': 'rock'})
    model = miscmodels.command()
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "Commands": [
            ('drop', 'drop all user data', ''),
            ('rock', "Alias for 'roll'", 'ro'),
            ('roll', 'never gonna give you up', 'rr'),
            ('stop', 'stop qutebrowser', 's'),
        ]
    })


def test_help_completion(qtmodeltester, monkeypatch, stubs, key_config_stub):
    """Test the results of command completion.

    Validates that:
        - only non-deprecated commands are included
        - the command description is shown in the desc column
        - the binding (if any) is shown in the misc column
        - aliases are included
        - only the first line of a multiline description is shown
    """
    module = 'qutebrowser.completion.models.miscmodels'
    key_config_stub.set_bindings_for('normal', {'s': 'stop', 'rr': 'roll'})
    _patch_cmdutils(monkeypatch, stubs, module + '.cmdutils')
    _patch_configdata(monkeypatch, stubs, module + '.configdata.DATA')
    model = miscmodels.helptopic()
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "Commands": [
            (':drop', 'drop all user data', ''),
            (':hide', '', ''),
            (':roll', 'never gonna give you up', 'rr'),
            (':stop', 'stop qutebrowser', 's'),
        ],
        "Settings": [
            ('general->time', 'Is an illusion.', None),
            ('general->volume', 'Goes to 11', None),
            ('searchengines->DEFAULT', '', None),
            ('ui->gesture', 'Waggle your hands to control qutebrowser', None),
            ('ui->mind', 'Enable mind-control ui (experimental)', None),
            ('ui->voice', 'Whether to respond to voice commands', None),
        ]
    })


def test_quickmark_completion(qtmodeltester, quickmarks):
    """Test the results of quickmark completion."""
    model = miscmodels.quickmark()
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "Quickmarks": [
            ('aw', 'https://wiki.archlinux.org', None),
            ('ddg', 'https://duckduckgo.com', None),
            ('wiki', 'https://wikipedia.org', None),
        ]
    })


def test_bookmark_completion(qtmodeltester, bookmarks):
    """Test the results of bookmark completion."""
    model = miscmodels.bookmark()
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "Bookmarks": [
            ('http://qutebrowser.org', 'qutebrowser | qutebrowser', None),
            ('https://github.com', 'GitHub', None),
            ('https://python.org', 'Welcome to Python.org', None),
        ]
    })


def test_url_completion(qtmodeltester, config_stub, web_history, quickmarks,
                        bookmarks):
    """Test the results of url completion.

    Verify that:
        - quickmarks, bookmarks, and urls are included
        - entries are sorted by access time
        - redirect entries are not included
        - only the most recent entry is included for each url
    """
    config_stub.data['completion'] = {'timestamp-format': '%Y-%m-%d'}
    model = urlmodel.url()
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "Quickmarks": [
            ('https://duckduckgo.com', 'ddg', None),
            ('https://wiki.archlinux.org', 'aw', None),
            ('https://wikipedia.org', 'wiki', None),
        ],
        "Bookmarks": [
            ('http://qutebrowser.org', 'qutebrowser | qutebrowser', None),
            ('https://github.com', 'GitHub', None),
            ('https://python.org', 'Welcome to Python.org', None),
        ],
        "History": [
            ('https://github.com', 'https://github.com', '2016-05-01'),
            ('https://python.org', 'Welcome to Python.org', '2016-03-08'),
            ('http://qutebrowser.org', 'qutebrowser', '2015-09-05'),
        ],
    })


@pytest.mark.parametrize('url, title, pattern, rowcount', [
    ('example.com', 'Site Title', '', 1),
    ('example.com', 'Site Title', 'ex', 1),
    ('example.com', 'Site Title', 'am', 1),
    ('example.com', 'Site Title', 'com', 1),
    ('example.com', 'Site Title', 'ex com', 1),
    ('example.com', 'Site Title', 'com ex', 0),
    ('example.com', 'Site Title', 'ex foo', 0),
    ('example.com', 'Site Title', 'foo com', 0),
    ('example.com', 'Site Title', 'exm', 0),
    ('example.com', 'Site Title', 'Si Ti', 1),
    ('example.com', 'Site Title', 'Ti Si', 0),
    ('example.com', '', 'foo', 0),
    ('foo_bar', '', '_', 1),
    ('foobar', '', '_', 0),
    ('foo%bar', '', '%', 1),
    ('foobar', '', '%', 0),
])
def test_url_completion_pattern(config_stub, web_history_stub,
                                quickmark_manager_stub, bookmark_manager_stub,
                                url, title, pattern, rowcount):
    """Test that url completion filters by url and title."""
    config_stub.data['completion'] = {'timestamp-format': '%Y-%m-%d'}
    web_history_stub.insert([url, title, 0, False])
    model = urlmodel.url()
    model.set_pattern(pattern)
    # 2, 0 is History
    assert model.rowCount(model.index(2, 0)) == rowcount


def test_url_completion_delete_bookmark(qtmodeltester, config_stub,
                                        web_history, quickmarks, bookmarks,
                                        qtbot):
    """Test deleting a bookmark from the url completion model."""
    config_stub.data['completion'] = {'timestamp-format': '%Y-%m-%d'}
    model = urlmodel.url()
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    # delete item (1, 1) -> (bookmarks, 'https://github.com')
    view = _mock_view_index(model, 1, 1, qtbot)
    model.delete_cur_item(view)
    assert 'https://github.com' not in bookmarks.marks
    assert 'https://python.org' in bookmarks.marks
    assert 'http://qutebrowser.org' in bookmarks.marks


def test_url_completion_delete_quickmark(qtmodeltester, config_stub,
                                         web_history, quickmarks, bookmarks,
                                         qtbot):
    """Test deleting a bookmark from the url completion model."""
    config_stub.data['completion'] = {'timestamp-format': '%Y-%m-%d'}
    model = urlmodel.url()
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    # delete item (0, 0) -> (quickmarks, 'ddg' )
    view = _mock_view_index(model, 0, 0, qtbot)
    model.delete_cur_item(view)
    assert 'aw' in quickmarks.marks
    assert 'ddg' not in quickmarks.marks
    assert 'wiki' in quickmarks.marks


def test_url_completion_delete_history(qtmodeltester, config_stub,
                                       web_history, quickmarks, bookmarks,
                                       qtbot):
    """Test that deleting a history entry is a noop."""
    config_stub.data['completion'] = {'timestamp-format': '%Y-%m-%d'}
    model = urlmodel.url()
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    hist_before = list(web_history)
    view = _mock_view_index(model, 2, 0, qtbot)
    model.delete_cur_item(view)
    assert list(web_history) == hist_before


def test_session_completion(qtmodeltester, session_manager_stub):
    session_manager_stub.sessions = ['default', '1', '2']
    model = miscmodels.session()
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "Sessions": [('1', None, None),
                     ('2', None, None),
                     ('default', None, None)]
    })


def test_tab_completion(qtmodeltester, fake_web_tab, app_stub, win_registry,
                        tabbed_browser_stubs):
    tabbed_browser_stubs[0].tabs = [
        fake_web_tab(QUrl('https://github.com'), 'GitHub', 0),
        fake_web_tab(QUrl('https://wikipedia.org'), 'Wikipedia', 1),
        fake_web_tab(QUrl('https://duckduckgo.com'), 'DuckDuckGo', 2),
    ]
    tabbed_browser_stubs[1].tabs = [
        fake_web_tab(QUrl('https://wiki.archlinux.org'), 'ArchWiki', 0),
    ]
    model = miscmodels.buffer()
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        '0': [
            ('0/1', 'https://github.com', 'GitHub'),
            ('0/2', 'https://wikipedia.org', 'Wikipedia'),
            ('0/3', 'https://duckduckgo.com', 'DuckDuckGo')
        ],
        '1': [
            ('1/1', 'https://wiki.archlinux.org', 'ArchWiki'),
        ]
    })


def test_tab_completion_delete(qtmodeltester, fake_web_tab, qtbot, app_stub,
                               win_registry, tabbed_browser_stubs):
    """Verify closing a tab by deleting it from the completion widget."""
    tabbed_browser_stubs[0].tabs = [
        fake_web_tab(QUrl('https://github.com'), 'GitHub', 0),
        fake_web_tab(QUrl('https://wikipedia.org'), 'Wikipedia', 1),
        fake_web_tab(QUrl('https://duckduckgo.com'), 'DuckDuckGo', 2)
    ]
    tabbed_browser_stubs[1].tabs = [
        fake_web_tab(QUrl('https://wiki.archlinux.org'), 'ArchWiki', 0),
    ]
    model = miscmodels.buffer()
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    view = _mock_view_index(model, 0, 1, qtbot)
    qtbot.add_widget(view)
    model.delete_cur_item(view)
    actual = [tab.url() for tab in tabbed_browser_stubs[0].tabs]
    assert actual == [QUrl('https://github.com'),
                      QUrl('https://duckduckgo.com')]


def test_setting_section_completion(qtmodeltester, monkeypatch, stubs):
    module = 'qutebrowser.completion.models.configmodel'
    _patch_configdata(monkeypatch, stubs, module + '.configdata.DATA')
    _patch_config_section_desc(monkeypatch, stubs,
                               module + '.configdata.SECTION_DESC')
    model = configmodel.section()
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "Sections": [
            ('general', 'General/miscellaneous options.', None),
            ('searchengines', 'Definitions of search engines ...', None),
            ('ui', 'General options related to the user interface.', None),
        ]
    })


def test_setting_option_completion(qtmodeltester, monkeypatch, stubs,
                                   config_stub):
    module = 'qutebrowser.completion.models.configmodel'
    _patch_configdata(monkeypatch, stubs, module + '.configdata.DATA')
    config_stub.data = {'ui': {'gesture': 'off',
                               'mind': 'on',
                               'voice': 'sometimes'}}
    model = configmodel.option('ui')
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "ui": [
            ('gesture', 'Waggle your hands to control qutebrowser', 'off'),
            ('mind', 'Enable mind-control ui (experimental)', 'on'),
            ('voice', 'Whether to respond to voice commands', 'sometimes'),
        ]
    })


def test_setting_option_completion_valuelist(qtmodeltester, monkeypatch, stubs,
                                             config_stub):
    module = 'qutebrowser.completion.models.configmodel'
    _patch_configdata(monkeypatch, stubs, module + '.configdata.DATA')
    config_stub.data = {
        'searchengines': {
            'DEFAULT': 'https://duckduckgo.com/?q={}'
        }
    }
    model = configmodel.option('searchengines')
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        'searchengines': [('DEFAULT', '', 'https://duckduckgo.com/?q={}')]
    })


def test_setting_value_completion(qtmodeltester, monkeypatch, stubs,
                                  config_stub):
    module = 'qutebrowser.completion.models.configmodel'
    _patch_configdata(monkeypatch, stubs, module + '.configdata.DATA')
    config_stub.data = {'general': {'volume': '0'}}
    model = configmodel.value('general', 'volume')
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "Current/Default": [
            ('0', 'Current value', None),
            ('11', 'Default value', None),
        ],
        "Completions": [
            ('0', '', None),
            ('11', '', None),
        ]
    })


def test_bind_completion(qtmodeltester, monkeypatch, stubs, config_stub,
                         key_config_stub):
    """Test the results of keybinding command completion.

    Validates that:
        - only non-hidden and non-deprecated commands are included
        - the command description is shown in the desc column
        - the binding (if any) is shown in the misc column
        - aliases are included
    """
    _patch_cmdutils(monkeypatch, stubs,
                    'qutebrowser.completion.models.miscmodels.cmdutils')
    config_stub.data['aliases'] = {'rock': 'roll'}
    key_config_stub.set_bindings_for('normal', {'s': 'stop',
                                                'rr': 'roll',
                                                'ro': 'rock'})
    model = miscmodels.bind('s')
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "Commands": [
            ('drop', 'drop all user data', ''),
            ('hide', '', ''),
            ('rock', "Alias for 'roll'", 'ro'),
            ('roll', 'never gonna give you up', 'rr'),
            ('stop', 'stop qutebrowser', 's'),
        ]
    })


def test_url_completion_benchmark(benchmark, config_stub,
                                  quickmark_manager_stub,
                                  bookmark_manager_stub,
                                  web_history_stub):
    """Benchmark url completion."""
    config_stub.data['completion'] = {'timestamp-format': '%Y-%m-%d',
                                      'web-history-max-items': 1000}

    entries = [web_history_stub.Entry(
        atime=i,
        url='http://example.com/{}'.format(i),
        title='title{}'.format(i),
        redirect=False)
        for i in range(100000)]

    web_history_stub.insert_batch(entries)

    quickmark_manager_stub.marks = collections.OrderedDict(
        (e.title, e.url)
        for e in entries[0:1000])

    bookmark_manager_stub.marks = collections.OrderedDict(
        (e.url, e.title)
        for e in entries[0:1000])

    def bench():
        model = urlmodel.url()
        model.set_pattern('')
        model.set_pattern('e')
        model.set_pattern('ex')
        model.set_pattern('ex ')
        model.set_pattern('ex 1')
        model.set_pattern('ex 12')
        model.set_pattern('ex 123')

    benchmark(bench)
