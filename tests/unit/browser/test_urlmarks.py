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

"""Tests for the global page history."""

from unittest import mock

import pytest
from PyQt5.QtCore import QUrl

from qutebrowser.browser import urlmarks


@pytest.fixture
def bm_file(config_tmpdir):
    return config_tmpdir / 'bookmarks.jsonl'


def test_init(bm_file, fake_save_manager):
    bm_file.write('\n'.join([
        '{"url": "http://example.com", "title": "Example Site"}',
        '{"url": "http://example.com/foo", "tags": ["one", "two"]}',
        '',
        '{"url": "http://example.com/bar", "title": "Bar", "tags": ["three"]}',
        '{"url": "http://example.com/notitle"}',
        '{"url": "http://example.com/foo", "tags": ["three", "four"]}',
    ]))

    bm = urlmarks.BookmarkManager()
    fake_save_manager.add_saveable.assert_called_once_with(
        'bookmark-manager',
        bm.save,
        mock.ANY,  # TODO: back to changed
        filename=str(bm_file),
    )

    assert list(bm) == [
        urlmarks.Bookmark('http://example.com', 'Example Site', []),
        urlmarks.Bookmark('http://example.com/foo', '', ['three', 'four']),
        urlmarks.Bookmark('http://example.com/bar', 'Bar', ['three']),
        urlmarks.Bookmark('http://example.com/notitle', '', []),
    ]


def test_init_empty(config_tmpdir, fake_save_manager):
    urlmarks.BookmarkManager()
    path = config_tmpdir / 'bookmarks.jsonl'
    path.ensure()


def test_add(bm_file, fake_save_manager, qtbot):
    bm = urlmarks.BookmarkManager()

    with qtbot.wait_signal(bm.changed):
        bm.add(QUrl('http://example.com'), 'Example Site')
    assert list(bm) == [
        urlmarks.Bookmark('http://example.com', 'Example Site', []),
    ]

    with qtbot.wait_signal(bm.changed):
        bm.add(QUrl('http://example.com/notitle'), '')
    assert list(bm) == [
        urlmarks.Bookmark('http://example.com/notitle', '', []),
        urlmarks.Bookmark('http://example.com', 'Example Site', []),
    ]

    with pytest.raises(urlmarks.InvalidUrlError):
        bm.add(QUrl('ht tp://example.com'), '')


def test_add_toggle(bm_file, fake_save_manager, qtbot):
    bm = urlmarks.BookmarkManager()

    with qtbot.wait_signal(bm.changed):
        bm.add(QUrl('http://example.com'), '', toggle=True)
    assert 'http://example.com' in bm

    with qtbot.wait_signal(bm.changed):
        bm.add(QUrl('http://example.com'), '', toggle=True)
    assert 'http://example.com' not in bm

    with qtbot.wait_signal(bm.changed):
        bm.add(QUrl('http://example.com'), '', toggle=True)
    assert 'http://example.com' in bm


def test_add_dupe(bm_file, fake_save_manager):
    bm = urlmarks.BookmarkManager()

    bm.add(QUrl('http://example.com'), '')
    with pytest.raises(urlmarks.AlreadyExistsError):
        bm.add(QUrl('http://example.com'), '')


def test_delete(bm_file, fake_save_manager, qtbot):
    bm = urlmarks.BookmarkManager()

    bm.add(QUrl('http://example.com/foo'), 'Foo')
    bm.add(QUrl('http://example.com/bar'), 'Bar')
    bm.add(QUrl('http://example.com/baz'), 'Baz')
    bm.save()

    with qtbot.wait_signal(bm.changed):
        bm.delete(QUrl('http://example.com/bar'))
    assert list(bm) == [
        urlmarks.Bookmark('http://example.com/baz', 'Baz', []),
        urlmarks.Bookmark('http://example.com/foo', 'Foo', []),
    ]

    with pytest.raises(urlmarks.DoesNotExistError):
        bm.delete(QUrl('http://example.com/nope'))


def test_save(bm_file, fake_save_manager):
    bm = urlmarks.BookmarkManager()

    bm.add(QUrl('http://example.com'), 'Example Site')
    bm.add(QUrl('http://example.com/notitle'), '')

    bm.add(QUrl('http://example.com/tags'), '')
    bm.tag(QUrl('http://example.com/tags'), ["a", "b"])

    bm.save()
    assert bm_file.read().splitlines() == [
        '{"url": "http://example.com/tags", "title": "", "tags": ["a", "b"]}',
        '{"url": "http://example.com/notitle", "title": "", "tags": []}',
        '{"url": "http://example.com", "title": "Example Site", "tags": []}',
    ]


def test_get(bm_file, fake_save_manager):
    bm = urlmarks.BookmarkManager()

    bm.add(QUrl('http://example.com'), 'Example Site')

    assert bm.get(QUrl('http://example.com')) == urlmarks.Bookmark(
        url='http://example.com',
        title='Example Site',
        tags=[],
    )

    with pytest.raises(urlmarks.DoesNotExistError):
        bm.get(QUrl('http://example.com/nope'))


