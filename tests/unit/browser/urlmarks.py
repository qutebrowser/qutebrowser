# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018-2020 Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
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

import pytest
from PyQt5.QtCore import QUrl

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
        bm.save,
        bm.changed,
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
