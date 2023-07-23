# SPDX-FileCopyrightText: Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for bookmarks/quickmarks."""

import unittest.mock

import pytest
from qutebrowser.qt.core import QUrl

from qutebrowser.browser import urlmarks


@pytest.fixture
def bm_file(config_tmpdir):
    bm_dir = config_tmpdir / 'bookmarks'
    bm_dir.mkdir()
    bm_file = bm_dir / 'urls'
    return bm_file


def test_init(bm_file, fake_save_manager):
    bm_file.write('\n'.join([
        'http://example.com Example Site',
        'http://example.com/foo Foo',
        'http://example.com/bar Bar',
        'http://example.com/notitle',
    ]))

    bm = urlmarks.BookmarkManager()
    fake_save_manager.add_saveable.assert_called_once_with(
        'bookmark-manager',
        unittest.mock.ANY,
        unittest.mock.ANY,
        filename=str(bm_file),
    )

    assert list(bm.marks.items()) == [
        ('http://example.com', 'Example Site'),
        ('http://example.com/foo', 'Foo'),
        ('http://example.com/bar', 'Bar'),
        ('http://example.com/notitle', ''),
    ]


def test_add(bm_file, fake_save_manager, qtbot):
    bm = urlmarks.BookmarkManager()

    with qtbot.wait_signal(bm.changed):
        bm.add(QUrl('http://example.com'), 'Example Site')
    assert list(bm.marks.items()) == [
        ('http://example.com', 'Example Site'),
    ]

    with qtbot.wait_signal(bm.changed):
        bm.add(QUrl('http://example.com/notitle'), '')
    assert list(bm.marks.items()) == [
        ('http://example.com', 'Example Site'),
        ('http://example.com/notitle', ''),
    ]


def test_add_toggle(bm_file, fake_save_manager, qtbot):
    bm = urlmarks.BookmarkManager()

    with qtbot.wait_signal(bm.changed):
        bm.add(QUrl('http://example.com'), '', toggle=True)
    assert 'http://example.com' in bm.marks

    with qtbot.wait_signal(bm.changed):
        bm.add(QUrl('http://example.com'), '', toggle=True)
    assert 'http://example.com' not in bm.marks

    with qtbot.wait_signal(bm.changed):
        bm.add(QUrl('http://example.com'), '', toggle=True)
    assert 'http://example.com' in bm.marks


def test_add_dupe(bm_file, fake_save_manager, qtbot):
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
        bm.delete('http://example.com/bar')
    assert list(bm.marks.items()) == [
        ('http://example.com/foo', 'Foo'),
        ('http://example.com/baz', 'Baz'),
    ]


def test_save(bm_file, fake_save_manager, qtbot):
    bm = urlmarks.BookmarkManager()

    bm.add(QUrl('http://example.com'), 'Example Site')
    bm.add(QUrl('http://example.com/notitle'), '')
    bm.save()
    assert bm_file.read().splitlines() == [
        'http://example.com Example Site',
        'http://example.com/notitle ',
    ]
