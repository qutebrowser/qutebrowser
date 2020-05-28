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

"""Tests for completion models."""

import collections
import random
import string
from datetime import datetime

import pytest
from PyQt5.QtCore import QUrl

from qutebrowser.misc import objects
from qutebrowser.completion import completer
from qutebrowser.completion.models import miscmodels, urlmodel, configmodel
from qutebrowser.config import configdata, configtypes
from qutebrowser.utils import usertypes


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
    __tracebackhide__ = True
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


@pytest.fixture()
def cmdutils_stub(monkeypatch, stubs):
    """Patch the cmdutils module to provide fake commands."""
    return monkeypatch.setattr(objects, 'commands', {
        'quit': stubs.FakeCommand(name='quit', desc='quit qutebrowser'),
        'open': stubs.FakeCommand(name='open', desc='open a url'),
        'prompt-yes': stubs.FakeCommand(name='prompt-yes', deprecated=True),
        'scroll': stubs.FakeCommand(
            name='scroll',
            desc='Scroll the current tab in the given direction.',
            modes=()),
        'tab-close': stubs.FakeCommand(
            name='tab-close',
            desc='Close the current tab.'),
    })


@pytest.fixture()
def configdata_stub(config_stub, monkeypatch, configdata_init):
    """Patch the configdata module to provide fake data."""
    monkeypatch.setattr(configdata, 'DATA', collections.OrderedDict([
        ('aliases', configdata.Option(
            name='aliases',
            description='Aliases for commands.',
            typ=configtypes.Dict(
                keytype=configtypes.String(),
                valtype=configtypes.Command(),
            ),
            default={'q': 'quit'},
            backends=[usertypes.Backend.QtWebKit,
                      usertypes.Backend.QtWebEngine],
            raw_backends=None)),
        ('bindings.default', configdata.Option(
            name='bindings.default',
            description='Default keybindings',
            typ=configtypes.Dict(
                keytype=configtypes.String(),
                valtype=configtypes.Dict(
                    keytype=configtypes.Key(),
                    valtype=configtypes.Command(),
                ),
            ),
            default={
                'normal': collections.OrderedDict([
                    ('<Ctrl+q>', 'quit'),
                    ('d', 'tab-close'),
                ])
            },
            backends=[],
            raw_backends=None,
            no_autoconfig=True)),
        ('bindings.commands', configdata.Option(
            name='bindings.commands',
            description='Default keybindings',
            typ=configtypes.Dict(
                keytype=configtypes.String(),
                valtype=configtypes.Dict(
                    keytype=configtypes.Key(),
                    valtype=configtypes.Command(),
                ),
            ),
            default={
                'normal': collections.OrderedDict([
                    ('<Ctrl+q>', 'quit'),
                    ('ZQ', 'quit'),
                    ('I', 'invalid'),
                    ('d', 'scroll down'),
                ])
            },
            backends=[],
            raw_backends=None)),
        ('content.javascript.enabled', configdata.Option(
            name='content.javascript.enabled',
            description='Enable/Disable JavaScript',
            typ=configtypes.Bool(),
            default=True,
            backends=[],
            raw_backends=None)),
        ('completion.open_categories', configdata.Option(
            name='completion.open_categories',
            description=('Which categories to show (in which order) in the '
                         ':open completion.'),
            typ=configtypes.FlagList(),
            default=["searchengines", "quickmarks", "bookmarks", "history"],
            backends=[],
            raw_backends=None)),
        ('url.searchengines', configdata.Option(
            name='url.searchengines',
            description='searchengines list',
            typ=configtypes.Dict(
                keytype=configtypes.String(),
                valtype=configtypes.String(),
            ),
            default={"DEFAULT": "https://duckduckgo.com/?q={}", "google": "https://google.com/?q={}"},
            backends=[],
            raw_backends=None)),
    ]))
    config_stub._init_values()


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


