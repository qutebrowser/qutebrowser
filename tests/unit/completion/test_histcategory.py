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

"""Test the web history completion category."""

import datetime
import logging

import hypothesis
from hypothesis import strategies
import pytest

from qutebrowser.misc import sql
from qutebrowser.completion.models import histcategory
from qutebrowser.utils import usertypes


@pytest.fixture
def hist(init_sql, config_stub):
    config_stub.val.completion.timestamp_format = '%Y-%m-%d'
    config_stub.val.completion.web_history.max_items = -1
    return sql.SqlTable('CompletionHistory', ['url', 'title', 'last_atime'])


@pytest.mark.parametrize('pattern, before, after', [
    ('foo',
     [('foo', ''), ('bar', ''), ('aafobbb', '')],
     [('foo',)]),

    ('FOO',
     [('foo', ''), ('bar', ''), ('aafobbb', '')],
     [('foo',)]),

    ('foo',
     [('FOO', ''), ('BAR', ''), ('AAFOBBB', '')],
     [('FOO',)]),

    ('foo',
     [('baz', 'bar'), ('foo', ''), ('bar', 'foo')],
     [('foo', ''), ('bar', 'foo')]),

    ('foo',
     [('fooa', ''), ('foob', ''), ('fooc', '')],
     [('fooa', ''), ('foob', ''), ('fooc', '')]),

    ('foo',
     [('foo', 'bar'), ('bar', 'foo'), ('biz', 'baz')],
     [('foo', 'bar'), ('bar', 'foo')]),

    ('foo bar',
     [('foo', ''), ('bar foo', ''), ('xfooyybarz', '')],
     [('bar foo', ''), ('xfooyybarz', '')]),

    ('foo%bar',
     [('foo%bar', ''), ('foo bar', ''), ('foobar', '')],
     [('foo%bar', '')]),

    ('_',
     [('a_b', ''), ('__a', ''), ('abc', '')],
     [('a_b', ''), ('__a', '')]),

    ('%',
     [('\\foo', '\\bar')],
     []),

    ("can't",
     [("can't touch this", ''), ('a', '')],
     [("can't touch this", '')]),

    ("ample itle",
     [('example.com', 'title'), ('example.com', 'nope')],
     [('example.com', 'title')]),

    # https://github.com/qutebrowser/qutebrowser/issues/4411
    ("mlfreq",
     [('https://qutebrowser.org/FAQ.html', 'Frequently Asked Questions')],
     []),
    ("ml freq",
     [('https://qutebrowser.org/FAQ.html', 'Frequently Asked Questions')],
     [('https://qutebrowser.org/FAQ.html', 'Frequently Asked Questions')]),
])
def test_set_pattern(pattern, before, after, model_validator, hist):
    """Validate the filtering and sorting results of set_pattern."""
    for row in before:
        hist.insert({'url': row[0], 'title': row[1], 'last_atime': 1})
    cat = histcategory.HistoryCategory()
    model_validator.set_model(cat)
    cat.set_pattern(pattern)
    model_validator.validate(after)


def test_set_pattern_repeated(model_validator, hist):
    """Validate multiple subsequent calls to set_pattern."""
    hist.insert({'url': 'example.com/foo', 'title': 'title1', 'last_atime': 1})
    hist.insert({'url': 'example.com/bar', 'title': 'title2', 'last_atime': 1})
    hist.insert({'url': 'example.com/baz', 'title': 'title3', 'last_atime': 1})
    cat = histcategory.HistoryCategory()
    model_validator.set_model(cat)

    cat.set_pattern('b')
    model_validator.validate([
        ('example.com/bar', 'title2'),
        ('example.com/baz', 'title3'),
    ])

    cat.set_pattern('ba')
    model_validator.validate([
        ('example.com/bar', 'title2'),
        ('example.com/baz', 'title3'),
    ])

    cat.set_pattern('ba ')
    model_validator.validate([
        ('example.com/bar', 'title2'),
        ('example.com/baz', 'title3'),
    ])

    cat.set_pattern('ba z')
    model_validator.validate([
        ('example.com/baz', 'title3'),
    ])


@pytest.mark.parametrize('pattern', [
    ' '.join(map(str, range(10000))),
    'x' * 50000,
], ids=['numbers', 'characters'])
def test_set_pattern_long(hist, message_mock, caplog, pattern):
    hist.insert({'url': 'example.com/foo', 'title': 'title1', 'last_atime': 1})
    cat = histcategory.HistoryCategory()
    with caplog.at_level(logging.ERROR):
        cat.set_pattern(pattern)
    msg = message_mock.getmsg(usertypes.MessageLevel.error)
    assert msg.text.startswith("Error with SQL query:")


