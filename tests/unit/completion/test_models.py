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

from qutebrowser.completion.models import miscmodels, urlmodel, configmodel
from qutebrowser.config import sections, value
from qutebrowser.utils import objreg
from qutebrowser.browser import history


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


@pytest.fixture
def quickmarks(quickmark_manager_stub):
    """Pre-populate the quickmark-manager stub with some quickmarks."""
    quickmark_manager_stub.marks = collections.OrderedDict([
        ('aw', 'https://wiki.archlinux.org'),
        ('wiki', 'https://wikipedia.org'),
        ('ddg', 'https://duckduckgo.com'),
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
def web_history(init_sql, stubs, config_stub):
    """Fixture which provides a web-history object."""
    config_stub.data['completion'] = {'timestamp-format': '%Y-%m-%d',
                                      'web-history-max-items': -1}
    stub = history.WebHistory()
    objreg.register('web-history', stub)
    yield stub
    objreg.delete('web-history')


@pytest.fixture
def web_history_populated(web_history):
    """Pre-populate the web-history database."""
    web_history.add_url(
        url=QUrl('http://qutebrowser.org'),
        title='qutebrowser',
        atime=datetime(2015, 9, 5).timestamp()
    )
    web_history.add_url(
        url=QUrl('https://python.org'),
        title='Welcome to Python.org',
        atime=datetime(2016, 3, 8).timestamp()
    )
    web_history.add_url(
        url=QUrl('https://github.com'),
        title='https://github.com',
        atime=datetime(2016, 5, 1).timestamp()
    )
    return web_history


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
            ('wiki', 'https://wikipedia.org', None),
            ('ddg', 'https://duckduckgo.com', None),
        ]
    })


@pytest.mark.parametrize('row, removed', [
    (0, 'aw'),
    (1, 'wiki'),
    (2, 'ddg'),
])
def test_quickmark_completion_delete(qtmodeltester, quickmarks, row, removed):
    """Test deleting a quickmark from the quickmark completion model."""
    model = miscmodels.quickmark()
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    parent = model.index(0, 0)
    idx = model.index(row, 0, parent)

    before = set(quickmarks.marks.keys())
    model.delete_cur_item(idx)
    after = set(quickmarks.marks.keys())
    assert before.difference(after) == {removed}


def test_bookmark_completion(qtmodeltester, bookmarks):
    """Test the results of bookmark completion."""
    model = miscmodels.bookmark()
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "Bookmarks": [
            ('https://github.com', 'GitHub', None),
            ('https://python.org', 'Welcome to Python.org', None),
            ('http://qutebrowser.org', 'qutebrowser | qutebrowser', None),
        ]
    })


@pytest.mark.parametrize('row, removed', [
    (0, 'https://github.com'),
    (1, 'https://python.org'),
    (2, 'http://qutebrowser.org'),
])
def test_bookmark_completion_delete(qtmodeltester, bookmarks, row, removed):
    """Test deleting a quickmark from the quickmark completion model."""
    model = miscmodels.bookmark()
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    parent = model.index(0, 0)
    idx = model.index(row, 0, parent)

    before = set(bookmarks.marks.keys())
    model.delete_cur_item(idx)
    after = set(bookmarks.marks.keys())
    assert before.difference(after) == {removed}