@pytest.fixture
def info(config_stub, key_config_stub):
    return completer.CompletionInfo(config=config_stub,
                                    keyconf=key_config_stub,
                                    win_id=0)


def test_command_completion(qtmodeltester, cmdutils_stub, configdata_stub,
                            key_config_stub, info):
    """Test the results of command completion.

    Validates that:
        - only non-hidden and non-deprecated commands are included
        - the command description is shown in the desc column
        - the binding (if any) is shown in the misc column
        - aliases are included
    """
    model = miscmodels.command(info=info)
    model.set_pattern('')
    qtmodeltester.check(model)

    _check_completions(model, {
        "Commands": [
            ('open', 'open a url', ''),
            ('q', "Alias for 'quit'", ''),
            ('quit', 'quit qutebrowser', 'ZQ, <Ctrl+q>'),
            ('tab-close', 'Close the current tab.', ''),
        ]
    })


def test_help_completion(qtmodeltester, cmdutils_stub, key_config_stub,
                         configdata_stub, config_stub, info):
    """Test the results of command completion.

    Validates that:
        - only non-deprecated commands are included
        - the command description is shown in the desc column
        - the binding (if any) is shown in the misc column
        - aliases are not included
        - only the first line of a multiline description is shown
    """
    model = miscmodels.helptopic(info=info)
    model.set_pattern('')
    qtmodeltester.check(model)

    _check_completions(model, {
        "Commands": [
            (':open', 'open a url', ''),
            (':quit', 'quit qutebrowser', 'ZQ, <Ctrl+q>'),
            (':scroll', 'Scroll the current tab in the given direction.', ''),
            (':tab-close', 'Close the current tab.', ''),
        ],
        "Settings": [
            ('aliases', 'Aliases for commands.', None),
            ('bindings.commands', 'Default keybindings', None),
            ('bindings.default', 'Default keybindings', None),
            ('completion.open_categories', 'Which categories to show (in '
             'which order) in the :open completion.', None),
            ('content.javascript.enabled', 'Enable/Disable JavaScript', None),
            ('url.searchengines', 'searchengines list', None),
        ],
    })