def test_get_tagged(bm_file, fake_save_manager, qtbot):
    bm = urlmarks.BookmarkManager()

    bm.add(QUrl('http://example.com/1'), 'Example')
    bm.tag(QUrl('http://example.com/1'), ['foo', 'bar'])

    bm.add(QUrl('http://example.com/2'), 'Example')
    bm.tag(QUrl('http://example.com/2'), ['foo', 'baz'])

    bm.add(QUrl('http://example.com/3'), 'Example')
    bm.tag(QUrl('http://example.com/3'), ['foo', 'baz', 'biz'])

    bm.add(QUrl('http://example.com/4'), 'Example')

    assert [m.url for m in bm.get_tagged(['foo'])] == [
        'http://example.com/3',
        'http://example.com/2',
        'http://example.com/1',
    ]

    assert [m.url for m in bm.get_tagged(['bar'])] == [
        'http://example.com/1',
    ]

    assert [m.url for m in bm.get_tagged(['baz', 'biz'])] == [
        'http://example.com/3',
    ]

    assert list(bm.get_tagged(['nope'])) == []


@pytest.mark.parametrize('old, add, new', [
    ([], ['foo', 'bar'], ['foo', 'bar']),
    (['baz'], ['foo', 'bar'], ['baz', 'foo', 'bar']),
    (['baz', 'bar'], ['foo', 'bar'], ['baz', 'bar', 'foo']),
    ([], ['foo', 'foo'], ['foo']),
])
def test_tag(bm_file, fake_save_manager, qtbot, old, add, new):
    bm = urlmarks.BookmarkManager()
    url = QUrl('http://example.com')
    bm.add(url, 'Example Site')
    bm.tag(url, old)

    with qtbot.wait_signal(bm.changed):
        bm.tag(url, add)

    assert bm.get(url).tags == new


@pytest.mark.parametrize('tags, violations', [
    (['a'], ['a']),
    (['b'], ['b']),
    (['e'], []),
    (['e', 'f'], []),
    (['e', 'a', 'b'], ['a', 'b']),
])
def test_tag_unique(bm_file, fake_save_manager, qtbot, tags, violations):
    bm = urlmarks.BookmarkManager()

    bm.add(QUrl('http://example.com/a'), 'Example Site')
    bm.tag(QUrl('http://example.com/a'), ['a'])

    bm.add(QUrl('http://example.com/b'), 'Example Site')
    bm.tag(QUrl('http://example.com/b'), ['b', 'c'])

    bm.add(QUrl('http://example.com/c'), 'Example Site')
    bm.tag(QUrl('http://example.com/c'), ['b', 'd'])

    url = QUrl('http://example.com/c')
    if violations:
        with pytest.raises(urlmarks.NotUniqueError) as excinfo:
            bm.tag(url, tags, unique=True)
        assert str(excinfo.value) == "{} are not unique".format(violations)
    else:
        bm.tag(url, tags, unique=True)
        assert bm.get(url).tags == ['b', 'd'] + tags


@pytest.mark.parametrize('old, remove, new', [
    ([], ['foo', 'bar'], []),
    (['baz'], ['foo', 'bar'], ['baz']),
    (['baz', 'bar'], ['foo', 'bar'], ['baz']),
    (['baz', 'bar', 'foo'], ['bar'], ['baz', 'foo']),
])
def test_untag(bm_file, fake_save_manager, qtbot, old, remove, new):
    bm = urlmarks.BookmarkManager()
    url = QUrl('http://example.com')
    bm.add(url, 'Example Site')
    bm.tag(url, old)

    with qtbot.wait_signal(bm.changed):
        bm.untag(url, remove)

    assert bm.get(url).tags == new


@pytest.mark.parametrize('old, remove, removed', [
    (['foo'], ['foo'], True),
    (['foo', 'bar'], ['foo', 'bar'], True),
    (['foo', 'bar'], ['foo'], False),
    (['foo', 'bar'], ['foo', 'bar', 'baz'], True),
    ([], ['foo', 'bar'], True),
])
def test_untag_purge(bm_file, fake_save_manager, qtbot, old, remove, removed):
    bm = urlmarks.BookmarkManager()
    url = QUrl('http://example.com')
    bm.add(url, 'Example Site')
    bm.tag(url, old)

    with qtbot.wait_signal(bm.changed):
        bm.untag(url, remove, purge=True)

    if removed:
        with pytest.raises(urlmarks.DoesNotExistError):
            bm.get(url)
    else:
        bm.get(url)


def test_invalid_url(bm_file, fake_save_manager):
    bm = urlmarks.BookmarkManager()
    url = QUrl('ht tp://example.com')

    with pytest.raises(urlmarks.InvalidUrlError):
        bm.add(url, 'title')
    with pytest.raises(urlmarks.InvalidUrlError):
        bm.tag(url, ['one', 'two'])
    with pytest.raises(urlmarks.InvalidUrlError):
        bm.untag(url, ['one', 'two'])
    with pytest.raises(urlmarks.InvalidUrlError):
        bm.delete(url)


def test_all_tags(bm_file, fake_save_manager):
    bm = urlmarks.BookmarkManager()
    bm.add(QUrl('http://example.com/foo'), '')

    bm.add(QUrl('http://example.com/bar'), '')
    bm.tag(QUrl('http://example.com/bar'), ['bar'])

    bm.add(QUrl('http://example.com/baz'), '')
    bm.tag(QUrl('http://example.com/baz'), ['biz', 'bar', 'baz'])

    bm.add(QUrl('http://example.com/buz'), '')
    bm.tag(QUrl('http://example.com/buz'), ['buz', 'foo', 'baz'])

    assert bm.all_tags() == {'foo', 'bar', 'baz', 'biz', 'buz'}