@hypothesis.given(pat=strategies.text())
def test_set_pattern_hypothesis(hist, pat, caplog):
    hist.insert({'url': 'example.com/foo', 'title': 'title1', 'last_atime': 1})
    cat = histcategory.HistoryCategory()
    with caplog.at_level(logging.ERROR):
        cat.set_pattern(pat)


@pytest.mark.parametrize('max_items, before, after', [
    (-1, [
        ('a', 'a', '2017-04-16'),
        ('b', 'b', '2017-06-16'),
        ('c', 'c', '2017-05-16'),
    ], [
        ('b', 'b', '2017-06-16'),
        ('c', 'c', '2017-05-16'),
        ('a', 'a', '2017-04-16'),
    ]),
    (3, [
        ('a', 'a', '2017-04-16'),
        ('b', 'b', '2017-06-16'),
        ('c', 'c', '2017-05-16'),
    ], [
        ('b', 'b', '2017-06-16'),
        ('c', 'c', '2017-05-16'),
        ('a', 'a', '2017-04-16'),
    ]),
    (2 ** 63 - 1, [  # Maximum value sqlite can handle for LIMIT
        ('a', 'a', '2017-04-16'),
        ('b', 'b', '2017-06-16'),
        ('c', 'c', '2017-05-16'),
    ], [
        ('b', 'b', '2017-06-16'),
        ('c', 'c', '2017-05-16'),
        ('a', 'a', '2017-04-16'),
    ]),
    (2, [
        ('a', 'a', '2017-04-16'),
        ('b', 'b', '2017-06-16'),
        ('c', 'c', '2017-05-16'),
    ], [
        ('b', 'b', '2017-06-16'),
        ('c', 'c', '2017-05-16'),
    ]),
    (1, [], []),  # issue 2849 (crash with empty history)
])
def test_sorting(max_items, before, after, model_validator, hist, config_stub):
    """Validate the filtering and sorting results of set_pattern."""
    config_stub.val.completion.web_history.max_items = max_items
    for url, title, atime in before:
        timestamp = datetime.datetime.strptime(atime, '%Y-%m-%d').timestamp()
        hist.insert({'url': url, 'title': title, 'last_atime': timestamp})
    cat = histcategory.HistoryCategory()
    model_validator.set_model(cat)
    cat.set_pattern('')
    model_validator.validate(after)


def test_remove_rows(hist, model_validator):
    hist.insert({'url': 'foo', 'title': 'Foo', 'last_atime': 0})
    hist.insert({'url': 'bar', 'title': 'Bar', 'last_atime': 0})
    cat = histcategory.HistoryCategory()
    model_validator.set_model(cat)
    cat.set_pattern('')
    hist.delete('url', 'foo')
    cat.removeRows(0, 1)
    model_validator.validate([('bar', 'Bar')])


def test_remove_rows_fetch(hist):
    """removeRows should fetch enough data to make the current index valid."""
    # we cannot use model_validator as it will fetch everything up front
    hist.insert_batch({
        'url': [str(i) for i in range(300)],
        'title': [str(i) for i in range(300)],
        'last_atime': [0] * 300,
    })
    cat = histcategory.HistoryCategory()
    cat.set_pattern('')

    # sanity check that we didn't fetch everything up front
    assert cat.rowCount() < 300
    cat.fetchMore()
    assert cat.rowCount() == 300

    hist.delete('url', '298')
    cat.removeRows(297, 1)
    assert cat.rowCount() == 299


@pytest.mark.parametrize('fmt, expected', [
    ('%Y-%m-%d', '2018-02-27'),
    ('%m/%d/%Y %H:%M', '02/27/2018 08:30'),
    ('', ''),
])
def test_timestamp_fmt(fmt, expected, model_validator, config_stub, init_sql):
    """Validate the filtering and sorting results of set_pattern."""
    config_stub.val.completion.timestamp_format = fmt
    hist = sql.SqlTable('CompletionHistory', ['url', 'title', 'last_atime'])
    atime = datetime.datetime(2018, 2, 27, 8, 30)
    hist.insert({'url': 'foo', 'title': '', 'last_atime': atime.timestamp()})
    cat = histcategory.HistoryCategory()
    model_validator.set_model(cat)
    cat.set_pattern('')
    model_validator.validate([('foo', '', expected)])


def test_skip_duplicate_set(message_mock, caplog, hist):
    cat = histcategory.HistoryCategory()
    cat.set_pattern('foo')
    cat.set_pattern('foobarbaz')
    msg = caplog.messages[-1]
    assert msg.startswith(
        "Skipping query on foobarbaz due to prefix foo returning nothing.")
