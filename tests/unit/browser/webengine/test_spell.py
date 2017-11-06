# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017 Michal Siedlaczek <michal.siedlaczek@gmail.com>

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

import pytest
from qutebrowser.browser.webengine import spell


def test_version():
    assert spell.version('en-US-8-0.bdic') == (8, 0)
    assert spell.version('pl-PL-3-0.bdic') == (3, 0)
    with pytest.raises(ValueError):
        spell.version('malformed_filename')


def test_local_filename_dictionary_does_not_exist(tmpdir, monkeypatch):
    monkeypatch.setattr(
        spell, 'dictionary_dir', lambda: '/some-non-existing-dir')
    assert not spell.local_filename('en-US')


def test_local_filename_dictionary_not_installed(tmpdir, monkeypatch):
    monkeypatch.setattr(spell, 'dictionary_dir', lambda: str(tmpdir))
    assert not spell.local_filename('en-US')


def test_local_filename_dictionary_installed(tmpdir, monkeypatch):
    monkeypatch.setattr(spell, 'dictionary_dir', lambda: str(tmpdir))
    for lang_file in ['en-US-11-0.bdic', 'en-US-7-1.bdic', 'pl-PL-3-0.bdic']:
        (tmpdir / lang_file).ensure()
    assert spell.local_filename('en-US') == 'en-US-11-0'
    assert spell.local_filename('pl-PL') == 'pl-PL-3-0'