def test_open_categories(qtmodeltester, config_stub, web_history_populated,
                         quickmarks, bookmarks, info):
    """Test that the open_categories setting has the desired effect.

    Verify that:
        - All categories are listed when they are defined in the
          completion.open_categories list.
    """
    config_stub.val.url.searchengines = {
        "DEFAULT": "https://duckduckgo.com/?q={}",
        "google": "https://google.com/?q={}",
    }
    config_stub.val.completion.open_categories = [
        "searchengines",
        "quickmarks",
        "bookmarks",
        "history",
    ]
    model = urlmodel.url(info=info)
    model.set_pattern('')
    qtmodeltester.check(model)

    _check_completions(model, {
        "Search engines": [
            ('google', 'https://google.com/?q={}', None),
        ],
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


def test_open_categories_remove_all(qtmodeltester, config_stub, web_history_populated,
                                    quickmarks, bookmarks, info):
    """Test removing all items from open_categories."""
    config_stub.val.url.searchengines = {
        "DEFAULT": "https://duckduckgo.com/?q={}",
        "google": "https://google.com/?q={}",
    }
    config_stub.val.completion.open_categories = []
    model = urlmodel.url(info=info)
    model.set_pattern('')
    qtmodeltester.check(model)

    _check_completions(model, {})


def test_open_categories_remove_one(qtmodeltester, config_stub, web_history_populated,
                                    quickmarks, bookmarks, info):
    """Test removing an item (boookmarks) from open_categories."""
    config_stub.val.url.searchengines = {
        "DEFAULT": "https://duckduckgo.com/?q={}",
        "google": "https://google.com/?q={}",
    }
    config_stub.val.completion.open_categories = [
        "searchengines", "quickmarks", "history"]
    model = urlmodel.url(info=info)
    model.set_pattern('')
    qtmodeltester.check(model)

    _check_completions(model, {
        "Search engines": [
            ('google', 'https://google.com/?q={}', None),
        ],
        "Quickmarks": [
            ('https://wiki.archlinux.org', 'aw', None),
            ('https://wikipedia.org', 'wiki', None),
            ('https://duckduckgo.com', 'ddg', None),
        ],
        "History": [
            ('https://github.com', 'https://github.com', '2016-05-01'),
            ('https://python.org', 'Welcome to Python.org', '2016-03-08'),
            ('http://qutebrowser.org', 'qutebrowser', '2015-09-05'),
        ],
    })


def test_quickmark_completion(qtmodeltester, quickmarks):
    """Test the results of quickmark completion."""
    model = miscmodels.quickmark()
    model.set_pattern('')
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
    qtmodeltester.check(model)

    parent = model.index(0, 0)
    idx = model.index(row, 0, parent)

    before = set(bookmarks.marks.keys())
    model.delete_cur_item(idx)
    after = set(bookmarks.marks.keys())
    assert before.difference(after) == {removed}


def test_url_completion(qtmodeltester, config_stub, web_history_populated,
                        quickmarks, bookmarks, info):
    """Test the results of url completion.

    Verify that:
        - searchengines, quickmarks, bookmarks, and urls are included
        - default search engine is not displayed
        - entries are sorted by access time
        - only the most recent entry is included for each url
    """
    config_stub.val.completion.open_categories = [
        "searchengines",
        "quickmarks",
        "bookmarks",
        "history",
    ]
    config_stub.val.url.searchengines = {
        "DEFAULT": "https://duckduckgo.com/?q={}",
        "google": "https://google.com/?q={}"
    }
    model = urlmodel.url(info=info)
    model.set_pattern('')
    qtmodeltester.check(model)

    _check_completions(model, {
        "Search engines": [
            ('google', 'https://google.com/?q={}', None),
        ],
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


def test_search_only_default(qtmodeltester, config_stub, web_history_populated,
                             quickmarks, bookmarks, info):
    """Test that search engines are not shown with only the default engine."""
    config_stub.val.completion.open_categories = [
        "searchengines",
        "quickmarks",
        "bookmarks",
        "history",
    ]
    config_stub.val.url.searchengines = {
        "DEFAULT": "https://duckduckgo.com/?q={}",
    }
    model = urlmodel.url(info=info)
    model.set_pattern('')
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


def test_url_completion_no_quickmarks(qtmodeltester, web_history_populated,
                                      quickmark_manager_stub, bookmarks, info):
    """Test that the quickmark category is gone with no quickmarks."""
    model = urlmodel.url(info=info)
    model.set_pattern('')
    qtmodeltester.check(model)

    _check_completions(model, {
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


def test_url_completion_no_bookmarks(qtmodeltester, web_history_populated,
                                     quickmarks, bookmark_manager_stub, info):
    """Test that the bookmarks category is gone with no bookmarks."""
    model = urlmodel.url(info=info)
    model.set_pattern('')
    qtmodeltester.check(model)

    _check_completions(model, {
        "Quickmarks": [
            ('https://wiki.archlinux.org', 'aw', None),
            ('https://wikipedia.org', 'wiki', None),
            ('https://duckduckgo.com', 'ddg', None),
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
    ('example.com', 'Site Title', 'com ex', 1),
    ('example.com', 'Site Title', 'ex foo', 0),
    ('example.com', 'Site Title', 'foo com', 0),
    ('example.com', 'Site Title', 'exm', 0),
    ('example.com', 'Site Title', 'Si Ti', 1),
    ('example.com', 'Site Title', 'Ti Si', 1),
    ('example.com', '', 'foo', 0),
    ('foo_bar', '', '_', 1),
    ('foobar', '', '_', 0),
    ('foo%bar', '', '%', 1),
    ('foobar', '', '%', 0),
])
def test_url_completion_pattern(web_history, quickmark_manager_stub,
                                bookmark_manager_stub, info,
                                url, title, pattern, rowcount):
    """Test that url completion filters by url and title."""
    web_history.add_url(QUrl(url), title)
    model = urlmodel.url(info=info)
    model.set_pattern(pattern)
    # 2, 0 is History
    assert model.rowCount(model.index(0, 0)) == rowcount


def test_url_completion_delete_bookmark(qtmodeltester, bookmarks,
                                        web_history, quickmarks, info):
    """Test deleting a bookmark from the url completion model."""
    model = urlmodel.url(info=info)
    model.set_pattern('')
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


def test_url_completion_delete_quickmark(qtmodeltester, info, qtbot,
                                         quickmarks, web_history, bookmarks):
    """Test deleting a bookmark from the url completion model."""
    model = urlmodel.url(info=info)
    model.set_pattern('')
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


def test_url_completion_delete_history(qtmodeltester, info,
                                       web_history_populated,
                                       quickmarks, bookmarks):
    """Test deleting a history entry."""
    model = urlmodel.url(info=info)
    model.set_pattern('')
    qtmodeltester.check(model)

    parent = model.index(2, 0)
    idx = model.index(1, 0, parent)

    # sanity checks
    assert model.data(parent) == "History"
    assert model.data(idx) == 'https://python.org'

    assert 'https://python.org' in web_history_populated
    model.delete_cur_item(idx)
    assert 'https://python.org' not in web_history_populated


def test_url_completion_zero_limit(config_stub, web_history, quickmarks, info,
                                   bookmarks):
    """Make sure there's no history if the limit was set to zero."""
    config_stub.val.completion.web_history.max_items = 0
    config_stub.val.completion.open_categories = [
        "searchengines",
        "quickmarks",
        "bookmarks",
        "history",
    ]
    config_stub.val.url.searchengines = {
        "DEFAULT": "https://duckduckgo.com/?q={}",
        "google": "https://google.com/?q={}",
    }
    model = urlmodel.url(info=info)
    model.set_pattern('')
    category = model.index(3, 0)  # "History" normally
    assert model.data(category) is None


def test_session_completion(qtmodeltester, session_manager_stub):
    session_manager_stub.sessions = ['default', '1', '2']
    model = miscmodels.session()
    model.set_pattern('')
    qtmodeltester.check(model)

    _check_completions(model, {
        "Sessions": [('1', None, None),
                     ('2', None, None),
                     ('default', None, None)]
    })


def test_tab_completion(qtmodeltester, fake_web_tab, win_registry,
                        tabbed_browser_stubs):
    tabbed_browser_stubs[0].widget.tabs = [
        fake_web_tab(QUrl('https://github.com'), 'GitHub', 0),
        fake_web_tab(QUrl('https://wikipedia.org'), 'Wikipedia', 1),
        fake_web_tab(QUrl('https://duckduckgo.com'), 'DuckDuckGo', 2),
    ]
    tabbed_browser_stubs[1].widget.tabs = [
        fake_web_tab(QUrl('https://wiki.archlinux.org'), 'ArchWiki', 0),
    ]
    model = miscmodels.buffer()
    model.set_pattern('')
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


def test_tab_completion_delete(qtmodeltester, fake_web_tab, win_registry,
                               tabbed_browser_stubs):
    """Verify closing a tab by deleting it from the completion widget."""
    tabbed_browser_stubs[0].widget.tabs = [
        fake_web_tab(QUrl('https://github.com'), 'GitHub', 0),
        fake_web_tab(QUrl('https://wikipedia.org'), 'Wikipedia', 1),
        fake_web_tab(QUrl('https://duckduckgo.com'), 'DuckDuckGo', 2)
    ]
    tabbed_browser_stubs[1].widget.tabs = [
        fake_web_tab(QUrl('https://wiki.archlinux.org'), 'ArchWiki', 0),
    ]
    model = miscmodels.buffer()
    model.set_pattern('')
    qtmodeltester.check(model)

    parent = model.index(0, 0)
    idx = model.index(1, 0, parent)

    # sanity checks
    assert model.data(parent) == "0"
    assert model.data(idx) == '0/2'

    model.delete_cur_item(idx)
    actual = [tab.url() for tab in tabbed_browser_stubs[0].widget.tabs]
    assert actual == [QUrl('https://github.com'),
                      QUrl('https://duckduckgo.com')]


def test_tab_completion_not_sorted(qtmodeltester, fake_web_tab, win_registry,
                                   tabbed_browser_stubs):
    """Ensure that the completion row order is the same as tab index order.

    Would be violated for more than 9 tabs if the completion was being
    alphabetically sorted on the first column, or the others.
    """
    expected = []
    for idx in range(1, 11):
        url = "".join(random.sample(string.ascii_letters, 12))
        title = "".join(random.sample(string.ascii_letters, 12))
        expected.append(("0/{}".format(idx), url, title))

    tabbed_browser_stubs[0].widget.tabs = [
        fake_web_tab(QUrl(tab[1]), tab[2], idx)
        for idx, tab in enumerate(expected)
    ]
    model = miscmodels.buffer()
    model.set_pattern('')
    qtmodeltester.check(model)

    _check_completions(model, {
        '0': expected,
        '1': [],
    })


def test_tab_completion_tabs_are_windows(qtmodeltester, fake_web_tab,
                                         win_registry, tabbed_browser_stubs,
                                         config_stub):
    """Verify tabs across all windows are listed under a single category."""
    tabbed_browser_stubs[0].widget.tabs = [
        fake_web_tab(QUrl('https://github.com'), 'GitHub', 0),
        fake_web_tab(QUrl('https://wikipedia.org'), 'Wikipedia', 1),
        fake_web_tab(QUrl('https://duckduckgo.com'), 'DuckDuckGo', 2),
    ]
    tabbed_browser_stubs[1].widget.tabs = [
        fake_web_tab(QUrl('https://wiki.archlinux.org'), 'ArchWiki', 0),
    ]

    config_stub.val.tabs.tabs_are_windows = True
    model = miscmodels.buffer()
    model.set_pattern('')
    qtmodeltester.check(model)

    _check_completions(model, {
        'Windows': [
            ('0/1', 'https://github.com', 'GitHub'),
            ('0/2', 'https://wikipedia.org', 'Wikipedia'),
            ('0/3', 'https://duckduckgo.com', 'DuckDuckGo'),
            ('1/1', 'https://wiki.archlinux.org', 'ArchWiki'),
        ]
    })


def test_other_buffer_completion(qtmodeltester, fake_web_tab, win_registry,
                                 tabbed_browser_stubs, info):
    tabbed_browser_stubs[0].widget.tabs = [
        fake_web_tab(QUrl('https://github.com'), 'GitHub', 0),
        fake_web_tab(QUrl('https://wikipedia.org'), 'Wikipedia', 1),
        fake_web_tab(QUrl('https://duckduckgo.com'), 'DuckDuckGo', 2),
    ]
    tabbed_browser_stubs[1].widget.tabs = [
        fake_web_tab(QUrl('https://wiki.archlinux.org'), 'ArchWiki', 0),
    ]
    info.win_id = 1
    model = miscmodels.other_buffer(info=info)
    model.set_pattern('')
    qtmodeltester.check(model)

    _check_completions(model, {
        '0': [
            ('0/1', 'https://github.com', 'GitHub'),
            ('0/2', 'https://wikipedia.org', 'Wikipedia'),
            ('0/3', 'https://duckduckgo.com', 'DuckDuckGo')
        ],
    })


def test_other_buffer_completion_id0(qtmodeltester, fake_web_tab,
                                     win_registry, tabbed_browser_stubs, info):
    tabbed_browser_stubs[0].widget.tabs = [
        fake_web_tab(QUrl('https://github.com'), 'GitHub', 0),
        fake_web_tab(QUrl('https://wikipedia.org'), 'Wikipedia', 1),
        fake_web_tab(QUrl('https://duckduckgo.com'), 'DuckDuckGo', 2),
    ]
    tabbed_browser_stubs[1].widget.tabs = [
        fake_web_tab(QUrl('https://wiki.archlinux.org'), 'ArchWiki', 0),
    ]
    info.win_id = 0
    model = miscmodels.other_buffer(info=info)
    model.set_pattern('')
    qtmodeltester.check(model)

    _check_completions(model, {
        '1': [
            ('1/1', 'https://wiki.archlinux.org', 'ArchWiki'),
        ],
    })


def test_tab_focus_completion(qtmodeltester, fake_web_tab, win_registry,
                              tabbed_browser_stubs, info):
    tabbed_browser_stubs[0].widget.tabs = [
        fake_web_tab(QUrl('https://github.com'), 'GitHub', 0),
        fake_web_tab(QUrl('https://wikipedia.org'), 'Wikipedia', 1),
        fake_web_tab(QUrl('https://duckduckgo.com'), 'DuckDuckGo', 2),
    ]
    tabbed_browser_stubs[1].widget.tabs = [
        fake_web_tab(QUrl('https://wiki.archlinux.org'), 'ArchWiki', 0),
    ]
    info.win_id = 1
    model = miscmodels.tab_focus(info=info)
    model.set_pattern('')
    qtmodeltester.check(model)

    _check_completions(model, {
        'Tabs': [
            ('1', 'https://wiki.archlinux.org', 'ArchWiki'),
        ],
        'Special': [
            ("last",
             "Focus the last-focused tab",
             None),

            ("stack-next",
             "Go forward through a stack of focused tabs",
             None),

            ("stack-prev",
             "Go backward through a stack of focused tabs",
             None),
        ]
    })


def test_window_completion(qtmodeltester, fake_web_tab, tabbed_browser_stubs,
                           info):
    tabbed_browser_stubs[0].widget.tabs = [
        fake_web_tab(QUrl('https://github.com'), 'GitHub', 0),
        fake_web_tab(QUrl('https://wikipedia.org'), 'Wikipedia', 1),
        fake_web_tab(QUrl('https://duckduckgo.com'), 'DuckDuckGo', 2)
    ]
    tabbed_browser_stubs[1].widget.tabs = [
        fake_web_tab(QUrl('https://wiki.archlinux.org'), 'ArchWiki', 0)
    ]

    info.win_id = 1
    model = miscmodels.window(info=info)
    model.set_pattern('')
    qtmodeltester.check(model)

    _check_completions(model, {
        'Windows': [
            ('0', 'window title - qutebrowser',
             'GitHub, Wikipedia, DuckDuckGo'),
        ]
    })


def test_setting_option_completion(qtmodeltester, config_stub,
                                   configdata_stub, info):
    model = configmodel.option(info=info)
    model.set_pattern('')
    qtmodeltester.check(model)

    _check_completions(model, {
        "Options": [
            ('aliases', 'Aliases for commands.', '{"q": "quit"}'),
            ('bindings.commands', 'Default keybindings', (
                '{"normal": {"<Ctrl+q>": "quit", "I": "invalid", '
                '"ZQ": "quit", "d": "scroll down"}}')),
            ('completion.open_categories', 'Which categories to show (in '
             'which order) in the :open completion.',
             '["searchengines", "quickmarks", "bookmarks", "history"]'),
            ('content.javascript.enabled', 'Enable/Disable JavaScript',
             'true'),
            ('url.searchengines', 'searchengines list',
             '{"DEFAULT": "https://duckduckgo.com/?q={}", '
             '"google": "https://google.com/?q={}"}'),
        ]
    })


def test_setting_dict_option_completion(qtmodeltester, config_stub,
                                        configdata_stub, info):
    model = configmodel.dict_option(info=info)
    model.set_pattern('')
    qtmodeltester.check(model)

    _check_completions(model, {
        "Dict options": [
            ('aliases', 'Aliases for commands.', '{"q": "quit"}'),
            ('bindings.commands', 'Default keybindings', (
                '{"normal": {"<Ctrl+q>": "quit", "I": "invalid", '
                '"ZQ": "quit", "d": "scroll down"}}')),
            ('url.searchengines', 'searchengines list',
             '{"DEFAULT": "https://duckduckgo.com/?q={}", '
             '"google": "https://google.com/?q={}"}'),
        ]
    })


def test_setting_list_option_completion(qtmodeltester, config_stub,
                                        configdata_stub, info):
    model = configmodel.list_option(info=info)
    model.set_pattern('')
    qtmodeltester.check(model)

    _check_completions(model, {
        "List options": [
            ('completion.open_categories', 'Which categories to show (in '
             'which order) in the :open completion.',
             '["searchengines", "quickmarks", "bookmarks", "history"]'),
        ]
    })


def test_setting_customized_option_completion(qtmodeltester, config_stub,
                                              configdata_stub, info):
    info.config.set_obj('aliases', {'foo': 'nop'})

    model = configmodel.customized_option(info=info)
    model.set_pattern('')
    qtmodeltester.check(model)

    _check_completions(model, {
        "Customized options": [
            ('aliases', 'Aliases for commands.', '{"foo": "nop"}'),
        ]
    })


def test_setting_value_completion(qtmodeltester, config_stub, configdata_stub,
                                  info):
    model = configmodel.value(optname='content.javascript.enabled', info=info)
    model.set_pattern('')
    qtmodeltester.check(model)

    _check_completions(model, {
        "Current/Default": [
            ('true', 'Current value', None),
            ('true', 'Default value', None),
        ],
        "Completions": [
            ('false', '', None),
            ('true', '', None),
        ],
    })


def test_setting_value_no_completions(qtmodeltester, config_stub,
                                      configdata_stub, info):
    model = configmodel.value(optname='aliases', info=info)
    model.set_pattern('')
    qtmodeltester.check(model)

    _check_completions(model, {
        "Current/Default": [
            ('{"q": "quit"}', 'Current value', None),
            ('{"q": "quit"}', 'Default value', None),
        ],
    })


def test_setting_value_completion_invalid(info):
    assert configmodel.value(optname='foobarbaz', info=info) is None


@pytest.mark.parametrize('args, expected', [
    ([], {
        "Current/Default": [
            ('true', 'Current value', None),
            ('true', 'Default value', None),
        ],
        "Completions": [
            ('false', '', None),
            ('true', '', None),
        ],
    }),
    (['false'], {
        "Current/Default": [
            ('true', 'Current value', None),
            ('true', 'Default value', None),
        ],
        "Completions": [
            ('true', '', None),
        ],
    }),
    (['true'], {
        "Completions": [
            ('false', '', None),
        ],
    }),
    (['false', 'true'], {}),
])
def test_setting_value_cycle(qtmodeltester, config_stub, configdata_stub,
                             info, args, expected):
    opt = 'content.javascript.enabled'

    model = configmodel.value(opt, *args, info=info)
    model.set_pattern('')
    qtmodeltester.check(model)
    _check_completions(model, expected)


def test_bind_completion(qtmodeltester, cmdutils_stub, config_stub,
                         key_config_stub, configdata_stub, info):
    """Test the results of keybinding command completion.

    Validates that:
        - only non-deprecated commands are included
        - the command description is shown in the desc column
        - the binding (if any) is shown in the misc column
        - aliases are included
    """
    model = configmodel.bind('ZQ', info=info)
    model.set_pattern('')
    qtmodeltester.check(model)

    _check_completions(model, {
        "Current/Default": [
            ('quit', '(Current) quit qutebrowser', 'ZQ'),
        ],
        "Commands": [
            ('open', 'open a url', ''),
            ('q', "Alias for 'quit'", ''),
            ('quit', 'quit qutebrowser', 'ZQ, <Ctrl+q>'),
            ('scroll', 'Scroll the current tab in the given direction.', ''),
            ('tab-close', 'Close the current tab.', ''),
        ],
    })


def test_bind_completion_invalid(cmdutils_stub, config_stub, key_config_stub,
                                 configdata_stub, info):
    """Test command completion with an invalid command bound."""
    model = configmodel.bind('I', info=info)
    model.set_pattern('')

    _check_completions(model, {
        "Current/Default": [
            ('invalid', '(Current) Invalid command!', 'I'),
        ],
        "Commands": [
            ('open', 'open a url', ''),
            ('q', "Alias for 'quit'", ''),
            ('quit', 'quit qutebrowser', 'ZQ, <Ctrl+q>'),
            ('scroll', 'Scroll the current tab in the given direction.', ''),
            ('tab-close', 'Close the current tab.', ''),
        ],
    })


def test_bind_completion_invalid_binding(cmdutils_stub, config_stub,
                                         key_config_stub, configdata_stub,
                                         info):
    """Test command completion with an invalid key binding."""
    model = configmodel.bind('<blub>', info=info)
    model.set_pattern('')

    _check_completions(model, {
        "Current/Default": [
            ('', "Could not parse '<blub>': Got invalid key!", '<blub>'),
        ],
        "Commands": [
            ('open', 'open a url', ''),
            ('q', "Alias for 'quit'", ''),
            ('quit', 'quit qutebrowser', 'ZQ, <Ctrl+q>'),
            ('scroll', 'Scroll the current tab in the given direction.', ''),
            ('tab-close', 'Close the current tab.', ''),
        ],
    })


def test_bind_completion_no_binding(qtmodeltester, cmdutils_stub, config_stub,
                                    key_config_stub, configdata_stub, info):
    """Test keybinding completion with no current or default binding."""
    model = configmodel.bind('x', info=info)
    model.set_pattern('')
    qtmodeltester.check(model)

    _check_completions(model, {
        "Commands": [
            ('open', 'open a url', ''),
            ('q', "Alias for 'quit'", ''),
            ('quit', 'quit qutebrowser', 'ZQ, <Ctrl+q>'),
            ('scroll', 'Scroll the current tab in the given direction.', ''),
            ('tab-close', 'Close the current tab.', ''),
        ],
    })


def test_bind_completion_changed(cmdutils_stub, config_stub, key_config_stub,
                                 configdata_stub, info):
    """Test command completion with a non-default command bound."""
    model = configmodel.bind('d', info=info)
    model.set_pattern('')

    _check_completions(model, {
        "Current/Default": [
            ('scroll down',
             '(Current) Scroll the current tab in the given direction.', 'd'),
            ('tab-close', '(Default) Close the current tab.', 'd'),
        ],
        "Commands": [
            ('open', 'open a url', ''),
            ('q', "Alias for 'quit'", ''),
            ('quit', 'quit qutebrowser', 'ZQ, <Ctrl+q>'),
            ('scroll', 'Scroll the current tab in the given direction.', ''),
            ('tab-close', 'Close the current tab.', ''),
        ],
    })


def test_url_completion_benchmark(benchmark, info,
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
        model = urlmodel.url(info=info)
        model.set_pattern('')
        model.set_pattern('e')
        model.set_pattern('ex')
        model.set_pattern('ex ')
        model.set_pattern('ex 1')
        model.set_pattern('ex 12')
        model.set_pattern('ex 123')

    benchmark(bench)