def test_url_completion(qtmodeltester, web_history_populated,
                        quickmarks, bookmarks):
    """Test the results of url completion.

    Verify that:
        - quickmarks, bookmarks, and urls are included
        - entries are sorted by access time
        - only the most recent entry is included for each url
    """
    model = urlmodel.url()
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "Quickmarks": [
            ('https://wiki.archlinux.org', 'aw', None),
            ('https://wikipedia.org', 'wiki', None),
            ('https://duckduckgo.com', 'ddg', None),
        ],
        "Bookmarks": [
            ('https://github.com', 'GitHub', None),
            ('https://python.org', 'Welcome to Python.org', None),
            ('http://qutebrowser.org', 'qutebrowser | qutebrowser', None),
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
def test_url_completion_pattern(web_history, quickmark_manager_stub,
                                bookmark_manager_stub, url, title, pattern,
                                rowcount):
    """Test that url completion filters by url and title."""
    web_history.add_url(QUrl(url), title)
    model = urlmodel.url()
    model.set_pattern(pattern)
    # 2, 0 is History
    assert model.rowCount(model.index(2, 0)) == rowcount


def test_url_completion_delete_bookmark(qtmodeltester, bookmarks,
                                        web_history, quickmarks):
    """Test deleting a bookmark from the url completion model."""
    model = urlmodel.url()
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    parent = model.index(1, 0)
    idx = model.index(1, 0, parent)

    # sanity checks
    assert model.data(parent) == "Bookmarks"
    assert model.data(idx) == 'https://python.org'
    assert 'https://github.com' in bookmarks.marks

    len_before = len(bookmarks.marks)
    model.delete_cur_item(idx)
    assert 'https://python.org' not in bookmarks.marks
    assert len_before == len(bookmarks.marks) + 1


def test_url_completion_delete_quickmark(qtmodeltester,
                                         quickmarks, web_history, bookmarks,
                                         qtbot):
    """Test deleting a bookmark from the url completion model."""
    model = urlmodel.url()
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    parent = model.index(0, 0)
    idx = model.index(0, 0, parent)

    # sanity checks
    assert model.data(parent) == "Quickmarks"
    assert model.data(idx) == 'https://wiki.archlinux.org'
    assert 'ddg' in quickmarks.marks

    len_before = len(quickmarks.marks)
    model.delete_cur_item(idx)
    assert 'aw' not in quickmarks.marks
    assert len_before == len(quickmarks.marks) + 1


def test_url_completion_delete_history(qtmodeltester,
                                       web_history_populated,
                                       quickmarks, bookmarks):
    """Test deleting a history entry."""
    model = urlmodel.url()
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    parent = model.index(2, 0)
    idx = model.index(1, 0, parent)

    # sanity checks
    assert model.data(parent) == "History"
    assert model.data(idx) == 'https://python.org'

    assert 'https://python.org' in web_history_populated
    model.delete_cur_item(idx)
    assert 'https://python.org' not in web_history_populated


def test_url_completion_zero_limit(config_stub, web_history, quickmarks,
                                   bookmarks):
    """Make sure there's no history if the limit was set to zero."""
    config_stub.data['completion']['web-history-max-items'] = 0
    model = urlmodel.url()
    model.set_pattern('')
    category = model.index(2, 0)  # "History" normally
    assert model.data(category) is None


def test_session_completion(qtmodeltester, session_manager_stub):
    session_manager_stub.sessions = ['default', '1', '2']
    model = miscmodels.session()
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "Sessions": [('default', None, None),
                     ('1', None, None),
                     ('2', None, None)]
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


def test_tab_completion_delete(qtmodeltester, fake_web_tab, app_stub,
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

    parent = model.index(0, 0)
    idx = model.index(1, 0, parent)

    # sanity checks
    assert model.data(parent) == "0"
    assert model.data(idx) == '0/2'

    model.delete_cur_item(idx)
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


def test_setting_option_completion_empty(monkeypatch, stubs, config_stub):
    module = 'qutebrowser.completion.models.configmodel'
    _patch_configdata(monkeypatch, stubs, module + '.configdata.DATA')
    assert configmodel.option('typo') is None


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


def test_setting_value_completion_empty(monkeypatch, stubs, config_stub):
    module = 'qutebrowser.completion.models.configmodel'
    _patch_configdata(monkeypatch, stubs, module + '.configdata.DATA')
    config_stub.data = {'general': {}}
    assert configmodel.value('general', 'typo') is None


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
    key_config_stub.set_bindings_for('normal', {'s': 'stop now',
                                                'rr': 'roll',
                                                'ro': 'rock'})
    model = miscmodels.bind('s')
    model.set_pattern('')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)

    _check_completions(model, {
        "Current": [
            ('stop now', 'stop qutebrowser', 's'),
        ],
        "Commands": [
            ('drop', 'drop all user data', ''),
            ('hide', '', ''),
            ('rock', "Alias for 'roll'", 'ro'),
            ('roll', 'never gonna give you up', 'rr'),
            ('stop', 'stop qutebrowser', ''),
        ]
    })


def test_url_completion_benchmark(benchmark,
                                  quickmark_manager_stub,
                                  bookmark_manager_stub,
                                  web_history):
    """Benchmark url completion."""
    r = range(100000)
    entries = {
        'last_atime': list(r),
        'url': ['http://example.com/{}'.format(i) for i in r],
        'title': ['title{}'.format(i) for i in r]
    }

    web_history.completion.insert_batch(entries)

    quickmark_manager_stub.marks = collections.OrderedDict([
        ('title{}'.format(i), 'example.com/{}'.format(i))
        for i in range(1000)])

    bookmark_manager_stub.marks = collections.OrderedDict([
        ('example.com/{}'.format(i), 'title{}'.format(i))
        for i in range(1000)])

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
