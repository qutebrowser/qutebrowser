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
    assert model.rowCount() == len(expected)
    for i in range(0, model.rowCount()):
        catidx = model.index(i, 0)
        catname = model.data(catidx)
        assert catname in expected
        expected_cat = expected[catname]
        assert model.rowCount(catidx) == len(expected_cat)
        for j in range(model.rowCount(catidx)):
            name = model.data(model.index(j, 0, parent=catidx))
            desc = model.data(model.index(j, 1, parent=catidx))
            misc = model.data(model.index(j, 2, parent=catidx))
            assert (name, desc, misc) in expected_cat
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
def quickmarks(init_sql):
    """Pre-populate the quickmark database."""
    table = sql.SqlTable('Quickmarks', ['name', 'url'], primary_key='name')
    table.insert(['aw', 'https://wiki.archlinux.org'])
    table.insert(['ddg', 'https://duckduckgo.com'])
    table.insert(['wiki', 'https://wikipedia.org'])


@pytest.fixture
def bookmarks(init_sql):
    """Pre-populate the bookmark database."""
    table = sql.SqlTable('Bookmarks', ['url', 'title'], primary_key='url')
    table.insert(['https://github.com', 'GitHub'])
    table.insert(['https://python.org', 'Welcome to Python.org'])
    table.insert(['http://qutebrowser.org', 'qutebrowser | qutebrowser'])


@pytest.fixture
def web_history(stubs, init_sql):
    """Pre-populate the web-history database."""
    table = sql.SqlTable("History", ['url', 'title', 'atime', 'redirect'],
                         primary_key='url')
    table.insert(['http://some-redirect.example.com', 'redirect',
                  datetime(2016, 9, 5).timestamp(), True])
    table.insert(['http://qutebrowser.org', 'qutebrowser',
                  datetime(2015, 9, 5).timestamp(), False])
    table.insert(['https://python.org', 'Welcome to Python.org',
                  datetime(2016, 3, 8).timestamp(), False])
    table.insert(['https://github.com', 'https://github.com',
                  datetime(2016, 5, 1).timestamp(), False])


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
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "Commands": [
            ('stop', 'stop qutebrowser', 's'),
            ('drop', 'drop all user data', ''),
            ('roll', 'never gonna give you up', 'rr'),
            ('rock', "Alias for 'roll'", 'ro'),
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
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "Commands": [
            (':stop', 'stop qutebrowser', 's'),
            (':drop', 'drop all user data', ''),
            (':roll', 'never gonna give you up', 'rr'),
            (':hide', '', ''),
        ],
        "Settings": [
            ('general->time', 'Is an illusion.', ''),
            ('general->volume', 'Goes to 11', ''),
            ('ui->gesture', 'Waggle your hands to control qutebrowser', ''),
            ('ui->mind', 'Enable mind-control ui (experimental)', ''),
            ('ui->voice', 'Whether to respond to voice commands', ''),
            ('searchengines->DEFAULT', '', ''),
        ]
    })


def test_quickmark_completion(qtmodeltester, quickmarks):
    """Test the results of quickmark completion."""
    model = miscmodels.quickmark()
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
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "Bookmarks": [
            ('https://github.com', 'GitHub', None),
            ('https://python.org', 'Welcome to Python.org', None),
            ('http://qutebrowser.org', 'qutebrowser | qutebrowser', None),
        ]
    })


def test_url_completion(qtmodeltester, config_stub, web_history, quickmarks,
                        bookmarks):
    """Test the results of url completion.

    Verify that:
        - quickmarks, bookmarks, and urls are included
        - no more than 'web-history-max-items' items are included (TODO)
        - the most recent entries are included
        - redirect entries are not included
    """
    # TODO: time formatting and item limiting
    config_stub.data['completion'] = {'timestamp-format': '%Y-%m-%d',
                                      'web-history-max-items': 2}
    model = urlmodel.url()
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "Quickmarks": [
            ('https://wiki.archlinux.org', 'aw', None),
            ('https://duckduckgo.com', 'ddg', None),
            ('https://wikipedia.org', 'wiki', None),
        ],
        "Bookmarks": [
            ('https://github.com', 'GitHub', None),
            ('https://python.org', 'Welcome to Python.org', None),
            ('http://qutebrowser.org', 'qutebrowser | qutebrowser', None),
        ],
        "History": [
            ('http://qutebrowser.org', 'qutebrowser', '2015-09-05'),
            ('https://python.org', 'Welcome to Python.org', '2016-03-08'),
        ],
    })


@pytest.mark.skip
def test_url_completion_delete_bookmark(qtmodeltester, config_stub,
                                        web_history, quickmarks, bookmarks,
                                        qtbot):
    """Test deleting a bookmark from the url completion model."""
    config_stub.data['completion'] = {'timestamp-format': '%Y-%m-%d',
                                      'web-history-max-items': 2}
    model = urlmodel.url()
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    # delete item (1, 0) -> (bookmarks, 'https://github.com' )
    view = _mock_view_index(model, 1, 0, qtbot)
    model.delete_cur_item(view)
    assert 'https://github.com' not in bookmarks.marks
    assert 'https://python.org' in bookmarks.marks
    assert 'http://qutebrowser.org' in bookmarks.marks


@pytest.mark.skip
def test_url_completion_delete_quickmark(qtmodeltester, config_stub,
                                         web_history, quickmarks, bookmarks,
                                         qtbot):
    """Test deleting a bookmark from the url completion model."""
    config_stub.data['completion'] = {'timestamp-format': '%Y-%m-%d',
                                      'web-history-max-items': 2}
    model = urlmodel.url()
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    # delete item (0, 1) -> (quickmarks, 'ddg' )
    view = _mock_view_index(model, 0, 1, qtbot)
    model.delete_cur_item(view)
    assert 'aw' in quickmarks.marks
    assert 'ddg' not in quickmarks.marks
    assert 'wiki' in quickmarks.marks


def test_session_completion(qtmodeltester, session_manager_stub):
    session_manager_stub.sessions = ['default', '1', '2']
    model = miscmodels.session()
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "Sessions": [('default', '', ''), ('1', '', ''), ('2', '', '')]
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
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "Sections": [
            ('general', 'General/miscellaneous options.', ''),
            ('ui', 'General options related to the user interface.', ''),
            ('searchengines', 'Definitions of search engines ...', ''),
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
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "Current/Default": [
            ('0', 'Current value', ''),
            ('11', 'Default value', ''),
        ],
        "Completions": [
            ('0', '', ''),
            ('11', '', ''),
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
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "Commands": [
            ('stop', 'stop qutebrowser', 's'),
            ('drop', 'drop all user data', ''),
            ('hide', '', ''),
            ('roll', 'never gonna give you up', 'rr'),
            ('rock', "Alias for 'roll'", 'ro'),
        ]
    })


def test_url_completion_benchmark(benchmark, config_stub,
                                  quickmark_manager_stub,
                                  bookmark_manager_stub,
                                  web_history_stub):
    """Benchmark url completion."""
    config_stub.data['completion'] = {'timestamp-format': '%Y-%m-%d',
                                      'web-history-max-items': 1000}

    entries = [history.Entry(
        atime=i,
        url=QUrl('http://example.com/{}'.format(i)),
        title='title{}'.format(i))
        for i in range(100000)]

    web_history_stub.history_dict = collections.OrderedDict(
        ((e.url_str(), e) for e in entries))

    quickmark_manager_stub.marks = collections.OrderedDict(
        (e.title, e.url_str())
        for e in entries[0:1000])

    bookmark_manager_stub.marks = collections.OrderedDict(
        (e.url_str(), e.title)
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
